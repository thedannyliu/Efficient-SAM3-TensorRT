from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    bundle_dir = LaunchConfiguration("bundle_dir")
    base_url = LaunchConfiguration("base_url")
    display_max_width = LaunchConfiguration("display_max_width")
    default_mode = LaunchConfiguration("default_mode")
    pipeline_overlap = LaunchConfiguration("pipeline_overlap")
    shared_memory_poll_hz = LaunchConfiguration("shared_memory_poll_hz")
    viewer = LaunchConfiguration("viewer")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "bundle_dir",
                default_value=(
                    "/home/ril-thor/Efficient-SAM2-TensorRT/bundles/"
                    "sam2.1-tinyvit-5m/fp16_aux0"
                ),
            ),
            DeclareLaunchArgument(
                "base_url", default_value="http://127.0.0.1:8767"
            ),
            DeclareLaunchArgument("display_max_width", default_value="2560"),
            DeclareLaunchArgument("default_mode", default_value="2"),
            DeclareLaunchArgument("pipeline_overlap", default_value="false"),
            DeclareLaunchArgument("shared_memory_poll_hz", default_value="240.0"),
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
                        "shared_memory_path": (
                            "/dev/shm/sam3_sam2_frame.bin"
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
                        "track_concurrency": 8,
                        "pipeline_overlap": ParameterValue(
                            pipeline_overlap, value_type=bool
                        ),
                        "queue_policy": "latest",
                    }
                ],
            ),
            Node(
                package="sam3_trt_ros",
                executable="interactive_viewer",
                output="screen",
                parameters=[{"display_max_width": display_max_width}],
                condition=IfCondition(viewer),
            ),
        ]
    )
