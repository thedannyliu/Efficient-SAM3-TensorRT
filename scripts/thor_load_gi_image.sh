#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GI_DELIVERY_DIR="${GI_DELIVERY_DIR:-$HOME/vendor/general-instinct/InstinctSAM-Thor-delivery}"

python3 "$REPO_ROOT/scripts/verify_gi_delivery.py" "$GI_DELIVERY_DIR"
gunzip -c "$GI_DELIVERY_DIR/instinctsam-thor-r39.tar.gz" | docker load
docker image inspect instinctsam:thor-r39 \
  --format 'image={{.Id}} architecture={{.Architecture}} created={{.Created}}'
