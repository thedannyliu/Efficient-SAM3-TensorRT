# Thor optimization log

Every row changes one primary variable and uses the same baseline input,
power/clocks, camera profile, warm-up, frame count, and repetitions. A candidate
is eligible only when mean mask quality retention is at least 95% and object
recall on the fixed workload is unchanged.

| ID | Commit | Pipeline | Change | Baseline latency/FPS | Candidate latency/FPS | Latency reduction | FPS gain | Source-age change | Quality retention | Decision |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| `gi-adapter-parallel-mjpeg-smoke` | `4bf136b` | GI native bridge | Replace sequential raw/overlay reads with two persistent latest-frame MJPEG readers | adapter poll 101.16 ms; raw 5.38 FPS | adapter poll 3.84 ms; raw 11.92 FPS; overlay 15.03 FPS | 96.2% | 121.8% | not measured | unchanged transport | accept; repeat in formal baseline |
| `hybrid-direct-gated-relay` | `f2a5037` | GI → TV5M SAM2, 2 objects | Adapter publishes the gated SAM2 input directly; coordinator obtains the frozen frame from the GI JPEG snapshot and no longer receives/re-publishes every 2.7 MB ROS Image | model mean/p95 49.04/54.78 ms; 5.746 FPS | model mean/p95 48.29/49.41 ms; 12.759 FPS | 1.5% mean | 122.0% | p95 330.19 → 95.80 ms (-71.0%) | model and boxes unchanged | accept |
| `hybrid-pause-unused-overlay` | `cb7021b` | GI → TV5M SAM2, 2 objects | Stop the GI overlay MJPEG decoder while mode 2 is active; reconnect it when returning to mode 1 | model mean/p95 48.29/49.41 ms; 12.759 FPS | model mean/p95 46.99/48.14 ms; 13.865 FPS | 2.7% mean | 8.7% | p95 95.80 → 92.75 ms (-3.2%) | model and boxes unchanged | accept |
| `hybrid-shared-frame` | `12dc408` / SAM2 `6f1c15c` | GI → TV5M SAM2, no objects, headless | Replace the 2.76 MB cross-process ROS Image with a locked latest-frame file under `/dev/shm`; retain ROS for frozen prompt initialization | 15.506 FPS; source age 21.96 ms | 29.210 FPS; source age 19.44 ms | callback 19.50 → 17.14 ms (-12.1%) | 88.4% | -11.5% mean | exact same uint8 BGR pixels | accept |
| `viewer-one-render-per-preview` | `fb19430` | GI → TV5M SAM2, 1 object, displayed | Do not call `imshow` for result JSON and again for the corresponding preview; draw newest metrics on the next preview | 23.031 FPS; inference 36.50 ms | 23.991 FPS; inference 33.12 ms | 9.3% inference | 4.2% | 62.59 → 59.53 ms (-4.9%) | rendering only | accept |
| `shared-rgb-input` | `8d85337` / SAM2 `87a4350` | GI → TV5M SAM2, 1 object, displayed | Use OpenCV's SIMD BGR-to-RGB conversion before the shared write and remove the C++ per-pixel channel loop | 23.991 FPS; source age 59.53 ms | 27.218 FPS; source age 48.30 ms | callback 57.22 → 45.36 ms (-20.7%) | 13.5% | -18.9% mean | exact channel permutation | accept |
| `opengl-scaled-viewer` | `1cc8594` | GI → TV5M SAM2, 1 object, displayed | Use the available Qt5 OpenGL HighGUI path to scale the 640x360 preview into the 2560x1440 interactive window | 27.218 FPS; inference 34.11 ms | 29.296 FPS; inference 29.46 ms | 13.6% inference | 7.6% | 48.30 → 39.18 ms (-18.9%) | rendering only | accept |
| `shared-track-engine-contexts` | SAM2 `377dfb0` | GI → TV5M SAM2, 1 object, displayed | Deserialize one track engine and create eight independent execution contexts instead of eight engine copies | inference 29.462 ms; TV11 load 3523.9 ms | inference 29.443 ms; TV11 load 3246.9 ms | neutral inference; 7.9% load | not claimed | 39.18 → 37.11 ms; camera variance | same engine and per-object state | accept for initialization/resource use |
| `shared-poll-1000hz` | `6a97a2c` / `a60e1cf` | GI → TV5M SAM2, 1 object, 848x480@60 displayed | Increase latest-frame header polling from 240 to 1000 Hz | source age 41.87 ms; inference 28.96 ms | source age 41.69 ms; inference 29.80 ms | not repeatable | not claimed | -0.19 ms (-0.4%) | same shared pixels | reject; retain configurable 240 Hz default |
| `cross-frame-overlap` | `65dc282` | GI → TV5M SAM2, 1 object, 848x480@60 displayed | Encode the current frame while completing tracking for the preceding frame | inference 29.219 ms; 33.766 FPS | inference 26.225 ms; 37.641 FPS | 10.2% | 11.5% | 42.07 → 65.25 ms (+55.1%) | same operations and FP16 engines | optional throughput mode; keep low-latency default off |
| `four-track-stream-limit` | `fab0c9e` | GI → TV5M SAM2, 8 objects, 848x480@60 displayed | Process at most four object contexts concurrently instead of eight | inference 166.75 ms; 5.993 FPS | inference 162.78 ms; 6.136 FPS | 2.4% | 2.4% | 181.58 → 176.86 ms (-2.6%) | same operations and FP16 engines | accept; unified default is 4 |
| `native-pause-raw-mjpeg` | `da4fcb7` | GI native, 1 object | Decode only the displayed overlay MJPEG in mode 1 instead of decoding raw and overlay | 111.65 ms; 9.135 vendor FPS | 111.39 ms; 9.166 vendor FPS | 0.2% | 0.35% | not available from vendor API | displayed overlay unchanged | no material FPS gain; keep opt-in |
| `current-bucket2` | `da4fcb7` / SAM2 `a77543a` | GI → TV5M SAM2, 4 objects | Replace four parallel batch-1 contexts with capacity-2 track buckets | 88.97 ms; 11.208 FPS | 185.69 ms; 5.380 FPS | -108.7% | -52.0% | 103.68 → 199.49 ms | same FP16 engines and object states | reject |
| `current-bucket4` | `da4fcb7` / SAM2 `a77543a` | GI → TV5M SAM2, 4 objects | Replace four parallel batch-1 contexts with one capacity-4 track bucket | 88.97 ms; 11.208 FPS | 170.62 ms; 5.852 FPS | -91.8% | -47.8% | 103.68 → 184.95 ms | same FP16 engines and object states | reject |
| `current-concurrency3` | `da4fcb7` / SAM2 `a77543a` | GI → TV5M SAM2, 4 fixed boxes | Process three object contexts concurrently instead of four | 88.88 ms; 11.208 FPS | 92.72 ms; 10.761 FPS | -4.3% | -4.0% | 103.14 → 107.69 ms | same FP16 engines and fixed prompts | reject; retain 4 |
| `balanced-window-1600` | `0fe4c4f` | unified displayed UI | Open at 1600x900 instead of 2560x1440 | mode 2: 34.16 ms, 29.053 FPS; mode 1 render 6.49 FPS | mode 2: 32.49 ms, 30.460 FPS; mode 1 render 7.56 FPS | 4.9% mode-2 inference | 4.8% tracking; 16.6% mode-1 render | 48.09 → 46.49 ms | display size only; masks unchanged | accept as balanced default |

