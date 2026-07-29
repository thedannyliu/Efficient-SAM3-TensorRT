cmake_minimum_required(VERSION 3.8)
project(sam3_trt_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/AddBox.srv"
  "srv/AddPoint.srv"
  "srv/SetCameraProfile.srv"
  "srv/SetPipelineMode.srv"
  "srv/SetTextPrompt.srv"
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
