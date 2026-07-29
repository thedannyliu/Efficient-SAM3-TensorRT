# Thor optimization log

Every row changes one primary variable and uses the same baseline input,
power/clocks, camera profile, warm-up, frame count, and repetitions. A candidate
is eligible only when mean mask quality retention is at least 95% and object
recall on the fixed workload is unchanged.

| ID | Commit | Pipeline | Change | Baseline latency/FPS | Candidate latency/FPS | Latency reduction | FPS gain | Source-age change | Quality retention | Decision |
|---|---|---|---|---|---|---:|---:|---:|---:|---|
| `gi-adapter-parallel-mjpeg-smoke` | `4bf136b` | GI native bridge | Replace sequential raw/overlay reads with two persistent latest-frame MJPEG readers | adapter poll 101.16 ms; raw 5.38 FPS | adapter poll 3.84 ms; raw 11.92 FPS; overlay 15.03 FPS | 96.2% | 121.8% | not measured | unchanged transport | accept; repeat in formal baseline |
