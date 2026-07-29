from __future__ import annotations

import unittest

import numpy as np

from sam31_trt.rle import decode_coco_rle, mask_to_box


def encode_counts(counts: list[int]) -> str:
    encoded = []
    for index, original in enumerate(counts):
        value = original - counts[index - 2] if index > 2 else original
        more = True
        while more:
            current = value & 0x1F
            value >>= 5
            more = value != (-1 if current & 0x10 else 0)
            if more:
                current |= 0x20
            encoded.append(chr(current + 48))
    return "".join(encoded)


class CocoRleTest(unittest.TestCase):
    def test_decodes_uncompressed_fortran_order(self) -> None:
        mask = decode_coco_rle({"size": [3, 4], "counts": [1, 2, 4, 1, 4]})
        expected = np.array(
            [[0, 0, 0, 0], [1, 0, 1, 0], [1, 0, 0, 0]], dtype=np.uint8
        )
        np.testing.assert_array_equal(mask, expected)

    def test_decodes_compressed_counts(self) -> None:
        counts = [40, 3, 2, 35, 20]
        compressed = encode_counts(counts)
        actual = decode_coco_rle({"size": [10, 10], "counts": compressed})
        expected = decode_coco_rle({"size": [10, 10], "counts": counts})
        np.testing.assert_array_equal(actual, expected)

    def test_rejects_incomplete_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "do not fill"):
            decode_coco_rle({"size": [2, 2], "counts": [1, 1]})

    def test_mask_to_box_and_minimum_area(self) -> None:
        mask = np.zeros((8, 10), dtype=np.uint8)
        mask[2:7, 3:9] = 1
        self.assertEqual(mask_to_box(mask, min_area=25), (3.0, 2.0, 8.0, 6.0))
        self.assertIsNone(mask_to_box(mask, min_area=31))
