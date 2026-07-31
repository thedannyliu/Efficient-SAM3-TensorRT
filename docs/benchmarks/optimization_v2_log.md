# Thor acceleration v2 experiment log

## Objective and promotion gate

Optimize the unified Thor camera pipeline while retaining at least 95% of the
deployed FP16 pipeline's quality. The stable fallback is documented in
`docs/thor_stable_baseline.md`.

Every candidate is evaluated in this order:

1. component or engine latency after warm-up;
2. deterministic same-input mask agreement;
3. recorded-video quality and temporal stability;
4. 848x480@60 Thor camera model latency, completed FPS, screen FPS, and source
   age;
5. one, two, four, and eight objects where the route applies.

Record the exact source commit, engine manifest/hash, precision, input,
prompt, object count, power mode, clocks, warm-up count, measured count, and
raw ignored-result path. A candidate is not promoted from this branch until
the matching stable pipeline can still be launched independently.

## Frozen starting point

| Route | Measurement | Result |
|---|---|---:|
| Mode 2, one object, TV5M, 848x480@60 | completed/model | 33.27 FPS / 29.80 ms |
| Mode 2, two objects, TV5M | completed/model | 22.40 FPS / 44.54 ms |
| Mode 2, four objects, TV5M | completed/model | 11.95 FPS / 83.57 ms |
| Mode 2, four objects, displayed integration | inference / tracking FPS | 88.97 ms / 11.21 |
| Mode 2, four objects, bucket 2 | inference / tracking FPS | 185.69 ms / 5.38 |
| Mode 2, four objects, bucket 4 | inference / tracking FPS | 170.62 ms / 5.85 |
| Mode 1, one `bag` object | model / tracking | 115.43 ms / 8.78 FPS |
| Mode 1, five `chair` objects | model / tracking | 134.67 ms / 8.37 FPS |

The refreshed engine-only TV5M track means are 15.095/58.568/121.740 ms for
batch 1/2/4. The four-object track tail is 81.65 ms, 91.8% of integrated model
latency.

## Experiment matrix

| ID | Candidate | Main hypothesis | Accuracy risk | Status |
|---|---|---|---|---|
| V2-01 | Separate static batch-2/4 track engines | Exact shapes enable better TensorRT tactics than the dynamic multi-profile plan | None | In progress |
| V2-02 | Shared-image multi-object track graph | Avoid repeating image features and image-side projections for every object | None | Implemented; engine pending |
| V2-03 | Device-resident state bank and fused gather | Remove per-frame per-memory packing, pointer copies, and host temporal arrays | None | Implemented; full A/B pending |
| V2-04 | CUDA Graph steady-state routes | Reduce launch/enqueue overhead after buffers and shapes become stable | None | Planned |
| V2-05 | One GPU label/overlay output | Avoid N full-resolution mask D2H transfers and Python composition | None | Planned |
| V2-06 | Per-layer lower precision in the tracking tail | Accelerate dominant Conv/MatMul/MLP while preserving sensitive operations | Medium | Planned |
| V2-07 | Motion-aware object-update router | Spend full tracking only on selected or moving objects | High | Planned |
| V2-08 | Direct Mode 2 camera path | Remove continuous GI MJPEG encode/HTTP/decode from SAM2 tracking | None | Planned |
| V2-09 | Extend GI Mode 1 TensorRT boundary | Move the remaining profiler-dominant vendor PyTorch components into TensorRT | Medium/license boundary | Planned |
| V2-10 | Direct mask handoff from GI to SAM2 | Avoid mask-to-box conversion and preserve non-rectangular first-frame evidence | Low | In progress |

The memory-count reduction experiment is intentionally excluded.

## V2-00 stable preservation

Date: 2026-07-30.

- Pushed `stable/thor-demo-20260730` and
  `thor-demo-baseline-20260730` in both repositories.
- Created independent stable worktrees and ROS/C++ installs on Thor.
- Snapshotted all three deployed engine bundles (2.4 GB total).
- Tagged the exact GI derived image.
- C++ state-selection test and both ROS workspaces built successfully.
- Stable wrapper cold-shell smoke reached GI, SAM2, and viewer ready state.

No model, precision, engine, prompt, or camera behavior changed.

## V2-10 mask handoff design

The current Mode 2 text handoff converts each GI binary mask into a bounding
box, then initializes SAM2 through its box-prompt engine. The conversion cost
is small (about 20--23 ms in earlier end-to-end handoff traces), but a box
discards shape and can include background or neighboring objects.

The candidate keeps both routes:

```text
GI text mask -> SAM2 mask initialization
             -> fallback to SAM2 box initialization
```

Promotion requires:

- no crash or stale-frame initialization;
- identical object count and IDs;
- lower or equal text-to-first-SAM2-mask latency after warm-up;
- first-frame and propagated mask agreement at least 0.95 versus the current
  deployed route, plus comparison to the GI source mask;
- no regression for overlapping or nearby objects.

SAM2's current TensorRT bundle has point, box, and track plans but no
mask-prompt initialization plan. V2-10 therefore requires a new mask prompt
export/engine and C++ service boundary; relabeling the box API is not a valid
test.

### V2-10 first implementation and Thor results

Date: 2026-07-30.

Source revisions:

