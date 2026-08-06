#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GI_DELIVERY_DIR="${GI_DELIVERY_DIR:-$HOME/vendor/general-instinct/InstinctSAM-Thor-delivery}"
IMAGE="${GI_UNIFIED_IMAGE:-instinctsam:thor-r39-unified-api}"
NAME="${GI_CONTAINER_NAME:-instinctsam-unified}"
PORT="${GI_PORT:-8767}"

python3 "$REPO_ROOT/scripts/verify_gi_delivery.py" "$GI_DELIVERY_DIR" --skip-tar
CAMERA_WAIT_SECONDS="${GI_CAMERA_WAIT_SECONDS:-120}"
HOST_SOURCE=""
CONTAINER_SOURCE="${GI_CAMERA_URI:-}"
device_arguments=()
application_arguments=(
  --width "${GI_CAMERA_WIDTH:-1280}"
  --height "${GI_CAMERA_HEIGHT:-720}"
  --cam-fps "${GI_CAMERA_FPS:-30}"
)
if [[ -z "$CONTAINER_SOURCE" ]]; then
  for ((second = 0; second < CAMERA_WAIT_SECONDS; second++)); do
    if [[ -n "${GI_CAMERA_DEVICE:-}" ]]; then
      test -c "$GI_CAMERA_DEVICE" && HOST_SOURCE="$GI_CAMERA_DEVICE"
    else
      shopt -s nullglob
      camera_links=(/dev/v4l/by-id/*RealSense*video-index0)
      shopt -u nullglob
      if ((${#camera_links[@]} > 0)); then
        candidate="$(readlink -f "${camera_links[0]}")"
        test -c "$candidate" && HOST_SOURCE="$candidate"
      fi
    fi
    [[ -n "$HOST_SOURCE" ]] && break
    if ((second > 0 && second % 10 == 0)); then
      echo "Waiting for the RealSense color camera (${second}s)"
    fi
    sleep 1
  done
  CONTAINER_SOURCE="/dev/video4"
  if [[ -z "$HOST_SOURCE" ]]; then
    echo "RealSense color device did not appear within $CAMERA_WAIT_SECONDS seconds" >&2
    echo "Reconnect the camera or set GI_CAMERA_DEVICE explicitly" >&2
    exit 1
  fi
  device_arguments=(--device "$HOST_SOURCE:$CONTAINER_SOURCE")
  echo "Using RealSense device $HOST_SOURCE as $CONTAINER_SOURCE in the container"
else
  echo "Using the configured network camera URI in the container"
  # The vendor entrypoint treats SOURCE as a local path and falls back to its
  # sample clip when `test -e` fails. Its final "$@" lets this last --source
  # override select the network stream without modifying the vendor image.
  application_arguments+=(--source "$CONTAINER_SOURCE")
fi
docker image inspect "$IMAGE" >/dev/null
docker rm -f instinctsam-native instinctsam-detect "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  --runtime nvidia \
  --network host \
  --ipc host \
  "${device_arguments[@]}" \
  -v instinctsam-trt:/root/.cache/instinctsam/tensorrt \
  -e PORT="$PORT" \
  -e SOURCE="$CONTAINER_SOURCE" \
  -e UNIFIED_API=1 \
  -e IN_RES="${GI_IN_RES:-768}" \
  -e DETECT_IN_RES="${GI_DETECT_IN_RES:-1152}" \
  -e CROSSOVER="${GI_CROSSOVER:-2}" \
  -e MAX_OBJECTS="${GI_MAX_OBJECTS:-24}" \
  --restart unless-stopped \
  "$IMAGE" \
  "${application_arguments[@]}" >/dev/null

for _ in $(seq 1 150); do
  if curl -fsS --max-time 2 \
    "http://127.0.0.1:$PORT/status.json" >/dev/null 2>&1; then
    PYTHONPATH="$REPO_ROOT/src" python3 "$REPO_ROOT/scripts/warm_gi.py" \
      --base-url "http://127.0.0.1:$PORT" || \
      echo "InstinctSAM warm-up failed; the first prompt will warm it"
    echo "InstinctSAM unified API ready on http://127.0.0.1:$PORT"
    exit 0
  fi
  if ! docker ps -q -f "name=^${NAME}$" | grep -q .; then
    docker logs "$NAME" 2>&1 | tail -100
    exit 1
  fi
  sleep 5
done
docker logs "$NAME" 2>&1 | tail -100
echo "InstinctSAM unified API did not become healthy" >&2
exit 1
