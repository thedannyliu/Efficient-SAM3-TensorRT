import unittest

import numpy as np

from sam31_trt.metrics import binary_iou, retention


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


if __name__ == "__main__":
    unittest.main()

