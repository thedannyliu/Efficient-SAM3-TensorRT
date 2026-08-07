#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


REMOTE_TRUNK_BUILD = (
    "        t = sam3_ext.make_hiera_student_trunk('large', "
    "in_res=in_res).to(DEV).eval()\n"
)
LOCAL_TRUNK_BUILD = (
    "        t = sam3_ext.make_hiera_student_trunk(\n"
    "            'large', in_res=in_res, pretrained=False\n"
    "        ).to(DEV).eval()\n"
)


def patch(path: Path) -> None:
    source = path.read_text()
    count = source.count(REMOTE_TRUNK_BUILD)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one GI remote trunk build in {path}, found {count}"
        )
    path.write_text(source.replace(REMOTE_TRUNK_BUILD, LOCAL_TRUNK_BUILD))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    patch(args.path)


if __name__ == "__main__":
    main()
