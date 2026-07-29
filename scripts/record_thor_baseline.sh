#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE="${1:?usage: record_thor_baseline.sh instinctsam|hybrid [experiment-id]}"
EXPERIMENT_ID="${2:-$(date -u +%Y%m%dT%H%M%SZ)_${PIPELINE}}"
case "$PIPELINE" in
  instinctsam) TOPIC=/instinctsam/result_json ;;
  hybrid) TOPIC=/sam/result_json ;;
  *) echo "pipeline must be instinctsam or hybrid" >&2; exit 2 ;;
esac

source "$REPO_ROOT/scripts/source_thor_ros_env.sh"
OUTPUT_DIR="$REPO_ROOT/results/benchmarks/$EXPERIMENT_ID"
mkdir -p "$OUTPUT_DIR"

git -C "$REPO_ROOT" rev-parse HEAD >"$OUTPUT_DIR/git_commit.txt"
uname -a >"$OUTPUT_DIR/uname.txt"
head -n 1 /etc/nv_tegra_release >"$OUTPUT_DIR/l4t.txt"
docker image inspect instinctsam:thor-r39 \
  --format '{{json .}}' >"$OUTPUT_DIR/gi_image.json" 2>/dev/null || true
nvidia-smi -q >"$OUTPUT_DIR/nvidia-smi.txt" 2>/dev/null || true

for repetition in 1 2 3; do
  ros2 run sam3_trt_ros trace_recorder --ros-args \
    -p topic:="$TOPIC" \
    -p output:="$OUTPUT_DIR/repeat_${repetition}.jsonl" \
    -p warmup_frames:=100 \
    -p measurement_frames:=1000
  sam31-benchmark-summary \
    "$OUTPUT_DIR/repeat_${repetition}.jsonl" \
    --warmup 0 \
    --output "$OUTPUT_DIR/repeat_${repetition}_summary.json"
done
echo "$OUTPUT_DIR"
