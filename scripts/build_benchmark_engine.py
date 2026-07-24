#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

import numpy as np
import tensorrt as trt
import torch


LOGGER = trt.Logger(trt.Logger.INFO)
TORCH_DTYPES = {
    trt.float16: torch.float16,
    trt.float32: torch.float32,
    trt.int32: torch.int32,
    trt.int64: torch.int64,
    trt.bool: torch.bool,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--workspace-gib", type=int, default=64)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    return parser.parse_args()


def cosine(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(
        torch.nn.functional.cosine_similarity(
            left.float().flatten(), right.float().flatten(), dim=0
        )
    )


def main() -> None:
    args = parse_args()
    builder = trt.Builder(LOGGER)
    flags = 1 << int(trt.NetworkDefinitionCreationFlag.STRONGLY_TYPED)
    network = builder.create_network(flags)
    parser = trt.OnnxParser(network, LOGGER)
    if not parser.parse_from_file(str(args.onnx)):
        errors = "\n".join(str(parser.get_error(i)) for i in range(parser.num_errors))
        raise RuntimeError(f"ONNX parse failed:\n{errors}")
    config = builder.create_builder_config()
    config.builder_optimization_level = 5
    config.set_memory_pool_limit(
        trt.MemoryPoolType.WORKSPACE, args.workspace_gib * 1024**3
    )
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT engine build failed")
    args.engine.parent.mkdir(parents=True, exist_ok=True)
    args.engine.write_bytes(serialized)

    runtime = trt.Runtime(LOGGER)
    engine = runtime.deserialize_cuda_engine(serialized)
    context = engine.create_execution_context()
    reference = torch.load(args.reference, map_location="cpu", weights_only=True)
    tensors: dict[str, torch.Tensor] = {}
    output_names = []
    for index in range(engine.num_io_tensors):
        name = engine.get_tensor_name(index)
        mode = engine.get_tensor_mode(name)
        dtype = TORCH_DTYPES[engine.get_tensor_dtype(name)]
        if mode == trt.TensorIOMode.INPUT:
            tensor = reference["input"].to(device="cuda", dtype=dtype).contiguous()
            context.set_input_shape(name, tuple(tensor.shape))
        else:
            shape = tuple(context.get_tensor_shape(name))
            tensor = torch.empty(shape, device="cuda", dtype=dtype)
            output_names.append(name)
        tensors[name] = tensor
        if not context.set_tensor_address(name, tensor.data_ptr()):
            raise RuntimeError(f"failed to bind {name}")

    stream = torch.cuda.current_stream().cuda_stream
    for _ in range(args.warmup):
        if not context.execute_async_v3(stream):
            raise RuntimeError("TensorRT warmup enqueue failed")
    torch.cuda.synchronize()
    samples = []
    for _ in range(args.iterations):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        start.record()
        if not context.execute_async_v3(stream):
            raise RuntimeError("TensorRT benchmark enqueue failed")
        end.record()
        end.synchronize()
        samples.append(start.elapsed_time(end))

    output = tensors[output_names[0]]
    native = reference["native_output"].to(device="cuda", dtype=output.dtype)
    fp32 = reference["fp32_output"].to(device="cuda")
    report = {
        "onnx": str(args.onnx),
        "engine": str(args.engine),
        "engine_bytes": args.engine.stat().st_size,
        "gpu": torch.cuda.get_device_name(),
        "tensorrt_version": trt.__version__,
        "mean_latency_ms": mean(samples),
        "p50_latency_ms": float(np.percentile(samples, 50)),
        "p95_latency_ms": float(np.percentile(samples, 95)),
        "effective_fps": 1000 / mean(samples),
        "output_shape": list(output.shape),
        "native_max_abs_error": float((output - native).abs().max()),
        "native_mean_abs_error": float((output - native).abs().mean()),
        "native_cosine": cosine(output, native),
        "fp32_max_abs_error": float((output.float() - fp32).abs().max()),
        "fp32_mean_abs_error": float((output.float() - fp32).abs().mean()),
        "fp32_cosine": cosine(output, fp32),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

