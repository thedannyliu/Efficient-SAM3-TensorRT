#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${GI_PORT:-8767}"

if ! curl -fsS --max-time 2 "http://127.0.0.1:$PORT/status.json" >/dev/null; then
  LOG="${TMPDIR:-/tmp}/instinctsam-unified-start.log"
  bash "$REPO_ROOT/scripts/thor_run_gi_unified.sh" >"$LOG" 2>&1 &
  echo "Loading InstinctSAM in parallel (log: $LOG)"
fi

exec bash "$REPO_ROOT/scripts/thor_launch_unified_ui.sh" "$@"
