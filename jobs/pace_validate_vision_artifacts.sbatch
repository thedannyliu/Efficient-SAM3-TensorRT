#!/usr/bin/env bash
#SBATCH --job-name=sam31-artifact-check
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

source_dir="${SOURCE_DIR:?set SOURCE_DIR to a vision-trunk result directory}"
mkdir -p logs

nvidia-smi
python scripts/validate_vision_artifacts.py \
  --onnx "${source_dir}/vision_trunk.onnx" \
  --engine "${source_dir}/vision_trunk.engine" \
  --reference "${source_dir}/reference.pt" \
  --report "${source_dir}/artifact_validation.json"
