#!/usr/bin/env bash
#SBATCH --job-name=sam31-rebuild-trt
#SBATCH --partition=gpu-h200
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

level="${BUILDER_LEVEL:?set BUILDER_LEVEL from 0 through 5}"
if [[ -n "${ONNX_PATH:-}" && -n "${REFERENCE_PATH:-}" ]]; then
  onnx_path="${ONNX_PATH}"
  reference_path="${REFERENCE_PATH}"
else
  source_dir="${SOURCE_DIR:?set SOURCE_DIR or ONNX_PATH and REFERENCE_PATH}"
  onnx_path="${source_dir}/vision_trunk.onnx"
  reference_path="${source_dir}/reference.pt"
fi
run_dir="results/${SLURM_JOB_ID}/${LABEL:-vision}_o${level}"
mkdir -p "${run_dir}" logs

extra_args=()
if [[ -n "${MAX_AUX_STREAMS:-}" ]]; then
  extra_args+=(--max-aux-streams "${MAX_AUX_STREAMS}")
fi

nvidia-smi
python scripts/build_benchmark_engine.py \
  --onnx "${onnx_path}" \
  --engine "${run_dir}/vision_trunk.engine" \
  --reference "${reference_path}" \
  --report "${run_dir}/report.json" \
  --builder-optimization-level "${level}" \
  "${extra_args[@]}"
