#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

import cv2
import numpy as np
import onnx
from modelopt.onnx.quantization import quantize


class CalibrationReader:
    def __init__(self, samples: list[np.ndarray]) -> None:
        self.samples = samples
        self.index = 0

    def get_next(self):
        if self.index >= len(self.samples):
            return None
        sample = self.samples[self.index]
        self.index += 1
        return {"image": sample[None]}

    def get_first(self):
        return {"image": self.samples[0][None]}

    def rewind(self) -> None:
        self.index = 0

    def __iter__(self):
        for sample in self.samples:
            yield {"image": sample[None]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--calibration-dir", type=Path, required=True)
    parser.add_argument("--calibration-samples", type=int, default=16)
    parser.add_argument("--mode", choices=("fp8", "int8"), required=True)
    parser.add_argument(
        "--high-precision-dtype",
        choices=("fp32", "fp16", "bf16"),
        default="fp16",
    )
    parser.add_argument(
        "--mha-accumulation-dtype",
        choices=("fp32", "fp16"),
        default="fp16",
    )
    parser.add_argument("--scope-regex", action="append", default=[])
    parser.add_argument(
        "--op-type", action="append", choices=("Conv", "MatMul", "Gemm"), default=[]
    )
    return parser.parse_args()


def semantic_scope(node: onnx.NodeProto) -> str:
    metadata = {item.key: item.value for item in node.metadata_props}
    encoded = metadata.get("pkg.torch.onnx.name_scopes")
    if encoded:
        scopes = ast.literal_eval(encoded)
        if scopes:
            return " -> ".join(scope for scope in scopes if scope)
    return node.name.strip("/").replace("/", ".")


def evenly_spaced_paths(paths: list[Path], limit: int) -> list[Path]:
    if limit <= 0:
        raise ValueError("calibration sample limit must be positive")
    if len(paths) <= limit:
        return paths
    indices = np.linspace(0, len(paths) - 1, num=limit, dtype=int)
    return [paths[index] for index in indices]


def calibration_samples(
    root: Path, limit: int, dtype: np.dtype
) -> tuple[list[np.ndarray], list[str]]:
    paths = evenly_spaced_paths(
        sorted(
            path
            for suffix in ("*.jpg", "*.jpeg", "*.png")
            for path in root.rglob(suffix)
        ),
        limit,
    )
    samples = []
    used_paths = []
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (1008, 1008), interpolation=cv2.INTER_LINEAR)
        image = (image.astype(np.float32) / 255.0 - 0.5) / 0.5
        samples.append(np.transpose(image, (2, 0, 1)).astype(dtype))
        used_paths.append(str(path))
    if not samples:
        raise RuntimeError(f"no calibration images found under {root}")
    return samples, used_paths


def main() -> None:
    args = parse_args()
    model = onnx.load(args.onnx, load_external_data=False)
    input_type = model.graph.input[0].type.tensor_type.elem_type
    calibration_dtype = {
        onnx.TensorProto.FLOAT: np.dtype(np.float32),
        onnx.TensorProto.FLOAT16: np.dtype(np.float16),
    }.get(input_type)
    if calibration_dtype is None:
        raise RuntimeError(f"unsupported calibration input type: {input_type}")
    expressions = [re.compile(pattern) for pattern in args.scope_regex]
    op_types = set(args.op_type or ("Conv", "MatMul", "Gemm"))
    selected = []
    scopes = {}
    for node in model.graph.node:
        scope = semantic_scope(node)
        if node.op_type not in op_types:
            continue
        if expressions and not any(expression.search(scope) for expression in expressions):
            continue
        if not node.name:
            raise RuntimeError(f"selected unnamed {node.op_type} node in {scope}")
        selected.append(node.name)
        scopes[node.name] = scope
    if not selected:
        raise RuntimeError("precision selection matched no Conv/MatMul/Gemm nodes")

    samples, sample_paths = calibration_samples(
        args.calibration_dir, args.calibration_samples, calibration_dtype
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    quantize(
        str(args.onnx),
        quantize_mode=args.mode,
        calibration_data_reader=CalibrationReader(samples),
        calibration_method="max",
        calibration_eps=["cuda:0", "cpu"],
        op_types_to_quantize=sorted(op_types),
        nodes_to_quantize=selected,
        high_precision_dtype=args.high_precision_dtype,
        mha_accumulation_dtype=args.mha_accumulation_dtype,
        use_external_data_format=True,
        output_path=str(args.output),
    )
    quantized = onnx.load(args.output, load_external_data=False)
    onnx.checker.check_model(str(args.output))
    report = {
        "mode": args.mode,
        "high_precision_dtype": args.high_precision_dtype,
        "mha_accumulation_dtype": args.mha_accumulation_dtype,
        "calibration_dtype": str(calibration_dtype),
        "source": str(args.onnx),
        "output": str(args.output),
        "scope_regex": args.scope_regex,
        "op_types": sorted(op_types),
        "selected_node_count": len(selected),
        "selected_scopes": scopes,
        "calibration_samples": sample_paths,
        "quantize_linear_nodes": sum(
            node.op_type == "QuantizeLinear" for node in quantized.graph.node
        ),
        "dequantize_linear_nodes": sum(
            node.op_type == "DequantizeLinear" for node in quantized.graph.node
        ),
    }
    if report["quantize_linear_nodes"] == 0:
        raise RuntimeError("ModelOpt produced no QuantizeLinear nodes")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
