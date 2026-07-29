from __future__ import annotations

import json
from time import perf_counter

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String, UInt8
from std_srvs.srv import Trigger

from sam2_trt_msgs.srv import SwitchModel
from sam3_trt_msgs.srv import (
    AddBox,
    AddPoint,
    SetCameraProfile,
    SetPipelineMode,
    SetTextPrompt,
)


class InteractiveViewer(Node):
    def __init__(self) -> None:
        super().__init__("sam3_trt_interactive_viewer")
        self.declare_parameter("display_max_width", 2560)
        self.declare_parameter("confidence", 0.5)
        self.declare_parameter(
            "sam2_bundle_root",
            "/home/ril-thor/Efficient-SAM2-TensorRT/bundles",
        )
        self.mode = 1
        self.bridge = CvBridge()
        self.canvas_size = (1280, 720)
        self.source_sizes = {0: (1280, 720), 1: (1280, 720)}
        self.frames: dict[int, object] = {}
        self.frame_versions = {0: 0, 1: 0, 2: 0}
        self.last_render_state: object = None
        self.window_initialized = False
        self.window_presets = [
            (1280, 720),
            (1600, 900),
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
        ]
        self.preset_index = 0
        self.fullscreen = False
        self.raw_frame = None
        self.drag_start: tuple[int, int] | None = None
        self.drag_current: tuple[int, int] | None = None
        self.entering_text = False
        self.model_menu = False
        self.camera_menu = False
        self.model_switching = False
        self.camera_switching = False
        self.text = ""
        self.status = (
            "t=text, m=model, c=camera, click=point, drag=box, [ ]=window"
        )
        self.metrics: dict[str, object] = {}
        bundle_root = str(self.get_parameter("sam2_bundle_root").value)
        self.model_options = [
            (
                "TV5M",
                "sam2.1-tinyvit-5m",
                f"{bundle_root}/sam2.1-tinyvit-5m/fp16_aux0",
            ),
            (
                "TV11M",
                "sam2.1-tinyvit-11m",
                f"{bundle_root}/sam2.1-tinyvit-11m/fp16_aux0",
            ),
            (
                "TV21M",
                "sam2.1-tinyvit-21m",
                f"{bundle_root}/sam2.1-tinyvit-21m/fp16_aux0",
            ),
        ]
        self.active_model = "TV5M"
        self.camera_profiles = [
            (640, 360, 30),
            (640, 360, 60),
            (848, 480, 30),
            (848, 480, 60),
            (1280, 720, 30),
        ]
        self.active_camera_profile = (1280, 720, 30)
        self.camera_observed_fps = 0.0
        self.display_max_width = int(self.get_parameter("display_max_width").value)
        self.preset_index = min(
            range(len(self.window_presets)),
            key=lambda index: abs(
                self.window_presets[index][0] - self.display_max_width
            ),
        )
        self.confidence = float(self.get_parameter("confidence").value)
        self.create_subscription(
            Image,
            "/instinctsam/raw",
            lambda message: self.on_image(0, message),
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Image,
            "/instinctsam/overlay",
            lambda message: self.on_image(1, message),
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Image,
            "/sam/preview",
            lambda message: self.on_image(2, message),
            qos_profile_sensor_data,
        )
        self.create_subscription(
            String,
            "/instinctsam/result_json",
            lambda message: self.on_result(1, message),
            10,
        )
        self.create_subscription(
            String,
            "/sam/result_json",
            lambda message: self.on_result(2, message),
            10,
        )
        mode_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            UInt8, "/sam3_pipeline/active_mode", self.on_mode, mode_qos
        )
        self.create_subscription(
            String,
            "/sam3_pipeline/camera_profile_json",
            self.on_camera_profile,
            mode_qos,
        )
        self.text_clients = {
            1: self.create_client(SetTextPrompt, "/instinctsam/set_text"),
            2: self.create_client(SetTextPrompt, "/hybrid/set_text"),
        }
        self.reset_clients = {
            1: self.create_client(Trigger, "/instinctsam/reset"),
            2: self.create_client(Trigger, "/hybrid/reset"),
        }
        self.box_clients = {
            1: self.create_client(AddBox, "/instinctsam/add_box"),
            2: self.create_client(AddBox, "/hybrid/add_box"),
        }
        self.point_clients = {
            1: self.create_client(AddPoint, "/instinctsam/add_point"),
            2: self.create_client(AddPoint, "/hybrid/add_point"),
        }
        self.mode_client = self.create_client(
            SetPipelineMode, "/sam3_pipeline/set_mode"
        )
        self.model_client = self.create_client(
            SwitchModel, "/sam/switch_model"
        )
        self.camera_client = self.create_client(
            SetCameraProfile, "/sam3_pipeline/set_camera_profile"
        )
        self.window_name = "SAM3 / SAM2 TensorRT tracking"
        cv2.namedWindow(
            self.window_name,
            cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO | cv2.WINDOW_OPENGL,
        )
        cv2.setMouseCallback(self.window_name, self.on_mouse)

    @property
    def frame(self) -> object:
        return self.frames.get(self.mode, self.raw_frame)

    def on_image(self, mode: int, message: Image) -> None:
        frame = self.bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        if mode in (0, 1):
            self.source_sizes[mode] = (frame.shape[1], frame.shape[0])
        if (frame.shape[1], frame.shape[0]) != self.canvas_size:
            frame = cv2.resize(frame, self.canvas_size, interpolation=cv2.INTER_LINEAR)
        self.frame_versions[mode] += 1
        if mode == 0:
            self.raw_frame = frame
        else:
            self.frames[mode] = frame

    def on_result(self, mode: int, message: String) -> None:
        if mode != self.mode:
            return
        try:
            self.metrics = json.loads(message.data)
            model_id = str(self.metrics.get("model_id", ""))
            for label, candidate_id, _ in self.model_options:
                if model_id == candidate_id:
                    self.active_model = label
                    break
        except json.JSONDecodeError:
            pass

    def on_mode(self, message: UInt8) -> None:
        self.mode = int(message.data)
        self.metrics = {}
        self.status = (
            "mode 1: General Instinct SAM3/SAM3.1"
            if self.mode == 1
            else f"mode 2: GI detection -> {self.active_model} SAM2 TensorRT"
        )

    def on_camera_profile(self, message: String) -> None:
        try:
            value = json.loads(message.data)
            self.active_camera_profile = (
                int(value["actual_width"]),
                int(value["actual_height"]),
                int(round(float(value["requested_fps"]))),
            )
            self.source_sizes[0] = self.active_camera_profile[:2]
            self.source_sizes[1] = self.active_camera_profile[:2]
            self.camera_observed_fps = float(value.get("observed_fps", 0.0))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return

    def to_source(self, x: int, y: int) -> tuple[float, float]:
        if self.mode == SetPipelineMode.Request.HYBRID:
            width = int(
                self.metrics.get("source_width", self.active_camera_profile[0])
            )
            height = int(
                self.metrics.get("source_height", self.active_camera_profile[1])
            )
        else:
            width, height = self.source_sizes.get(
                self.mode, self.active_camera_profile[:2]
            )
        canvas_width, canvas_height = self.canvas_size
        return (
            min(max(float(x) * width / canvas_width, 0.0), width - 1.0),
            min(max(float(y) * height / canvas_height, 0.0), height - 1.0),
        )

    def apply_window_preset(self) -> None:
        width, height = self.window_presets[self.preset_index]
        if self.fullscreen:
            cv2.setWindowProperty(
                self.window_name,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_NORMAL,
            )
            self.fullscreen = False
        cv2.resizeWindow(self.window_name, width, height)
        self.status = f"window size: {width}x{height}"
        self.last_render_state = None

    def change_window_preset(self, offset: int) -> None:
        self.preset_index = (
            self.preset_index + offset
        ) % len(self.window_presets)
        self.apply_window_preset()

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        cv2.setWindowProperty(
            self.window_name,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL,
        )
        if not self.fullscreen:
            self.apply_window_preset()
        else:
            self.status = "fullscreen; press f to restore"
            self.last_render_state = None

    def on_mouse(self, event: int, x: int, y: int, flags: int, _: object) -> None:
        if (
            self.entering_text
            or self.model_menu
            or self.camera_menu
            or self.frame is None
        ):
            return
        point = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drag_start = (int(point[0]), int(point[1]))
            self.drag_current = self.drag_start
        elif event == cv2.EVENT_MOUSEMOVE and self.drag_start is not None:
            if flags & cv2.EVENT_FLAG_LBUTTON:
                self.drag_current = (int(point[0]), int(point[1]))
        elif event == cv2.EVENT_LBUTTONUP and self.drag_start is not None:
            end = (int(point[0]), int(point[1]))
            start = self.drag_start
            self.drag_start = None
            self.drag_current = None
            dx = abs(end[0] - start[0])
            dy = abs(end[1] - start[1])
            if max(dx, dy) < 5:
                source = self.to_source(*end)
                self.send_point(source)
                return
            if dx < 5 or dy < 5:
                self.status = "box must be at least 5x5 pixels"
                return
            self.send_box(self.to_source(*start), self.to_source(*end))

    def send_box(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> None:
        client = self.box_clients[self.mode]
        if not client.service_is_ready():
            self.status = "box service is not ready"
            return
        request = AddBox.Request()
        request.x0, request.x1 = sorted((float(start[0]), float(end[0])))
        request.y0, request.y1 = sorted((float(start[1]), float(end[1])))
        future = client.call_async(request)
        future.add_done_callback(self.on_action_response)
        self.status = "sending box"

    def send_point(self, point: tuple[float, float]) -> None:
        client = self.point_clients[self.mode]
        if not client.service_is_ready():
            self.status = "point service is not ready"
            return
        request = AddPoint.Request()
        request.x, request.y = float(point[0]), float(point[1])
        future = client.call_async(request)
        future.add_done_callback(self.on_action_response)
        self.status = "sending positive point"

    def send_text(self) -> None:
        text = self.text.strip()
        if not text:
            self.status = "empty text cancelled"
            return
        client = self.text_clients[self.mode]
        if not client.service_is_ready():
            self.status = "text service is not ready"
            return
        request = SetTextPrompt.Request()
        request.text = text
        request.confidence = self.confidence
        future = client.call_async(request)
        future.add_done_callback(self.on_action_response)
        self.status = f"detecting: {text}"

    def on_action_response(self, future: object) -> None:
        try:
            response = future.result()
            self.status = response.message
        except Exception as error:
            self.status = str(error)

    def reset(self) -> None:
        client = self.reset_clients[self.mode]
        if not client.service_is_ready():
            self.status = "reset service is not ready"
            return
        future = client.call_async(Trigger.Request())
        future.add_done_callback(self.on_action_response)
        self.status = "resetting"

    def set_mode(self, mode: int) -> None:
        if not self.mode_client.service_is_ready():
            self.status = "mode service is not ready"
            return
        request = SetPipelineMode.Request()
        request.mode = mode
        future = self.mode_client.call_async(request)
        future.add_done_callback(self.on_action_response)
        self.status = f"switching to mode {mode}"

    def switch_model(self, index: int) -> None:
        if self.model_switching:
            self.status = "a model switch is already in progress"
            return
        if not self.model_client.service_is_ready():
            self.status = "model switch service is not ready"
            return
        label, model_id, bundle_dir = self.model_options[index]
        request = SwitchModel.Request()
        request.model_id = model_id
        request.bundle_dir = bundle_dir
        request.precision = "fp16"
        self.model_switching = True
        future = self.model_client.call_async(request)
        future.add_done_callback(self.on_model_response)
        self.status = f"loading {label}; tracking will reset"

    def on_model_response(self, future: object) -> None:
        self.model_switching = False
        try:
            response = future.result()
            if not response.success:
                self.status = f"model switch failed: {response.message}"
                return
            for label, model_id, _ in self.model_options:
                if response.active_model_id == model_id:
                    self.active_model = label
                    break
            if self.reset_clients[2].service_is_ready():
                self.reset_clients[2].call_async(Trigger.Request())
            self.metrics = {}
            self.status = (
                f"{self.active_model} ready in {response.load_ms:.1f} ms"
            )
        except Exception as error:
            self.status = f"model switch failed: {error}"

    def switch_camera_profile(self, index: int) -> None:
        if self.camera_switching:
            self.status = "a camera switch is already in progress"
            return
        if not self.camera_client.service_is_ready():
            self.status = "camera profile service is not ready"
            return
        width, height, fps = self.camera_profiles[index]
        request = SetCameraProfile.Request()
        request.width = width
        request.height = height
        request.fps = float(fps)
        self.camera_switching = True
        future = self.camera_client.call_async(request)
        future.add_done_callback(self.on_camera_response)
        self.status = f"restarting camera at {width}x{height}@{fps}"

    def on_camera_response(self, future: object) -> None:
        self.camera_switching = False
        try:
            response = future.result()
            if not response.success:
                self.status = f"camera switch failed: {response.message}"
                return
            self.active_camera_profile = (
                int(response.actual_width),
                int(response.actual_height),
                int(round(response.requested_fps)),
            )
            self.source_sizes[0] = self.active_camera_profile[:2]
            self.source_sizes[1] = self.active_camera_profile[:2]
            self.camera_observed_fps = float(response.observed_fps)
            if self.reset_clients[2].service_is_ready():
                self.reset_clients[2].call_async(Trigger.Request())
            self.metrics = {}
            self.status = (
                f"camera {response.actual_width}x{response.actual_height}"
                f" requested {response.requested_fps:g}, observed "
                f"{response.observed_fps:.1f} FPS; ready in "
                f"{response.switch_ms:.1f} ms"
            )
        except Exception as error:
            self.status = f"camera switch failed: {error}"

    def handle_model_menu(self, key: int) -> None:
        if key in (27, ord("m")):
            self.model_menu = False
            self.status = "model selection cancelled"
            return
        index = key - ord("1")
        if 0 <= index < len(self.model_options):
            self.model_menu = False
            self.switch_model(index)

    def handle_camera_menu(self, key: int) -> None:
        if key in (27, ord("c")):
            self.camera_menu = False
            self.status = "camera selection cancelled"
            return
        index = key - ord("1")
        if 0 <= index < len(self.camera_profiles):
            self.camera_menu = False
            self.switch_camera_profile(index)

    def handle_key(self, key: int) -> None:
        if self.entering_text:
            if key in (10, 13):
                self.entering_text = False
                self.send_text()
            elif key == 27:
                self.entering_text = False
                self.text = ""
                self.status = "text cancelled"
            elif key in (8, 127):
                self.text = self.text[:-1]
            elif 32 <= key <= 126:
                self.text += chr(key)
            return
        if self.model_menu:
            self.handle_model_menu(key)
            return
        if self.camera_menu:
            self.handle_camera_menu(key)
            return
        if key == ord("t"):
            self.entering_text = True
            self.text = ""
            self.status = "type a prompt; Enter=send, Esc=cancel"
        elif key == ord("m"):
            self.model_menu = True
            self.status = "select SAM2 model"
        elif key == ord("c"):
            self.camera_menu = True
            self.status = "select camera profile"
        elif key == ord("r"):
            self.reset()
        elif key == ord("1"):
            self.set_mode(SetPipelineMode.Request.INSTINCTSAM)
        elif key == ord("2"):
            self.set_mode(SetPipelineMode.Request.HYBRID)
        elif key == ord("["):
            self.change_window_preset(-1)
        elif key == ord("]"):
            self.change_window_preset(1)
        elif key == ord("f"):
            self.toggle_fullscreen()
        elif key in (27, ord("q")):
            rclpy.shutdown()

    def display(self) -> None:
        if self.frame is None:
            self.handle_key(cv2.waitKeyEx(1))
            return
        frame_mode = self.mode if self.mode in self.frames else 0
        render_state = (
            frame_mode,
            self.frame_versions[frame_mode],
            self.mode,
            self.status,
            self.entering_text,
            self.model_menu,
            self.camera_menu,
            self.model_switching,
            self.camera_switching,
            self.active_model,
            self.active_camera_profile,
            self.camera_observed_fps,
            self.text,
            self.drag_start,
            self.drag_current,
        )
        if render_state == self.last_render_state:
            self.handle_key(cv2.waitKeyEx(1))
            return
        self.last_render_state = render_state
        rendered = self.frame.copy()
        if self.drag_start is not None and self.drag_current is not None:
            cv2.rectangle(
                rendered,
                self.drag_start,
                self.drag_current,
                (0, 255, 255),
                2,
            )
        camera = (
            f"{self.active_camera_profile[0]}x{self.active_camera_profile[1]}"
            f" req{self.active_camera_profile[2]}"
        )
        if self.camera_observed_fps > 0.0:
            camera += f" obs{self.camera_observed_fps:.0f}"
        model = f" | {self.active_model}" if self.mode == 2 else ""
        lines = [
            f"Mode {self.mode}{model} | Cam {camera} | 1=GI  2=GI->SAM2",
            self.status,
        ]
        if self.entering_text:
            lines.append(f"> {self.text}_")
        if self.model_menu:
            lines.extend(
                f"[{index}] {label}"
                + (" (active)" if label == self.active_model else "")
                for index, (label, _, _) in enumerate(self.model_options, 1)
            )
            lines.append("Esc=cancel")
        if self.camera_menu:
            lines.extend(
                f"[{index}] {width}x{height}@{fps}"
                + (
                    " (active)"
                    if (width, height, fps) == self.active_camera_profile
                    else ""
                )
                for index, (width, height, fps) in enumerate(
                    self.camera_profiles, 1
                )
            )
            lines.append("Esc=cancel")
        if self.mode == SetPipelineMode.Request.HYBRID:
            latency = self.metrics.get(
                "tracker_total_ms",
                self.metrics.get("inference_ms", self.metrics.get("latency_ms")),
            )
            fps = self.metrics.get(
                "tracking_fps",
                self.metrics.get("fps", self.metrics.get("processed_fps")),
            )
            backend = self.metrics.get(
                "tracker_backend", self.metrics.get("backend")
            )
            metric_parts = []
            if latency is not None:
                metric_parts.append(f"model {float(latency):.1f} ms")
            if fps is not None:
                metric_parts.append(f"{float(fps):.1f} FPS")
            if backend is not None:
                metric_parts.append(str(backend))
            if metric_parts:
                lines.append(" | ".join(metric_parts))
        first_line_y = (
            rendered.shape[0] - 12 - (len(lines) - 1) * 28
            if self.mode == SetPipelineMode.Request.INSTINCTSAM
            else 28
        )
        for index, line in enumerate(lines):
            cv2.putText(
                rendered,
                line,
                (12, first_line_y + index * 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
        cv2.imshow(self.window_name, rendered)
        if not self.window_initialized:
            width, height = self.window_presets[self.preset_index]
            cv2.resizeWindow(self.window_name, width, height)
            self.window_initialized = True
        self.handle_key(cv2.waitKeyEx(1))


def main() -> None:
    rclpy.init()
    node = InteractiveViewer()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.001)
            node.display()
    finally:
        cv2.destroyAllWindows()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
