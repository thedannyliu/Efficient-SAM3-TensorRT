# Thor baseline

Status: original-image and two-object headless hybrid baselines complete;
displayed and hybrid quality baselines remain pending.

No optimization result may be reported against this system until this document
contains a completed baseline row using the same fixed input and protocol.

## Protocol

- Thor power mode and clocks: record exact values; keep unchanged.
- Camera: record negotiated resolution, measured FPS, exposure, and USB speed.
- Warm-up: 100 completed output frames.
- Measurement: 1,000 completed output frames.
- Repetitions: 3.
- Report: median across repetitions plus within-run mean/p50/p90/p95/p99.
- FPS: completed outputs divided by elapsed source timestamp interval.
- Modes: model/component-only, headless ROS, and displayed end-to-end.
- Fixed inputs: record local path and SHA256; large video/rosbag files remain
  ignored.

## Environment

| Field | Value |
|---|---|
| Date | 2026-07-28 |
| Git commit | `92b2c7e8402cab1b5c7c1cdd60cd785e6c397855` |
| GI archive SHA256 | `30b40a025a76e8a8e911a3c57320637260e9fc78b54fcc4b90b73c7982bb7e75` |
| Original GI image ID | `sha256:8fd009341104f6944441d4e6fccbcd9af2598fa03812ee7ae64488ac28906ecd` |
| Thor/L4T | R38.4 compatibility smoke |
| JetPack | 7.1-b112 |
| CUDA | 13.0 |
| Host TensorRT | 10.13.3.9 |
| Power mode/clocks | 120 W mode; clocks not locked |
| Camera/profile/actual FPS | D455 `/dev/video4`, requested 1280x720@30; native idle observed 18.03–18.33 FPS (camera smoke, not the fixed-input rows below) |
| USB link | D455 negotiated 5000M |
| Fixed input | GI bundled `assets/videos/0001` |
| Fixed input aggregate SHA256 | `1ce47e344fc78d7ce4650cd2b819083628f3f0083f02ac7bb156ccecd63f506e` |

## Native InstinctSAM

Each value is the median of the three run-level values. Component timing is
reported as mean/p95 because the vendor status is an exponential moving average,
not an independent per-frame kernel trace.

| Display mode | Objects | Backend | Backbone mean/p95 ms | Tracker mean/p95 ms | Adapter mean/p95 ms | Output FPS | Drops | Notes |
|---|---:|---|---:|---:|---:|---:|---:|---|
| headless | 0 | per-object | 54.072/54.497 | 0.094/0.127 | 3.536/4.282 | 19.379 | 0 | fixed bundled input |
| headless | 1 | per-object | 53.827/54.138 | 48.478/48.734 | 3.630/4.424 | 10.829 | 0 | one accepted synthetic box |
| headless | 2 | multiplex | 43.649/43.919 | 55.894/56.582 | 3.691/4.413 | 10.942 | 0 | performance-only; both synthetic boxes became lost |
| displayed | 1 | n/a (point) | n/a | n/a | functional smoke | 37.12/39.64 | 13.923 | 47.50/50.56 |
| displayed | 2+ | pending | pending | pending | pending | pending | pending | pending |

The two-object row is not a quality result: both seeded objects were reported
lost. It only verifies the multiplex execution cost.

## Unified API compatibility smoke

The locally licensed derived image
`sha256:86cac7af8ebf22858ea3aaf7f02472e478b20a520e3d1ef5b4b1ec70fac668b3`
loaded the prebuilt FP16 engines on R38.4. These are smoke values, not formal
baseline rows:

- first `native` to `hybrid` request: 33.9 ms wall time;
- warmed `hybrid` to `native` request: 3.8 ms wall time;
- first camera-frame text detection: 965.2 ms model time due to one-time warm-up;
- subsequent camera-frame detections: 181.0–184.4 ms model time;
- bundled `dog_person.jpeg`: 207.0 ms for `dog` (one object, score 0.698)
  and 223.0 ms for `person` (two objects, best score 0.980);
- masks returned as compressed COCO RLE and decoded by the public handoff code.

## GI to SAM2 hybrid

| Display mode | Objects | GI detect ms | JPEG+HTTP ms | Mask-to-box ms | SAM2 init ms | SAM2 model p50/p95 ms | Output FPS | Source age p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| headless | 1 | pending | pending | pending | pending | pending | pending | pending |
| headless | 2 | 212.5 smoke | 13.2 encode; 265.8 total detect wall | 22.9 | 23.7 | 49.04/54.78 | 5.746 | 92.99/330.19 |
| headless | 4 | pending | pending | pending | pending | pending | pending | pending |
| headless | 8 | pending | pending | pending | pending | pending | pending | pending |
| displayed | 1 | pending | pending | pending | pending | pending | pending | pending |

