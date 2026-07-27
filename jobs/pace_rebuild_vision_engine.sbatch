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

source_dir="${SOURCE_DIR:?set SOURCE_DIR to an FP16 vision-trunk result}"
level="${BUILDER_LEVEL:?set BUILDER_LEVEL from 0 through 5}"
aux_streams="${MAX_AUX_STREAMS:?set MAX_AUX_STREAMS}"
run_dir="results/${SLURM_JOB_ID}/vision_fp16_o${level}_aux${aux_streams}"
mkdir -p "${run_dir}" logs

nvidia-smi
python scripts/build_benchmark_engine.py \
  --onnx "${source_dir}/vision_trunk.onnx" \
  --engine "${run_dir}/vision_trunk.engine" \
  --reference "${source_dir}/reference.pt" \
  --report "${run_dir}/report.json" \
  --builder-optimization-level "${level}" \
  --max-aux-streams "${aux_streams}"
