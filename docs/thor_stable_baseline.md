# Thor stable demo baseline

This baseline preserves the working unified Mode 1/Mode 2 desktop pipeline
before the second multi-object optimization campaign.

## Immutable source revisions

| Repository | Stable branch | Tag | Commit |
|---|---|---|---|
| Efficient-SAM3-TensorRT | `stable/thor-demo-20260730` | `thor-demo-baseline-20260730` | `bbb3a89ddcf04f78851d993f8cb495111e0fd7fa` |
| Efficient-SAM2-TensorRT | `stable/thor-demo-20260730` | `thor-demo-baseline-20260730` | `a77543a6ab57579bfe1d11ed439030d85654a3d1` |

New optimization work belongs on `opt/thor-acceleration-v2`. Do not move the
stable branches or rebuild candidates into the baseline bundle directories.

## Thor runtime snapshot

The Thor keeps independent source/build trees:

```text
~/Efficient-SAM3-TensorRT-stable
~/Efficient-SAM2-TensorRT-stable
```

Non-Git runtime artifacts are preserved under:

```text
~/thor-demo-baseline-20260730/
  start.sh
  runtime_manifest.txt
  bundle_sha256.txt
  bundles/
```

The General Instinct derived image is also tagged locally as:

```text
instinctsam:thor-r39-unified-api-baseline-20260730
```

Its expected image ID is
`sha256:cc3c99b2b09d0f92a308d8dab8d5444fa0a5444843ee38a8992564411176bfbe`.
The tag and engine snapshots are intentionally not committed to Git.

## Start the known-good pipeline

From any Thor terminal:

```bash
~/thor-demo-baseline-20260730/start.sh
```

The wrapper refuses to start if either stable worktree is at the wrong commit,
the baseline GI image is absent, or the TV5M bundle is incomplete. It starts:

- Mode 2;
- TV5M `fp16_best_20260729`;
- bucket size 1;
- four independent TensorRT execution contexts;
- synchronous tracking with no cross-frame overlap;
- the 1600-pixel desktop preset.

Additional launch arguments may be appended. For example:

```bash
~/thor-demo-baseline-20260730/start.sh default_mode:=1
```

## Rebuild the stable worktrees

The Thor cold SSH shell does not discover CUDA automatically. Use explicit
SM110 and `nvcc` settings:

```bash
SAM2_STABLE="$HOME/Efficient-SAM2-TensorRT-stable"

cmake -S "$SAM2_STABLE/cpp" -B "$SAM2_STABLE/build/core" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=110 \
  -DCMAKE_INSTALL_PREFIX="$SAM2_STABLE/build/install"
cmake --build "$SAM2_STABLE/build/core" -j4
ctest --test-dir "$SAM2_STABLE/build/core" --output-on-failure
cmake --install "$SAM2_STABLE/build/core"

source /opt/ros/jazzy/setup.bash
cd "$SAM2_STABLE/ros_ws"
colcon build --symlink-install --parallel-workers 4 \
  --cmake-args \
    -DCMAKE_PREFIX_PATH="$SAM2_STABLE/build/install" \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
    -DCMAKE_CUDA_ARCHITECTURES=110

cd "$HOME/Efficient-SAM3-TensorRT-stable"
SAM2_ROOT="$SAM2_STABLE" bash scripts/setup_thor_ros.sh
```

This build and the stable-start smoke passed on 2026-07-30. The running
`sam2_trt_node` and `interactive_viewer` paths were both verified to resolve
inside their respective `-stable` worktrees.