The final two-object candidate is 2.413x the original ROS relay throughput
(+141.3%), reduces source-age p95 by 71.9%, and reduces latest-slot overwrites
from a median 229 to 7 per 1,000 completed frames. Its three rates were 13.865,
11.781, and 13.894 FPS; report the median, not the best run.

## Display rendering smoke

The first fixed-3x viewer redrew the same 3840x2160 image in an unthrottled
loop. It used about 245% CPU and the live relay measured about 10.5 FPS. Redraw
on frame/status changes reduced viewer CPU to about 60%; disabling the viewer
entirely measured about 17.5 FPS in a short topic-rate smoke.

The final viewer renders at the 1280x720 source resolution and lets the
resizable GUI scale image, text, and overlays together. Its formal displayed
single-object median was 13.923 FPS with inference mean/p95 36.53/39.64 ms,
source-age p50/p95 47.50/50.56 ms, and zero drops across all three 1,000-frame
runs. The earlier 10.5 FPS figure was a short diagnostic, so it is not entered
as a formal A/B row in the table above.

## Shared-memory/RGB final single-object matrix

The final displayed runs used the same Thor, General Instinct capture-only
mode, RealSense 1280x720@30, center positive point, 100 warm-up frames, and 500
measured frames. All three use the selected `fp16_aux0` bundles. Raw traces
remain ignored on Thor under
`results/benchmarks/shared_transport_12dc408/`.

