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
| V2-01 | Separate static batch-2/4 track engines | Exact shapes enable better TensorRT tactics than the dynamic multi-profile plan | None | Rejected: 0.58--1.17% |
| V2-02 | Shared-image multi-object track graph | Avoid repeating image features and image-side projections for every object | None | b2 rejected: 0.70%; b4 pending |
| V2-03 | Device-resident state bank and fused gather | Remove per-frame per-memory packing, pointer copies, and host temporal arrays | None | Rejected |
| V2-04 | CUDA Graph steady-state routes | Reduce launch/enqueue overhead after buffers and shapes become stable | None | Engine A/B implemented |
| V2-05 | One GPU label/overlay output | Avoid N full-resolution mask D2H transfers and Python composition | None | CPU composition fast path implemented |
| V2-06 | Per-layer lower precision in the tracking tail | Accelerate dominant Conv/MatMul/MLP while preserving sensitive operations | Medium | Planned |
| V2-07 | Motion-aware object-update router | Spend full tracking only on selected or moving objects | High | Planned |
| V2-08 | Direct Mode 2 camera path | Remove continuous GI MJPEG encode/HTTP/decode from SAM2 tracking | None | Implemented; Thor A/B pending |
| V2-09 | Extend GI Mode 1 TensorRT boundary | Move the remaining profiler-dominant vendor PyTorch components into TensorRT | Medium/license boundary | Planned |
| V2-10 | Direct mask handoff from GI to SAM2 | Avoid mask-to-box conversion and preserve non-rectangular first-frame evidence | Low | In progress |
| V2-11 | Empirical object-count router | Select parallel b1, b2, or b4 from measured model/object-count crossovers | None | Implemented; Thor table pending |

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

Static b4 completed after the tunnel recovered. Two interleaved full-state
runs produced 172.862 ms for the deployed multi-profile engine and 170.839 ms
for the static engine, a 1.17% latency reduction. Same-input binary mask IoU
was 0.999183 and the minimum output cosine was 0.9999996. Both static b2 and
b4 are accurate, but neither changes the fact that parallel b1 execution is
substantially faster on Thor. They are not deployment candidates.

Artifacts are under:

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
and full-state optimization endpoint. The TV5M b2 plan passed same-input
parity with binary mask IoU 0.999341 and minimum output cosine 0.9999992.
Two interleaved full-state runs measured 85.597 ms for the deployed graph and
84.999 ms for the shared-input graph, only 0.70% faster. TensorRT still expands
the image features before the object-dependent attention/decoder work, so the
rewrite saves input movement but does not remove the dominant arithmetic.

Two interleaved full-state b4 runs averaged 171.119 ms for the baseline and
169.168 ms for the shared-image candidate, a 1.14% reduction. Same-input
binary mask IoU was 0.998957. Like b2, this passes the requested quality gate
but is too small to change the object router or deployment default. No C++
runtime or deployed bundle selects this graph. Raw artifacts are under:

```text
~/Efficient-SAM2-TensorRT/results/benchmarks/shared_image_v2_20260731/
```

## V2-03 fused state gather boundary

SAM2 revision `5ba244d` replaces up to fourteen memory packing kernels and
sixteen pointer copies per object with three pointer-table uploads and fused
memory/position/pointer gather kernels. The route is opt-in through
`fused_state_gather:=true`; the default remains false. Revision `b7e5c69` adds
a deterministic full-tracker A/B that alternates execution order, waits at
least sixteen frames for full temporal state, and compares every mask pixel.

The CUDA layout test compiled and passed on Thor, along with the existing state
selection test and both ROS workspaces. Deterministic tracker A/B results were:

| Objects | Baseline | Fused | Speed change | Binary IoU |
|---:|---:|---:|---:|---:|
| 1 | 30.406 ms | 30.553 ms | -0.48% | 1.000000 |
| 2 | 48.401 ms | 48.575 ms | -0.36% | 0.999742 |
| 4 | 87.568 ms | 87.209 ms | +0.41% | 0.999493 |
| 8 | 168.513 ms | 169.573 ms | -0.63% | 0.805386 |

The state copies are not a meaningful latency bottleneck. More importantly,
the eight-object route accumulates a temporal disagreement, so the option
remains disabled and is excluded from the empirical router. Raw artifacts are
under:

```text
~/Efficient-SAM2-TensorRT/results/benchmarks/fused_gather_v2_20260731/
```

## V2-04 CUDA Graph launch upper bound

SAM2 revision `99c1bb7` adds a fixed-buffer TensorRT CUDA Graph A/B to the
engine benchmark. This intentionally measures the maximum launch-overhead
benefit before changing the live tracker to persistent input addresses. A live
integration is justified only if the engine-only result exceeds measurement
noise.

The engine-only result was 15.135 to 14.675 ms at the common four-memory,
eight-pointer state (3.04%), and 21.629 to 21.205 ms at the steady
seven-memory, sixteen-pointer state (1.96%). Revisions `6511936`, `84f806d`,
and `2156751` then integrated persistent-address capture in the C++ tracker,
added safe fallback, and limited graph use by object count.

