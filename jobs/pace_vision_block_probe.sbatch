#!/usr/bin/env bash
#SBATCH --job-name=sam31-block-probe
#SBATCH --partition=gpu-h200
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

blocks=(0 7 31)
block="${blocks[${SLURM_ARRAY_TASK_ID}]}"
run_dir="results/${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}/block_${block}"
mkdir -p "${run_dir}" logs

nvidia-smi
python scripts/export_vision_block.py \
  --checkpoint "${CHECKPOINT:-checkpoints/sam3.1_multiplex.pt}" \
  --sam3-repo external/sam3 \
  --image "${IMAGE:?set IMAGE to a representative frame}" \
  --block "${block}" \
  --onnx "${run_dir}/block.onnx" \
  --reference "${run_dir}/reference.pt"

python scripts/build_benchmark_engine.py \
  --onnx "${run_dir}/block.onnx" \
  --engine "${run_dir}/block.engine" \
  --reference "${run_dir}/reference.pt" \
  --report "${run_dir}/report.json"
