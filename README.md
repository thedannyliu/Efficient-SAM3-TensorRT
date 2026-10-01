# SAM3 TensorRT and Thor integration

Export and benchmark SAM 3.1 vision components, and integrate text/geometry
tracking into a Jetson Thor ROS 2 camera pipeline. The repository separates
precision experiments from the deployed viewer and detector-to-SAM2 handoff.

## Two workflows

| Workflow | Entry points |
| --- | --- |
| Native SAM 3.1 export and precision experiments | `scripts/export/`, `scripts/benchmark/`, `jobs/` |
| Thor camera, viewer and SAM2 handoff | `scripts/thor/`, `ros_ws/`, `src/sam31_trt/` |

The Thor integration uses a separately supplied General Instinct InstinctSAM
container. Its application, weights and engines are excluded; read
[THIRD_PARTY.md](THIRD_PARTY.md) before deployment.

## CPU development checks

Use Python 3.12+ with a compatible CPU PyTorch installation:

```bash
python -m pip install -e '.[test]'
python -m pytest tests
bash scripts/dev/run_pace_thor_pipeline_smoke.sh
```

The synthetic smoke checks detection-to-box handoff and metric reporting.
It does not start a container or validate ROS, camera, engines or model accuracy.

## Export and benchmark

The recorded native baseline uses SAM3 source commit
`46957e47805eaa273f4aa7bbbd25a88bca9108ce` and
`facebook/sam3.1/sam3.1_multiplex.pt`
(SHA256 `0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`).
Install that upstream source and the CUDA dependencies for your target runtime;
`requirements-pace.txt` describes the PACE experiment environment.

Start with the [script guide](scripts/README.md). Compare each precision candidate
with the matching BF16 baseline using absolute task mIoU, relative retention,
latency, effective FPS, GPU type and peak memory. The 90% mIoU-retention threshold
is an acceptance target, not a claim that every candidate has passed.

TensorRT plans must be rebuilt on the deployment GPU. Server-side engines and
timings do not establish Thor compatibility or performance.

## Deploy on Thor

Follow the [deployment guide](docs/thor_deployment.md) and
[runtime architecture](docs/architecture.md). Mode 1 tracks in the InstinctSAM
container; Mode 2 uses its initial text detections to initialize the companion
[SAM2 TensorRT tracker](https://github.com/thedannyliu/Efficient-SAM2-TensorRT).
The unified viewer switches modes with `1` and `2`.

Record a [Thor baseline](docs/benchmarks/thor_baseline.md) before claiming a
performance improvement. Keep generated checkpoints, ONNX files, plans, raw
traces and logs in ignored artifact directories.