| Model | Completed FPS | Mean inference | Mean callback | Mean source age | Dropped latest frames |
|---|---:|---:|---:|---:|---:|
| TV5M | 27.218 | 34.112 ms | 45.356 ms | 48.303 ms | 25 |
| TV11M | 27.046 | 35.737 ms | 51.072 ms | 54.154 ms | 49 |
| TV21M | 24.908 | 39.050 ms | 55.200 ms | 58.135 ms | 90 |

TV5M's historical pre-shared-memory displayed result was 13.923 FPS. The final
27.218 FPS is 1.955x that rate, although the historical and final runs did not
freeze the physical camera scene and therefore are not a mask-quality A/B.
The transport changes do not alter model weights, TensorRT precision, or
pixels supplied to the tracker.

The adapter now records `raw_reader_fps`, `image_publish_fps`,
`image_copy_ms`, `image_publish_ms`, and `image_transport`. A final steady
sample reported 30.03 FPS vendor capture, 30.03 FPS MJPEG decode, 30.86 shared
writes, 0.67 ms OpenCV BGR-to-RGB, and 2.80 ms locked shared-buffer write.

## OpenGL viewer matrix

The general HighGUI window used about 78% of one CPU core while scaling the
640x360 SAM2 preview to the initial 2560x1440 window. Thor's OpenCV build
reports Qt5 OpenGL support, so commit `1cc8594` adds `WINDOW_OPENGL` without
changing the preview, model, mask, prompt, or window dimensions. Viewer CPU
fell to 3--4%.

The following 500-frame runs use the same 1280x720@30 camera profile, one
center point, FP16 bundles, 100 warm-up outputs, and the displayed viewer.
Traces remain ignored on Thor under
`results/benchmarks/opengl_viewer_1cc8594/`.

| Model | Completed FPS | Mean inference | Mean source age | Drops | Inference change | Source-age change |
|---|---:|---:|---:|---:|---:|---:|
| TV5M | 29.296 | 29.462 ms | 39.184 ms | 0 | -13.6% | -18.9% |
| TV11M | 29.910 | 30.744 ms | 41.870 ms | 0 | -14.0% | -22.7% |
| TV21M | 27.877 | 34.723 ms | 52.477 ms | 36 | -11.1% | -9.7% |

The comparison baseline is the preceding shared-memory/RGB matrix. The
TV11M completed rate being slightly higher than TV5M is within camera timing
variance; the model-path ordering remains TV5M, TV11M, then TV21M.

## 60 FPS camera capacity

The RealSense does not expose 1280x720@60, so the capacity run used its
supported 848x480@60 color profile. The licensed vendor runtime reported a
stable 59.74 FPS capture after its 93.7 s full restart. This profile measures
processing capacity; it is not an image-quality comparison with the
1280x720@30 deployment default.

