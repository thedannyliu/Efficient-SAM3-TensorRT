# Thor baseline

Status: pending General Instinct image transfer and R38 compatibility smoke.

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
| Date | pending |
| Git commit | pending |
| GI archive SHA256 | `30b40a025a76e8a8e911a3c57320637260e9fc78b54fcc4b90b73c7982bb7e75` |
| GI image ID | pending |
| Thor/L4T | R38.4 compatibility smoke |
| JetPack | 7.1-b112 |
| CUDA | 13.0 |
| Host TensorRT | 10.13.3.9 |
| Power mode/clocks | pending |
| Camera/profile/actual FPS | pending |
| USB link | D455, 5000M observed before baseline |
| Fixed input SHA256 | pending |

## Native InstinctSAM

| Display mode | Objects | Backend | Model p50/p95 ms | Pipeline p50/p95 ms | Output FPS | Source age p50/p95 ms | Drops | Peak memory |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| headless | 1 | pending | pending | pending | pending | pending | pending | pending |
| headless | 2+ | pending | pending | pending | pending | pending | pending | pending |
| displayed | 1 | pending | pending | pending | pending | pending | pending | pending |
| displayed | 2+ | pending | pending | pending | pending | pending | pending | pending |

## GI to SAM2 hybrid

| Display mode | Objects | GI detect ms | JPEG+HTTP ms | Mask-to-box ms | SAM2 init ms | SAM2 model p50/p95 ms | Output FPS | Source age p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| headless | 1 | pending | pending | pending | pending | pending | pending | pending |
| headless | 2 | pending | pending | pending | pending | pending | pending | pending |
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

## Raw result locations

Raw result directories are intentionally ignored. Record experiment IDs and
paths here after the runs.
