# Jetson Thor deployment

This runbook deploys two selectable ROS 2 pipelines in one viewer:

1. InstinctSAM native text/box tracking.
2. InstinctSAM first-frame text detection followed by TV5M FP16 SAM2 TensorRT
   tracking.

General Instinct artifacts stay under `~/vendor` and never enter Git.

## 1. One-time Thor setup

Run locally on Thor:

```bash
sudo usermod -aG docker "$USER"
getent group docker
```

Open a new login and verify:

```bash
id -Gn
docker info
```

The account must list `docker`. The scripts explicitly request the NVIDIA
runtime, so Docker's default runtime may remain `runc`.

## 2. Obtain code and private delivery

```bash
cd ~
git clone git@github.com:thedannyliu/Efficient-SAM3-TensorRT.git
cd Efficient-SAM3-TensorRT
```

The private delivery must be copied separately to:

```text
~/vendor/general-instinct/InstinctSAM-Thor-delivery/
```

Read the licenses, then acknowledge research/evaluation use for the current
shell:

```bash
export GI_RESEARCH_USE_ACK=research-evaluation-only
python3 scripts/verify_gi_delivery.py \
  ~/vendor/general-instinct/InstinctSAM-Thor-delivery
```

## 3. Load and smoke the original image

```bash
export GI_RESEARCH_USE_ACK=research-evaluation-only
bash scripts/thor_load_gi_image.sh
docker image inspect instinctsam:thor-r39
```

The delivery targets L4T r39.2 and TensorRT 10.16. This Thor currently runs
L4T R38.4, so all initial results are unsupported compatibility results. Do not
install a mismatched host TensorRT to make the image load. If startup or engine
rebuild fails, preserve `docker logs` and stop.

## 4. Build the ROS integration

The existing SAM2 workspace must already be built.

```bash
cd ~/Efficient-SAM3-TensorRT
export SAM2_ROOT=~/Efficient-SAM2-TensorRT
bash scripts/setup_thor_ros.sh
```

Every new terminal uses:

```bash
source ~/Efficient-SAM3-TensorRT/scripts/source_thor_ros_env.sh
```

## 5. Discover and lock the D455 profile

Start the driver without assuming a profile:

```bash
ros2 launch realsense2_camera rs_launch.py \
  enable_color:=true enable_depth:=false
```

In another terminal:

```bash
ros2 param describe /camera/camera rgb_camera.color_profile
ros2 param get /camera/camera rgb_camera.color_profile
ros2 topic echo --once /camera/camera/color/camera_info
ros2 topic hz /camera/camera/color/image_raw
lsusb -t
```

Only use a 60 FPS profile if the installed driver lists it and the measured
topic rate confirms it. Record the negotiated profile and USB speed in the
baseline document.

## 6. Unmodified vendor baseline

Stop the ROS RealSense node so the container can own `/dev/video4`, then run:

```bash
cd ~/Efficient-SAM3-TensorRT
export GI_RESEARCH_USE_ACK=research-evaluation-only
export GI_CAMERA_DEVICE=/dev/video4
bash scripts/thor_run_gi_native.sh
curl -s http://127.0.0.1:8767/status.json
```

Launch the ROS adapter and viewer on the Thor desktop:

```bash
source ~/Efficient-SAM3-TensorRT/scripts/source_thor_ros_env.sh
export DISPLAY=:0
ros2 launch sam3_trt_ros instinctsam_native.launch.py
```

Controls:

- `t`: type a text prompt; Enter sends, Esc cancels.
- comma-separated concepts are accepted.
- mouse drag: geometry box prompt.
- `r`: reset.
- `q`: exit.

This unmodified run is the licensing and compatibility baseline. The final
unified interface uses a locally patched image after this baseline is recorded.

## 7. Unified mode 1/mode 2 interface

The unified interface needs a locally licensed image named
`instinctsam:thor-r39-unified-api`. Its local patch adds a one-shot detection
endpoint and a `native`/`hybrid` mode endpoint. The derived image and patch are
never pushed to GitHub.

Stop the unmodified container and start the unified image:

```bash
docker rm -f instinctsam-native 2>/dev/null || true
cd ~/Efficient-SAM3-TensorRT
export GI_RESEARCH_USE_ACK=research-evaluation-only
bash scripts/thor_run_gi_unified.sh
```

The GI container remains the sole owner of `/dev/video4`. Its ROS adapter
publishes the same source frames to both routes, so switching does not reopen
the camera.

```bash
source ~/Efficient-SAM3-TensorRT/scripts/source_thor_ros_env.sh
export DISPLAY=:0
ros2 launch sam3_trt_ros unified.launch.py
```

Controls:

- `1`: native General Instinct SAM3/SAM3.1 tracking.
- `2`: GI first-frame text detection followed by TV5M SAM2 TensorRT.
- `t`: enter a text prompt for the active mode.
- mouse drag: geometry prompt in mode 1.
- `r`: reset the active mode.
- `q`: exit.

In mode 2, the coordinator converts masks to at most eight boxes and initializes
SAM2 using the exact source timestamp. SAM2 stays loaded but receives no frames
in mode 1.

## 8. Baseline

Do not change precision, resolution, crossover, rendering, or engine settings
until the baseline is complete. With the selected pipeline already running:

```bash
cd ~/Efficient-SAM3-TensorRT
bash scripts/record_thor_baseline.sh instinctsam
# or
bash scripts/record_thor_baseline.sh hybrid
```

Each command records 100 warm-up frames plus 1,000 measured frames, repeated
three times. Raw outputs remain ignored under `results/`; summarized results
must be copied into `docs/benchmarks/thor_baseline.md`.
