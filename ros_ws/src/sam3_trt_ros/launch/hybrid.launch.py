from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    bundle_dir = LaunchConfiguration("bundle_dir")
    source_topic = LaunchConfiguration("source_topic")
    display_max_width = LaunchConfiguration("display_max_width")
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
                "source_topic", default_value="/camera/camera/color/image_raw"
            ),
            DeclareLaunchArgument("display_max_width", default_value="1600"),
            Node(
                package="sam3_trt_ros",
                executable="hybrid_coordinator",
                output="screen",
                parameters=[
                    {
                        "source_topic": source_topic,
                        "relay_topic": "/hybrid/camera/image_raw",
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
                parameters=[
                    {
                        "mode": "hybrid",
                        "image_topic": "/sam/preview",
                        "result_topic": "/sam/result_json",
                        "display_max_width": display_max_width,
                    }
                ],
            ),
        ]
    )
