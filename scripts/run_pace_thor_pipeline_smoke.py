#!/usr/bin/env python3

from __future__ import annotations

import json

from sam31_trt.benchmark import summarize_rows
from sam31_trt.gi_client import DetectObject, DetectResponse
from sam31_trt.handoff import select_handoff_objects


def rectangle_rle(
    height: int, width: int, x0: int, y0: int, x1: int, y1: int
) -> dict[str, object]:
    flat = [
        int(x0 <= x <= x1 and y0 <= y <= y1)
        for x in range(width)
        for y in range(height)
    ]
    counts: list[int] = []
    value = 0
    run = 0
    for item in flat:
        if item == value:
            run += 1
        else:
            counts.append(run)
            run = 1
            value = item
    counts.append(run)
    return {"size": [height, width], "counts": counts}


def main() -> None:
    response = DetectResponse(
        width=64,
        height=48,
        detect_ms=12.0,
        objects=(
            DetectObject("monitor", 0.95, rectangle_rle(48, 64, 4, 5, 30, 35)),
            DetectObject("keyboard", 0.85, rectangle_rle(48, 64, 20, 36, 55, 45)),
        ),
    )
    handoff = select_handoff_objects(response)
    if len(handoff) != 2:
        raise RuntimeError("null backend did not produce two handoff boxes")
    rows = [
        {
            "stamp_ns": index * 50_000_000,
            "inference_ms": 30.0,
            "source_age_ms": 45.0,
            "dropped": 0,
        }
        for index in range(1, 12)
    ]
    summary = summarize_rows(rows, warmup=1)
    output = {
        "backend": "null",
        "handoff": [
            {"label": item.label, "score": item.score, "box": item.box}
            for item in handoff
        ],
        "summary": summary,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