| Model | Objects | Completed FPS | Mean inference | Mean source age | Latest-slot drops |
|---|---:|---:|---:|---:|---:|
| TV5M | 1 | 33.267 | 29.797 ms | 41.686 ms | 244 |
| TV11M | 1 | 32.650 | 30.427 ms | 42.387 ms | 259 |
| TV21M | 1 | 28.872 | 34.445 ms | 46.501 ms | 356 |
| TV5M | 2 | 22.397 | 44.541 ms | 57.422 ms | 356 |
| TV5M | 4 | 11.949 | 83.565 ms | 96.054 ms | 871 |

The single-object rows use 100 warm-up and 500 measured outputs. The two- and
four-object rows use 50 warm-up and 300 requested outputs; the four-object
SSH collector retained 280 rows, which is sufficient for the capacity smoke
but should be repeated for a formal three-run median. The model continues to
process latest-only input, so drops are expected whenever capacity is below
59.74 FPS and do not indicate an accumulating queue.

## Background concurrency sweeps

The current unified pipeline already overlaps work that does not change frame
semantics:

- the vendor camera reader and shared-memory writer run independently of SAM2;
- image encoding uses the main CUDA stream while per-object state packing uses
  object streams and waits on a CUDA event only where required;
- independent object tracks use separate TensorRT execution contexts and CUDA
  streams;
- mask device-to-host copies use the corresponding object streams;
- preview construction runs on a C++ worker thread; the OpenGL viewer runs in
  its own process.

Commit `65dc282` exposes the additional double-buffered cross-frame path as
`pipeline_overlap:=true`. The following same-session A/B uses TV5M FP16,
848x480@60 capture, the displayed OpenGL viewer, 100 warm-up outputs, and
400 measured outputs for one and two objects. Four objects use 100 warm-up and
300 measured outputs. Raw traces remain ignored on Thor under
`results/benchmarks/camera60_{sync,overlap}_65dc282/`.

| Objects | Sync inference / FPS / source age | Overlap inference / FPS / source age | FPS change | Source-age change |
|---:|---|---|---:|---:|
| 1 | 29.219 ms / 33.766 / 42.072 ms | 26.225 ms / 37.641 / 65.250 ms | +11.5% | +23.178 ms |
| 2 | 46.667 ms / 21.356 / 61.250 ms | 45.429 ms / 21.923 / 105.665 ms | +2.7% | +44.415 ms |
| 4 | 83.527 ms / 11.952 / 98.314 ms | 85.667 ms / 11.657 / 185.864 ms | -2.5% | +87.550 ms |

Overlap is therefore useful only when single-object completed throughput is
more important than interactive latency. Its fixed one-processed-frame delay
becomes increasingly expensive as object count grows, and concurrent encoder
and tracking kernels contend for the same GPU. Commit `f19ab9e` routes this
automatically: overlap is active for one tracked object and the synchronous
path is restored for two or more. A route transition discards only the pending
encoded frame; object memories and IDs remain intact. Later moving-camera
validation found that the one-frame delay was visible as mask lag, so the
unified launch now defaults to `pipeline_overlap:=false`. Enable the router
only for throughput-first runs.

Commit `fab0c9e` also exposes `track_concurrency`. A four-object sweep used the
synchronous path with otherwise identical settings:

| Track concurrency | Completed FPS | Mean inference | Mean source age |
|---:|---:|---:|---:|
| 1 | 10.287 | 97.004 ms | 111.027 ms |
| 2 | 11.493 | 86.835 ms | 101.008 ms |
| 4 | 11.952 | 83.504 ms | 98.201 ms |
| 8 | 11.952 | 83.527 ms | 98.314 ms |

Four concurrent contexts saturate the useful four-object parallelism. For
eight objects, three repetitions of 150 measured outputs found concurrency 4
at 6.136 FPS and 162.78 ms mean inference, versus 5.993 FPS and 166.75 ms for
concurrency 8. Processing two groups of four avoids enough GPU contention to
improve both throughput and source age without changing masks. The unified
launch therefore defaults to `track_concurrency:=4`; the standalone SAM2
launches retain their separately documented defaults.

