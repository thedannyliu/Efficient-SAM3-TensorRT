# Efficient SAM3 TensorRT

This repository measures and optimizes Meta's native SAM 3.1 Object Multiplex
pipeline before deployment to Jetson Thor. The acceptance threshold is a task
mIoU retention of at least 90% relative to the official BF16 PyTorch runtime.

Generated checkpoints, ONNX graphs, TensorRT engines, logs, and benchmark
results are intentionally ignored.

## Pinned inputs

- Meta SAM 3 source: commit `46957e47805eaa273f4aa7bbbd25a88bca9108ce`
- Checkpoint: `facebook/sam3.1/sam3.1_multiplex.pt`
  (`sha256:0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`)
- First accuracy smoke: the fixed SA-V point-prompt subset owned by
  `efficientsam3-benchmark`
- PACE QOS: `embers`

## Setup

```bash
module load python/3.12.5 cuda/12.6.1
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install torch==2.10.0 torchvision \
  --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e external/sam3 -e .
python -m pip install -r requirements-pace.txt
```

## Baseline submission

```bash
MANIFEST=/storage/project/r-agarg35-0/eliu354/projects/efficientsam3-benchmark/data/manifests/sav_val_fixed3.jsonl \
DATA_ROOT=/storage/project/r-agarg35-0/eliu354/projects/efficientsam3-benchmark \
sbatch jobs/pace_baseline.sbatch
```

Every precision candidate must report absolute task mIoU, relative mIoU
retention, model latency, effective FPS, GPU type, and peak CUDA memory.

TensorRT engines must be rebuilt on the deployment GPU. PACE engines are
benchmark artifacts and must not be copied to Jetson Thor.

## Jetson Thor pipelines

The repository also provides two ROS 2 integrations:

- General Instinct InstinctSAM native text/geometry tracking.
- First-frame InstinctSAM text detection followed by optimized TV5M FP16 SAM2
  TensorRT tracking.

The unified Thor viewer switches between them with `1` and `2`; the camera and
models remain resident so switching does not require reloading an engine.

General Instinct's container, weights, engines, and application are licensed
and supplied separately. They are intentionally excluded from this repository.
Read [THIRD_PARTY.md](THIRD_PARTY.md) and
[docs/thor_deployment.md](docs/thor_deployment.md) before deployment.

Thor performance claims require a completed
[baseline record](docs/benchmarks/thor_baseline.md). Raw traces stay under the
ignored `results/` directory, while lightweight summaries and each optimization
delta are committed.
