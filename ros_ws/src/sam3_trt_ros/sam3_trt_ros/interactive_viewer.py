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

from sam3_trt_msgs.srv import AddBox, AddPoint, SetPipelineMode, SetTextPrompt


class InteractiveViewer(Node):
    def __init__(self) -> None:
        super().__init__("sam3_trt_interactive_viewer")
        self.declare_parameter("display_scale", 3.0)
        self.declare_parameter("display_max_width", 3840)
        self.declare_parameter("confidence", 0.5)
        self.mode = 1
        self.bridge = CvBridge()
        self.frames: dict[int, object] = {}
        self.frame_versions = {0: 0, 1: 0, 2: 0}
        self.last_render_state: object = None
        self.raw_frame = None
        self.source_width = 0
        self.source_height = 0
        self.scale = 1.0
        self.drag_start: tuple[int, int] | None = None
        self.drag_current: tuple[int, int] | None = None
        self.entering_text = False
        self.text = ""
        self.status = "t=text, click=point, drag=box, r=reset, q=quit"
        self.metrics: dict[str, object] = {}
        self.display_max_width = int(self.get_parameter("display_max_width").value)
        self.display_scale = float(self.get_parameter("display_scale").value)
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
        self.window_name = "SAM3 / SAM2 TensorRT tracking"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self.on_mouse)

    @property
    def frame(self) -> object:
        return self.frames.get(self.mode, self.raw_frame)

    def on_image(self, mode: int, message: Image) -> None:
        frame = self.bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        self.frame_versions[mode] += 1
        if mode == 0:
            self.raw_frame = frame
        else:
            self.frames[mode] = frame
        current = self.frame
        if current is not None:
            self.source_height, self.source_width = current.shape[:2]

    def on_result(self, mode: int, message: String) -> None:
        if mode != self.mode:
            return
        try:
            self.metrics = json.loads(message.data)
        except json.JSONDecodeError:
            pass

    def on_mode(self, message: UInt8) -> None:
        self.mode = int(message.data)
        self.metrics = {}
        self.status = (
            "mode 1: General Instinct SAM3/SAM3.1"
            if self.mode == 1
            else "mode 2: GI detection -> TV5M SAM2 TensorRT"
        )

    def to_source(self, x: int, y: int) -> tuple[float, float]:
        return x / self.scale, y / self.scale

    def on_mouse(self, event: int, x: int, y: int, flags: int, _: object) -> None:
        if self.entering_text or self.frame is None:
            return
        point = self.to_source(x, y)
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
                self.send_point(end)
                return
            if dx < 5 or dy < 5:
                self.status = "box must be at least 5x5 pixels"
                return
            self.send_box(start, end)

    def send_box(self, start: tuple[int, int], end: tuple[int, int]) -> None:
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

    def send_point(self, point: tuple[int, int]) -> None:
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
        if key == ord("t"):
            self.entering_text = True
            self.text = ""
            self.status = "type a prompt; Enter=send, Esc=cancel"
        elif key == ord("r"):
            self.reset()
        elif key == ord("1"):
            self.set_mode(SetPipelineMode.Request.INSTINCTSAM)
        elif key == ord("2"):
            self.set_mode(SetPipelineMode.Request.HYBRID)
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
            self.text,
            self.drag_start,
            self.drag_current,
            json.dumps(self.metrics, sort_keys=True, default=str),
        )
        if render_state == self.last_render_state:
            self.handle_key(cv2.waitKeyEx(1))
            return
        self.last_render_state = render_state
        self.scale = min(
            self.display_scale,
            self.display_max_width / self.frame.shape[1],
        )
        rendered = cv2.resize(
            self.frame,
            (
                int(self.frame.shape[1] * self.scale),
                int(self.frame.shape[0] * self.scale),
            ),
            interpolation=cv2.INTER_LINEAR,
        )
        if self.drag_start is not None and self.drag_current is not None:
            start = tuple(int(value * self.scale) for value in self.drag_start)
            current = tuple(int(value * self.scale) for value in self.drag_current)
            cv2.rectangle(rendered, start, current, (0, 255, 255), 2)
        lines = [f"Mode {self.mode} | 1=GI SAM3  2=GI->SAM2", self.status]
        if self.entering_text:
            lines.append(f"> {self.text}_")
        latency = self.metrics.get(
            "tracker_total_ms",
            self.metrics.get("inference_ms", self.metrics.get("latency_ms")),
        )
        fps = self.metrics.get(
            "tracking_fps", self.metrics.get("fps", self.metrics.get("processed_fps"))
        )
        backend = self.metrics.get("tracker_backend", self.metrics.get("backend"))
        metric_parts = []
        if latency is not None:
            metric_parts.append(f"model {float(latency):.1f} ms")
        if fps is not None:
            metric_parts.append(f"{float(fps):.1f} FPS")
        if backend is not None:
            metric_parts.append(str(backend))
        if metric_parts:
            lines.append(" | ".join(metric_parts))
        for index, line in enumerate(lines):
            cv2.putText(
                rendered,
                line,
                (12, 28 + index * 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
        cv2.imshow(self.window_name, rendered)
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
