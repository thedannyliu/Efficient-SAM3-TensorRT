#!/usr/bin/env python3

from __future__ import annotations

import argparse
from time import perf_counter

from sam31_trt.gi_client import InstinctSAMClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    args = parser.parse_args()
    client = InstinctSAMClient(args.base_url, timeout=30.0)
    start = perf_counter()
    jpeg = client.raw_jpeg()
    result = client.detect(jpeg, "object", confidence=1.0, max_objects=1)
    wall_ms = (perf_counter() - start) * 1000.0
    print(
        f"InstinctSAM warm-up complete: model={result.detect_ms:.1f} ms, "
        f"wall={wall_ms:.1f} ms"
    )


if __name__ == "__main__":
    main()
