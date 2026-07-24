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

End-to-end candidates use `TensorRTVisionTrunk` to replace only
`detector.backbone.vision_backbone.trunk` inside the official predictor. The
TensorRT output remains a CUDA tensor and feeds the three original SAM3.1 necks
without a host copy. This is the path used for final mIoU retention; standalone
vision feature cosine is only a fast sensitivity filter.

- `11461938`: FP16 TensorRT vision, end-to-end SA-V mIoU, depends on `11461852`.
- `11461939`: FP8 TensorRT vision, end-to-end SA-V mIoU, depends on `11461875`.
- `11461940`: INT8 TensorRT vision, end-to-end SA-V mIoU, depends on `11461876`.
