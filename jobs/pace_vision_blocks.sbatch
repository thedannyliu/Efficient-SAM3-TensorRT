#!/usr/bin/env bash
#SBATCH --job-name=sam31-layer-fp8
#SBATCH --partition=gpu-h200
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --array=0-31%1
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

source_dir="${SOURCE_DIR:?set SOURCE_DIR to an FP16 vision_trunk result}"
block="${SLURM_ARRAY_TASK_ID}"
scope_regex="blocks\\.${block}\\."
run_dir="results/${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}/block_${block}_fp8"
quantized_onnx="${run_dir}/vision_trunk.fp8.onnx"
engine_path="${run_dir}/vision_trunk.fp8.engine"
mkdir -p "${run_dir}" logs

nvidia-smi
python scripts/quantize_vision_onnx.py \
  --onnx "${source_dir}/vision_trunk.onnx" \
  --output "${quantized_onnx}" \
  --report "${run_dir}/quantization.json" \
  --calibration-dir "${CALIBRATION_DIR:?set CALIBRATION_DIR}" \
  --calibration-samples "${CALIBRATION_SAMPLES:-16}" \
  --mode fp8 \
  --scope-regex "${scope_regex}"

python scripts/build_benchmark_engine.py \
  --onnx "${quantized_onnx}" \
  --engine "${engine_path}" \
  --reference "${source_dir}/reference.pt" \
  --report "${run_dir}/report.json"

if [[ "${KEEP_ARTIFACTS:-0}" != "1" ]]; then
  rm -- "${quantized_onnx}" "${engine_path}"
fi

