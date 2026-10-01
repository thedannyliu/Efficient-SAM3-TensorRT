#!/usr/bin/env bash
set -euo pipefail

mapfile -t launch_pids < <(
  pgrep -f \
    '^/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch sam3_trt_ros unified.launch.py' \
    || true
)
if ((${#launch_pids[@]} == 0)); then
  echo "No unified launch process is running"
  exit 0
fi

child_pids=()
for launch_pid in "${launch_pids[@]}"; do
  while read -r child_pid; do
    [[ -n "$child_pid" ]] && child_pids+=("$child_pid")
  done < <(pgrep -P "$launch_pid" || true)
done

kill -INT "${launch_pids[@]}" 2>/dev/null || true
for _ in $(seq 1 20); do
  alive=false
  for process_id in "${launch_pids[@]}" "${child_pids[@]}"; do
    if kill -0 "$process_id" 2>/dev/null; then
      alive=true
      break
    fi
  done
  [[ "$alive" == false ]] && break
  sleep 0.25
done

remaining=()
for process_id in "${launch_pids[@]}" "${child_pids[@]}"; do
  kill -0 "$process_id" 2>/dev/null && remaining+=("$process_id")
done
if ((${#remaining[@]} > 0)); then
  kill -TERM "${remaining[@]}" 2>/dev/null || true
fi

echo "Stopped unified launch and its captured child processes"
