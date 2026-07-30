from __future__ import annotations

import json
from threading import Event, Lock, Thread
from time import perf_counter

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String, UInt8
from std_srvs.srv import SetBool, Trigger

from sam31_trt.gi_client import InstinctSAMClient
from sam31_trt.shared_frame import SharedFrameWriter
from sam3_trt_msgs.srv import AddBox, AddPoint, SetTextPrompt


class MjpegReader:
    def __init__(self, url: str, gstreamer_decode: bool = False) -> None:
        self.url = url
        self.gstreamer_decode = gstreamer_decode
        self.backend = "opencv_ffmpeg"
        self.lock = Lock()
        self.stop = Event()
        self.enabled = Event()
        self.frame: np.ndarray | None = None
        self.sequence = 0
        self.capture: cv2.VideoCapture | None = None
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def open_capture(self) -> cv2.VideoCapture:
        if self.gstreamer_decode:
            pipeline = (
                f"souphttpsrc location={self.url} is-live=true "
                "! multipartdemux ! nvjpegdec ! videoconvert "
                "! video/x-raw,format=BGR "
                "! appsink drop=true max-buffers=1 sync=false"
            )
            capture = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if capture.isOpened():
                self.backend = "gstreamer_nvjpeg"
                return capture
            capture.release()
        self.backend = "opencv_ffmpeg"
        return cv2.VideoCapture(self.url)

    def run(self) -> None:
        while not self.stop.is_set():
            if not self.enabled.wait(0.2):
                continue
            if self.stop.is_set():
                break
            capture = self.open_capture()
            if self.backend == "opencv_ffmpeg":
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
        self.declare_parameter("poll_fps", 60.0)
        self.declare_parameter("status_fps", 5.0)
        self.declare_parameter("http_timeout", 1.0)
        self.declare_parameter("gstreamer_mjpeg_decode", True)
        self.declare_parameter("native_raw_stream", True)
        self.declare_parameter("relay_topic", "/hybrid/camera/image_raw")
        self.declare_parameter("shared_memory_path", "")
        self.declare_parameter("shared_memory_max_bytes", 8 * 1024 * 1024)
        base_url = str(self.get_parameter("base_url").value)
        timeout = float(self.get_parameter("http_timeout").value)
        self.client = InstinctSAMClient(base_url, timeout=timeout)
        self.base_url = base_url
        self.bridge = CvBridge()
        gstreamer_decode = bool(
            self.get_parameter("gstreamer_mjpeg_decode").value
        )
        self.raw_reader = MjpegReader(
            f"{base_url}/raw.mjpg", gstreamer_decode
        )
        self.overlay_reader = MjpegReader(
            f"{base_url}/track.mjpg", gstreamer_decode
        )
        shared_memory_path = str(
            self.get_parameter("shared_memory_path").value
        )
        self.shared_writer = (
            SharedFrameWriter(
                shared_memory_path,
                int(self.get_parameter("shared_memory_max_bytes").value),
            )
            if shared_memory_path
            else None
        )
        self.last_raw_sequence = 0
        self.last_overlay_sequence = 0
        self.width = 0
        self.height = 0
        self.hybrid_enabled = False
        self.relay_gated = False
        self.mode_received = False
        self.vendor_ready = False
        self.published_frames = 0
        self.rate_time = perf_counter()
        self.rate_reader_sequence = 0
        self.rate_overlay_sequence = 0
        self.rate_published_frames = 0
        self.raw_reader_fps = 0.0
        self.overlay_reader_fps = 0.0
        self.image_publish_fps = 0.0
        self.image_copy_ms = 0.0
        self.image_publish_ms = 0.0
        self.image_group = MutuallyExclusiveCallbackGroup()
        self.status_group = MutuallyExclusiveCallbackGroup()
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
        self.create_service(AddPoint, "/instinctsam/add_point", self.on_add_point)
        self.create_service(Trigger, "/instinctsam/reset", self.on_reset)
        self.create_service(
            SetBool, "/instinctsam/set_hybrid_relay", self.on_set_hybrid_relay
        )
        mode_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            UInt8, "/sam3_pipeline/active_mode", self.on_mode, mode_qos
        )
        poll_fps = float(self.get_parameter("poll_fps").value)
        status_fps = float(self.get_parameter("status_fps").value)
        self.create_timer(
            1.0 / poll_fps,
            self.poll_images,
            callback_group=self.image_group,
        )
        self.create_timer(
            1.0 / status_fps,
            self.poll_status,
            callback_group=self.status_group,
        )
        self.get_logger().info(f"bridging InstinctSAM at {base_url}")

    def image_message(self, frame: np.ndarray, stamp: object) -> Image:
        message = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        message.header.stamp = stamp
        return message

    def update_readers(self) -> None:
        enabled = self.vendor_ready and self.mode_received
        native_raw_stream = bool(
            self.get_parameter("native_raw_stream").value
        )
        self.raw_reader.set_enabled(
            enabled and (self.hybrid_enabled or native_raw_stream)
        )
        self.overlay_reader.set_enabled(enabled and not self.hybrid_enabled)

    def poll_images(self) -> None:
        if not self.vendor_ready or not self.mode_received:
            return
        stamp = self.get_clock().now().to_msg()
        raw_sequence, raw = self.raw_reader.latest()
        if raw is not None and raw_sequence != self.last_raw_sequence:
            self.height, self.width = raw.shape[:2]
            start = perf_counter()
            shared_frame = None
            if self.hybrid_enabled and self.shared_writer is not None:
                shared_frame = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
                message = None
            else:
                message = self.image_message(raw, stamp)
            self.image_copy_ms = (perf_counter() - start) * 1000.0
            start = perf_counter()
            published = False
            if self.hybrid_enabled:
                if not self.relay_gated:
                    if self.shared_writer is not None:
                        stamp_ns = (
                            int(stamp.sec) * 1_000_000_000
                            + int(stamp.nanosec)
                        )
                        assert shared_frame is not None
                        self.shared_writer.write(shared_frame, stamp_ns)
                    else:
                        assert message is not None
                        self.relay_publisher.publish(message)
                    published = True
            else:
                assert message is not None
                self.raw_publisher.publish(message)
                published = True
            self.image_publish_ms = (perf_counter() - start) * 1000.0
            if published:
                self.published_frames += 1
            self.last_raw_sequence = raw_sequence

        if not self.hybrid_enabled:
            overlay_sequence, overlay = self.overlay_reader.latest()
            if (
                overlay is not None
                and overlay_sequence != self.last_overlay_sequence
            ):
                self.height, self.width = overlay.shape[:2]
                self.overlay_publisher.publish(self.image_message(overlay, stamp))
                self.last_overlay_sequence = overlay_sequence

    def poll_status(self) -> None:
        start = perf_counter()
        try:
            status = self.client.status()
            if not self.vendor_ready:
                self.vendor_ready = True
                self.update_readers()
                self.get_logger().info("InstinctSAM API is ready")
            raw_sequence, _ = self.raw_reader.latest()
            overlay_sequence, _ = self.overlay_reader.latest()
            now = perf_counter()
            rate_duration = now - self.rate_time
            if rate_duration >= 1.0:
                self.raw_reader_fps = (
                    raw_sequence - self.rate_reader_sequence
                ) / rate_duration
                self.image_publish_fps = (
                    self.published_frames - self.rate_published_frames
                ) / rate_duration
                self.overlay_reader_fps = (
                    overlay_sequence - self.rate_overlay_sequence
                ) / rate_duration
                self.rate_time = now
                self.rate_reader_sequence = raw_sequence
                self.rate_overlay_sequence = overlay_sequence
                self.rate_published_frames = self.published_frames
            stamp = self.get_clock().now().to_msg()
            status.update(
                {
                    "schema_version": 1,
                    "stamp_ns": int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec),
                    "source_width": self.width,
                    "source_height": self.height,
                    "adapter_poll_ms": (perf_counter() - start) * 1000.0,
                    "raw_reader_fps": self.raw_reader_fps,
                    "overlay_reader_fps": self.overlay_reader_fps,
                    "raw_decode_backend": self.raw_reader.backend,
                    "overlay_decode_backend": self.overlay_reader.backend,
                    "image_publish_fps": self.image_publish_fps,
                    "image_copy_ms": self.image_copy_ms,
                    "image_publish_ms": self.image_publish_ms,
                    "image_transport": (
                        "shared_memory"
                        if self.shared_writer is not None
                        else "ros_image"
                    ),
                }
            )
            message = String()
            message.data = json.dumps(status, separators=(",", ":"))
            self.result_publisher.publish(message)
        except Exception as error:
            if self.vendor_ready:
                self.vendor_ready = False
                self.update_readers()
            self.get_logger().warning(
                f"waiting for InstinctSAM API: {error}",
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
        if self.shared_writer is not None:
            self.shared_writer.close()
        return super().destroy_node()

    def on_mode(self, message: UInt8) -> None:
        self.hybrid_enabled = message.data == 2
        self.mode_received = True
        self.update_readers()

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

    def on_add_point(
        self, request: AddPoint.Request, response: AddPoint.Response
    ) -> AddPoint.Response:
        if self.width < 1 or self.height < 1:
            response.message = "no source frame is available"
            return response
        try:
            self.client.add_point(
                max(0.0, min(request.x / self.width, 1.0)),
                max(0.0, min(request.y / self.height, 1.0)),
            )
            response.success = True
            response.message = "point accepted"
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
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
