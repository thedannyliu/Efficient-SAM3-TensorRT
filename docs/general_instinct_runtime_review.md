# General Instinct runtime review

This note describes the locally licensed InstinctSAM Thor delivery without
redistributing its source, weights, or TensorRT artifacts. The delivery is
restricted to research, evaluation, and testing.

## TensorRT boundary

The delivered application is a PyTorch/Torch-TensorRT hybrid, not a complete
TensorRT C++ implementation.

```text
camera
  -> resize/normalize in PyTorch
  -> distilled Hiera-L vision trunk in Torch-TensorRT FP16
  -> neck, detector/prompt/mask heads in PyTorch
  -> SAM3.0 per-object or SAM3.1 multiplex tracker in PyTorch
  -> CPU overlay/JPEG
```

Torch-TensorRT loads a serialized exported-program artifact and exposes its
module as the replacement for the original vision trunk. Input is cast to FP16
by a thin PyTorch wrapper. Input resolution is static in the compiled graph, so
tracking and detection use separate engines:

- 768x768: every-frame tracking trunk;
- 1152x1152: higher-quality detection trunk.

No INT8/FP8 path, calibration set, quantization-aware training, per-layer
precision search, custom TensorRT plugin, or CUDA Graph was found in the
delivered runtime. The SAM3.1 multiplex model is explicitly built without
`torch.compile`.

## Effective optimizations

| Optimization | Purpose/effect |
|---|---|
| Distilled Hiera-L trunk | Roughly one third of the teacher vision parameters |
| FP16 Torch-TensorRT trunk | Accelerates the largest every-frame vision component |
| 768 tracking / 1152 detection | Spend resolution where the first mask affects the whole track |
| Detection every 12 frames | Amortizes the higher-resolution detector cost |
| Memory encoder stride 2 | Vendor note reports about 40% tracker speed improvement |
| Top-32 mask queries | Avoids mask-head work for queries that will not be retained |
| Latest-frame camera reader | Prevents an old-frame backlog |
| Backbone/detector feature cache | Reuses a frame's features across prompt operations |
| SAM3.0/SAM3.1 crossover at two objects | Avoids multiplex overhead at one object and keeps multi-object cost nearly flat |
| Shared trunk and resident predictors | Avoids a second trunk copy and mode-switch model loading |
| Separate render thread | Keeps overlay/JPEG work out of the inference loop |

The delivery reports about 10.5 FPS for 1–14 objects on its supported Thor
software stack. Our R38.4 compatibility baseline measured 10.829 FPS at one
object and 10.942 FPS at two objects headless. The two-object synthetic masks
were lost, so that row is a performance result, not a quality result.

## Quality and deployment limitations

The delivery reports cgF1 0.348 on its 6,544-pair SA-Co/Gold subset versus
0.520 for the SAM3 teacher: about 67% of teacher quality. Its own documentation
identifies small objects as the largest weakness. This does not meet a
90–95%-of-teacher target.

The shipped engines target SM110 with TensorRT 10.16 and L4T r39.2. The current
Thor runs L4T R38.4 and prints cross-device engine-plan warnings. Results here
are compatibility measurements until the engines are rebuilt on this exact
Thor software stack or the host is moved to the supported stack.

The remaining PyTorch detector/tracker control flow, Python ROS/HTTP bridge,
CPU image copies, JPEG, and display path leave meaningful optimization space.

## Recommendation for our SAM3 TensorRT pipeline

Use InstinctSAM as a design and speed baseline, but build our own pipeline for
the 90–95% quality target:

1. Freeze a reproducible teacher-quality set with text, point, box, small-object,
   and video tracking cases.
2. Profile image encoder, neck, text/prompt encoder, detector decoder, mask
   head, memory encoder, and tracker separately.
3. Establish a full-FP16 TensorRT baseline before lower precision.
4. Search FP8/INT8 per component and per layer, keeping normalization, softmax,
   coordinate transforms, memory state, and sensitive mask logits in FP16/FP32
   when required by the quality constraint.
5. Distill and/or QAT only the components that fail the post-training
   quantization quality gate.
6. Use optimization profiles for supported prompt/object counts and fixed
   camera resolutions.
7. Add custom plugins or CUDA kernels only for profiler-confirmed unsupported
   or dominant operations.
8. Keep a small C++ orchestrator for dynamic tracker state if forcing the whole
   video loop into one TensorRT graph adds complexity without speed.

