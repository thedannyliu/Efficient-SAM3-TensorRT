from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    adaptive_display_fps = LaunchConfiguration("adaptive_display_fps")
    bundle_dir = LaunchConfiguration("bundle_dir")
    base_url = LaunchConfiguration("base_url")
    display_fps = LaunchConfiguration("display_fps")
    display_max_width = LaunchConfiguration("display_max_width")
    default_mode = LaunchConfiguration("default_mode")
    gstreamer_mjpeg_decode = LaunchConfiguration("gstreamer_mjpeg_decode")
    opengl_view = LaunchConfiguration("opengl_view")
    pipeline_overlap = LaunchConfiguration("pipeline_overlap")
    pipeline_overlap_max_objects = LaunchConfiguration(
        "pipeline_overlap_max_objects"
    )
    render_height = LaunchConfiguration("render_height")
    render_width = LaunchConfiguration("render_width")
    shared_memory_poll_hz = LaunchConfiguration("shared_memory_poll_hz")
    shared_view_poll_hz = LaunchConfiguration("shared_view_poll_hz")
    smooth_camera_view = LaunchConfiguration("smooth_camera_view")
    track_concurrency = LaunchConfiguration("track_concurrency")
    track_bucket_min_objects = LaunchConfiguration(
        "track_bucket_min_objects"
    )
    track_bucket_size = LaunchConfiguration("track_bucket_size")
    viewer = LaunchConfiguration("viewer")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "adaptive_display_fps", default_value="false"
            ),
            DeclareLaunchArgument(
                "bundle_dir",
                default_value=(
                    "/home/ril-thor/Efficient-SAM2-TensorRT/bundles/"
                    "sam2.1-tinyvit-5m/fp16_best_20260729"
                ),
            ),
            DeclareLaunchArgument(
                "base_url", default_value="http://127.0.0.1:8767"
            ),
            DeclareLaunchArgument("display_fps", default_value="60.0"),
            DeclareLaunchArgument("display_max_width", default_value="2560"),
            DeclareLaunchArgument("default_mode", default_value="2"),
            DeclareLaunchArgument(
                "gstreamer_mjpeg_decode", default_value="false"
            ),
            DeclareLaunchArgument("opengl_view", default_value="false"),
            DeclareLaunchArgument("pipeline_overlap", default_value="false"),
            DeclareLaunchArgument(
                "pipeline_overlap_max_objects", default_value="1"
            ),
            DeclareLaunchArgument("render_height", default_value="480"),
            DeclareLaunchArgument("render_width", default_value="848"),
            DeclareLaunchArgument("shared_memory_poll_hz", default_value="240.0"),
            DeclareLaunchArgument("shared_view_poll_hz", default_value="120.0"),
            DeclareLaunchArgument("smooth_camera_view", default_value="false"),
            DeclareLaunchArgument("track_concurrency", default_value="4"),
            DeclareLaunchArgument(
                "track_bucket_min_objects", default_value="4"
            ),
            DeclareLaunchArgument("track_bucket_size", default_value="1"),
            DeclareLaunchArgument("viewer", default_value="true"),
            Node(
                package="sam3_trt_ros",
                executable="instinctsam_adapter",
                output="screen",
                respawn=True,
                respawn_delay=2.0,
                parameters=[
                    {
                        "base_url": base_url,
                        "gstreamer_mjpeg_decode": ParameterValue(
                            gstreamer_mjpeg_decode, value_type=bool
                        ),
                        "shared_memory_path": (
                            "/dev/shm/sam3_sam2_frame.bin"
                        ),
                        "shared_view_poll_hz": ParameterValue(
                            shared_view_poll_hz, value_type=float
                        ),
                    }
                ],
            ),
            Node(
                package="sam3_trt_ros",
                executable="mode_manager",
                output="screen",
                parameters=[
                    {
                        "gi_base_url": base_url,
                        "default_mode": ParameterValue(
                            default_mode, value_type=int
                        ),
                    }
                ],
            ),
            Node(
                package="sam3_trt_ros",
                executable="hybrid_coordinator",
                output="screen",
                parameters=[
                    {
                        "relay_topic": "/hybrid/camera/image_raw",
                        "gi_base_url": base_url,
                    }
                ],
            ),
            Node(
                package="sam2_trt_ros",
                executable="sam2_trt_node",
                output="screen",
                parameters=[
                    {
                        "model_id": "sam2.1-tinyvit-5m",
                        "bundle_dir": bundle_dir,
                        "precision": "fp16",
                        "image_topic": "/hybrid/camera/image_raw",
                        "shared_memory_path": (
                            "/dev/shm/sam3_sam2_frame.bin"
                        ),
                        "shared_memory_poll_hz": ParameterValue(
                            shared_memory_poll_hz, value_type=float
                        ),
                        "max_objects": 8,
                        "track_concurrency": ParameterValue(
                            track_concurrency, value_type=int
                        ),
                        "track_bucket_min_objects": ParameterValue(
                            track_bucket_min_objects, value_type=int
                        ),
                        "track_bucket_size": ParameterValue(
                            track_bucket_size, value_type=int
                        ),
                        "pipeline_overlap": ParameterValue(
                            pipeline_overlap, value_type=bool
                        ),
                        "pipeline_overlap_max_objects": ParameterValue(
                            pipeline_overlap_max_objects, value_type=int
                        ),
                        "queue_policy": "latest",
                    }
                ],
            ),
            Node(
                package="sam3_trt_ros",
                executable="interactive_viewer",
                output="screen",
                parameters=[
                    {
                        "adaptive_display_fps": ParameterValue(
                            adaptive_display_fps, value_type=bool
                        ),
                        "display_fps": ParameterValue(
                            display_fps, value_type=float
                        ),
                        "display_max_width": display_max_width,
                        "render_height": ParameterValue(
                            render_height, value_type=int
                        ),
                        "render_width": ParameterValue(
                            render_width, value_type=int
                        ),
                        "opengl_view": ParameterValue(
                            opengl_view, value_type=bool
                        ),
                        "shared_memory_path": (
                            "/dev/shm/sam3_sam2_frame.bin"
                        ),
                        "shared_view_poll_hz": ParameterValue(
                            shared_view_poll_hz, value_type=float
                        ),
                        "smooth_camera_view": ParameterValue(
                            smooth_camera_view, value_type=bool
                        ),
                    }
                ],
                condition=IfCondition(viewer),
            ),
        ]
    )
