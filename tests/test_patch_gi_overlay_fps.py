import tempfile
import unittest
from pathlib import Path

from scripts.patch_gi_overlay_fps import OVERLAY_FPS_BLOCK, REPLACEMENT, patch


class PatchGiOverlayFpsTests(unittest.TestCase):
    def test_removes_only_the_vendor_fps_draw(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "live_tracking_sam3.py"
            source.write_text(
                "before\n" + OVERLAY_FPS_BLOCK + "            keep_masks()\n"
            )

            patch(source)

            self.assertEqual(
                source.read_text(),
                "before\n" + REPLACEMENT + "            keep_masks()\n",
            )

    def test_rejects_an_unrecognized_vendor_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "live_tracking_sam3.py"
            source.write_text("changed upstream\n")

            with self.assertRaisesRegex(RuntimeError, "found 0"):
                patch(source)


if __name__ == "__main__":
    unittest.main()
