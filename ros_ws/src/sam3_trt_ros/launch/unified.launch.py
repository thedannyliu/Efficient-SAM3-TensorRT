from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    bundle_dir = LaunchConfiguration("bundle_dir")
    base_url = LaunchConfiguration("base_url")
    display_max_width = LaunchConfiguration("display_max_width")
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
            DeclareLaunchArgument("display_max_width", default_value="1600"),
            DeclareLaunchArgument("viewer", default_value="true"),
            Node(
                package="sam3_trt_ros",
                executable="instinctsam_adapter",
                output="screen",
                parameters=[{"base_url": base_url}],
            ),
            Node(
                package="sam3_trt_ros",
                executable="mode_manager",
                output="screen",
                parameters=[{"gi_base_url": base_url}],
            ),
            Node(
                package="sam3_trt_ros",
                executable="hybrid_coordinator",
                output="screen",
                parameters=[
                    {
                        "source_topic": "/instinctsam/raw",
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
                        "max_objects": 8,
                        "track_concurrency": 8,
                        "pipeline_overlap": False,
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
