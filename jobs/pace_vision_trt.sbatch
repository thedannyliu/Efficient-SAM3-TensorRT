#!/usr/bin/env bash
#SBATCH --job-name=sam31-vision-trt
#SBATCH --partition=gpu-h200
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

precision="${PRECISION:-fp16}"
run_dir="results/${SLURM_JOB_ID}/vision_trunk_${precision}"
mkdir -p "${run_dir}" logs

extra_args=()
if [[ "${FP32_LAYERNORM:-0}" == "1" ]]; then
  extra_args+=(--fp32-layernorm)
fi

nvidia-smi
python scripts/export_vision_trunk.py \
  --checkpoint "${CHECKPOINT:-checkpoints/sam3.1_multiplex.pt}" \
  --sam3-repo external/sam3 \
  --precision "${precision}" \
  --onnx "${run_dir}/vision_trunk.onnx" \
  --reference "${run_dir}/reference.pt" \
  "${extra_args[@]}"

python scripts/build_benchmark_engine.py \
  --onnx "${run_dir}/vision_trunk.onnx" \
  --engine "${run_dir}/vision_trunk.engine" \
  --reference "${run_dir}/reference.pt" \
  --report "${run_dir}/report.json"
