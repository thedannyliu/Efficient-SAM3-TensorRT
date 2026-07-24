# SAM 3.1 TensorRT on PACE

This repository measures and optimizes Meta's native SAM 3.1 Object Multiplex
pipeline before deployment to Jetson Thor. The acceptance threshold is a task
mIoU retention of at least 90% relative to the official BF16 PyTorch runtime.

Generated checkpoints, ONNX graphs, TensorRT engines, logs, and benchmark
results are intentionally ignored.

## Pinned inputs

- Meta SAM 3 source: commit `46957e47805eaa273f4aa7bbbd25a88bca9108ce`
- Checkpoint: `facebook/sam3.1/sam3.1_multiplex.pt`
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
