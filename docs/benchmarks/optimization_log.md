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
and tracking kernels contend for the same GPU. The unified launch keeps it
off by default.

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
