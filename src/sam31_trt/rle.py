from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _decode_compressed_counts(encoded: str | bytes) -> list[int]:
    data = encoded.encode("ascii") if isinstance(encoded, str) else encoded
    counts: list[int] = []
    position = 0
    while position < len(data):
        value = 0
        shift = 0
        while True:
            current = data[position] - 48
            position += 1
            value |= (current & 0x1F) << (5 * shift)
            more = current & 0x20
            shift += 1
            if not more:
                if current & 0x10:
                    value |= -1 << (5 * shift)
                break
            if position >= len(data):
                raise ValueError("truncated compressed RLE")
        if len(counts) > 2:
            value += counts[-2]
        if value < 0:
            raise ValueError("negative compressed RLE count")
        counts.append(value)
    return counts


def decode_coco_rle(rle: dict[str, Any]) -> np.ndarray:
    size = rle.get("size")
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        raise ValueError("RLE size must be [height, width]")
    height, width = int(size[0]), int(size[1])
    if height <= 0 or width <= 0:
        raise ValueError("RLE dimensions must be positive")
    raw_counts = rle.get("counts")
    counts: Iterable[int]
    if isinstance(raw_counts, (str, bytes)):
        counts = _decode_compressed_counts(raw_counts)
    elif isinstance(raw_counts, list):
        counts = (int(value) for value in raw_counts)
    else:
        raise ValueError("RLE counts must be a list or compressed string")

    flat = np.zeros(height * width, dtype=np.uint8)
    offset = 0
    foreground = False
    for count in counts:
        if count < 0 or offset + count > flat.size:
            raise ValueError("RLE counts exceed mask size")
        if foreground:
            flat[offset : offset + count] = 1
        offset += count
        foreground = not foreground
    if offset != flat.size:
        raise ValueError("RLE counts do not fill mask")
    return flat.reshape((height, width), order="F")


def mask_to_box(mask: np.ndarray, min_area: int = 25) -> tuple[float, float, float, float] | None:
    binary = np.asarray(mask).astype(bool)
    if binary.ndim != 2:
        raise ValueError("mask must be two-dimensional")
    if int(binary.sum()) < min_area:
        return None
    y, x = np.nonzero(binary)
    return float(x.min()), float(y.min()), float(x.max()), float(y.max())
