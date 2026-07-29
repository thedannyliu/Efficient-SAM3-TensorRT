#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAM2_ROOT="${SAM2_ROOT:-$HOME/Efficient-SAM2-TensorRT}"

source /opt/ros/jazzy/setup.bash
test -f "$SAM2_ROOT/ros_ws/install/setup.bash" || {
  echo "build the existing SAM2 ROS workspace first: $SAM2_ROOT/ros_ws" >&2
  exit 1
}
source "$SAM2_ROOT/ros_ws/install/setup.bash"
python3 -m pip install -e "$REPO_ROOT" --no-deps
cd "$REPO_ROOT/ros_ws"
colcon build --symlink-install
