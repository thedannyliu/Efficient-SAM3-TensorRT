import tempfile
import unittest
from pathlib import Path

from scripts.patch_gi_local_trunk import (
    LOCAL_TRUNK_BUILD,
    REMOTE_TRUNK_BUILD,
    patch,
)


class PatchGiLocalTrunkTests(unittest.TestCase):
    def test_disables_the_redundant_pretrained_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "live_tracking_sam3.py"
            source.write_text("before\n" + REMOTE_TRUNK_BUILD + "after\n")

            patch(source)

            self.assertEqual(
                source.read_text(),
                "before\n" + LOCAL_TRUNK_BUILD + "after\n",
            )

    def test_rejects_an_unrecognized_vendor_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "live_tracking_sam3.py"
            source.write_text("changed upstream\n")

            with self.assertRaisesRegex(RuntimeError, "found 0"):
                patch(source)


if __name__ == "__main__":
    unittest.main()
