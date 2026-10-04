#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import onnx


OUTPUT_DTYPES = {
    "bf16": onnx.TensorProto.BFLOAT16,
    "fp16": onnx.TensorProto.FLOAT16,
}


def set_output_dtype(model: onnx.ModelProto, dtype: int) -> None:
    if len(model.graph.output) != 1:
        raise ValueError(f"expected one graph output, got {len(model.graph.output)}")
    output = model.graph.output[0]
    source_name = output.name
    output.name = f"{source_name}_cast"
    output.type.tensor_type.elem_type = dtype
    model.graph.node.append(
        onnx.helper.make_node(
            "Cast",
            [source_name],
            [output.name],
            name="output_precision_cast",
            to=dtype,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dtype", choices=OUTPUT_DTYPES, required=True)
    args = parser.parse_args()

    model = onnx.load(args.onnx, load_external_data=False)
    set_output_dtype(model, OUTPUT_DTYPES[args.dtype])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, args.output)
    onnx.checker.check_model(str(args.output))


if __name__ == "__main__":
    main()
