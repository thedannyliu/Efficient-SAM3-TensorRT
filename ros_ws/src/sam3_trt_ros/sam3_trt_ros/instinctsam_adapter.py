from __future__ import annotations

import json
from threading import Event, Lock, Thread
from time import perf_counter

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String, UInt8
from std_srvs.srv import SetBool, Trigger

from sam31_trt.gi_client import InstinctSAMClient
from sam3_trt_msgs.srv import AddBox, SetTextPrompt


class MjpegReader:
    def __init__(self, url: str) -> None:
        self.url = url
        self.lock = Lock()
        self.stop = Event()
        self.enabled = Event()
        self.enabled.set()
        self.frame: np.ndarray | None = None
        self.sequence = 0
        self.capture: cv2.VideoCapture | None = None
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self) -> None:
        while not self.stop.is_set():
            if not self.enabled.wait(0.2):
                continue
            if self.stop.is_set():
                break
            capture = cv2.VideoCapture(self.url)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.capture = capture
            while not self.stop.is_set() and self.enabled.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                with self.lock:
                    self.frame = frame
                    self.sequence += 1
            capture.release()
            self.stop.wait(0.2)

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.enabled.set()
        else:
            self.enabled.clear()

    def latest(self) -> tuple[int, np.ndarray | None]:
        with self.lock:
            return self.sequence, self.frame

    def close(self) -> None:
        self.stop.set()
        self.enabled.set()
        self.thread.join(timeout=2.0)
        if self.thread.is_alive() and self.capture is not None:
            self.capture.release()
            self.thread.join(timeout=2.0)


class InstinctSAMAdapter(Node):
    def __init__(self) -> None:
        super().__init__("instinctsam_adapter")
        self.declare_parameter("base_url", "http://127.0.0.1:8767")
        self.declare_parameter("poll_fps", 20.0)
        self.declare_parameter("http_timeout", 1.0)
        self.declare_parameter("relay_topic", "/hybrid/camera/image_raw")
        base_url = str(self.get_parameter("base_url").value)
        timeout = float(self.get_parameter("http_timeout").value)
        self.client = InstinctSAMClient(base_url, timeout=timeout)
        self.base_url = base_url
        self.bridge = CvBridge()
        self.raw_reader = MjpegReader(f"{base_url}/raw.mjpg")
        self.overlay_reader = MjpegReader(f"{base_url}/track.mjpg")
        self.last_raw_sequence = 0
        self.last_overlay_sequence = 0
        self.width = 0
        self.height = 0
        self.hybrid_enabled = False
        self.relay_gated = False
        self.raw_publisher = self.create_publisher(
            Image, "/instinctsam/raw", qos_profile_sensor_data
        )
        self.relay_publisher = self.create_publisher(
            Image,
            str(self.get_parameter("relay_topic").value),
            qos_profile_sensor_data,
        )
        self.overlay_publisher = self.create_publisher(
            Image, "/instinctsam/overlay", qos_profile_sensor_data
        )
        self.result_publisher = self.create_publisher(
            String, "/instinctsam/result_json", 10
        )
        self.create_service(
            SetTextPrompt, "/instinctsam/set_text", self.on_set_text
        )
        self.create_service(AddBox, "/instinctsam/add_box", self.on_add_box)
        self.create_service(Trigger, "/instinctsam/reset", self.on_reset)
        self.create_service(
            SetBool, "/instinctsam/set_hybrid_relay", self.on_set_hybrid_relay
        )
        mode_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            UInt8, "/sam3_pipeline/active_mode", self.on_mode, mode_qos
        )
        poll_fps = float(self.get_parameter("poll_fps").value)
        self.create_timer(1.0 / poll_fps, self.poll)
        self.get_logger().info(f"bridging InstinctSAM at {base_url}")

    def image_message(self, frame: np.ndarray, stamp: object) -> Image:
        message = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        message.header.stamp = stamp
        return message

    def poll(self) -> None:
        start = perf_counter()
        try:
            stamp = self.get_clock().now().to_msg()
            raw_sequence, raw = self.raw_reader.latest()
            overlay_sequence, overlay = self.overlay_reader.latest()
            if raw is None or overlay is None:
                raise RuntimeError("waiting for InstinctSAM MJPEG streams")
            if (
                raw_sequence == self.last_raw_sequence
                and overlay_sequence == self.last_overlay_sequence
            ):
                return
            status = self.client.status()
            self.height, self.width = raw.shape[:2]
            if raw_sequence != self.last_raw_sequence:
                message = self.image_message(raw, stamp)
                self.raw_publisher.publish(message)
                if self.hybrid_enabled and not self.relay_gated:
                    self.relay_publisher.publish(message)
                self.last_raw_sequence = raw_sequence
            if overlay_sequence != self.last_overlay_sequence:
                self.overlay_publisher.publish(self.image_message(overlay, stamp))
                self.last_overlay_sequence = overlay_sequence
            status.update(
                {
                    "schema_version": 1,
                    "stamp_ns": int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec),
                    "source_width": self.width,
                    "source_height": self.height,
                    "adapter_poll_ms": (perf_counter() - start) * 1000.0,
                }
            )
            message = String()
            message.data = json.dumps(status, separators=(",", ":"))
            self.result_publisher.publish(message)
        except Exception as error:
            self.get_logger().warning(
                f"InstinctSAM poll failed: {error}",
                throttle_duration_sec=2.0,
            )

    def on_set_text(
        self, request: SetTextPrompt.Request, response: SetTextPrompt.Response
    ) -> SetTextPrompt.Response:
        text = request.text.strip()
        if not text:
            response.message = "text prompt must not be empty"
            return response
        try:
            result = self.client.set_prompt(text, request.confidence)
            response.success = True
            response.object_count = int(
                result.get("object_count", result.get("objects", 0))
            )
            response.message = "prompt accepted"
        except Exception as error:
            response.message = str(error)
        return response

    def destroy_node(self) -> bool:
        self.raw_reader.close()
        self.overlay_reader.close()
        return super().destroy_node()

    def on_mode(self, message: UInt8) -> None:
        self.hybrid_enabled = message.data == 2
        self.overlay_reader.set_enabled(not self.hybrid_enabled)

    def on_set_hybrid_relay(
        self, request: SetBool.Request, response: SetBool.Response
    ) -> SetBool.Response:
        self.relay_gated = not request.data
        response.success = True
        response.message = "relay enabled" if request.data else "relay gated"
        return response

    def on_add_box(
        self, request: AddBox.Request, response: AddBox.Response
    ) -> AddBox.Response:
        if self.width < 1 or self.height < 1:
            response.message = "no source frame is available"
            return response
        x0, x1 = sorted((request.x0, request.x1))
        y0, y1 = sorted((request.y0, request.y1))
        if x1 - x0 < 1 or y1 - y0 < 1:
            response.message = "box is too small"
            return response
        try:
            self.client.add_box(
                max(0.0, min(x0 / self.width, 1.0)),
                max(0.0, min(y0 / self.height, 1.0)),
                max(0.0, min(x1 / self.width, 1.0)),
                max(0.0, min(y1 / self.height, 1.0)),
            )
            response.success = True
            response.message = "box accepted"
        except Exception as error:
            response.message = str(error)
        return response

    def on_reset(
        self, _: Trigger.Request, response: Trigger.Response
    ) -> Trigger.Response:
        try:
            self.client.reset()
            response.success = True
            response.message = "reset"
        except Exception as error:
            response.message = str(error)
        return response


def main() -> None:
    rclpy.init()
    node = InstinctSAMAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
