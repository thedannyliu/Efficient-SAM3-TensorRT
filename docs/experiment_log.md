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

The next candidate (`11515363`) starts from the correct FP32 ONNX graph and uses
ModelOpt calibration-aware FP8 Q/DQ for Conv/MatMul while retaining unquantized
operations and MHA accumulation in FP32. This avoids converting the entire graph
to FP16 merely as a side effect of quantization.
