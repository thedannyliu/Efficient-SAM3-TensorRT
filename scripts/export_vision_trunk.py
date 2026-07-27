#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from sam31_trt.upstream_compat import validate_vision_state_mismatch


PREFIX = "detector.backbone.vision_backbone.trunk."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sam3-repo", type=Path, required=True)
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--precision", choices=("fp32", "fp16"), default="fp16")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.sam3_repo.resolve()))
    from sam3.model import vitdet
    from sam3.model_builder import _create_vit_backbone

    # Upstream's inference-only fused MLP always returns BF16. Replace it only
    # in this export process so FP32 reference and FP16 ONNX have consistent
    # activation/weight dtypes. End-to-end task mIoU remains the acceptance gate.
    def export_addmm_act(activation, linear, value):
        return activation()(linear(value))

    vitdet.addmm_act = export_addmm_act

    checkpoint = torch.load(
        args.checkpoint, map_location="cpu", mmap=True, weights_only=True
    )
    state = {
        name.removeprefix(PREFIX): value
        for name, value in checkpoint.items()
        if name.startswith(PREFIX)
    }
    model = _create_vit_backbone(use_fa3=False, use_rope_real=True)
    missing, unexpected = model.load_state_dict(state, strict=False)
    derived_rope_buffers = validate_vision_state_mismatch(missing, unexpected)
    model = model.cuda().eval()
    torch.manual_seed(20260724)
    input_fp32 = torch.randn(1, 3, 1008, 1008, device="cuda")
    with torch.inference_mode():
        output_fp32 = model(input_fp32)[0]

    dtype = torch.float16 if args.precision == "fp16" else torch.float32
    model = model.to(dtype=dtype)
    model_input = input_fp32.to(dtype=dtype)
    with torch.inference_mode():
        native_output = model(model_input)[0]

    args.onnx.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        (model_input,),
        args.onnx,
        input_names=["image"],
        output_names=["embedding"],
        opset_version=18,
        dynamo=True,
        external_data=True,
    )
    args.reference.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "input": model_input.cpu(),
            "native_output": native_output.cpu(),
            "fp32_output": output_fp32.cpu(),
        },
        args.reference,
    )
    metadata = {
        "component": "detector.backbone.vision_backbone.trunk",
        "precision": args.precision,
        "input_shape": list(model_input.shape),
        "output_shape": list(native_output.shape),
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "checkpoint_keys": len(state),
        "derived_rope_buffers": len(derived_rope_buffers),
        "onnx": str(args.onnx),
        "reference": str(args.reference),
    }
    args.onnx.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
