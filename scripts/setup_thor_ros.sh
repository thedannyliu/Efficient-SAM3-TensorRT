#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAM2_ROOT="${SAM2_ROOT:-$HOME/Efficient-SAM2-TensorRT}"
THOR_VENV="${THOR_VENV:-$HOME/venvs/efficient_sam3_trt_ros}"

set +u
source /opt/ros/jazzy/setup.bash
test -f "$SAM2_ROOT/ros_ws/install/setup.bash" || {
  echo "build the existing SAM2 ROS workspace first: $SAM2_ROOT/ros_ws" >&2
  exit 1
}
source "$SAM2_ROOT/ros_ws/install/setup.bash"
set -u
if [[ ! -x "$THOR_VENV/bin/python" ]]; then
  python3 -m venv --system-site-packages "$THOR_VENV"
fi
source "$THOR_VENV/bin/activate"
python -m pip install -U pip
python -m pip install -e "$REPO_ROOT" --no-deps
cd "$REPO_ROOT/ros_ws"
colcon build --symlink-install
