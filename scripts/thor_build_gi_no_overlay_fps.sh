#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GI_DELIVERY_DIR="${GI_DELIVERY_DIR:-$HOME/vendor/general-instinct/InstinctSAM-Thor-delivery}"
BASE_IMAGE="${GI_BASE_IMAGE:-instinctsam:thor-r39-unified-api-baseline-20260730}"
OUTPUT_IMAGE="${GI_NO_FPS_IMAGE:-instinctsam:thor-r39-unified-api-no-overlay-fps}"

python3 "$REPO_ROOT/scripts/verify_gi_delivery.py" \
  "$GI_DELIVERY_DIR" --skip-tar >/dev/null
docker image inspect "$BASE_IMAGE" >/dev/null
docker build \
  --build-arg "BASE_IMAGE=$BASE_IMAGE" \
  --file "$REPO_ROOT/docker/gi-no-overlay-fps.Dockerfile" \
  --tag "$OUTPUT_IMAGE" \
  "$REPO_ROOT"

echo "Built $OUTPUT_IMAGE from the licensed local GI image"
