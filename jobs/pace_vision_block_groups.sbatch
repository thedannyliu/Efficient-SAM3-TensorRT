#!/usr/bin/env bash
#SBATCH --job-name=sam31-block-fp8
#SBATCH --partition=gpu-h200
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --array=0-3%4
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

source_dir="${SOURCE_DIR:?set SOURCE_DIR to a vision_trunk export result}"
group="${SLURM_ARRAY_TASK_ID}"
start=$((group * 8))
end=$((start + 7))
alternatives="$(seq -s '|' "${start}" "${end}")"
component="${COMPONENT_SCOPE:-}"
scope_regex="blocks\\.(${alternatives})\\.${component}"
component_suffix="${component:+_${component}}"
run_dir="results/${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}/blocks_${start}_${end}${component_suffix}_fp8"
mkdir -p "${run_dir}" logs

quantization_args=()
if [[ "${DISABLE_MHA_QDQ:-0}" == "1" ]]; then
  quantization_args+=(--disable-mha-qdq)
fi

nvidia-smi
python scripts/quantize_vision_onnx.py \
  --onnx "${source_dir}/vision_trunk.onnx" \
  --output "${run_dir}/vision_trunk.fp8.onnx" \
  --report "${run_dir}/quantization.json" \
  --calibration-dir "${CALIBRATION_DIR:?set CALIBRATION_DIR}" \
  --calibration-samples "${CALIBRATION_SAMPLES:-16}" \
  --calibration-method "${CALIBRATION_METHOD:-max}" \
  --mode fp8 \
  --high-precision-dtype "${HIGH_PRECISION_DTYPE:-fp32}" \
  --mha-accumulation-dtype "${MHA_ACCUMULATION_DTYPE:-fp32}" \
  --scope-regex "${scope_regex}" \
  "${quantization_args[@]}"

python scripts/build_benchmark_engine.py \
  --onnx "${run_dir}/vision_trunk.fp8.onnx" \
  --engine "${run_dir}/vision_trunk.fp8.engine" \
  --reference "${source_dir}/reference.pt" \
  --report "${run_dir}/report.json" \
  --builder-optimization-level "${BUILDER_OPTIMIZATION_LEVEL:-5}"
