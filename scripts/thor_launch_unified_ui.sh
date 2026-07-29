#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_PID="$(pgrep -u "$(id -u)" -x gnome-shell | head -1)"
if [[ -z "$DESKTOP_PID" || ! -r "/proc/$DESKTOP_PID/environ" ]]; then
  echo "No readable GNOME desktop session found for $USER" >&2
  exit 1
fi

DESKTOP_ENV="/proc/$DESKTOP_PID/environ"
DISPLAY_VALUE="$(tr '\0' '\n' < "$DESKTOP_ENV" | sed -n 's/^DISPLAY=//p' | head -1)"
XAUTHORITY_VALUE="$(tr '\0' '\n' < "$DESKTOP_ENV" | sed -n 's/^XAUTHORITY=//p' | head -1)"
RUNTIME_VALUE="$(tr '\0' '\n' < "$DESKTOP_ENV" | sed -n 's/^XDG_RUNTIME_DIR=//p' | head -1)"
if [[ -z "$DISPLAY_VALUE" || -z "$XAUTHORITY_VALUE" ]]; then
  echo "GNOME session does not expose DISPLAY and XAUTHORITY" >&2
  exit 1
fi

export DISPLAY="$DISPLAY_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"
if [[ -n "$RUNTIME_VALUE" ]]; then
  export XDG_RUNTIME_DIR="$RUNTIME_VALUE"
fi

source "$REPO_ROOT/scripts/source_thor_ros_env.sh"
exec ros2 launch sam3_trt_ros unified.launch.py "$@"
