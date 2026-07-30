#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ACK="research-evaluation-only"
LOG="${THOR_UNIFIED_LOG:-/tmp/efficient-sam3-unified.log}"

if [[ "${GI_RESEARCH_USE_ACK:-}" != "$EXPECTED_ACK" ]]; then
  echo "Set GI_RESEARCH_USE_ACK=$EXPECTED_ACK after reading the GI licenses" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is unavailable to $(id -un)" >&2
  echo "Verify the docker service and log in again after joining the docker group" >&2
  exit 1
fi
docker image inspect \
  "${GI_UNIFIED_IMAGE:-instinctsam:thor-r39-unified-api}" >/dev/null

export GI_CAMERA_WIDTH="${GI_CAMERA_WIDTH:-848}"
export GI_CAMERA_HEIGHT="${GI_CAMERA_HEIGHT:-480}"
export GI_CAMERA_FPS="${GI_CAMERA_FPS:-60}"

bash "$REPO_ROOT/scripts/thor_stop_unified_desktop.sh"
rm -f /dev/shm/sam3_sam2_frame.bin

nohup bash "$REPO_ROOT/scripts/thor_start_unified_desktop.sh" "$@" \
  >"$LOG" 2>&1 </dev/null &
launcher_pid=$!

for _ in $(seq 1 120); do
  if ! kill -0 "$launcher_pid" 2>/dev/null; then
    echo "Unified desktop failed to start; last log lines:" >&2
    tail -80 "$LOG" >&2
    exit 1
  fi
  if pgrep -f \
    '/sam3_trt_ros/interactive_viewer' >/dev/null; then
    echo "Unified desktop started (PID $launcher_pid)"
    echo "Log: $LOG"
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for the interactive viewer; last log lines:" >&2
tail -80 "$LOG" >&2
exit 1
