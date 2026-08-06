#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ACK="research-evaluation-only"
LOG="${THOR_UNIFIED_LOG:-/tmp/efficient-sam3-unified.log}"
PORT="${GI_PORT:-8767}"
DOCKER_WAIT_SECONDS="${THOR_DOCKER_WAIT_SECONDS:-60}"
CAMERA_WAIT_SECONDS="${THOR_CAMERA_WAIT_SECONDS:-120}"

gi_camera_ready() {
  curl -fsS --max-time 2 "http://127.0.0.1:$PORT/status.json" 2>/dev/null |
    python3 -c '
import json
import sys

value = json.load(sys.stdin)
if value.get("state") != "running" or int(value.get("frame", 0)) <= 0:
    raise SystemExit(1)
' >/dev/null 2>&1
}

camera_available() {
  if [[ -n "${GI_CAMERA_URI:-}" ]]; then
    return 0
  fi
  if [[ -n "${GI_CAMERA_DEVICE:-}" ]]; then
    test -c "$GI_CAMERA_DEVICE"
    return
  fi
  shopt -s nullglob
  local camera_links=(/dev/v4l/by-id/*RealSense*video-index0)
  shopt -u nullglob
  ((${#camera_links[@]} > 0))
}

if [[ "${GI_RESEARCH_USE_ACK:-}" != "$EXPECTED_ACK" ]]; then
  echo "Set GI_RESEARCH_USE_ACK=$EXPECTED_ACK after reading the GI licenses" >&2
  exit 1
fi
if ! id -nG | tr ' ' '\n' | grep -qx docker; then
  echo "$(id -un) does not have Docker access in this login session" >&2
  echo "Log out of the Thor desktop and log back in once" >&2
  exit 1
fi

echo "Preflight: waiting for Docker"
docker_ready=false
for ((second = 0; second < DOCKER_WAIT_SECONDS; second++)); do
  if docker info >/dev/null 2>&1; then
    docker_ready=true
    break
  fi
  if ((second > 0 && second % 10 == 0)); then
    echo "  Docker is still starting (${second}s)"
  fi
  sleep 1
done
if [[ "$docker_ready" != true ]]; then
  echo "Docker is unavailable to $(id -un)" >&2
  systemctl is-active docker >&2 || true
  docker info >&2 || true
  exit 1
fi
echo "Preflight: Docker is ready"
docker image inspect \
  "${GI_UNIFIED_IMAGE:-instinctsam:thor-r39-unified-api}" >/dev/null

export GI_CAMERA_WIDTH="${GI_CAMERA_WIDTH:-848}"
export GI_CAMERA_HEIGHT="${GI_CAMERA_HEIGHT:-480}"
export GI_CAMERA_FPS="${GI_CAMERA_FPS:-60}"
export THOR_DESKTOP_WAIT_SECONDS="${THOR_DESKTOP_WAIT_SECONDS:-120}"

if gi_camera_ready; then
  echo "Preflight: reusing the healthy GI camera runtime"
else
  if [[ -n "${GI_CAMERA_URI:-}" ]]; then
    echo "Preflight: network camera URI configured"
  else
    echo "Preflight: waiting for the RealSense color camera"
  fi
  camera_ready=false
  for ((second = 0; second < CAMERA_WAIT_SECONDS; second++)); do
    if camera_available; then
      camera_ready=true
      break
    fi
    if ((second > 0 && second % 10 == 0)); then
      echo "  RealSense is still enumerating (${second}s)"
    fi
    sleep 1
  done
  if [[ "$camera_ready" != true ]]; then
    echo "Configured camera source did not become available within $CAMERA_WAIT_SECONDS seconds" >&2
    ls -l /dev/v4l/by-id >&2 || true
    exit 1
  fi
  echo "Preflight: camera source found; cold GI loading can take about 2 minutes"
fi

bash "$REPO_ROOT/scripts/thor_stop_unified_desktop.sh"
rm -f /dev/shm/sam3_sam2_frame.bin

echo "Starting the ROS viewer and both model runtimes"
nohup bash "$REPO_ROOT/scripts/thor_start_unified_desktop.sh" "$@" \
  >"$LOG" 2>&1 </dev/null &
launcher_pid=$!

for ((second = 0; second < 900; second++)); do
  if ! kill -0 "$launcher_pid" 2>/dev/null; then
    echo "Unified desktop failed to start; last log lines:" >&2
    tail -80 "$LOG" >&2
    exit 1
  fi
  viewer_ready=false
  sam2_ready=false
  gi_ready=false
  if pgrep -f '/sam3_trt_ros/interactive_viewer' >/dev/null; then
    viewer_ready=true
  fi
  if pgrep -f '/sam2_trt_ros/sam2_trt_node' >/dev/null; then
    sam2_ready=true
  fi
  if gi_camera_ready; then
    gi_ready=true
  fi
  if [[ "$viewer_ready" == true &&
    "$sam2_ready" == true &&
    "$gi_ready" == true ]]; then
    echo "Unified desktop and both model runtimes are ready (PID $launcher_pid)"
    echo "Log: $LOG"
    exit 0
  fi
  if ((second > 0 && second % 10 == 0)); then
    container_state="$(
      docker inspect --format '{{.State.Status}}' \
        "${GI_CONTAINER_NAME:-instinctsam-unified}" 2>/dev/null ||
        echo missing
    )"
    echo "  Loading (${second}s): container=$container_state GI=$gi_ready SAM2=$sam2_ready viewer=$viewer_ready"
  fi
  sleep 1
done

echo "Timed out waiting for the unified desktop; last log lines:" >&2
tail -80 "$LOG" >&2
docker logs "${GI_CONTAINER_NAME:-instinctsam-unified}" 2>&1 |
  tail -80 >&2 || true
exit 1
