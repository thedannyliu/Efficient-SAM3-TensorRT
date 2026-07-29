#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


EXPECTED_TAR_SHA256 = (
    "30b40a025a76e8a8e911a3c57320637260e9fc78b54fcc4b90b73c7982bb7e75"
)
ACKNOWLEDGEMENT = "research-evaluation-only"
REQUIRED = ("LICENSE.InstinctSAM", "LICENSE.SAM", "NOTICE")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(delivery: Path, *, check_tar: bool = True) -> dict[str, object]:
    if os.environ.get("GI_RESEARCH_USE_ACK") != ACKNOWLEDGEMENT:
        raise RuntimeError(
            "set GI_RESEARCH_USE_ACK=research-evaluation-only after reading "
            "LICENSE.InstinctSAM, LICENSE.SAM, and NOTICE"
        )
    missing = [name for name in REQUIRED if not (delivery / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing required license files: {', '.join(missing)}")
    result: dict[str, object] = {
        "delivery_dir": str(delivery.resolve()),
        "research_use_acknowledged": True,
        "required_files": list(REQUIRED),
    }
    if check_tar:
        archive = delivery / "instinctsam-thor-r39.tar.gz"
        actual = sha256(archive)
        if actual != EXPECTED_TAR_SHA256:
            raise RuntimeError(
                f"GI archive checksum mismatch: expected {EXPECTED_TAR_SHA256}, got {actual}"
            )
        result["archive"] = str(archive)
        result["archive_sha256"] = actual
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--skip-tar", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.delivery, check_tar=not args.skip_tar), indent=2))


if __name__ == "__main__":
    main()
