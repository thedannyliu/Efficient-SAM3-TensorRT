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
