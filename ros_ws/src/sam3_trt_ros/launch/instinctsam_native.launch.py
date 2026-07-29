from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.nodes import Node


def generate_launch_description() -> LaunchDescription:
    base_url = LaunchConfiguration("base_url")
    display_max_width = LaunchConfiguration("display_max_width")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "base_url", default_value="http://127.0.0.1:8767"
            ),
            DeclareLaunchArgument("display_max_width", default_value="1600"),
            Node(
                package="sam3_trt_ros",
                executable="instinctsam_adapter",
                output="screen",
                parameters=[{"base_url": base_url}],
            ),
            Node(
                package="sam3_trt_ros",
                executable="interactive_viewer",
                output="screen",
                parameters=[
                    {
                        "mode": "instinctsam",
                        "image_topic": "/instinctsam/overlay",
                        "result_topic": "/instinctsam/result_json",
                        "display_max_width": display_max_width,
                    }
                ],
            ),
        ]
    )
