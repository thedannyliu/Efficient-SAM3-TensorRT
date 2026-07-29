from __future__ import annotations

import fcntl
import os
from pathlib import Path
import struct

import numpy as np


MAGIC = b"SAM2RGB1"
HEADER = struct.Struct("<8sQQIIII")


class SharedFrameWriter:
    def __init__(self, path: str | Path, max_payload_bytes: int) -> None:
        self.path = Path(path)
        self.max_payload_bytes = max_payload_bytes
        self.sequence = 0
        self.file_descriptor = os.open(
            self.path,
            os.O_CREAT | os.O_RDWR,
            0o660,
        )
        os.ftruncate(
            self.file_descriptor,
            HEADER.size + self.max_payload_bytes,
        )
        self._write_all(self.file_descriptor, bytes(HEADER.size), 0)

    @staticmethod
    def _write_all(
        file_descriptor: int,
        value: memoryview | bytes,
        offset: int,
    ) -> None:
        view = memoryview(value).cast("B")
        written = 0
        while written < len(view):
            count = os.pwrite(
                file_descriptor,
                view[written:],
                offset + written,
            )
            if count < 1:
                raise OSError("shared-frame write made no progress")
            written += count

    def write(self, frame: np.ndarray, stamp_ns: int) -> None:
        if (
            frame.dtype != np.uint8
            or frame.ndim != 3
            or frame.shape[2] != 3
        ):
            raise ValueError("shared frame must be an HxWx3 uint8 array")
        contiguous = np.ascontiguousarray(frame)
        height, width = contiguous.shape[:2]
        stride = int(contiguous.strides[0])
        payload = memoryview(contiguous)
        payload_bytes = payload.nbytes
        if payload_bytes > self.max_payload_bytes:
            raise ValueError(
                f"frame needs {payload_bytes} bytes, shared buffer allows "
                f"{self.max_payload_bytes}"
            )
        self.sequence += 1
        header = HEADER.pack(
            MAGIC,
            self.sequence,
            stamp_ns,
            width,
            height,
            stride,
            payload_bytes,
        )
        fcntl.flock(self.file_descriptor, fcntl.LOCK_EX)
        try:
            self._write_all(self.file_descriptor, payload, HEADER.size)
            self._write_all(self.file_descriptor, header, 0)
        finally:
            fcntl.flock(self.file_descriptor, fcntl.LOCK_UN)

    def close(self) -> None:
        if self.file_descriptor >= 0:
            os.close(self.file_descriptor)
            self.file_descriptor = -1


class SharedFrameReader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.file_descriptor = os.open(self.path, os.O_RDONLY)
        self.sequence = 0

    def read_latest(self) -> tuple[int, int, np.ndarray | None]:
        fcntl.flock(self.file_descriptor, fcntl.LOCK_SH)
        try:
            header = os.pread(self.file_descriptor, HEADER.size, 0)
            if len(header) != HEADER.size:
                return self.sequence, 0, None
            (
                magic,
                sequence,
                stamp_ns,
                width,
                height,
                stride,
                payload_bytes,
            ) = HEADER.unpack(header)
            if (
                magic != MAGIC
                or sequence == self.sequence
                or width < 1
                or height < 1
                or stride < width * 3
                or payload_bytes != stride * height
                or payload_bytes > 64 * 1024 * 1024
            ):
                return self.sequence, stamp_ns, None
            payload = os.pread(
                self.file_descriptor, payload_bytes, HEADER.size
            )
        finally:
            fcntl.flock(self.file_descriptor, fcntl.LOCK_UN)
        if len(payload) != payload_bytes:
            return self.sequence, stamp_ns, None
        rows = np.frombuffer(payload, dtype=np.uint8).reshape(height, stride)
        frame = rows[:, : width * 3].reshape(height, width, 3)
        self.sequence = sequence
        return sequence, stamp_ns, frame

    def close(self) -> None:
        if self.file_descriptor >= 0:
            os.close(self.file_descriptor)
            self.file_descriptor = -1
