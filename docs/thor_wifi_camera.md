# Thor Wi-Fi camera integration

## Scope

This feature adds an RTSP or HTTP network camera as an alternative to the
wired RealSense source. The preserved stable worktrees and
`~/thor-demo-baseline-20260730/start-object-hud.sh` are unchanged.

The internal `~/repo/live_wifi_cam_stream` package documents the camera URL
and provides a ROS 2 publisher. Its `package.xml` declares MIT, but the clone
does not contain a license text. Its source is therefore not copied or
vendored into this repository.

## Data path

The production path opens the network stream directly in the licensed GI
container:

```text
RTSP/HTTP camera
  -> GI OpenCV latest-frame reader (one decode)
  -> SAM3 native tracking and text/geometry prompting
  -> GI raw frame adapter/shared memory
  -> TV5M SAM2 TensorRT tracking
  -> synchronized preview and unified HUD
```

Launching the separate Python ROS publisher in front of GI would require an
additional full-frame ROS copy and another bridge into the container. Direct
URI input avoids that overhead and guarantees that GI detection and SAM2
tracking see the same source.

The URI is passed only through `GI_WIFI_CAMERA_URL`/`GI_CAMERA_URI`. Scripts
and HUD output never print it, because it may contain credentials.

Before replacing a running wired container, the selector asks `ffprobe` to
open the configured stream. An unreachable server, invalid path, or rejected
credentials fail without interrupting the current camera runtime.

## Build on Thor

```bash
cd ~/Efficient-SAM3-TensorRT-wifi-camera/ros_ws
source /opt/ros/jazzy/setup.bash
source ~/Efficient-SAM2-TensorRT-stable/ros_ws/install/setup.bash
source ~/venvs/efficient_sam3_trt_ros/bin/activate
colcon build --symlink-install
```

## Select the Wi-Fi camera

Set the URL without committing it:

```bash
export GI_WIFI_CAMERA_URL='rtsp://USER:PASSWORD@CAMERA_IP:PORT/PATH'
export GI_UNIFIED_IMAGE=instinctsam:thor-r39-unified-api-baseline-20260730
export SAM2_ROOT="$HOME/Efficient-SAM2-TensorRT-stable"
export GI_RESEARCH_USE_ACK=research-evaluation-only

cd ~/Efficient-SAM3-TensorRT-wifi-camera
bash scripts/thor_select_camera_demo.sh wifi \
  default_mode:=2 \
  bundle_dir:="$HOME/thor-demo-baseline-20260730/bundles/sam2.1-tinyvit-5m/fp16_best_20260729" \
  display_max_width:=1600 \
  track_bucket_size:=1 \
  track_concurrency:=4 \
  pipeline_overlap:=false
```

The HUD reports `Source: Wi-Fi Camera`. Wi-Fi camera resolution and FPS are
controlled by the source, so the HUD omits the wired camera profile and the
`C` profile menu is disabled. The first switch recreates the GI
container and can take 70--120 seconds because both GI models are reloaded.

For the `IP Camera for iOS` HTTP source, select `1024x768` as the default
video resolution in the iOS app before starting the Thor pipeline. Its
`/video` endpoint does not accept width or height query parameters, and Thor
does not upscale a lower-resolution stream because that adds work without
recovering image detail.

The licensed GI image burns its own FPS text into Mode 1 overlays. Build the
local derived image once to remove only that duplicate text:

```bash
cd ~/Efficient-SAM3-TensorRT-wifi-camera
GI_RESEARCH_USE_ACK=research-evaluation-only \
  bash scripts/thor_build_gi_no_overlay_fps.sh
export GI_UNIFIED_IMAGE=instinctsam:thor-r39-unified-api-no-overlay-fps
```

The derived image remains local to Thor and is not pushed to GitHub or a
container registry. The unified ROS HUD continues to report Screen FPS and
model latency in both modes. It also disables the redundant Hugging Face
download used while constructing the Hiera trunk; the runtime immediately
loads the licensed local multiresolution checkpoint instead, so wired and
Wi-Fi startup do not depend on Thor DNS or Internet access.

## Return to the wired camera

```bash
export GI_UNIFIED_IMAGE=instinctsam:thor-r39-unified-api-baseline-20260730
export SAM2_ROOT="$HOME/Efficient-SAM2-TensorRT-stable"
export GI_RESEARCH_USE_ACK=research-evaluation-only

cd ~/Efficient-SAM3-TensorRT-wifi-camera
bash scripts/thor_select_camera_demo.sh wired \
  default_mode:=2 \
  bundle_dir:="$HOME/thor-demo-baseline-20260730/bundles/sam2.1-tinyvit-5m/fp16_best_20260729" \
  display_max_width:=1600 \
  track_bucket_size:=1 \
  track_concurrency:=4 \
  pipeline_overlap:=false
```

The HUD reports `Source: Wired RealSense`. The original exact-stable command
remains available independently:

```bash
GI_RESEARCH_USE_ACK=research-evaluation-only \
  bash ~/thor-demo-baseline-20260730/start-object-hud.sh
```

## Validation checklist

For each source:

1. Verify `status.json` advances its frame counter.
2. Verify the HUD source label and actual image.
3. In Mode 1, test text, point, and box prompts.
4. In Mode 2, use a text prompt for GI-to-SAM2 handoff, then move the camera
   and verify the synchronized mask has no previous-frame ghost.
5. Record camera FPS, Screen FPS, model latency, object count, and source age.

## 2026-08-06 initial probe

Thor could reach the internally configured camera host at layer 2, but the
configured RTSP port refused the TCP connection. The camera server must be
started before a real stream/prompt/FPS acceptance run can be recorded. The
private endpoint and credentials are intentionally not recorded here.
