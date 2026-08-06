from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from time import perf_counter, sleep

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String, UInt8

from sam31_trt.gi_client import InstinctSAMClient
from sam3_trt_msgs.srv import SetCameraProfile, SetPipelineMode


class ModeManager(Node):
    def __init__(self) -> None:
        super().__init__("sam3_pipeline_mode_manager")
        self.declare_parameter("gi_base_url", "http://127.0.0.1:8767")
        self.declare_parameter("default_mode", 1)
        self.declare_parameter(
            "repository_root", "/home/ril-thor/Efficient-SAM3-TensorRT"
        )
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
        self.camera_publisher = self.create_publisher(
            String, "/sam3_pipeline/camera_profile_json", qos
        )
        self.active_mode = int(self.get_parameter("default_mode").value)
        self.camera_profile = (1280, 720, 30.0)
        self.camera_observed_fps = 0.0
        self.camera_source = "wired"
        self.create_service(
            SetPipelineMode, "/sam3_pipeline/set_mode", self.on_set_mode
        )
        self.create_service(
            SetCameraProfile,
            "/sam3_pipeline/set_camera_profile",
            self.on_set_camera_profile,
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

    def publish_camera_profile(self, switch_ms: float = 0.0) -> None:
        width, height, fps = self.camera_profile
        message = String()
        message.data = json.dumps(
            {
                "schema_version": 1,
                "actual_width": width,
                "actual_height": height,
                "requested_fps": fps,
                "observed_fps": self.camera_observed_fps,
                "source": self.camera_source,
                "switch_ms": switch_ms,
            },
            separators=(",", ":"),
        )
        self.camera_publisher.publish(message)

    def read_container_camera_profile(self) -> tuple[int, int, float]:
        completed = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .Args}}",
                "instinctsam-unified",
            ],
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
        arguments = json.loads(completed.stdout)
        values = {
            arguments[index]: arguments[index + 1]
            for index in range(0, len(arguments) - 1)
            if arguments[index] in {"--width", "--height", "--cam-fps"}
        }
        return (
            int(values["--width"]),
            int(values["--height"]),
            float(values["--cam-fps"]),
        )

    def read_container_camera_source(self) -> str:
        completed = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .Config.Env}}",
                "instinctsam-unified",
            ],
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
        environment = json.loads(completed.stdout)
        source = next(
            (
                item.split("=", 1)[1]
                for item in environment
                if item.startswith("SOURCE=")
            ),
            "",
        )
        return "wired" if source.startswith("/dev/") else "wifi"

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
        try:
            self.camera_profile = self.read_container_camera_profile()
            self.camera_source = self.read_container_camera_source()
        except Exception as error:
            self.get_logger().warning(f"cannot read camera profile: {error}")
        try:
            status = self.client.status()
            if status.get("backend") == "capture_only":
                self.camera_observed_fps = float(status.get("fps", 0.0))
        except Exception:
            pass
        self.publish_camera_profile()
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

    def on_set_camera_profile(
        self,
        request: SetCameraProfile.Request,
        response: SetCameraProfile.Response,
    ) -> SetCameraProfile.Response:
        requested = (int(request.width), int(request.height), float(request.fps))
        allowed = {
            (640, 360, 30.0),
            (640, 360, 60.0),
            (848, 480, 30.0),
            (848, 480, 60.0),
            (1280, 720, 30.0),
        }
        response.requested_fps = requested[2]
        if requested not in allowed:
            response.message = "unsupported camera profile"
            return response
        if requested == self.camera_profile:
            response.success = True
            response.actual_width = requested[0]
            response.actual_height = requested[1]
            response.observed_fps = self.camera_observed_fps
            response.message = "camera profile is already active"
            return response

        start = perf_counter()
        try:
            repository_root = Path(
                str(self.get_parameter("repository_root").value)
            )
            script = repository_root / "scripts" / "thor_run_gi_unified.sh"
            if not script.is_file():
                raise FileNotFoundError(script)
            environment = os.environ.copy()
            if (
                environment.get("GI_RESEARCH_USE_ACK")
                != "research-evaluation-only"
            ):
                raise RuntimeError(
                    "camera switching is unavailable because the unified UI "
                    "was started without GI_RESEARCH_USE_ACK; stop it, export "
                    "GI_RESEARCH_USE_ACK=research-evaluation-only after "
                    "reading the license files, and start it again"
                )
            environment.update(
                {
                    "GI_CAMERA_WIDTH": str(requested[0]),
                    "GI_CAMERA_HEIGHT": str(requested[1]),
                    "GI_CAMERA_FPS": f"{requested[2]:g}",
                }
            )
            completed = subprocess.run(
                ["bash", str(script)],
                cwd=repository_root,
                env=environment,
                text=True,
                capture_output=True,
                timeout=900,
                check=False,
            )
            if completed.returncode:
                detail = (completed.stderr or completed.stdout).strip()
                raise RuntimeError(detail[-1000:] or "camera restart failed")

            self.client.set_mode("hybrid")
            self.client.reset()
            sleep(1.0)
            self.camera_observed_fps = float(
                self.client.status().get("fps", 0.0)
            )
            if self.active_mode != SetPipelineMode.Request.HYBRID:
                self.client.set_mode(self.mode_name(self.active_mode))
                self.client.reset()
            frame = cv2.imdecode(
                np.frombuffer(self.client.raw_jpeg(), dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if frame is None:
                raise RuntimeError("restarted camera did not return a valid frame")
            actual_height, actual_width = frame.shape[:2]
            switch_ms = (perf_counter() - start) * 1000.0
            self.camera_profile = (actual_width, actual_height, requested[2])
            self.camera_source = self.read_container_camera_source()
            self.publish_camera_profile(switch_ms)
            response.success = True
            response.actual_width = actual_width
            response.actual_height = actual_height
            response.observed_fps = self.camera_observed_fps
            response.switch_ms = switch_ms
            response.message = (
                f"camera {actual_width}x{actual_height} ready in "
                f"{switch_ms:.1f} ms"
            )
        except Exception as error:
            response.switch_ms = (perf_counter() - start) * 1000.0
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
