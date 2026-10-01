#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

from sam31_trt.upstream_compat import validate_vision_state_mismatch


PREFIX = "detector.backbone.vision_backbone.trunk."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sam3-repo", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--block", type=int, choices=range(32), required=True)
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    return parser.parse_args()


def load_image(path: Path) -> torch.Tensor:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"failed to read image: {path}")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, (1008, 1008), interpolation=cv2.INTER_LINEAR)
    image = image.astype(np.float32) / 255.0
    image = (image - 0.5) / 0.5
    return torch.from_numpy(image.transpose(2, 0, 1)[None]).cuda()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.sam3_repo.resolve()))
    from sam3.model import vitdet
    from sam3.model_builder import _create_vit_backbone

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
    validate_vision_state_mismatch(missing, unexpected)
    model = model.cuda().eval()

    captured: dict[str, torch.Tensor] = {}

    def capture_input(_module, values):
        captured["input"] = values[0].detach()

    handle = model.blocks[args.block].register_forward_pre_hook(capture_input)
    with torch.inference_mode():
        model(load_image(args.image))
    handle.remove()

    block = model.blocks[args.block]
    block_input_fp32 = captured["input"]
    with torch.inference_mode():
        output_fp32 = block(block_input_fp32)

    block = block.half()
    block_input = block_input_fp32.half()
    with torch.inference_mode():
        native_output = block(block_input)

    args.onnx.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        block,
        (block_input,),
        args.onnx,
        input_names=["activation"],
        output_names=["output"],
        opset_version=18,
        dynamo=True,
        external_data=True,
    )
    args.reference.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "input": block_input.cpu(),
            "native_output": native_output.cpu(),
            "fp32_output": output_fp32.cpu(),
        },
        args.reference,
    )
    metadata = {
        "block": args.block,
        "attention": "global" if args.block in (7, 15, 23, 31) else "local",
        "input_shape": list(block_input.shape),
        "output_shape": list(native_output.shape),
        "onnx": str(args.onnx),
        "reference": str(args.reference),
    }
    args.onnx.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
