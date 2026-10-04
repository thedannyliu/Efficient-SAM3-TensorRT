# Thor runtime architecture

The host runs the ROS 2 viewer and orchestration. A separately licensed
InstinctSAM container owns its detector/tracker and camera capture.

| Component | Responsibility |
| --- | --- |
| `src/sam31_trt/gi_client.py` | HTTP endpoint and response contract |
| `src/sam31_trt/handoff.py` | Select detections and convert masks to initialization boxes |
| `src/sam31_trt/shared_frame.py` | Latest RGB frame transport with sequence/timestamp metadata |
| ROS `instinctsam_adapter.py` | HTTP streams to ROS image/result topics |
| ROS `mode_manager.py` | Mode and camera-profile control |
| ROS `hybrid_coordinator.py` | Detection-to-SAM2 handoff and rollback |
| ROS `interactive_viewer.py` | Prompts, model/mode selection and rendering |

ROS Python files live under `ros_ws/src/sam3_trt_ros/sam3_trt_ros/`.
Launch parameters are in `ros_ws/src/sam3_trt_ros/launch/unified.launch.py`.

In Mode 1, detection and tracking remain inside the container. In Mode 2,
the coordinator freezes the detection frame, converts selected masks to boxes,
and initializes the host-side SAM2 TensorRT tracker for subsequent frames.
The shared-memory transport uses locked snapshots; sequence numbers prevent
consuming the same frame twice. Preserve timestamps through rendering to avoid
pairing a delayed mask with the wrong image.

The supplied Thor deployment handoff makes these component boundaries explicit.
Its model/engine files are LFS pointers; it does not provide runnable artifacts
for validating hardware changes in a CPU development environment.

For changes to the ROS graph or runtime, rebuild the workspace using
`scripts/thor/setup_thor_ros.sh` and exercise both modes on the target device.
CPU regression tests cover transport, selection and reporting contracts only.
