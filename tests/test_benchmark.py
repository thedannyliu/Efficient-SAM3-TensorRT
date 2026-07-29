from __future__ import annotations

import unittest

from sam31_trt.benchmark import percentile, summarize_rows


class BenchmarkSummaryTest(unittest.TestCase):
    def test_percentile_interpolates(self) -> None:
        self.assertEqual(percentile([1, 2, 3], 0.5), 2)
        self.assertEqual(percentile([1, 3], 0.5), 2)

    def test_completed_fps_uses_timestamps(self) -> None:
        rows = [
            {"stamp_ns": 0, "inference_ms": 100, "dropped": 9},
            {"stamp_ns": 1_000_000_000, "inference_ms": 10, "dropped": 1},
            {"stamp_ns": 1_100_000_000, "inference_ms": 20, "dropped": 2},
            {"stamp_ns": 1_200_000_000, "inference_ms": 30, "dropped": 3},
        ]
        result = summarize_rows(rows, warmup=1)
        self.assertAlmostEqual(result["completed_output_fps"], 10.0)
        self.assertEqual(result["inference_ms"]["mean"], 20.0)
        self.assertEqual(result["dropped_frames"], 6)
