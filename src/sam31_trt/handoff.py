from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .gi_client import DetectResponse
from .rle import decode_coco_rle, mask_to_box


@dataclass(frozen=True)
class HandoffObject:
    label: str
    score: float
    box: tuple[float, float, float, float]
    mask: np.ndarray


def select_handoff_objects(
    response: DetectResponse,
    *,
    max_objects: int = 8,
    min_area: int = 25,
) -> tuple[HandoffObject, ...]:
    if max_objects < 1:
        raise ValueError("max_objects must be positive")
    selected: list[HandoffObject] = []
    seen: set[tuple[int, int, int, int]] = set()
    for detected in sorted(response.objects, key=lambda value: value.score, reverse=True):
        mask = decode_coco_rle(detected.mask)
        if mask.shape != (response.height, response.width):
            raise ValueError("detect mask dimensions do not match response")
        box = mask_to_box(mask, min_area=min_area)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        clamped = (
            max(0.0, min(x0, response.width - 1.0)),
            max(0.0, min(y0, response.height - 1.0)),
            max(0.0, min(x1, response.width - 1.0)),
            max(0.0, min(y1, response.height - 1.0)),
        )
        key = tuple(int(value) for value in clamped)
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            HandoffObject(detected.label, detected.score, clamped, mask)
        )
        if len(selected) >= max_objects:
            break
    return tuple(selected)
