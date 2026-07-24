# Experiment log

## Protocol

- Accuracy reference: native SAM 3.1 FP32 with one positive point on frame 0.
- Task metric: mean binary mask IoU on annotated SA-V frames.
- Deployment fidelity: mean binary IoU between TensorRT and PyTorch masks.
- Acceptance: candidate task mIoU / FP32 task mIoU >= 0.90.
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