- SAM2 TensorRT `943866e` adds the mask ONNX role, C++ TensorRT path, CUDA
  mono8 preprocessing, and `/sam/add_mask`.
- SAM3 integration `f3ab2c7` adds the `box|mask` route and carries decoded GI
  masks across the ROS boundary.
- SAM2 TensorRT `fdc1142` and SAM3 integration `a9ea7d1` add reproducible
  parity sample/evaluation tools.

The TV5M candidate is
`bundles/sam2.1-tinyvit-5m/fp16_mask_v2_20260730`. Existing encoder,
point, box, and track ONNX/engines are baseline hardlinks; only the 12,314,358
byte mask ONNX and its engine are new. The mask engine SHA256 is
`264b0bd797527251bec05b4d33e99e410080df96222673cf189769e6cb66f40c`.
TensorRT builder level 5 with zero auxiliary streams took 746.71 seconds.

Clean engine results, warm-up 20 and measured 100:

| Mask batch | Mean | p90 | Object prompts/s |
|---:|---:|---:|---:|
| 1 | 1.797 ms | 1.852 ms | 556.64 |
| 2 | 3.416 ms | 3.469 ms | 585.44 |
| 4 | 7.354 ms | 7.380 ms | 543.92 |
| 8 | 15.056 ms | 15.188 ms | 531.36 |

Six real GI masks were captured at 848x480: two `bag` and four `chair`.
TensorRT versus the matching PyTorch mask graph produced:

- mean/minimum binary mask IoU: 1.000/1.000;
- input-mask versus TensorRT output IoU: 1.000;
- minimum object-pointer cosine: 0.9999985;
- minimum new-memory cosine: 0.9999442;
- memory-position cosine: 1.000.

The live unified camera smoke completed both routes without a crash. The box
sample found three objects and the mask sample found two, so their total
handoff times are not a controlled speed A/B. Subsequent model latency scaled
normally with object count: 70.58 ms for three box-initialized tracks and
50.85 ms for two mask-initialized tracks. Direct mask initialization does not
change the steady tracking graph.

Raw ignored artifacts are under:

```text
~/Efficient-SAM2-TensorRT/results/benchmarks/mask_prompt_v2_20260730/
```

Decision: retain `text_handoff_prompt:=mask` as an experimental route. Keep
`box` as the default until the two routes are propagated through the same
recorded frames and compared to temporal ground truth. Engine/component
accuracy already passes the 95% gate.

## V2-01 static track profiles

Date: 2026-07-30. SAM2 revisions `ca98527` and `9ff00eb` provide isolated
single-profile builds, explicit runtime-state endpoints, and same-input engine
parity. The deployed engine was not overwritten.

The first static batch-2 plan used the deployed TV5M FP16 ONNX, builder level
5, zero auxiliary streams, and a seven-memory/sixteen-pointer optimization
point. Interleaved warm-up-20/run-100 measurements were:

| Runtime state | Multi-profile mean | Static b2 mean | Latency change |
|---|---:|---:|---:|
| 4 memories / 8 pointers | 58.191 ms | 57.560 ms | -1.08% |
| 7 memories / 16 pointers | 86.378 ms | 85.874 ms | -0.58% |

On identical seeded full-state inputs, static versus multi-profile mask IoU was
0.998141. Mask cosine was 0.9999994; the minimum reported output cosine was
0.9999967. This passes the 95% gate, but the speed difference is too small to
change the bucket decision: batch 2 remains much slower than parallel batch-1
contexts.

The deployed plan also emitted TensorRT's cross-device-model warning while the
new plan did not. A new same-day multi-profile control is required before
attributing the sub-1% full-state result specifically to static shapes.

Static b4 was building as ignored Thor process `87267` when the Windows-to-Thor
reverse tunnel stopped forwarding SSH. Its result is deliberately recorded as
unknown, not failed or complete. Artifacts are under:

```text
~/Efficient-SAM2-TensorRT/results/benchmarks/static_batch_v2_20260730/
```

## V2-02 shared-image graph boundary

SAM2 revision `85eab22` adds an isolated ONNX rewrite in which the four
per-frame image feature inputs remain batch one while object memory and pointer
inputs remain batch N. ONNX `Expand` nodes derive N from the state tensor, so
the model arithmetic is unchanged and TensorRT can fuse or broadcast instead
of receiving four physically repeated feature buffers.

Unit tests cover the rewritten input shapes, broadcast nodes, profile shapes,
and full-state optimization endpoint. The actual TV5M shared-image engine and
b2/b4 parity/latency are pending Thor access. No C++ runtime or deployed bundle
has selected this graph.

## V2-03 fused state gather boundary

SAM2 revision `5ba244d` replaces up to fourteen memory packing kernels and
sixteen pointer copies per object with three pointer-table uploads and fused
memory/position/pointer gather kernels. The route is opt-in through
`fused_state_gather:=true`; the default remains false. Revision `b7e5c69` adds
a deterministic full-tracker A/B that alternates execution order, waits at
least sixteen frames for full temporal state, and compares every mask pixel.

The CUDA layout test compiled and passed on Thor, along with the existing state
selection test and both ROS workspaces. The deterministic 1/2/4-object tracker
A/B and live camera test remain pending because the reverse tunnel failed
before the new A/B executable could be built. This candidate is not promoted.