## Smooth rendered-camera and object-count routing

The original mode-2 window was paced by processed SAM2 previews. Camera motion
therefore looked slower whenever the tracker was busy even though the vendor
capture remained near 60 FPS. Commits `98fdc61` through `7be68ff` instead read
the latest raw frame from shared memory, composite the newest low-resolution
label image, and publish `/sam3_viewer/render_metrics`. The camera and mask now
have independent cadences.

Two correctness/performance bugs were found during the displayed test:

- mask and color arrays were updated separately across the ROS and display
  threads, which could produce a shape mismatch and terminate the viewer;
  `be91a25` replaces the pair atomically;
- NumPy per-pixel alpha blending cost about 9.1 ms per displayed frame;
  OpenCV vectorized blending plus an 848x480 render canvas reduced the latest
  one-object composite sample to 5.2 ms. The resizable window still opens at
  2560x1440 and prompt coordinates are mapped from the render canvas to the
  camera source.

Thor's current desktop session throttled the OpenGL HighGUI path to about
0.94 FPS, so these measurements use the software HighGUI path. NVIDIA
`nvjpegdec` was also tested. It decoded an isolated MJPEG stream faster, but
the integrated adapter remained at about 48 FPS and rendered at 57.91 FPS,
versus about 50 FPS adapter input and 59.77 FPS render with OpenCV/FFmpeg.
The launch therefore defaults to FFmpeg and retains GStreamer as an opt-in
experiment.

Rendering at a fixed 60 FPS while TensorRT saturated the GPU caused irregular
paint waits and also reduced tracking throughput. The final display router
keeps 60 FPS while idle and chooses
`max(5, min(28, 36 / object_count))` FPS while tracking. The TensorRT router
uses overlap for one object and synchronous tracking for two or more. The
following live-camera results use TV5M FP16, 848x480@60, software display, and
four tracking contexts:

| Objects | TensorRT route | Model latency | Tracking FPS | Display target / measured | Display interval std | Source age |
|---:|---|---:|---:|---:|---:|---:|
| 0 | idle | -- | -- | 60 / 59.23 FPS | 0.78 ms | -- |
| 1 | overlap | 30.57 ms | 32.43 | 28 / 28.00 FPS | 3.16 ms | 75.51 ms |
| 2 | synchronous | 52.07 ms | 19.13 | 18 / 18.00 FPS | 1.60 ms | 67.10 ms |
| 4 | synchronous | 87.96 ms | 11.26 | 9 / 9.00 FPS | 2.35 ms | 102.33 ms |

The one-to-two-object transition preserved object `1` and produced IDs
`[1, 2]` while `pipeline_overlap` changed from `true` to `false`. At two
objects, routing the display to 18 FPS instead of attempting 30 FPS improved
tracking from 17.87 to 19.13 FPS (+7.0%), reduced tracker latency from 55.73
to 52.07 ms (-6.6%), and reduced display interval standard deviation from
5.99 to 1.60 ms. This changes only presentation cadence and frame scheduling;
model weights, FP16 precision, masks, and object state are unchanged.

## 2026-07-29 current mode 1/mode 2 sweep

These live-camera runs use the refreshed TV5M bundle, SAM3 commit `da4fcb7`,
SAM2 commit `a77543a`, 848x480@60 capture, 120 W mode, synchronous masks,
software HighGUI, bucket 1, and four track contexts. Raw traces are ignored on
Thor under `results/benchmarks/20260729_mode_analysis/`.

Mode 1 used three repetitions of 10 warm-up plus 50 measured status rows:

