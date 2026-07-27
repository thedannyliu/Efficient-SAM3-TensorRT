#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

import cv2
import numpy as np
import torch

from sam31_trt.metrics import binary_iou
from sam31_trt.upstream_compat import supported_kwargs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sam3-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--precision",
        choices=("official_bf16", "fp32", "fp16", "bf16"),
        default="official_bf16",
    )
    parser.add_argument("--max-videos", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=16)
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--use-fa3", action="store_true")
    parser.add_argument("--vision-engine", type=Path)
    parser.add_argument("--vision-engine-call-limit", type=int)
    return parser.parse_args()


def autocast_context(precision: str):
    if precision == "fp16":
        return torch.autocast("cuda", dtype=torch.float16)
    if precision == "bf16":
        return torch.autocast("cuda", dtype=torch.bfloat16)
    return nullcontext()


def synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def read_mask(item: dict[str, Any], frame_index: int) -> np.ndarray | None:
    path = (
        Path(item["annotations_dir"])
        / str(item["object_id"])
        / f"{frame_index:05d}.png"
    )
    if not path.exists():
        return None
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return None if mask is None else mask > 0


def select_mask(outputs: dict[str, Any], object_id: int) -> np.ndarray:
    masks = np.asarray(outputs.get("out_binary_masks", []))
    ids = np.asarray(outputs.get("out_obj_ids", []))
    if masks.ndim == 2:
        return masks.astype(bool)
    if masks.shape[0] == 0:
        return np.zeros((1, 1), dtype=bool)
    matches = np.flatnonzero(ids == object_id)
    return masks[int(matches[0]) if matches.size else 0].astype(bool)


def start_session(predictor: Any, resource_path: Path) -> str:
    init_kwargs = supported_kwargs(
        predictor.model.init_state,
        {
            "resource_path": str(resource_path),
            "offload_video_to_cpu": False,
            "offload_state_to_cpu": False,
            "async_loading_frames": False,
        },
    )
    state = predictor.model.init_state(**init_kwargs)
    session_id = str(uuid.uuid4())
    now = time.time()
    predictor._all_inference_states[session_id] = {
        "state": state,
        "session_id": session_id,
        "start_time": now,
        "last_use_time": now,
    }
    return session_id


def profile_video(
    predictor: Any,
    item: dict[str, Any],
    precision: str,
    max_frames: int,
) -> dict[str, Any]:
    frame_dir = Path(item["frames_dir"]).resolve()
    session_id = start_session(predictor, frame_dir)
    object_id = 1
    point = torch.tensor(
        [[item["point"][0] / item["width"], item["point"][1] / item["height"]]],
        dtype=torch.float32,
    )
    labels = torch.tensor([int(item.get("point_label", 1))], dtype=torch.int32)
    try:
        synchronize()
        start = perf_counter()
        with autocast_context(precision):
            predictor.handle_request(
                {
                    "type": "add_prompt",
                    "session_id": session_id,
                    "frame_index": int(item["prompt_frame_index"]),
                    "points": point,
                    "point_labels": labels,
                    "obj_id": object_id,
                }
            )
        synchronize()
        prompt_ms = (perf_counter() - start) * 1000

        iterator = predictor.handle_stream_request(
            {
                "type": "propagate_in_video",
                "session_id": session_id,
                "propagation_direction": "forward",
                "start_frame_index": int(item["prompt_frame_index"]),
                "max_frame_num_to_track": max_frames,
            }
        )
        frame_rows = []
        while True:
            synchronize()
            start = perf_counter()
            try:
                with autocast_context(precision):
                    response = next(iterator)
            except StopIteration:
                break
            synchronize()
            step_ms = (perf_counter() - start) * 1000
            frame_index = int(response["frame_index"])
            prediction = select_mask(response["outputs"], object_id)
            target = read_mask(item, frame_index)
            frame_rows.append(
                {
                    "frame_index": frame_index,
                    "latency_ms": step_ms,
                    "iou": None if target is None else binary_iou(prediction, target),
                }
            )
    finally:
        predictor.handle_request({"type": "close_session", "session_id": session_id})

    latencies = [row["latency_ms"] for row in frame_rows]
    ious = [row["iou"] for row in frame_rows if row["iou"] is not None]
    return {
        "video_id": item["video_id"],
        "object_id": item["object_id"],
        "prompt_ms": prompt_ms,
        "frames": len(frame_rows),
        "evaluated_frames": len(ious),
        "mean_latency_ms": mean(latencies) if latencies else None,
        "effective_fps": 1000 / mean(latencies) if latencies else None,
        "mean_iou": mean(ious) if ious else None,
        "frame_rows": frame_rows,
    }


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required")
    if str(args.sam3_repo.resolve()) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(args.sam3_repo.resolve()))
    from sam3.model_builder import build_sam3_predictor

    rows = [
        json.loads(line)
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][: args.max_videos]
    for item in rows:
        for field in ("frames_dir", "annotations_dir"):
            path = Path(item[field])
            if not path.is_absolute():
                item[field] = str((args.data_root / path).resolve())
    predictor = build_sam3_predictor(
        checkpoint_path=str(args.checkpoint.resolve()),
        version="sam3.1",
        compile=args.compile,
        warm_up=False,
        use_fa3=args.use_fa3,
        use_rope_real=True,
        async_loading_frames=False,
    )
    vision_trunk = None
    if args.vision_engine:
        from sam31_trt.runtime import LimitedCallsVisionTrunk, TensorRTVisionTrunk

        native_trunk = predictor.model.detector.backbone.vision_backbone.trunk
        vision_trunk = TensorRTVisionTrunk(args.vision_engine)
        if args.vision_engine_call_limit is not None:
            vision_trunk = LimitedCallsVisionTrunk(
                vision_trunk,
                native_trunk,
                args.vision_engine_call_limit,
            )
        predictor.model.detector.backbone.vision_backbone.trunk = vision_trunk
    if args.precision != "official_bf16" and hasattr(predictor, "bf16_context"):
        predictor.bf16_context.__exit__(None, None, None)
    torch.cuda.reset_peak_memory_stats()
    videos = [
        profile_video(predictor, item, args.precision, args.max_frames) for item in rows
    ]
    if hasattr(predictor, "shutdown"):
        predictor.shutdown()

    latency = [row["mean_latency_ms"] for row in videos if row["mean_latency_ms"]]
    ious = [row["mean_iou"] for row in videos if row["mean_iou"] is not None]
    report = {
        "schema_version": 1,
        "backend": "tensorrt-vision-sam3.1" if args.vision_engine else "pytorch-native-sam3.1",
        "vision_engine": str(args.vision_engine) if args.vision_engine else None,
        "vision_engine_call_limit": args.vision_engine_call_limit,
        "vision_engine_calls": getattr(vision_trunk, "calls", None),
        "precision": args.precision,
        "prompt_precision": "bf16",
        "compile": args.compile,
        "use_fa3": args.use_fa3,
        "checkpoint": str(args.checkpoint),
        "manifest": str(args.manifest),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(),
        "hostname": platform.node(),
        "mean_latency_ms": mean(latency) if latency else None,
        "effective_fps": 1000 / mean(latency) if latency else None,
        "mean_iou": mean(ious) if ious else None,
        "cuda_peak_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2,
        "videos": videos,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "videos"}, indent=2))


if __name__ == "__main__":
    main()
