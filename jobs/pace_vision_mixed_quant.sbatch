#!/usr/bin/env bash
#SBATCH --job-name=sam31-mixed-8bit
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

source_dir="${SOURCE_DIR:?set SOURCE_DIR to the FP32 vision-trunk result}"
calibration_dir="${CALIBRATION_DIR:?set CALIBRATION_DIR}"
core_mode="${CORE_MODE:?set CORE_MODE to fp8 or int8}"
rest_mode="${REST_MODE:?set REST_MODE to fp8 or int8}"
run_dir="results/${SLURM_JOB_ID}/core_${core_mode}_rest_${rest_mode}"
stage_one="${run_dir}/vision_trunk.core_${core_mode}.onnx"
mixed_onnx="${run_dir}/vision_trunk.mixed.onnx"
mkdir -p "${run_dir}" logs

nvidia-smi
python scripts/quantize_vision_onnx.py \
  --onnx "${source_dir}/vision_trunk.onnx" \
  --output "${stage_one}" \
  --report "${run_dir}/core_quantization.json" \
  --calibration-dir "${calibration_dir}" \
  --calibration-samples "${CALIBRATION_SAMPLES:-16}" \
  --calibration-method max \
  --mode "${core_mode}" \
  --high-precision-dtype fp32 \
  --mha-accumulation-dtype fp32 \
  --scope-regex "scaled_dot_product_attention"

python scripts/quantize_vision_onnx.py \
  --onnx "${stage_one}" \
  --output "${mixed_onnx}" \
  --report "${run_dir}/rest_quantization.json" \
  --calibration-dir "${calibration_dir}" \
  --calibration-samples "${CALIBRATION_SAMPLES:-16}" \
  --calibration-method max \
  --mode "${rest_mode}" \
  --high-precision-dtype fp32 \
  --mha-accumulation-dtype fp32 \
  --scope-map-onnx "${source_dir}/vision_trunk.onnx" \
  --scope-regex "(attn\\.(qkv|proj)|\\.mlp)"

python scripts/build_benchmark_engine.py \
  --onnx "${mixed_onnx}" \
  --engine "${run_dir}/vision_trunk.mixed.engine" \
  --reference "${source_dir}/reference.pt" \
  --report "${run_dir}/report.json" \
  --builder-optimization-level "${BUILDER_OPTIMIZATION_LEVEL:-0}"