| Prompt | Objects/backend | Vendor FPS | Model time | Adapter poll |
|---|---|---:|---:|---:|
| `bag` | 1 / per-object | 9.135 | 111.65 ms | 2.51 ms |
| `chair` | 4 / multiplex | 9.275 | 118.87 ms | 2.62 ms |
| `bag`, raw MJPEG paused | 1 / per-object | 9.166 | 111.39 ms | 2.46 ms |

The small one-versus-four FPS inversion is within run variance and vendor EMA
behavior. Multiplex keeps multi-object throughput nearly flat, while model
time still increases by 6.5%. Pausing the unused native raw decoder saved
about 0.05 ms in the Python adapter but did not move vendor or displayed FPS,
so `native_raw_stream` remains an experiment rather than the default.

Mode 2's four-object bucket/concurrency sweep used 30 warm-up plus 100
measured outputs:

| Route | Inference | Tracking FPS | Source age |
|---|---:|---:|---:|
| bucket 1, concurrency 4 | 88.97 ms | 11.208 | 103.68 ms |
| bucket 2 | 185.69 ms | 5.380 | 199.49 ms |
| bucket 4 | 170.62 ms | 5.852 | 184.95 ms |
| bucket 1, concurrency 3, fixed boxes | 92.72 ms | 10.761 | 107.69 ms |
| bucket 1, concurrency 4, fixed boxes | 88.88 ms | 11.208 | 103.14 ms |

The track tail is the multi-object bottleneck. At four objects it consumed
81.65 ms of the 88.97 ms inference time, while the encoder used 7.22 ms.
Capacity-2/4 engines are therefore rejected on Thor; four parallel batch-1
contexts remain fastest.

A preview/render decomposition found 11.83 FPS with no preview subscriber,
11.81 FPS with a preview subscriber but no GUI, and 11.21 FPS with the
displayed viewer. Preview composition already runs on a replace-latest worker
and is not the bottleneck. Desktop display accounts for roughly 5–6% at four
objects.

The single-object overlap A/B used the same center point, three repetitions,
50 warm-up outputs, and 200 measured outputs:

| Route | Inference | Tracking FPS | Source age |
|---|---:|---:|---:|
| synchronous | 34.16 ms | 29.053 | 48.09 ms |
| cross-frame overlap | 29.87 ms | 32.980 | 73.07 ms |

Overlap gains 13.5% throughput but adds 52.0% source age and one processed
frame of delay. It remains opt-in because the interactive camera should
prioritize mask freshness.

Finally, software HighGUI window scaling was profiled without changing the
848x480 render canvas:

| Initial window | Mode 1 render FPS | Mode 2 tracking FPS | Mode 2 inference |
|---|---:|---:|---:|
| 1280x720 | 8.51 | 31.420 | 31.43 ms |
| 1600x900 | 7.56 | 30.460 | 32.49 ms |
| 1920x1080 | 7.01 | not repeated | not repeated |
| 2560x1440 | 6.49 | 29.053 | 34.16 ms |

1280x720 is the fastest preset. Commit `0fe4c4f` selects 1600x900 as the
balanced default: compared with 2560x1440 it improves mode-1 visible cadence
by 16.6% and mode-2 tracking by 4.8%, while preserving a larger interaction
window. `[` and `]` still change presets immediately.

## Runtime selector smoke

Commit `706e524` adds UI menus for TV5M/11M/21M and camera profiles. Model
reloads took 2.2–2.7 s while keeping one tracker resident. One-object
tracker mean/p95 was 35.530/38.873 ms for TV5M, 37.170/40.181 ms for TV11M,
and 46.122/48.850 ms for TV21M. This speed smoke does not replace the
cross-model accuracy gate.

Camera profile changes took 87.7–92.8 s because the licensed vendor runtime
does not expose camera-only reconfiguration and its complete SAM3/SAM3.1
runtime must reload. 848x480@60 reached 60.305 capture FPS but reduced the
short SAM2 preview diagnostic to about 8.8 FPS, so 1280x720@30 remains the
default. See `thor_baseline.md` for the complete requested-versus-observed
table.
