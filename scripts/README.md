# Script guide

`export/` owns ONNX/precision tools; `benchmark/` owns measurement runners;
`thor/` owns deployment helpers; `dev/` contains synthetic smokes and the mock
server. `jobs/` at the repository root contains Slurm launch recipes.

All in-repository callers have been updated. External automation must update
its paths using the map below; argument names and model behavior are unchanged.
Research outputs belong outside source control.

## Path migration

| Previous path | Current path |
| --- | --- |
| `scripts/build_benchmark_engine.py` | `scripts/benchmark/build_benchmark_engine.py` |
| `scripts/compare_e2e.py` | `scripts/benchmark/compare_e2e.py` |
| `scripts/export_vision_block.py` | `scripts/export/export_vision_block.py` |
| `scripts/export_vision_trunk.py` | `scripts/export/export_vision_trunk.py` |
| `scripts/mock_gi_server.py` | `scripts/dev/mock_gi_server.py` |
| `scripts/native_vos_baseline.py` | `scripts/benchmark/native_vos_baseline.py` |
| `scripts/quantize_vision_onnx.py` | `scripts/export/quantize_vision_onnx.py` |
| `scripts/record_thor_baseline.sh` | `scripts/thor/record_thor_baseline.sh` |
| `scripts/run_pace_thor_pipeline_smoke.py` | `scripts/dev/run_pace_thor_pipeline_smoke.py` |
| `scripts/run_pace_thor_pipeline_smoke.sh` | `scripts/dev/run_pace_thor_pipeline_smoke.sh` |
| `scripts/set_onnx_output_dtype.py` | `scripts/export/set_onnx_output_dtype.py` |
| `scripts/setup_thor_ros.sh` | `scripts/thor/setup_thor_ros.sh` |
| `scripts/source_thor_ros_env.sh` | `scripts/thor/source_thor_ros_env.sh` |
| `scripts/thor_launch_unified_ui.sh` | `scripts/thor/thor_launch_unified_ui.sh` |
| `scripts/thor_load_gi_image.sh` | `scripts/thor/thor_load_gi_image.sh` |
| `scripts/thor_restart_unified_desktop.sh` | `scripts/thor/thor_restart_unified_desktop.sh` |
| `scripts/thor_run_gi_detect_only.sh` | `scripts/thor/thor_run_gi_detect_only.sh` |
| `scripts/thor_run_gi_native.sh` | `scripts/thor/thor_run_gi_native.sh` |
| `scripts/thor_run_gi_unified.sh` | `scripts/thor/thor_run_gi_unified.sh` |
| `scripts/thor_start_unified_desktop.sh` | `scripts/thor/thor_start_unified_desktop.sh` |
| `scripts/thor_stop_unified_desktop.sh` | `scripts/thor/thor_stop_unified_desktop.sh` |
| `scripts/validate_vision_artifacts.py` | `scripts/export/validate_vision_artifacts.py` |
| `scripts/verify_gi_delivery.py` | `scripts/thor/verify_gi_delivery.py` |
| `scripts/warm_gi.py` | `scripts/thor/warm_gi.py` |
