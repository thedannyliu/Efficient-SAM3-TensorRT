#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from sam31_trt.gi_client import InstinctSAMClient
from sam31_trt.rle import decode_coco_rle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture one GI frame and its text-prompt masks as an NPZ."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--max-objects", type=int, default=8)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    client = InstinctSAMClient(args.base_url, timeout=30.0)
    jpeg = client.raw_jpeg()
    bgr = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError("GI raw stream did not return a valid JPEG")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    response = client.detect(
        jpeg,
        args.prompt,
        confidence=args.confidence,
        max_objects=args.max_objects,
    )
    arrays = {}
    for index, item in enumerate(response.objects):
        mask = decode_coco_rle(item.mask)
        if mask.shape != rgb.shape[:2]:
            raise ValueError("GI mask dimensions do not match the captured frame")
        name = f"{args.prompt}_{index:02d}"
        arrays[f"image__{name}"] = rgb
        arrays[f"mask__{name}"] = mask
    if not arrays:
        raise RuntimeError(f"GI found no {args.prompt!r} masks")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **arrays)
    print(
        f"saved {len(response.objects)} masks at "
        f"{response.width}x{response.height} to {output}"
    )


if __name__ == "__main__":
    main()
