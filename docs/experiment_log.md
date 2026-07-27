# Experiment log

## Protocol

- Accuracy reference: native SAM 3.1 official BF16 runtime with one positive
  point on frame 0. The official predictor enters a persistent BF16 autocast
  context and also hard-codes BF16 around `add_prompt`.
- Task metric: mean binary mask IoU on annotated SA-V frames.
- Deployment fidelity: mean binary IoU between TensorRT and PyTorch masks.
- Acceptance: candidate task mIoU / official BF16 task mIoU >= 0.90.
- Timing: synchronize CUDA immediately before and after each propagation step.
- Generated artifacts stay under ignored `results/`, `logs/`, and `checkpoints/`.

## Planned search order

1. Native FP32, BF16, FP16 and `torch.compile` baselines.
2. Export compatibility and FP16 TensorRT engines by component.
3. One-at-a-time FP8/INT8 sensitivity for vision encoder, detector transformer,
   multiplex memory attention, memory encoder, prompt path, and mask decoder.
4. Per-block sensitivity inside the components that dominate latency.
5. Accumulate low-sensitivity precision changes and confirm the Pareto candidates
   end to end on the same GPU.

## Runs

- `11461819`: FP32 native smoke, H100, `embers`, pending.
- `11461821`: FP32 native smoke, H200, `embers`, pending.
- `11461852`: FP16 vision-trunk ONNX/TensorRT probe, H200, `embers`, pending.
- `11461854`: FP32 native smoke, L40S, `embers`, pending.
- `11461855`: FP16 vision-trunk ONNX/TensorRT probe, L40S, `embers`, pending.
- `11461875`: full vision-trunk FP8 PTQ, H200, `embers`, depends on `11461852`.
- `11461876`: full vision-trunk INT8 PTQ, H200, `embers`, depends on `11461852`.
- `11461877`: FP16 vision-trunk ONNX/TensorRT probe, RTX Pro 6000 Blackwell,
  `embers`, pending.
- `11461878`: FP32 native smoke, RTX Pro 6000 Blackwell, `embers`, pending.
- `11461879`: A100 probe failed before model load because ModelOpt upgraded
  `setuptools` to 83, which removed `pkg_resources` still imported by upstream.
- `11461880`: A100 baseline hit the same environment failure.
- `11461885[0-3]`: four FP8 vision block-group sensitivity runs (blocks
  0-7, 8-15, 16-23, 24-31), H200, `embers`, depends on `11461852`.
- `11461896`: official BF16 native reference, H200, `embers`, pending.
- `11461897`: official BF16 native reference, L40S, `embers`, pending.

The first submission attempt for the 32 individual vision-block FP8 array was
rejected by PACE with `QOSMaxSubmitJobPerUserLimit`. The implementation is in
`jobs/pace_vision_blocks.sbatch`; resubmit after queued `embers` work frees
submission capacity. No `inferno` jobs were used.

Fix: pin `setuptools==80.9.0`, which both retains `pkg_resources` and satisfies
ModelOpt 0.45's `setuptools>=80` requirement. Local upstream import and
`pip check` pass after the pin.

- `11461969`: A100 FP16 vision-trunk retry after the environment fix, pending.
- `11461970`: A100 official BF16 baseline retry after the environment fix,
  pending.
- `11461976[0-7]`: individual FP8 sensitivity for vision blocks 0 through 7,
  H200, `embers`, depends on `11461852`. The remaining blocks will be submitted
  in bounded batches as QOS capacity becomes available.
- `11461982[8-15]`: individual FP8 sensitivity for vision blocks 8 through 15,
  H200, `embers`, depends on `11461852`.

The blocks 16-23 batch was rejected by `QOSMaxSubmitJobPerUserLimit`; no paid
QOS fallback was used.

