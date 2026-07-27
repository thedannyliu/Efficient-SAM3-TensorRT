#!/usr/bin/env bash
#SBATCH --job-name=sam31-e2e-trt
#SBATCH --partition=gpu-h200
#SBATCH --account=gts-agarg35
#SBATCH --qos=embers
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

module load python/3.12.5 cuda/12.6.1
source .venv/bin/activate
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

label="${LABEL:?set a precision label}"
output="results/${SLURM_JOB_ID}/e2e_${label}.json"
mkdir -p "$(dirname "${output}")" logs

extra_args=()
if [[ -n "${VISION_ENGINE_CALL_LIMIT:-}" ]]; then
  extra_args+=(--vision-engine-call-limit "${VISION_ENGINE_CALL_LIMIT}")
fi

nvidia-smi
python scripts/native_vos_baseline.py \
  --manifest "${MANIFEST:?set MANIFEST to the SA-V JSONL}" \
  --data-root "${DATA_ROOT:?set DATA_ROOT to the benchmark repository}" \
  --checkpoint "${CHECKPOINT:-checkpoints/sam3.1_multiplex.pt}" \
  --sam3-repo external/sam3 \
  --precision official_bf16 \
  --vision-engine "${VISION_ENGINE:?set VISION_ENGINE}" \
  --max-videos "${MAX_VIDEOS:-1}" \
  --max-frames "${MAX_FRAMES:-16}" \
  --output "${output}" \
  "${extra_args[@]}"
