#!/usr/bin/env bash
#SBATCH --job-name=sam31-vision-quant
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

mode="${MODE:?set MODE to fp8 or int8}"
source_dir="${SOURCE_DIR:?set SOURCE_DIR to an FP16 vision_trunk result}"
run_dir="results/${SLURM_JOB_ID}/vision_trunk_${mode}"
mkdir -p "${run_dir}" logs

scope_args=()
if [[ -n "${SCOPE_REGEX:-}" ]]; then
  scope_args+=(--scope-regex "${SCOPE_REGEX}")
fi

nvidia-smi
python scripts/quantize_vision_onnx.py \
  --onnx "${source_dir}/vision_trunk.onnx" \
  --output "${run_dir}/vision_trunk.${mode}.onnx" \
  --report "${run_dir}/quantization.json" \
  --calibration-dir "${CALIBRATION_DIR:?set CALIBRATION_DIR}" \
  --calibration-samples "${CALIBRATION_SAMPLES:-16}" \
  --mode "${mode}" \
  "${scope_args[@]}"

python scripts/build_benchmark_engine.py \
  --onnx "${run_dir}/vision_trunk.${mode}.onnx" \
  --engine "${run_dir}/vision_trunk.${mode}.engine" \
  --reference "${source_dir}/reference.pt" \
  --report "${run_dir}/report.json"