End-to-end candidates use `TensorRTVisionTrunk` to replace only
`detector.backbone.vision_backbone.trunk` inside the official predictor. The
TensorRT output remains a CUDA tensor and feeds the three original SAM3.1 necks
without a host copy. This is the path used for final mIoU retention; standalone
vision feature cosine is only a fast sensitivity filter.

- `11461938`: FP16 TensorRT vision, end-to-end SA-V mIoU, depends on `11461852`.
- `11461939`: FP8 TensorRT vision, end-to-end SA-V mIoU, depends on `11461875`.
- `11461940`: INT8 TensorRT vision, end-to-end SA-V mIoU, depends on `11461876`.

## 2026-07-27 compatibility iteration

All earlier jobs that reached execution failed before producing a benchmark
report. Their pending dependent jobs (`11461875`, `11461876`, `11461885`,
`11461938`-`11461940`, `11461976`, and `11461982`) were cancelled because
their prerequisites could no longer succeed.

Three upstream compatibility issues were isolated and fixed:

1. The SAM 3.1 multiplex `init_state` method does not accept
   `offload_state_to_cpu`, although the common predictor forwards it. The
   benchmark now filters session arguments against the actual method signature.
2. The checkpoint stores one complex RoPE buffer per vision block, while the
   ONNX-compatible real-valued path additionally derives real and imaginary
   buffers. Only those 64 deterministic buffers may be absent during load;
   any learned-weight mismatch still fails.
3. The upstream fused MLP always computes its first projection and GELU in
   BF16. The isolated ONNX export process replaces that fusion with the
   mathematically equivalent standard linear-plus-GELU path so FP32 reference
   and FP16 export dtypes remain consistent.

Validation after the fixes:

- `11514301`, H200 official BF16 smoke, completed. One SA-V video, one object,
  nine propagated frames and three annotated frames: 74.880 ms/frame,
  13.355 effective FPS, 0.22144 mIoU, and 8126.9 MiB peak CUDA allocation.
  This is a functional and relative-accuracy smoke, not the final dataset
  estimate.
- `11514248` reached the vision forward and exposed issue 3.
- `11514300` successfully generated the 897 MB external-data FP16 ONNX graph,
  then exposed that the official trunk returns a single-element feature list.
  The TensorRT runtime and reference writer now preserve that exact contract.
- `11514348`, corrected FP16 ONNX/TensorRT vision-trunk smoke on H200, submitted
  with `embers`.

Subsequent H200 results:

- `11514348`: full FP16 vision engine, 15.261 ms and 65.53 FPS, but rejected:
  PyTorch feature cosine was 0.03697.
- `11514622`: ONNX Runtime isolated the failure. ONNX versus PyTorch cosine was
  0.99991, while TensorRT versus the same ONNX output was 0.03689.
- The original environment had selected the CUDA 13 TensorRT wheel beside CUDA
  12.8 PyTorch. It is now pinned to `tensorrt-cu12==11.1.0.106`. Re-running the
  old engine with the CUDA 12 runtime did not alter its output, so wheel mixing
  was not the numerical root cause.
- `11514663` and `11514665`: builder optimization levels 0 and 5 with no
  auxiliary streams produced the same rejected cosine. Level 0 was 125.71 ms;
  level 5 was 15.22 ms. This rules out tactic level and multi-stream execution.
- `11514667`: full FP32 TensorRT control passed with cosine 0.999996 at
  48.924 ms (20.44 FPS).
- `11514684`: all 65 LayerNorms retained in FP32 did not improve the FP16
  engine (cosine 0.03699 at 15.23 ms).
- `11514761`: retaining attention softmax in FP32 also did not improve the
  optimization-level-0 engine (cosine 0.03677).
- `11514758`: full BF16 was 15.532 ms but had the same rejected cosine
  (0.03705). The issue is therefore not specific to FP16 mantissa width.
- `11514784`: both 16-bit engine inputs and outputs were confirmed as linear,
  non-vectorized TensorRT tensors. I/O layout is not the source of the error.
