#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


OVERLAY_FPS_BLOCK = """            cv2.putText(overlay, f"{stats['fps']:.1f} FPS", (12, 42), cv2.FONT_HERSHEY_SIMPLEX,
                        1.3, (77, 208, 225), 3)
"""
REPLACEMENT = "            # FPS is rendered by the unified ROS HUD.\n"


def patch(path: Path) -> None:
    source = path.read_text()
    count = source.count(OVERLAY_FPS_BLOCK)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one GI overlay FPS block in {path}, found {count}"
        )
    path.write_text(source.replace(OVERLAY_FPS_BLOCK, REPLACEMENT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    patch(args.path)


if __name__ == "__main__":
    main()
