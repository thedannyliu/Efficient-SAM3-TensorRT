import unittest

import numpy as np

from sam31_trt.metrics import binary_iou, retention, runtime_metrics


class MetricsTest(unittest.TestCase):
    def test_binary_iou(self) -> None:
        left = np.array([[1, 1], [0, 0]], dtype=bool)
        right = np.array([[1, 0], [1, 0]], dtype=bool)
        self.assertAlmostEqual(binary_iou(left, right), 1 / 3)

    def test_empty_masks_match(self) -> None:
        empty = np.zeros((2, 2), dtype=bool)
        self.assertEqual(binary_iou(empty, empty), 1.0)

    def test_retention(self) -> None:
        self.assertAlmostEqual(retention(0.72, 0.80), 0.9)
        with self.assertRaises(ValueError):
            retention(0.0, 0.0)

    def test_runtime_metrics_normalizes_instinctsam(self) -> None:
        value = runtime_metrics(
            {
                "backbone_ms": 58.0,
                "tracker_ms": 56.0,
                "fps": 8.7,
                "num_objects": 1,
                "backend": "per_object",
            }
        )
        self.assertEqual(value["model_ms"], 114.0)
        self.assertAlmostEqual(value["capacity_fps"], 1000.0 / 114.0)
        self.assertEqual(value["tracking_fps"], 8.7)
        self.assertEqual(value["object_count"], 1)
        self.assertEqual(value["backend"], "per_object")

    def test_runtime_metrics_normalizes_sam2(self) -> None:
        value = runtime_metrics(
            {
                "tracker_total_ms": 22.5,
                "tracking_fps": 30.0,
                "source_age_ms": 41.0,
                "objects": [{"id": 1}, {"id": 2}],
            }
        )
        self.assertEqual(value["model_ms"], 22.5)
        self.assertAlmostEqual(value["capacity_fps"], 1000.0 / 22.5)
        self.assertEqual(value["tracking_fps"], 30.0)
        self.assertEqual(value["source_age_ms"], 41.0)
        self.assertEqual(value["object_count"], 2)


if __name__ == "__main__":
    unittest.main()