- `11514743` used a real frame for ONNX but accidentally retained the random
  input for TensorRT and is invalid. The corrected `11514748` used the same
  real SA-V frame on both paths; FP16 TensorRT versus ONNX cosine was 0.04008,
  confirming that the random stress input was not the cause.

Per-block probes use activations generated from SA-V frame
`sav_018669/00000.jpg`:

| Job | Vision block | Attention | TensorRT ms | TRT/native cosine |
| --- | ---: | --- | ---: | ---: |
| `11514794_0` | 0 | local | 0.451 | 0.96151 |
| `11514794_1` | 7 | global | 0.597 | 0.97342 |
| `11514794_2` | 31 | global | 0.599 | 0.99105 |

No isolated block fails catastrophically; small block errors accumulate across
the 32-block graph. Mixed-block prefix probes therefore use a binary search:

- `11514806`, only block 0 in FP32: cosine 0.03133.
- `11514808`, blocks 0-7 in FP32: cosine 0.05356.
- blocks 0-15 and 0-23 are the next pending prefix candidates. These use
  optimization level 0 only as a quick parity filter; accepted candidates will
  be rebuilt at level 5 for meaningful latency.

The prefix boundary and end-to-end validation were then completed:

- blocks 0-17: feature cosine 0.88591, rejected.
- blocks 0-18: feature cosine 0.90072 at 44.753 ms with level 5, but end-to-end
  mIoU retention was 0.89907, narrowly below the 0.90 task gate.
- blocks 0-19: feature cosine 0.91177 at 45.412 ms with level 5. End-to-end
  mIoU retention was 0.91123, so this is the smallest accepted FP32 prefix.
- blocks 0-23: level-5 feature cosine 0.99995 at 49.325 ms. End-to-end mIoU
  retention was 0.99899, but propagation was slower than native.
- Keeping only residual accumulation in FP32 while all block computation stayed
  FP16 did not recover parity (cosine 0.03684).

The initial one-video/eight-frame runs made first-frame and cold-start effects
look like a speedup. The benchmark now reports steady-state latency separately
by excluding the first propagated frame. A fair three-video, 32-frame H200 run
produced:

| Candidate | Steady ms | Steady FPS | mIoU | Retention |
| --- | ---: | ---: | ---: | ---: |
| Native official BF16 (`11515351`) | 72.470 | 13.799 | 0.09150 | 1.0000 |
| 0-19 TensorRT first call per session (`11515357`) | 72.167 | 13.857 | 0.08893 | 0.9719 |
| Full FP16 TensorRT first call per session (`11515358`) | 72.394 | 13.813 | 0.01035 | 0.1131 |

The accepted mixed candidate differs from native steady-state by only 0.42%,
which is below a credible speedup claim. Its mean prompt time was 293.07 ms
versus native 284.98 ms. Full FP16 prompt time was 267.26 ms but its task
accuracy is unusable. The current conclusion is therefore: TensorRT integration
works, and the 90% precision boundary is known, but no accuracy-qualified
end-to-end acceleration has yet been demonstrated.

The first attempt (`11515363`) exposed an ONNX external-data validation bug.
After fixing validation, retry `11515378` completed on one H200 with TensorRT
11.1.0.106. It starts from the correct FP32 ONNX graph and uses ModelOpt
calibration-aware FP8 Q/DQ for 193 Conv/MatMul nodes, while retaining unquantized
operations and MHA accumulation in FP32. The 16 calibration frames came from
`sav_018669`.

| Vision trunk candidate | Mean ms | Effective FPS | Cosine vs FP32 |
| --- | ---: | ---: | ---: |
| TensorRT FP32 (`11514667`) | 48.924 | 20.440 | 0.999996 |
| TensorRT full FP8 (`11515378`) | 12.977 | 77.062 | 0.037865 |

