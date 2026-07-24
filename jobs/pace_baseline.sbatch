#!/usr/bin/env bash
#SBATCH --job-name=sam31-baseline
#SBATCH --partition=gpu-h100
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate

export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

precision="${PRECISION:-fp32}"
output="results/${SLURM_JOB_ID}/native_${precision}.json"
mkdir -p "$(dirname "${output}")" logs

extra_args=()
if [[ "${COMPILE:-0}" == "1" ]]; then
  extra_args+=(--compile)
fi
if [[ "${USE_FA3:-0}" == "1" ]]; then
  extra_args+=(--use-fa3)
fi

nvidia-smi
python scripts/native_vos_baseline.py \
  --manifest "${MANIFEST:?set MANIFEST to the SA-V JSONL}" \
  --data-root "${DATA_ROOT:?set DATA_ROOT to the benchmark repository}" \
  --checkpoint "${CHECKPOINT:-checkpoints/sam3.1_multiplex.pt}" \
  --sam3-repo external/sam3 \
  --precision "${precision}" \
  --max-videos "${MAX_VIDEOS:-1}" \
  --max-frames "${MAX_FRAMES:-16}" \
  --output "${output}" \
  "${extra_args[@]}"
