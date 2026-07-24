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

