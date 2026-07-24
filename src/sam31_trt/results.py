from __future__ import annotations

import math
from typing import Any

from .metrics import retention


def compare_candidate(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    minimum_retention: float = 0.90,
) -> dict[str, Any]:
    reference_miou = float(reference["mean_iou"])
    candidate_miou = float(candidate["mean_iou"])
    reference_latency = float(reference["mean_latency_ms"])
    candidate_latency = float(candidate["mean_latency_ms"])
    accuracy_retention = retention(candidate_miou, reference_miou)
    return {
        "reference_backend": reference["backend"],
        "candidate_backend": candidate["backend"],
        "gpu": candidate["gpu"],
        "reference_miou": reference_miou,
        "candidate_miou": candidate_miou,
        "miou_delta": candidate_miou - reference_miou,
        "miou_retention": accuracy_retention,
        "minimum_retention": minimum_retention,
        "accepted": accuracy_retention >= minimum_retention
        or math.isclose(accuracy_retention, minimum_retention),
        "reference_latency_ms": reference_latency,
        "candidate_latency_ms": candidate_latency,
        "speedup": reference_latency / candidate_latency,
    }
