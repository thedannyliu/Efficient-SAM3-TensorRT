#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ACK="research-evaluation-only"
if [[ "${GI_RESEARCH_USE_ACK:-}" != "$EXPECTED_ACK" ]]; then
  echo "Unified camera switching requires GI_RESEARCH_USE_ACK=$EXPECTED_ACK" >&2
  echo "Set it only after reading LICENSE.InstinctSAM, LICENSE.SAM, and NOTICE." >&2
  exit 1
fi

DISPLAY_VALUE=""
XAUTHORITY_VALUE=""
RUNTIME_VALUE=""
WAIT_SECONDS="${THOR_DESKTOP_WAIT_SECONDS:-60}"
for ((attempt = 0; attempt < WAIT_SECONDS; attempt++)); do
  DESKTOP_PID="$(
    pgrep -u "$(id -u)" -x gnome-shell 2>/dev/null | head -1 || true
  )"
  if [[ -n "$DESKTOP_PID" && -r "/proc/$DESKTOP_PID/environ" ]]; then
    DESKTOP_ENV="/proc/$DESKTOP_PID/environ"
    DISPLAY_VALUE="$(
      tr '\0' '\n' < "$DESKTOP_ENV" |
        sed -n 's/^DISPLAY=//p' |
        head -1
    )"
    XAUTHORITY_VALUE="$(
      tr '\0' '\n' < "$DESKTOP_ENV" |
        sed -n 's/^XAUTHORITY=//p' |
        head -1
    )"
    RUNTIME_VALUE="$(
      tr '\0' '\n' < "$DESKTOP_ENV" |
        sed -n 's/^XDG_RUNTIME_DIR=//p' |
        head -1
    )"
    if [[ -n "$DISPLAY_VALUE" && -n "$XAUTHORITY_VALUE" ]]; then
      break
    fi
  fi
  sleep 1
done
if [[ -z "$DISPLAY_VALUE" || -z "$XAUTHORITY_VALUE" ]]; then
  echo "No usable GNOME session appeared within $WAIT_SECONDS seconds" >&2
  echo "Log into the Thor desktop once, then run the command again" >&2
  exit 1
fi

export DISPLAY="$DISPLAY_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"
if [[ -n "$RUNTIME_VALUE" ]]; then
  export XDG_RUNTIME_DIR="$RUNTIME_VALUE"
fi

source "$REPO_ROOT/scripts/source_thor_ros_env.sh"
exec ros2 launch sam3_trt_ros unified.launch.py "$@"
