from __future__ import annotations

import unittest

from sam31_trt.gi_client import DetectObject, DetectResponse
from sam31_trt.handoff import select_handoff_objects


def rectangle_rle(
    height: int, width: int, x0: int, y0: int, x1: int, y1: int
) -> dict[str, object]:
    values = []
    for x in range(width):
        for y in range(height):
            values.append(int(x0 <= x <= x1 and y0 <= y <= y1))
    counts = []
    current = 0
    run = 0
    for value in values:
        if value == current:
            run += 1
        else:
            counts.append(run)
            run = 1
            current = value
    counts.append(run)
    return {"size": [height, width], "counts": counts}


class HandoffSelectionTest(unittest.TestCase):
    def test_sorts_caps_filters_and_deduplicates(self) -> None:
        response = DetectResponse(
            width=20,
            height=20,
            detect_ms=4.0,
            objects=(
                DetectObject("low", 0.2, rectangle_rle(20, 20, 0, 0, 5, 5)),
                DetectObject("best", 0.9, rectangle_rle(20, 20, 8, 8, 15, 15)),
                DetectObject("duplicate", 0.8, rectangle_rle(20, 20, 8, 8, 15, 15)),
                DetectObject("tiny", 1.0, rectangle_rle(20, 20, 0, 0, 1, 1)),
            ),
        )
        selected = select_handoff_objects(response, max_objects=2, min_area=25)
        self.assertEqual([item.label for item in selected], ["best", "low"])
        self.assertEqual(selected[0].box, (8.0, 8.0, 15.0, 15.0))

    def test_requires_matching_dimensions(self) -> None:
        response = DetectResponse(
            width=20,
            height=20,
            detect_ms=0.0,
            objects=(
                DetectObject("bad", 1.0, rectangle_rle(10, 10, 0, 0, 5, 5)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "dimensions"):
            select_handoff_objects(response)
