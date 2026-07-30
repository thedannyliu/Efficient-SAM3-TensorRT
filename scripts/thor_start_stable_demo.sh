#!/usr/bin/env bash
set -euo pipefail

SAM3_STABLE_ROOT="${SAM3_STABLE_ROOT:-$HOME/Efficient-SAM3-TensorRT-stable}"
SAM2_STABLE_ROOT="${SAM2_STABLE_ROOT:-$HOME/Efficient-SAM2-TensorRT-stable}"
BASELINE_ROOT="${THOR_BASELINE_ROOT:-$HOME/thor-demo-baseline-20260730}"
GI_BASELINE_IMAGE="${GI_BASELINE_IMAGE:-instinctsam:thor-r39-unified-api-baseline-20260730}"
SAM3_BASELINE_COMMIT="bbb3a89ddcf04f78851d993f8cb495111e0fd7fa"
SAM2_BASELINE_COMMIT="a77543a6ab57579bfe1d11ed439030d85654a3d1"
TV5_BUNDLE="$BASELINE_ROOT/bundles/sam2.1-tinyvit-5m/fp16_best_20260729"

require_commit() {
  local repo="$1"
  local expected="$2"
  local actual
  actual="$(git -C "$repo" rev-parse HEAD)"
  if [[ "$actual" != "$expected" ]]; then
    echo "Baseline checkout mismatch: $repo" >&2
    echo "Expected $expected, found $actual" >&2
    exit 1
  fi
}

require_commit "$SAM3_STABLE_ROOT" "$SAM3_BASELINE_COMMIT"
require_commit "$SAM2_STABLE_ROOT" "$SAM2_BASELINE_COMMIT"
docker image inspect "$GI_BASELINE_IMAGE" >/dev/null
test -f "$TV5_BUNDLE/manifest.json"
test -f "$SAM2_STABLE_ROOT/ros_ws/install/setup.bash"
test -f "$SAM3_STABLE_ROOT/ros_ws/install/setup.bash"

export SAM2_ROOT="$SAM2_STABLE_ROOT"
export GI_UNIFIED_IMAGE="$GI_BASELINE_IMAGE"
export GI_RESEARCH_USE_ACK="${GI_RESEARCH_USE_ACK:-research-evaluation-only}"

exec bash "$SAM3_STABLE_ROOT/scripts/thor_restart_unified_desktop.sh" \
  default_mode:=2 \
  bundle_dir:="$TV5_BUNDLE" \
  display_max_width:=1600 \
  track_bucket_size:=1 \
  track_concurrency:=4 \
  pipeline_overlap:=false \
  "$@"
