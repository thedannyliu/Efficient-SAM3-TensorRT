#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${GI_PORT:-8767}"

if pgrep -f \
  '^/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch sam3_trt_ros unified.launch.py' \
  >/dev/null; then
  echo "Unified ROS pipeline is already running; stop it before starting another" >&2
  exit 1
fi

if ! curl -fsS --max-time 2 \
  "http://127.0.0.1:$PORT/status.json" >/dev/null 2>&1; then
  LOG="${TMPDIR:-/tmp}/instinctsam-unified-start.log"
  bash "$REPO_ROOT/scripts/thor_run_gi_unified.sh" >"$LOG" 2>&1 &
  echo "Loading InstinctSAM in parallel (log: $LOG)"
fi

exec bash "$REPO_ROOT/scripts/thor_launch_unified_ui.sh" "$@"
