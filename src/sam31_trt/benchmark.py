from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return math.nan
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize_rows(
    rows: Iterable[dict[str, Any]],
    *,
    warmup: int = 100,
    latency_fields: tuple[str, ...] = (
        "inference_ms",
        "gpu_total_ms",
        "backbone_ms",
        "tracker_ms",
        "overlay_ms",
        "adapter_poll_ms",
        "callback_total_ms",
        "source_age_ms",
    ),
) -> dict[str, Any]:
    measured = list(rows)[warmup:]
    if not measured:
        raise ValueError("no rows remain after warm-up")
    summary: dict[str, Any] = {
        "warmup_rows": warmup,
        "measured_rows": len(measured),
    }
    stamps = [int(row["stamp_ns"]) for row in measured if int(row.get("stamp_ns", 0)) > 0]
    if len(stamps) >= 2:
        duration = (max(stamps) - min(stamps)) / 1.0e9
        summary["completed_output_fps"] = (
            (len(stamps) - 1) / duration if duration > 0 else math.nan
        )
    for field in latency_fields:
        values = [
            float(row[field])
            for row in measured
            if field in row and math.isfinite(float(row[field]))
        ]
        if not values:
            continue
        summary[field] = {
            "mean": statistics.fmean(values),
            "p50": percentile(values, 0.50),
            "p90": percentile(values, 0.90),
            "p95": percentile(values, 0.95),
            "p99": percentile(values, 0.99),
        }
    summary["dropped_frames"] = sum(int(row.get("dropped", 0)) for row in measured)
    return summary


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize_rows(load_jsonl(args.trace), warmup=args.warmup)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
