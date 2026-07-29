#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GI_DELIVERY_DIR="${GI_DELIVERY_DIR:-$HOME/vendor/general-instinct/InstinctSAM-Thor-delivery}"
IMAGE="${GI_DETECT_IMAGE:-instinctsam:thor-r39-detect-api}"
NAME="${GI_CONTAINER_NAME:-instinctsam-detect}"
PORT="${GI_PORT:-8767}"

python3 "$REPO_ROOT/scripts/verify_gi_delivery.py" "$GI_DELIVERY_DIR" --skip-tar
docker image inspect "$IMAGE" >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  --runtime nvidia \
  --network host \
  --ipc host \
  -v instinctsam-trt:/root/.cache/instinctsam/tensorrt \
  -e PORT="$PORT" \
  -e DETECT_ONLY=1 \
  -e IN_RES="${GI_IN_RES:-768}" \
  -e DETECT_IN_RES="${GI_DETECT_IN_RES:-1152}" \
  -e MAX_OBJECTS="${GI_MAX_OBJECTS:-8}" \
  --restart unless-stopped \
  "$IMAGE" >/dev/null

for _ in $(seq 1 150); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/status.json" >/dev/null; then
    echo "InstinctSAM detect API ready on http://127.0.0.1:$PORT"
    exit 0
  fi
  if ! docker ps -q -f "name=^${NAME}$" | grep -q .; then
    docker logs "$NAME" 2>&1 | tail -100
    exit 1
  fi
  sleep 5
done
docker logs "$NAME" 2>&1 | tail -100
echo "InstinctSAM detect API did not become healthy" >&2
exit 1
