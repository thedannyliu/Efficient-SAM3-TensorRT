#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GI_DELIVERY_DIR="${GI_DELIVERY_DIR:-$HOME/vendor/general-instinct/InstinctSAM-Thor-delivery}"
IMAGE="${GI_UNIFIED_IMAGE:-instinctsam:thor-r39-unified-api}"
NAME="${GI_CONTAINER_NAME:-instinctsam-unified}"
SOURCE="${GI_CAMERA_DEVICE:-/dev/video4}"
PORT="${GI_PORT:-8767}"

python3 "$REPO_ROOT/scripts/verify_gi_delivery.py" "$GI_DELIVERY_DIR" --skip-tar
test -c "$SOURCE" || { echo "camera device is not a character device: $SOURCE" >&2; exit 1; }
docker image inspect "$IMAGE" >/dev/null
docker rm -f instinctsam-native instinctsam-detect "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  --runtime nvidia \
  --network host \
  --ipc host \
  --device "$SOURCE:$SOURCE" \
  -v instinctsam-trt:/root/.cache/instinctsam/tensorrt \
  -e PORT="$PORT" \
  -e SOURCE="$SOURCE" \
  -e UNIFIED_API=1 \
  -e IN_RES="${GI_IN_RES:-768}" \
  -e DETECT_IN_RES="${GI_DETECT_IN_RES:-1152}" \
  -e CROSSOVER="${GI_CROSSOVER:-2}" \
  -e MAX_OBJECTS="${GI_MAX_OBJECTS:-24}" \
  --restart unless-stopped \
  "$IMAGE" \
  --width "${GI_CAMERA_WIDTH:-1280}" \
  --height "${GI_CAMERA_HEIGHT:-720}" \
  --cam-fps "${GI_CAMERA_FPS:-30}" >/dev/null

for _ in $(seq 1 150); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/status.json" >/dev/null; then
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
