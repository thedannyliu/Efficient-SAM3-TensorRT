from glob import glob

from setuptools import find_packages, setup


package_name = "sam3_trt_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Efficient SAM3 TensorRT maintainers",
    maintainer_email="maintainer@example.com",
    description="ROS 2 integration for InstinctSAM and SAM2 TensorRT.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "instinctsam_adapter = sam3_trt_ros.instinctsam_adapter:main",
            "hybrid_coordinator = sam3_trt_ros.hybrid_coordinator:main",
            "mode_manager = sam3_trt_ros.mode_manager:main",
            "interactive_viewer = sam3_trt_ros.interactive_viewer:main",
            "trace_recorder = sam3_trt_ros.trace_recorder:main",
        ],
    },
)