Three warm-up-30/run-300 single-object tracker repetitions averaged 30.251 ms
without graph and 29.958 ms with graph, a 0.97% latency reduction. Mask output
was pixel-identical. Two/four-object thread-local capture was neutral or
slower, and an eight-object temporal comparison diverged, so the quality-first
route keeps `track_cuda_graph:=false`. The experimental route is constrained
to `track_cuda_graph_max_objects:=1`.

A batch-1-only native-Thor track plan was also built to remove unused b2/b4
profiles from tactic selection. It averaged 21.448 ms versus 21.590 ms for the
current multi-profile engine (0.66% reduction), with 0.999253 binary mask IoU.
It is accurate but rejected as too small to deploy.

## V2-05 label composition

Four-object Thor traces showed 28--32 ms of asynchronous C++ preview-label
composition, while inference itself was about 84--89 ms. The old loop visited
every preview pixel and then every object. SAM2 revision `2e06d40` changes this
to one linear pass per object with precomputed resize indices; object overwrite
order and the mono8 label output are unchanged.

SAM3 revision `c26e7d2` replaces repeated `np.unique` and boolean color scans
in the viewer with a 256-entry color lookup table. A 640x360 deterministic CPU
microbenchmark produced identical bytes and changed label coloring from
11.251 ms to 2.486 ms (4.53x). These are render-path changes and do not alter
model masks. In the direct-transport camera A/B, preview composition fell from
4.386 to 3.797 ms (13.4%); the screen loop remained dominated by OpenCV
`waitKey` variation, so this is not claimed as a matching screen-FPS gain.

## V2-08 direct vendor camera transport

SAM3 revision `9ce951f` adds an opt-in vendor-shared-frame route. In hybrid
Mode 2, the local licensed GI patch can write its captured BGR frame directly
as RGB into the existing host shared-memory contract. The adapter then disables
the raw MJPEG reader, removing JPEG encode, HTTP multipart transfer, JPEG
decode, and the second BGR-to-RGB conversion. A byte-exact local writer/reader
test passed.

The GI source modification remains ignored and is not redistributed. It is
subject to the General Instinct evaluation/non-commercial license. The tracked
route defaults off and requires both `GI_DIRECT_SHARED_FRAME=1` for the
container and `vendor_shared_frame:=true` for the ROS launch. Derived-image and
Thor camera A/B used the same TV5M one-object workload:

| Metric | MJPEG transport | Direct shared frame | Change |
|---|---:|---:|---:|
| SAM2 inference | 36.551 ms | 35.999 ms | -1.51% |
| Processed tracking rate | 27.218 FPS | 27.615 FPS | +1.46% |
| Input transport | 0.492 ms | 0.387 ms | -21.3% |
| Raw unique camera rate | 47.623 FPS | 58.346 FPS | +22.5% |
| Source age | 51.570 ms | 51.711 ms | neutral |
| Screen render rate | 51.934 FPS | 48.181 FPS | noisy/regressed |

Direct transport substantially increases fresh-frame availability by removing
JPEG/HTTP work, but it does not accelerate the model. The screen-rate result
varied in the opposite direction and is not promoted as a rendering win.
Point initialization through the on-demand raw snapshot succeeded. The ignored
GI patch SHA256 is
`bc3a86ed6a9e1fd1bd0f79b72dc9bb51d2b5fb9e7417631e568c9837eb415488`;
the tested image is
`instinctsam:thor-r39-unified-api-direct-v2` with image ID
`sha256:7f2dcdd0d17b533c2b94fd6db109c99820db6cb154097c5af589838b2b50e76c`.

Raw ignored artifacts are under:

```text
~/Efficient-SAM3-TensorRT/results/benchmarks/direct_camera_v2_20260731/
```

## V2-11 empirical object-count router

The original scheduler has one global bucket size and one minimum-object
threshold. That cannot express a measured route such as b1 for one to three
objects, b2 for four to six, and b4 for seven or eight.

The candidate accepts one route entry for every supported object count. For
example:

```text
track_bucket_router:=1,1,1,2,2,2,4,4
```

Changing object count selects the corresponding capacity before groups are
formed. It does not recreate the tracker, clear prompts, move temporal state,
or change mask arithmetic. Result JSON records both the legacy configured
bucket and `track_bucket_route_size`, the actual selected route.

The route must be generated from interleaved 1--8-object measurements for the
specific engine, power mode, concurrency, and model. The current deployed
TV5M/11M/21M plans have no measured bucket crossover, so their provisional
safe table is all b1:

```text
1,1,1,1,1,1,1,1
```

The router is infrastructure, not an acceleration claim. It is promoted only
if static/shared-image/CUDA-Graph candidates make b2 or b4 faster at a real
object count while preserving at least 95% quality.
