from __future__ import annotations

import fcntl
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from sam31_trt.shared_frame import (
    HEADER,
    MAGIC,
    SharedFrameReader,
    SharedFrameWriter,
)


class SharedFrameWriterTest(unittest.TestCase):
    def test_writes_header_and_contiguous_bgr_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.bin"
            writer = SharedFrameWriter(path, 1024)
            frame = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
            writer.write(frame[:, ::-1], 123456789)

            descriptor = os.open(path, os.O_RDONLY)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_SH)
                header = os.pread(descriptor, HEADER.size, 0)
                payload = os.pread(descriptor, frame.nbytes, HEADER.size)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
                writer.close()

            (
                magic,
                sequence,
                stamp_ns,
                width,
                height,
                stride,
                payload_bytes,
            ) = HEADER.unpack(header)
            expected = np.ascontiguousarray(frame[:, ::-1])
            self.assertEqual(magic, MAGIC)
            self.assertEqual(sequence, 1)
            self.assertEqual(stamp_ns, 123456789)
            self.assertEqual((width, height), (5, 4))
            self.assertEqual(stride, 15)
            self.assertEqual(payload_bytes, 60)
            self.assertEqual(payload, expected.tobytes())

    def test_rejects_frame_larger_than_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = SharedFrameWriter(Path(directory) / "frame.bin", 8)
            try:
                with self.assertRaisesRegex(ValueError, "shared buffer"):
                    writer.write(np.zeros((2, 2, 3), dtype=np.uint8), 1)
            finally:
                writer.close()

    def test_reader_returns_each_sequence_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.bin"
            writer = SharedFrameWriter(path, 1024)
            reader = SharedFrameReader(path)
            try:
                expected = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
                writer.write(expected, 123)
                sequence, stamp_ns, frame = reader.read_latest()
                self.assertEqual((sequence, stamp_ns), (1, 123))
                np.testing.assert_array_equal(frame, expected)
                self.assertEqual(reader.read_latest(), (1, 123, None))
            finally:
                reader.close()
                writer.close()


if __name__ == "__main__":
    unittest.main()