## Quality handoff

| Workload | GI objects | SAM2 initialized | Mean/min first-frame mask IoU | Lost frames | Notes |
|---|---:|---:|---:|---:|---|
| fixed single-object | pending | pending | pending | pending | |
| fixed multi-object | pending | pending | pending | pending | |

## Mode switching

| Direction | Switch p50/p95 ms | First displayed frame ms | Previous state cleared | Notes |
|---|---:|---:|---|---|
| 1 → 2 | pending | pending | pending | |
| 2 → 1 | pending | pending | pending | |

## Runtime TinyViT selection

Measured on 2026-07-29 with SAM3 commit `706e524`, SAM2 commit `b8d78ef`,
1280x720@30 capture, one point-initialized object, the displayed viewer, 20
warm-up outputs, and 100 measured outputs per model. These are runtime
performance smokes, not cross-model quality measurements.

| Model | Reload ms | SAM2 process memory | Tracker mean/p95 ms | GPU mean ms |
|---|---:|---:|---:|---:|
| TV5M | 2,218–2,328 | 22,340–22,432 MiB | 35.530/38.873 | 35.238 |
| TV11M | 2,201–2,695 | 22,408 MiB | 37.170/40.181 | 36.857 |
| TV21M | 2,240–2,322 | 22,610 MiB | 46.122/48.850 | 45.855 |

Only one tracker is resident. The replacement is fully constructed before an
atomic swap, and the previous tracker remains active if engine loading fails.
Preloading three complete trackers was rejected: the single process already
uses about 22.3–22.6 GiB, while every tracker would duplicate the large common
prompt/track contexts for a UI action that currently takes only 2.2–2.7 s.

## Runtime camera profiles

Camera switching uses the vendor entrypoint and retains the TensorRT cache but
reloads the resident GI models. `Observed FPS` is the vendor capture-only loop,
not SAM2 output FPS.

| Requested profile | Returned dimensions | Observed FPS | Switch ms | Result |
|---|---:|---:|---:|---|
| 640x360@30 | 640x360 | 29.98–30.02 | 87,791 | accepted |
| 848x480@30 | 848x480 | about 30 | 87,730 | accepted |
| 848x480@60 | 848x480 | 60.305 | 88,771 | capture accepted; SAM2 preview short diagnostic fell to about 8.8 FPS |
| 1280x720@60 | 1280x720 | 28.87–30.02 | 87,686 | rejected from menu; D455 descriptor caps this resolution at 30 FPS |
| 1280x720@30 | 1280x720 | 28.60 initially, 29.95 steady | 92,833 | accepted and restored as default |

The D455 USB descriptor exposes 60 FPS intervals at 640x360 and 848x480, but
only 30 FPS at 1280x720. Higher capture FPS is not automatically higher
pipeline FPS: MJPEG encode/decode and memory-bandwidth work increased enough
that the 848x480@60 short SAM2 preview diagnostic was slower. Use
1280x720@30 as the current default until a fixed-input end-to-end profile
benchmark proves otherwise.

## Raw result locations

Raw result directories are intentionally ignored. Record experiment IDs and
paths here after the runs.

- `results/benchmarks/20260728_gi_bundled_idle_headless`
- `results/benchmarks/20260728_gi_bundled_1obj_headless`
- `results/benchmarks/20260728_gi_bundled_2obj_multiplex_headless`
- `results/benchmarks/20260728_gi_sam2_camera_2obj_headless`
- `results/benchmarks/20260728_gi_sam2_camera_2obj_direct_relay`
- `results/benchmarks/20260728_gi_sam2_camera_2obj_overlay_paused`
- `results/benchmarks/20260729_hybrid_1obj_display_resizable_v8`
- `results/benchmarks/20260729_mode_analysis`

The two-object hybrid baseline used the live D455, prompt `monitor`, confidence
0.1, TV5M FP16 bundle, 100 warm-up outputs, 1,000 measured outputs, and three
repetitions. Its three completed-output rates were 6.114, 5.746, and 5.362 FPS.
The table reports medians across repetitions. The handoff component values are
from the preceding functional smoke because handoff occurs before the tracking
trace begins.

The displayed single-object row used the live D455, a positive point on a
monitor, TV5M FP16, the resizable 2560x1440 initial viewer, 100 warm-up outputs,
1,000 measured outputs, and three repetitions at commit
`d0b6c033fe3a0b785baefc1a200953f729b57bde`. Completed-output rates were
13.923, 13.025, and 14.778 FPS. The table reports the median of each run-level
metric; all three runs reported zero dropped frames.
