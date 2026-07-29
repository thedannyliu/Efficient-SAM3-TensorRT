from __future__ import annotations

import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class TraceRecorder(Node):
    def __init__(self) -> None:
        super().__init__("sam3_trt_trace_recorder")
        self.declare_parameter("topic", "/sam/result_json")
        self.declare_parameter("output", "results/trace.jsonl")
        self.declare_parameter("warmup_frames", 100)
        self.declare_parameter("measurement_frames", 1000)
        self.warmup = int(self.get_parameter("warmup_frames").value)
        self.measurement = int(self.get_parameter("measurement_frames").value)
        output = Path(str(self.get_parameter("output").value)).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.stream = output.open("w", encoding="utf-8")
        self.received = 0
        topic = str(self.get_parameter("topic").value)
        self.create_subscription(String, topic, self.on_result, 100)
        self.get_logger().info(
            f"recording {self.measurement} rows after {self.warmup} warm-up rows "
            f"from {topic} to {output}"
        )

    def on_result(self, message: String) -> None:
        self.received += 1
        if self.received <= self.warmup:
            return
        try:
            row = json.loads(message.data)
        except json.JSONDecodeError:
            self.get_logger().warning("ignored non-JSON result")
            return
        if not isinstance(row, dict):
            return
        row["collector_receive_monotonic_ns"] = time.monotonic_ns()
        row["collector_receive_wall_ns"] = time.time_ns()
        self.stream.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.stream.flush()
        if self.received >= self.warmup + self.measurement:
            self.get_logger().info("trace complete")
            rclpy.shutdown()

    def destroy_node(self) -> bool:
        self.stream.close()
        return super().destroy_node()


def main() -> None:
    rclpy.init()
    node = TraceRecorder()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
