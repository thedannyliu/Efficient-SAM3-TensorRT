#!/usr/bin/env bash

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAM2_ROOT="${SAM2_ROOT:-$HOME/Efficient-SAM2-TensorRT}"
THOR_VENV="${THOR_VENV:-$HOME/venvs/efficient_sam3_trt_ros}"

restore_nounset=false
case "$-" in
  *u*) restore_nounset=true; set +u ;;
esac
source /opt/ros/jazzy/setup.bash
source "$SAM2_ROOT/ros_ws/install/setup.bash"
source "$THOR_VENV/bin/activate"
if [[ -f "$REPO_ROOT/ros_ws/install/setup.bash" ]]; then
  source "$REPO_ROOT/ros_ws/install/setup.bash"
fi
if [[ "$restore_nounset" == true ]]; then
  set -u
fi
