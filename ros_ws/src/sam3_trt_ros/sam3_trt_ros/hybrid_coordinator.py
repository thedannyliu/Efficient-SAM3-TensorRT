from __future__ import annotations

import json
from threading import Event, Lock
from time import perf_counter

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Image
from std_msgs.msg import String, UInt8
from std_srvs.srv import SetBool, Trigger

from sam2_trt_msgs.srv import AddObject
from sam31_trt.gi_client import InstinctSAMClient
from sam31_trt.handoff import select_handoff_objects
from sam3_trt_msgs.srv import SetPipelineMode, SetTextPrompt


class HybridCoordinator(Node):
    def __init__(self) -> None:
        super().__init__("sam3_sam2_hybrid_coordinator")
        self.declare_parameter("relay_topic", "/hybrid/camera/image_raw")
        self.declare_parameter("gi_base_url", "http://127.0.0.1:8767")
        self.declare_parameter("gi_timeout", 60.0)
        self.declare_parameter("max_objects", 8)
        self.declare_parameter("min_mask_area", 25)
        self.declare_parameter("sam2_service_timeout", 10.0)
        self.declare_parameter("initialization_timeout", 30.0)

        callback_group = ReentrantCallbackGroup()
        self.bridge = CvBridge()
        self.client = InstinctSAMClient(
            str(self.get_parameter("gi_base_url").value),
            timeout=float(self.get_parameter("gi_timeout").value),
        )
        self.enabled = False
        self.handoff_lock = Lock()
        self.expected_stamp = 0
        self.expected_objects = 0
        self.initialized = Event()
        self.sam2_ready = Event()
        frozen_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE
        )
        self.relay = self.create_publisher(
            Image,
            str(self.get_parameter("relay_topic").value),
            frozen_qos,
        )
        self.metrics = self.create_publisher(String, "/hybrid/handoff_json", 10)
        self.create_subscription(
            String,
            "/sam/result_json",
            self.on_sam2_result,
            10,
            callback_group=callback_group,
        )
        mode_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            UInt8,
            "/sam3_pipeline/active_mode",
            self.on_mode,
            mode_qos,
            callback_group=callback_group,
        )
        self.add_client = self.create_client(
            AddObject, "/sam/add_object", callback_group=callback_group
        )
        self.reset_client = self.create_client(
            Trigger, "/sam/reset", callback_group=callback_group
        )
        self.relay_client = self.create_client(
            SetBool,
            "/instinctsam/set_hybrid_relay",
            callback_group=callback_group,
        )
        self.create_service(
            SetTextPrompt,
            "/hybrid/set_text",
            self.on_set_text,
            callback_group=callback_group,
        )
        self.create_service(
            Trigger,
            "/hybrid/reset",
            self.on_reset,
            callback_group=callback_group,
        )

    @staticmethod
    def stamp_ns(message: Image) -> int:
        return (
            int(message.header.stamp.sec) * 1_000_000_000
            + int(message.header.stamp.nanosec)
        )

    def on_mode(self, message: UInt8) -> None:
        enabled = message.data == SetPipelineMode.Request.HYBRID
        self.enabled = enabled
        if enabled:
            self.sam2_ready.clear()
        if self.relay_client.service_is_ready():
            request = SetBool.Request()
            request.data = enabled
            self.relay_client.call_async(request)
        if self.reset_client.service_is_ready():
            self.reset_client.call_async(Trigger.Request())

    def on_sam2_result(self, message: String) -> None:
        try:
            value = json.loads(message.data)
        except json.JSONDecodeError:
            return
        self.sam2_ready.set()
        if (
            int(value.get("stamp_ns", 0)) == self.expected_stamp
            and len(value.get("objects", [])) == self.expected_objects
        ):
            self.initialized.set()

    def wait_for_service(self, client: object, name: str) -> None:
        timeout = float(self.get_parameter("sam2_service_timeout").value)
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f"{name} service is not ready")

    def call(self, client: object, request: object, name: str) -> object:
        self.wait_for_service(client, name)
        future = client.call_async(request)
        completed = Event()
        future.add_done_callback(lambda _: completed.set())
        timeout = float(self.get_parameter("sam2_service_timeout").value)
        if not completed.wait(timeout):
            raise TimeoutError(f"{name} timed out")
        return future.result()

    def reset_sam2(self) -> None:
        response = self.call(self.reset_client, Trigger.Request(), "/sam/reset")
        if not response.success:
            raise RuntimeError(f"/sam/reset failed: {response.message}")

    def set_relay(self, enabled: bool) -> None:
        request = SetBool.Request()
        request.data = enabled
        response = self.call(
            self.relay_client, request, "/instinctsam/set_hybrid_relay"
        )
        if not response.success:
            raise RuntimeError(
                f"/instinctsam/set_hybrid_relay failed: {response.message}"
            )

    def resume(self) -> None:
        if self.enabled:
            self.set_relay(True)

    def on_set_text(
        self, request: SetTextPrompt.Request, response: SetTextPrompt.Response
    ) -> SetTextPrompt.Response:
        if not self.handoff_lock.acquire(blocking=False):
            response.message = "another handoff is in progress"
            return response
        reset_started = False
        start = perf_counter()
        try:
            if not self.enabled:
                raise RuntimeError("hybrid pipeline is inactive; press 2 first")
            timeout = float(self.get_parameter("initialization_timeout").value)
            if not self.sam2_ready.wait(timeout):
                raise TimeoutError("SAM2 did not become ready after mode switch")
            text = request.text.strip()
            if not text:
                raise ValueError("text prompt must not be empty")
            self.set_relay(False)
            snapshot_start = perf_counter()
            jpeg = self.client.raw_jpeg()
            snapshot_ms = (perf_counter() - snapshot_start) * 1000.0
            frame = cv2.imdecode(
                np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if frame is None:
                raise RuntimeError("InstinctSAM snapshot is not a valid JPEG")
            frozen = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            frozen.header.stamp = self.get_clock().now().to_msg()
            frozen_stamp = self.stamp_ns(frozen)
            detect_start = perf_counter()
            detection = self.client.detect(
                jpeg,
                text,
                confidence=request.confidence,
                max_objects=int(self.get_parameter("max_objects").value),
            )
            detect_wall_ms = (perf_counter() - detect_start) * 1000.0
            select_start = perf_counter()
            objects = select_handoff_objects(
                detection,
                max_objects=int(self.get_parameter("max_objects").value),
                min_area=int(self.get_parameter("min_mask_area").value),
            )
            select_ms = (perf_counter() - select_start) * 1000.0
            if not objects:
                self.resume()
                response.message = "InstinctSAM found no usable masks; tracking preserved"
                return response

            self.reset_sam2()
            reset_started = True
            for selected in objects:
                add_request = AddObject.Request()
                add_request.kind = AddObject.Request.BOX
                (
                    add_request.x0,
                    add_request.y0,
                    add_request.x1,
                    add_request.y1,
                ) = selected.box
                add_response = self.call(
                    self.add_client, add_request, "/sam/add_object"
                )
                if not add_response.success:
                    raise RuntimeError(
                        f"/sam/add_object failed: {add_response.message}"
                    )

            self.expected_stamp = frozen_stamp
            self.expected_objects = len(objects)
            self.initialized.clear()
            init_start = perf_counter()
            self.relay.publish(frozen)
            if not self.initialized.wait(timeout):
                raise TimeoutError("SAM2 did not initialize on the frozen frame")
            init_ms = (perf_counter() - init_start) * 1000.0
            self.resume()
            total_ms = (perf_counter() - start) * 1000.0
            metric = {
                "schema_version": 1,
                "stamp_ns": frozen_stamp,
                "text": text,
                "object_count": len(objects),
                "gi_snapshot_ms": snapshot_ms,
                "jpeg_encode_ms": 0.0,
                "gi_detect_wall_ms": detect_wall_ms,
                "gi_detect_ms": detection.detect_ms,
                "mask_to_box_ms": select_ms,
                "sam2_initialization_ms": init_ms,
                "time_to_first_mask_ms": total_ms,
                "objects": [
                    {
                        "label": item.label,
                        "score": item.score,
                        "box": list(item.box),
                    }
                    for item in objects
                ],
            }
            result = String()
            result.data = json.dumps(metric, separators=(",", ":"))
            self.metrics.publish(result)
            response.success = True
            response.object_count = len(objects)
            response.message = "handoff complete"
        except Exception as error:
            if reset_started:
                try:
                    self.reset_sam2()
                except Exception as reset_error:
                    self.get_logger().error(f"rollback reset failed: {reset_error}")
            self.resume()
            response.message = str(error)
        finally:
            self.expected_stamp = 0
            self.expected_objects = 0
            self.handoff_lock.release()
        return response

    def on_reset(
        self, _: Trigger.Request, response: Trigger.Response
    ) -> Trigger.Response:
        try:
            self.reset_sam2()
            response.success = True
            response.message = "reset"
        except Exception as error:
            response.message = str(error)
        return response


def main() -> None:
    rclpy.init()
    node = HybridCoordinator()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
