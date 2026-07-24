from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_PRECISIONS = frozenset({"fp32", "bf16", "fp16", "fp8", "int8"})


@dataclass(frozen=True)
class PrecisionRule:
    pattern: str
    precision: str

    def __post_init__(self) -> None:
        if not self.pattern:
            raise ValueError("precision rule pattern must not be empty")
        if self.precision not in SUPPORTED_PRECISIONS:
            raise ValueError(f"unsupported precision: {self.precision}")


SENSITIVE_DEFAULTS = (
    PrecisionRule("*.layer_norm*", "fp16"),
    PrecisionRule("*.softmax*", "fp16"),
    PrecisionRule("*.mask_decoder*", "fp16"),
    PrecisionRule("*.iou_prediction_head*", "fp16"),
)

