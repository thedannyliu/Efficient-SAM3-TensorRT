import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from scripts.validate_vision_artifacts import load_normalized_image


class ArtifactInputTest(unittest.TestCase):
    def test_image_is_rgb_chw_and_normalized(self) -> None:
        image = np.zeros((2, 2, 3), dtype=np.uint8)
        image[:, :] = (0, 128, 255)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            cv2.imwrite(str(path), image)
            output = load_normalized_image(path)

        self.assertEqual(output.shape, (1, 3, 1008, 1008))
        self.assertEqual(output.dtype, np.float16)
        np.testing.assert_allclose(
            output[0, :, 0, 0],
            np.array([1.0, 128 / 127.5 - 1.0, -1.0], dtype=np.float16),
            atol=1e-3,
        )


if __name__ == "__main__":
    unittest.main()
