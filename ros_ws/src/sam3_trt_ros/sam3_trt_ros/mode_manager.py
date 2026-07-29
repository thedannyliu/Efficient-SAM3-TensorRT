from __future__ import annotations

import json
from time import perf_counter

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String, UInt8

from sam31_trt.gi_client import InstinctSAMClient
from sam3_trt_msgs.srv import SetPipelineMode


class ModeManager(Node):
    def __init__(self) -> None:
        super().__init__("sam3_pipeline_mode_manager")
        self.declare_parameter("gi_base_url", "http://127.0.0.1:8767")
        self.declare_parameter("default_mode", 1)
        self.client = InstinctSAMClient(
            str(self.get_parameter("gi_base_url").value), timeout=10.0
        )
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.mode_publisher = self.create_publisher(
            UInt8, "/sam3_pipeline/active_mode", qos
        )
        self.metrics_publisher = self.create_publisher(
            String, "/sam3_pipeline/mode_json", 10
        )
        self.active_mode = int(self.get_parameter("default_mode").value)
        self.create_service(
            SetPipelineMode, "/sam3_pipeline/set_mode", self.on_set_mode
        )
        self.ready = False
        self.retry_timer = self.create_timer(1.0, self.initialize_mode)

    @staticmethod
    def mode_name(mode: int) -> str:
        if mode == SetPipelineMode.Request.INSTINCTSAM:
            return "native"
        if mode == SetPipelineMode.Request.HYBRID:
            return "hybrid"
        raise ValueError("mode must be 1 (InstinctSAM) or 2 (GI to SAM2)")

    def publish_mode(self) -> None:
        message = UInt8()
        message.data = self.active_mode
        self.mode_publisher.publish(message)

    def initialize_mode(self) -> None:
        if self.ready:
            return
        try:
            self.client.set_mode(self.mode_name(self.active_mode))
        except Exception as error:
            self.get_logger().warning(
                f"waiting for InstinctSAM mode API: {error}",
                throttle_duration_sec=5.0,
            )
            return
        self.ready = True
        self.publish_mode()
        self.get_logger().info(f"active pipeline mode is {self.active_mode}")

    def on_set_mode(
        self,
        request: SetPipelineMode.Request,
        response: SetPipelineMode.Response,
    ) -> SetPipelineMode.Response:
        start = perf_counter()
        try:
            mode_name = self.mode_name(request.mode)
            result = self.client.set_mode(mode_name)
            self.client.reset()
            self.active_mode = request.mode
            self.ready = True
            self.publish_mode()
            switch_ms = (perf_counter() - start) * 1000.0
            metric = String()
            metric.data = json.dumps(
                {
                    "schema_version": 1,
                    "active_mode": self.active_mode,
                    "mode_name": mode_name,
                    "mode_switch_ms": switch_ms,
                    "vendor_response": result,
                },
                separators=(",", ":"),
            )
            self.metrics_publisher.publish(metric)
            response.success = True
            response.active_mode = self.active_mode
            response.message = f"mode {self.active_mode} active in {switch_ms:.1f} ms"
        except Exception as error:
            response.active_mode = self.active_mode
            response.message = str(error)
        return response


def main() -> None:
    rclpy.init()
    node = ModeManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
