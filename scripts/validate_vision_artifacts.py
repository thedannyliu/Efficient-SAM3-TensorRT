#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import onnxruntime as ort
import torch

from sam31_trt.runtime import TensorRTVisionTrunk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--image", type=Path)
    return parser.parse_args()


def metrics(candidate: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    candidate = candidate.astype(np.float32).reshape(-1)
    reference = reference.astype(np.float32).reshape(-1)
    difference = np.abs(candidate - reference)
    return {
        "max_abs_error": float(difference.max()),
        "mean_abs_error": float(difference.mean()),
        "cosine": float(
            np.dot(candidate, reference)
            / (np.linalg.norm(candidate) * np.linalg.norm(reference))
        ),
    }


def statistics(value: np.ndarray) -> dict[str, float]:
    value = value.astype(np.float32)
    return {
        "minimum": float(value.min()),
        "maximum": float(value.max()),
        "mean": float(value.mean()),
        "standard_deviation": float(value.std()),
    }


def load_normalized_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"failed to read image: {path}")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, (1008, 1008), interpolation=cv2.INTER_LINEAR)
    image = image.astype(np.float32) / 255.0
    image = (image - 0.5) / 0.5
    return image.transpose(2, 0, 1)[None].astype(np.float16)


def main() -> None:
    args = parse_args()
    reference = torch.load(args.reference, map_location="cpu", weights_only=True)
    image = (
        load_normalized_image(args.image)
        if args.image
        else reference["input"].numpy()
    )
    native = None if args.image else reference["native_output"].numpy()

    session = ort.InferenceSession(
        str(args.onnx),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    start = perf_counter()
    onnx_output = session.run(None, {session.get_inputs()[0].name: image})[0]
    onnx_ms = (perf_counter() - start) * 1000

    engine = TensorRTVisionTrunk(args.engine)
    image_cuda = reference["input"].cuda()
    torch.cuda.synchronize()
    start = perf_counter()
    trt_output = engine(image_cuda)[0]
    torch.cuda.synchronize()
    trt_ms = (perf_counter() - start) * 1000
    trt_output = trt_output.cpu().numpy()

    report = {
        "onnx_providers": session.get_providers(),
        "onnx_latency_ms_first": onnx_ms,
        "tensorrt_latency_ms_first": trt_ms,
        "input_kind": "real_image" if args.image else "random_stress",
        "image": str(args.image) if args.image else None,
        "native_statistics": None if native is None else statistics(native),
        "onnx_statistics": statistics(onnx_output),
        "tensorrt_statistics": statistics(trt_output),
        "onnx_vs_native": None if native is None else metrics(onnx_output, native),
        "tensorrt_vs_native": None if native is None else metrics(trt_output, native),
        "tensorrt_vs_onnx": metrics(trt_output, onnx_output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
