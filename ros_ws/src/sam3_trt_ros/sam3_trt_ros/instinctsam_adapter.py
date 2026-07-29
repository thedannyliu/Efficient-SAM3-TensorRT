from __future__ import annotations

import json
from time import perf_counter

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String
from std_srvs.srv import Trigger

from sam31_trt.gi_client import InstinctSAMClient
from sam3_trt_msgs.srv import AddBox, SetTextPrompt


class InstinctSAMAdapter(Node):
    def __init__(self) -> None:
        super().__init__("instinctsam_adapter")
        self.declare_parameter("base_url", "http://127.0.0.1:8767")
        self.declare_parameter("poll_fps", 20.0)
        self.declare_parameter("http_timeout", 1.0)
        base_url = str(self.get_parameter("base_url").value)
        timeout = float(self.get_parameter("http_timeout").value)
        self.client = InstinctSAMClient(base_url, timeout=timeout)
        self.base_url = base_url
        self.bridge = CvBridge()
        self.raw_capture = self.open_capture("raw.mjpg")
        self.overlay_capture = self.open_capture("track.mjpg")
        self.width = 0
        self.height = 0
        self.raw_publisher = self.create_publisher(
            Image, "/instinctsam/raw", qos_profile_sensor_data
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
        poll_fps = float(self.get_parameter("poll_fps").value)
        self.create_timer(1.0 / poll_fps, self.poll)
        self.get_logger().info(f"bridging InstinctSAM at {base_url}")

    def open_capture(self, path: str) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(f"{self.base_url}/{path}")
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def read_capture(
        self, capture: cv2.VideoCapture, path: str
    ) -> tuple[cv2.VideoCapture, np.ndarray]:
        ok, frame = capture.read()
        if ok and frame is not None:
            return capture, frame
        capture.release()
        capture = self.open_capture(path)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"cannot read InstinctSAM /{path}")
        return capture, frame

    def publish_frame(self, publisher: object, frame: np.ndarray, stamp: object) -> None:
        message = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        message.header.stamp = stamp
        publisher.publish(message)

    def poll(self) -> None:
        start = perf_counter()
        try:
            stamp = self.get_clock().now().to_msg()
            self.raw_capture, raw = self.read_capture(
                self.raw_capture, "raw.mjpg"
            )
            self.overlay_capture, overlay = self.read_capture(
                self.overlay_capture, "track.mjpg"
            )
            status = self.client.status()
            self.height, self.width = raw.shape[:2]
            self.publish_frame(self.raw_publisher, raw, stamp)
            self.publish_frame(self.overlay_publisher, overlay, stamp)
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
        self.raw_capture.release()
        self.overlay_capture.release()
        return super().destroy_node()

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
