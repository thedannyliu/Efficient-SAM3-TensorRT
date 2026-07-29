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