Full FP8 is 3.77x faster than the FP32 TensorRT trunk in isolation, but its
feature cosine is unusable. It therefore did not advance to end-to-end mIoU
evaluation.

While preparing partial FP8, inspection found that the selector discarded the
ONNX block hierarchy and retained only generic leaf names such as `linear_119`.
Commit `460a206` preserves the complete semantic scope, and a test confirms that
`blocks.N` remains selectable. Each eight-block regular expression now selects
exactly 48 MatMul nodes. H200 array `11515414[0-3]` evaluates blocks 0-7, 8-15,
16-23, and 24-31 independently with FP32 fallback and FP32 MHA accumulation.
It produced:

| FP8 block range | Mean ms | Cosine vs FP32 | Result |
| --- | ---: | ---: | --- |
| 0-7 | 47.021 | 0.977180 | feature pass; 4.04% faster than TRT FP32 |
| 8-15 | 49.760 | 0.988102 | accurate but 1.71% slower |
| 16-23 | 49.674 | 0.998877 | accurate but 1.53% slower |
| 24-31 | 50.591 | 0.999222 | accurate but 3.41% slower |

The full end-to-end check for blocks 0-7 is `11515450`, using the same fixed
three videos and 32 propagated frames as native run `11515351`. It retained
99.25% mIoU (`0.09082` versus `0.09150`) but steady-state propagation was
96.055 ms instead of 72.470 ms. A partially FP32 TensorRT engine is therefore
not competitive with native BF16 even when it is slightly faster than the
TensorRT FP32 reference.

Increasing FP8 coverage exposed nonlinear error accumulation:

| FP8 block range | Mean ms | Cosine vs FP32 |
| --- | ---: | ---: |
| 16-31 (`11515436`) | 42.439 | 0.813187 |
| 8-31 (`11515437`) | 27.833 | 0.054065 |
| 0-7 and 16-31 (`11515443`) | 27.206 | 0.609971 |
| all 32 blocks, level 0 (`11515476`) | 20.536 | 0.037504 |

Attention-only FP8 (`11515467`, 128 MatMul nodes) reached 20.538 ms but only
0.038853 cosine, locating the dominant sensitivity in attention. The patch
embedding Conv selected by `11515478` is unsupported by ModelOpt FP8 and
received no Q/DQ nodes; the quantizer now excludes Conv by default in FP8 mode
to report actual coverage accurately.

The next calibration jobs sample 48 frames uniformly across all three fixed
videos rather than using 16 consecutive frames from one video. Jobs `11515484`
and `11515485` screen all-block and full-scope FP8 with the broader calibration
set. Attention is also split into eight-block groups (`11515488[0-3]`) and into
projection versus attention-core MatMul (`11515491`, `11515492`). Precision
screens use TensorRT builder level 0; only passing candidates are rebuilt at
level 5 for speed measurement.

Uniform 48-frame calibration did not improve all-block FP8: `11515484` produced
0.037958 cosine versus 0.037504 with the original 16 frames. Duplicate
`11515485` was cancelled after both jobs reported the same 192 selected MatMul
nodes and 384 Q/DQ pairs.

The finer component split shows an interaction rather than one universally
unsafe operation class:

| FP8 scope | Builder | Mean ms | Cosine vs FP32 |
| --- | ---: | ---: | ---: |
| all MLP (`11515466`) | 5 | 52.030 | 0.983510 |
| all attention projections (`11515491`) | 0 | 121.847 | 0.988017 |
| all attention core MatMul (`11515492`) | 0 | 119.430 | 0.968714 |
| all attention projections + core (`11515467`) | 5 | 20.538 | 0.038853 |
| projections + MLP, core FP32 (`11515520`) | 0 | 91.153 | 0.977780 |

