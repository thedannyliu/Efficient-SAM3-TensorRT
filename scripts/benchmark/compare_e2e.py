#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sam31_trt.results import compare_candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-retention", type=float, default=0.90)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    if reference["gpu"] != candidate["gpu"]:
        raise ValueError(
            f"latency comparison requires the same GPU: "
            f"{reference['gpu']} != {candidate['gpu']}"
        )
    report = compare_candidate(reference, candidate, args.minimum_retention)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

