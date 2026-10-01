#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

import torch
import torch.nn.functional as functional

from sam31_trt.upstream_compat import validate_vision_state_mismatch


PREFIX = "detector.backbone.vision_backbone.trunk."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sam3-repo", type=Path, required=True)
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument(
        "--precision", choices=("fp32", "fp16", "bf16"), default="fp16"
    )
    parser.add_argument("--fp32-layernorm", action="store_true")
    parser.add_argument("--fp32-softmax", action="store_true")
    parser.add_argument("--fp32-blocks", default="")
    parser.add_argument("--fp32-residuals", action="store_true")
    return parser.parse_args()


def fp32_layer_norm_forward(self, value):
    output = functional.layer_norm(
        value.float(),
        self.normalized_shape,
        None if self.weight is None else self.weight.float(),
        None if self.bias is None else self.bias.float(),
        self.eps,
    )
    return output.to(value.dtype)


def configure_fp32_layer_norms(model: torch.nn.Module) -> int:
    count = 0
    for module in model.modules():
        if isinstance(module, torch.nn.LayerNorm):
            module.forward = types.MethodType(fp32_layer_norm_forward, module)
            count += 1
    return count


def fp32_softmax_sdpa(query, key, value):
    scores = torch.matmul(query, key.transpose(-2, -1)) * query.shape[-1] ** -0.5
    probabilities = torch.softmax(scores.float(), dim=-1).to(query.dtype)
    return torch.matmul(probabilities, value)


class FP32Block(torch.nn.Module):
    def __init__(self, block: torch.nn.Module) -> None:
        super().__init__()
        self.block = block.float()

    def forward(self, value):
        return self.block(value.float()).to(value.dtype)


class FP32ResidualBlock(torch.nn.Module):
    def __init__(self, block: torch.nn.Module, partition, unpartition) -> None:
        super().__init__()
        self.block = block
        self.partition = partition
        self.unpartition = unpartition

    def forward(self, value):
        compute_dtype = self.block.norm1.weight.dtype
        shortcut = value.float()
        branch = self.block.norm1(value.to(compute_dtype))
        if self.block.window_size > 0:
            height, width = branch.shape[1:3]
            branch, padded_shape = self.partition(branch, self.block.window_size)
        branch = self.block.ls1(self.block.attn(branch))
        if self.block.window_size > 0:
            branch = self.unpartition(
                branch,
                self.block.window_size,
                padded_shape,
                (height, width),
            )
        residual = shortcut + self.block.dropout(self.block.drop_path(branch)).float()
        branch = self.block.mlp(
            self.block.norm2(residual.to(compute_dtype))
        )
        branch = self.block.ls2(branch)
        return residual + self.block.dropout(self.block.drop_path(branch)).float()


def parse_fp32_blocks(value: str) -> list[int]:
    if not value:
        return []
    blocks = sorted({int(item) for item in value.split(",")})
    if blocks[0] < 0 or blocks[-1] >= 32:
        raise ValueError(f"FP32 block index outside [0, 31]: {blocks}")
    return blocks


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
    if args.fp32_softmax:
        vitdet.F.scaled_dot_product_attention = fp32_softmax_sdpa

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
    fp32_layer_norms = configure_fp32_layer_norms(model) if args.fp32_layernorm else 0
    model = model.cuda().eval()
    torch.manual_seed(20260724)
    input_fp32 = torch.randn(1, 3, 1008, 1008, device="cuda")
    with torch.inference_mode():
        output_fp32 = model(input_fp32)[0]

    dtype = {
        "fp32": torch.float32,
        "fp16": torch.float16,
        "bf16": torch.bfloat16,
    }[args.precision]
    model = model.to(dtype=dtype)
    if args.fp32_residuals:
        for block_index, block in enumerate(model.blocks):
            model.blocks[block_index] = FP32ResidualBlock(
                block, vitdet.window_partition, vitdet.window_unpartition
            )
    fp32_blocks = parse_fp32_blocks(args.fp32_blocks)
    if args.fp32_residuals and fp32_blocks:
        raise ValueError("--fp32-residuals and --fp32-blocks are mutually exclusive")
    for block_index in fp32_blocks:
        model.blocks[block_index] = FP32Block(model.blocks[block_index])
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
        "fp32_layer_norms": fp32_layer_norms,
        "fp32_softmax": args.fp32_softmax,
        "fp32_blocks": fp32_blocks,
        "fp32_residuals": args.fp32_residuals,
        "onnx": str(args.onnx),
        "reference": str(args.reference),
    }
    args.onnx.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