Builder-level-0 latency is only a fast screening metric and must not be compared
with the level-5 timings. Both attention halves pass independently, but
quantizing them consecutively collapses feature parity. The official
`disable_mha_qdq` path (`11515518`) matches the explicit projections-plus-MLP
scope at 0.977814 cosine. Formal level-5 rebuilds are `11515552` for core-only
and `11515553` for projections-plus-MLP. Job `11515517` separately checks
entropy calibration as a control.

The level-5 rebuilds completed as follows:

| Candidate | Mean ms | Effective FPS | Cosine vs FP32 |
| --- | ---: | ---: | ---: |
| attention core FP8 (`11515552`) | 46.127 | 21.679 | 0.990682 |
| projections + MLP FP8 (`11515553`) | 52.875 | 18.912 | 0.976551 |

Core-only is 6.06% faster than TensorRT FP32 but remains in the same latency
range as the blocks-0-7 engine whose measured end-to-end propagation was much
slower than native BF16. Projections-plus-MLP is slower than TensorRT FP32.
Neither advances to end-to-end testing. This leaves no accuracy-qualified PTQ
candidate that can plausibly beat native BF16 end-to-end.

Attention-only eight-block screens further show the depth sensitivity:

| Attention FP8 block range | Cosine vs FP32 |
| --- | ---: |
| 0-7 | 0.699224 |
| 8-15 | 0.463401 |
| 16-23 | 0.884360 |
| 24-31 | 0.921678 |

## INT8 control

Full INT8 job `11515606` calibrated successfully but TensorRT could not find an
implementation for the quantized patch-embedding Conv. Retrying only the 192
transformer MatMul nodes in `11515612` succeeded with max calibration:

| Candidate | Builder | Mean ms | Cosine vs FP32 |
| --- | ---: | ---: | ---: |
| INT8 blocks 0-31 (`11515612`) | 0 | 49.838 | 0.966941 |

This passes the precision screen. Level-5 rebuild `11515623` is the next formal
latency candidate. Initial 48-frame entropy jobs were cancelled after measuring
75-90 seconds of histogram work per calibration frame; at that rate they would
occupy GPUs for roughly one hour. Job `11515624` uses four uniformly spaced
frames to retain an entropy-vs-max control without delaying the main loop.

Level-5 INT8 `11515623` produced 29.116 ms, 34.345 effective FPS, and 0.965917
feature cosine. This is 1.68x faster than TensorRT FP32. The corresponding
three-video end-to-end run `11515628` retained 100.81% mIoU (`0.09224` versus
native `0.09150`) but reached 75.334 ms / 13.274 FPS steady-state versus native
72.470 ms / 13.799 FPS. It is accuracy-qualified but 3.95% slower end-to-end.
Jobs `11515634` and `11515635` rebuild the same graph with zero and three
auxiliary TensorRT streams to try to close the remaining gap.

Auxiliary streams did not materially change engine time: aux 0 produced 28.986
ms and aux 3 produced 28.991 ms, compared with 29.116 ms by the default
one-aux-stream engine. A BF16 output-boundary graph (`11515638`) also retained
0.965896 cosine and 29.125 ms standalone latency. Its end-to-end run `11516061`
improved steady-state latency from 75.334 to 74.953 ms by halving the output
embedding width, with identical 0.09224 mIoU. It remains 3.43% slower than
native BF16.

Four-frame entropy INT8 (`11515624`) produced 0.963904 cosine versus 0.966941
for max calibration and therefore did not replace the max-calibrated graph.

Two-stage mixed INT8/FP8 attempts `11516062` and `11516063` initially exposed
loss of PyTorch scope metadata after ModelOpt rewrites. Commit `14c53c9` allows
the second stage to use scopes from the original ONNX. Retry `11516071`
completed at 0.967703 cosine, but inspection of Q/DQ zero-point types showed
that ModelOpt had removed the first stage rather than retaining both data
types: the final graph contained only 130 FP8 Q nodes and no INT8 Q nodes.
Sequential ModelOpt calls therefore do not create a genuine mixed INT8/FP8
graph and the result was not promoted.
