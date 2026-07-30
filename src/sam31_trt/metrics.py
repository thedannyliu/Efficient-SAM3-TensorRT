from __future__ import annotations

import cv2
import numpy as np


def resize_binary_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape != shape:
        mask = cv2.resize(
            mask.astype(np.uint8),
            (shape[1], shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
    return mask.astype(bool)


def binary_iou(prediction: np.ndarray, target: np.ndarray) -> float:
    prediction = resize_binary_mask(prediction, target.shape)
    target = target.astype(bool)
    union = np.logical_or(prediction, target).sum()
    if union == 0:
        return 1.0
    intersection = np.logical_and(prediction, target).sum()
    return float(intersection / union)


def retention(candidate_miou: float, reference_miou: float) -> float:
    if reference_miou <= 0:
        raise ValueError("reference_miou must be positive")
    return candidate_miou / reference_miou


def runtime_metrics(value: dict[str, object]) -> dict[str, object]:
    model_ms = value.get("tracker_total_ms")
    if model_ms is None:
        components = (value.get("backbone_ms"), value.get("tracker_ms"))
        present = [float(item) for item in components if item is not None]
        model_ms = sum(present) if present else None
    else:
        model_ms = float(model_ms)

    tracking_fps = value.get(
        "tracking_fps",
        value.get("fps", value.get("processed_fps")),
    )
    tracking_fps = (
        float(tracking_fps) if tracking_fps is not None else None
    )
    capacity_fps = (
        1000.0 / float(model_ms)
        if model_ms is not None and float(model_ms) > 0.0
        else None
    )
    objects = value.get("objects")
    object_count = (
        len(objects)
        if isinstance(objects, list)
        else int(value.get("num_objects", 0))
    )
    return {
        "model_ms": model_ms,
        "tracking_fps": tracking_fps,
        "capacity_fps": capacity_fps,
        "source_age_ms": value.get("source_age_ms"),
        "backend": value.get("tracker_backend", value.get("backend")),
        "object_count": object_count,
    }
