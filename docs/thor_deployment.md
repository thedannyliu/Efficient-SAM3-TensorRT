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

The interactive defaults use four concurrent object contexts, synchronous
tracking, synchronized previews, and no adaptive display throttling:

```bash
bash scripts/thor_start_unified_desktop.sh \
  track_concurrency:=4 pipeline_overlap:=false \
  smooth_camera_view:=false adaptive_display_fps:=false
```

For one object, overlap raised the isolated 848x480@60 completed rate from
33.766 to 37.641 FPS but increased mean source age from 42.072 to 65.250 ms.
At two objects the gain was only 2.7% while source age increased by 44.4 ms,
and at four objects overlap was slower. It also adds one explicit mask-delay
frame. Set `pipeline_overlap:=true pipeline_overlap_max_objects:=1` only for a
throughput-oriented one-object benchmark.

TensorRT object batching is a separate experimental switch:

```bash
bash scripts/thor_start_unified_desktop.sh \
  track_bucket_size:=2 track_bucket_min_objects:=4
```

Supported bucket sizes are 1, 2, and 4. Size 1 is the default and uses the
faster parallel per-object contexts. Thor testing found that bucket 2/4
increased four-object latency from 86.49 ms to 189.90/198.33 ms, so neither is
enabled for the demo. The options remain available for newly rebuilt engines
and future TensorRT versions. `/sam/result_json` reports
`track_bucket_active`, `track_bucket_size`, and
`track_bucket_min_objects`.

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
together. Mode 2 composites the current raw camera frame and newest SAM2 label
image on an 848x480 interaction canvas, then the GUI performs the final display
scaling. Mouse callbacks are returned in the shared canvas coordinates and
converted once to the active camera coordinates, so point/box prompts remain
aligned at every display size and camera profile. Override the internal canvas
with `render_width:=WIDTH render_height:=HEIGHT` only when measuring that
rendering tradeoff.
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
resize or SAM2 model switch. The UI maps its interaction canvas back
to the active camera pixels before sending point/box prompts.

Thor validation on 2026-07-29 found that model changes take 2.2–2.7 s. Camera
changes take 87.7–92.8 s because the complete licensed GI runtime reloads.
The menu therefore reports requested and observed camera FPS separately.
848x480@60 reached 60.3 capture FPS and is the recommended latency/capacity
profile. Use 1280x720@30 when spatial detail matters more than motion cadence.
The D455 does not expose 60 FPS at 1280x720, so that unsupported combination
is not offered.

Mode 2 defaults to the synchronized SAM2 preview: each displayed source frame
is paired with the mask computed from that exact frame. This removes the
moving-camera ghost where a mask from frame `t-1` was drawn on the latest raw
frame `t`. The tradeoff is that the complete view updates at tracking FPS.
For a smooth camera at the cost of spatially stale masks, launch with
`smooth_camera_view:=true`; that path reads the latest raw RGB frame from
shared memory and composites the newest available label image.

When masks are active, desktop painting and TensorRT contend for compute.
The original `adaptive_display_fps:=true` rule selected 28 FPS for one object
and `36 / object_count` thereafter. A 2026-07-29 moving-camera check rejected
that rule for the interactive default: at three objects it limited display to
12 FPS even though tracking was 14.17 FPS and could add about 83 ms before a
completed mask was painted. The default is now
`adaptive_display_fps:=false`. Re-enable it only for throughput experiments
where model capacity matters more than mask presentation delay.

Inspect the actual GUI cadence and model path separately:

```bash
ros2 topic echo /sam3_viewer/render_metrics --once --field data
ros2 topic echo /sam/result_json --once --field data
```

The first reports configured/active display FPS, interval jitter, and
compose/paint timing. It also reports unique raw camera cadence when the smooth
shared-camera view is enabled. The second reports model latency, tracking FPS,
source age, object IDs, and whether overlap is currently active.

Both modes draw the same normalized metrics at the bottom:
`model ms`, `tracking FPS`, `capacity FPS`, backend, `render FPS`, and
`raw FPS`. Mode 2 also reports source age. Mode 1's delivered vendor overlay
retains its own top-left FPS watermark. For mode 1, model time is
`backbone_ms + tracker_ms`; for mode 2 it is `tracker_total_ms`.
`capacity FPS` is `1000 / model_ms`, while `tracking FPS` is the measured
pipeline output cadence. Render FPS is only the desktop refresh cadence and
must not be reported as model throughput.

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

The TV5M, TV11M, and TV21M model-menu entries use their on-device
`fp16_best_20260729` bundles built from `tv5-best.pt`, `tv11-best.pt`, and
`tv21-best.pt`. Only the selected SAM2 model is resident. Switching models
resets tracking state but does not restart the GI container.

The three menu entries were smoke-tested in the live 848x480@60 camera
pipeline on 2026-07-29. Each test used mode 2 and the text prompt `chair`,
which produced five SAM2 tracks:

| Model | TensorRT load | Encoder GPU | Five-object inference | Tracking FPS |
|---|---:|---:|---:|---:|
| TV5M | 2823.7 ms | 7.44 ms | 113.73 ms | 8.65 |
| TV11M | 2428.7 ms | 7.62 ms | 111.99 ms | 8.86 |
| TV21M | 2365.6 ms | 13.63 ms | 117.61 ms | 8.44 |

These are single live samples, not a controlled statistical benchmark. They
verify model switching, GI text-to-box handoff, and multi-object tracking.
The near-equal five-object results show that the shared SAM2 tracking tail
dominates at this object count. TV21M's larger encoder is more visible with no
active objects: the same smoke measured 14.52 ms total inference versus
7.75 ms for TV11M. `/sam/result_json` is the authoritative runtime source for
`model_id`; the launch parameter still describes the initial bundle.

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

Text initialization now uses the same retry rule. Before the fix, a single
dropped frozen frame made the service wait 30 seconds and return
`SAM2 did not initialize on the frozen frame`, which appeared to be a UI crash.
After commit `7eb9435`, two consecutive `bag` text handoffs completed without
restarting the viewer or either model. The UI also rejects a new text request
while the previous handoff is pending.

Additional live-camera validation on 2026-07-29:

- mode 1 accepted text, native positive-point, and native box prompts;
- mode 2 accepted text, SAM2 positive-point, and SAM2 box prompts;
- a warmed `monitor` text handoff took 345.1 ms to first SAM2 mask, including
  251.3 ms GI detection and 20.8 ms SAM2 initialization;
- the resizable displayed single-object run reached a three-run median of
  13.923 FPS, inference mean/p95 36.53/39.64 ms, and source-age p50/p95
  47.50/50.56 ms with zero drops.

The General Instinct router was also checked with the requested prompts under
848x480@60 capture. After prompt stabilization, `bag` produced one object on
the `per_object` backend at 8.78 FPS with 115.43 ms of
backbone-plus-tracker time. `chair` produced five objects on `multiplex` at
8.37 FPS with 134.67 ms of model time. The one-object steady state was
therefore faster. Brief inversions immediately after reset are caused by the
vendor's 0.9 EMA retaining re-anchor/backend-switch frames; use capacity FPS
and stabilized tracking FPS for router comparisons.

The synchronized Mode 2 default was validated with two `chair` objects:
57.36 ms model time, 15.78 tracking FPS, 15.87 render FPS, 72.00 ms source
age, `pipeline_overlap=false`, and zero delayed frames. This configuration
displays an older complete frame rather than drawing an older mask on a newer
camera frame.

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
