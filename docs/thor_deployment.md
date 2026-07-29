# Jetson Thor deployment

This runbook deploys two selectable ROS 2 pipelines in one viewer:

1. InstinctSAM native text/point/box tracking.
2. InstinctSAM first-frame text detection followed by selectable TV5M, TV11M,
   or TV21M FP16 SAM2 TensorRT tracking, with additional point/box prompts
   handled directly by SAM2.

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

The GI container remains the sole owner of `/dev/video4`. Switching routes does
not reopen the camera.

```bash
cd ~/Efficient-SAM3-TensorRT
bash scripts/thor_launch_unified_ui.sh
```

For a cold start, launch both model loaders concurrently:

```bash
cd ~/Efficient-SAM3-TensorRT
export GI_RESEARCH_USE_ACK=research-evaluation-only
bash scripts/thor_start_unified_desktop.sh
```

This starts the GI container in the background while ROS loads the default
TV5M SAM2 engine. If the GI service is already healthy, it is reused instead
of being restarted. GI and the selected SAM2 model remain resident, so mode 2
only performs first-frame detection and state transfer during normal tracking.

Stop the complete ROS launch before rebuilding or starting another copy:

```bash
cd ~/Efficient-SAM3-TensorRT
bash scripts/thor_stop_unified_desktop.sh
```

The start script refuses to create a second unified launch. This avoids two
adapters and two SAM2 nodes decoding and processing the same camera stream.

The launcher reads `DISPLAY`, `XAUTHORITY`, and `XDG_RUNTIME_DIR` from the
logged-in GNOME session. Do not assume `DISPLAY=:0`; it was `:1` during the
2026-07-28 Thor validation.

The unified launch defaults to mode 2 so an idle UI does not continuously run
the full InstinctSAM backbone. Press `1` when native SAM3 tracking is needed;
press `2` to return to the lower-power capture/hybrid path.

Controls:

- `1`: native General Instinct SAM3/SAM3.1 tracking.
- `2`: GI first-frame text detection followed by the selected SAM2 TensorRT.
- `t`: enter a text prompt for the active mode.
- `m`: open the SAM2 model menu; choose `1`=TV5M, `2`=TV11M, or `3`=TV21M.
- `c`: open the camera profile menu; choose `1`=640x360@30,
  `2`=640x360@60, `3`=848x480@30, `4`=848x480@60, or
  `5`=1280x720@30.
- mouse single-click: positive point prompt in either mode.
- mouse drag: box prompt in either mode.
- `[` / `]`: select the previous/next display preset: 1280x720,
  1600x900, 1920x1080, 2560x1440, or 3840x2160.
- `f`: toggle fullscreen and restore the selected preset.
- `r`: reset the active mode.
- `q`: exit.

The viewer initially opens at 2560x1440. Use a preset or drag any window edge
or corner to choose another size; image, status text, and prompt overlays scale
together. Both modes are normalized to one 1280x720 interaction canvas before
rendering (the native GI overlay is 1280x720 while the SAM2 preview is
640x360), and the GUI performs only the final display scaling. This keeps text
at the same visual size when switching modes. Mouse callbacks are returned in
the shared canvas coordinates and converted once to the active camera
coordinates, so point/box prompts remain aligned at every display size and
camera profile.
Override the initial preset selection with `display_max_width:=WIDTH`.

The model menu keeps only one SAM2 tracker resident. A switch constructs and
validates the replacement TensorRT tracker before atomically replacing the
current tracker, then clears tracking state. This avoids triplicating the
large prompt/track contexts shared by all three TinyViT encoders. The UI stays
responsive and reports the measured load time.

The camera menu is different from the display-size presets. It changes the
actual capture request, restarts the licensed GI container using its public
entrypoint arguments, restores the active pipeline mode, verifies the returned
JPEG dimensions, and resets tracking. The TensorRT cache volume is retained,
but GI model loading makes a camera switch substantially slower than a window
resize or SAM2 model switch. The UI maps its 1280x720 interaction canvas back
to the active camera pixels before sending point/box prompts.

Thor validation on 2026-07-29 found that model changes take 2.2–2.7 s. Camera
changes take 87.7–92.8 s because the complete licensed GI runtime reloads.
The menu therefore reports requested and observed camera FPS separately.
848x480@60 reached 60.3 capture FPS, but its short SAM2 preview diagnostic was
only about 8.8 FPS; 1280x720@30 remains the recommended default. The D455 does
not expose 60 FPS at 1280x720, so that unsupported combination is not offered.

Mode 1 keeps the vendor FPS watermark at the top-left and places only our mode
and action status at the bottom. Mode 2 draws our model latency/FPS/backend
line because its SAM2 preview has no vendor metric watermark.

Validated on the D455 and the real TV5M FP16 bundle on 2026-07-28:

- mode 1 text prompt created three `monitor` tracks and selected multiplex;
- mode 2 created two `monitor` masks, converted them to boxes, and initialized
  two TV5M tracks;
- mode 2 handoff took 337.4 ms in that smoke run: 212.5 ms GI detection,
  22.9 ms mask-to-box, and 23.7 ms SAM2 initialization;
- subsequent SAM2 model inference was 48.4 ms for two objects.

After direct gated relay and pausing the unused GI overlay stream in mode 2,
the formal two-object headless median improved from 5.746 to 13.865 FPS
(2.413x). Model mean/p95 was 46.99/48.14 ms, and source-age p50/p95 was
62.87/92.75 ms. See `docs/benchmarks/thor_baseline.md` for the protocol and raw
result paths.

The TV5M bundle printed TensorRT's cross-device engine warning, so rebuild its
engines on Thor before treating this as the final achievable Thor speed.

In mode 2, the coordinator converts masks to at most eight boxes and initializes
SAM2 using the exact source timestamp. SAM2 stays loaded but receives no frames
in mode 1.

Mode 2 publishes only the SAM2 relay image, not a duplicate raw ROS image. The
GI overlay MJPEG reader is also paused. These two omissions reduce image
decode/copy/DDS work without changing model precision or masks.

The current Mode 2 steady stream uses
`/dev/shm/sam3_sam2_frame.bin` instead of serializing a 2.76 MB ROS Image
between the Python adapter and C++ tracker. The file contains only the latest
locked RGB8 frame and source stamp. The ROS image subscription remains active
for the frozen point/box/text handoff frame. Do not delete the shared file
while the pipeline is running; the adapter creates or resets it at startup.

Point/box initialization gates the live relay, drains the preceding camera
queue, and retries the same frozen timestamp until SAM2 confirms the new object.
This prevents a successful track from leaving the UI service waiting on a
dropped initialization frame.

Additional live-camera validation on 2026-07-29:

- mode 1 accepted text, native positive-point, and native box prompts;
- mode 2 accepted text, SAM2 positive-point, and SAM2 box prompts;
- a warmed `monitor` text handoff took 345.1 ms to first SAM2 mask, including
  251.3 ms GI detection and 20.8 ms SAM2 initialization;
- the resizable displayed single-object run reached a three-run median of
  13.923 FPS, inference mean/p95 36.53/39.64 ms, and source-age p50/p95
  47.50/50.56 ms with zero drops.

See `docs/general_instinct_runtime_review.md` for the delivered TensorRT
boundary, effective optimizations, quality limits, and the recommended scope of
our own SAM3 TensorRT implementation.

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
