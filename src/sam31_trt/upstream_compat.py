from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Mapping
from typing import Any


_DERIVED_ROPE_BUFFER = re.compile(
    r"^blocks\.\d+\.attn\.freqs_cis_(?:real|imag)$"
)


def supported_kwargs(
    function: Callable[..., Any], kwargs: Mapping[str, Any]
) -> dict[str, Any]:
    """Return only keyword arguments accepted by an upstream callable."""
    parameters = inspect.signature(function).parameters
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return dict(kwargs)
    return {name: value for name, value in kwargs.items() if name in parameters}


def validate_vision_state_mismatch(
    missing: list[str], unexpected: list[str]
) -> list[str]:
    """Validate that only deterministic real-valued RoPE buffers are absent."""
    invalid_missing = [name for name in missing if not _DERIVED_ROPE_BUFFER.fullmatch(name)]
    if invalid_missing or unexpected:
        raise RuntimeError(
            f"vision state mismatch: missing={invalid_missing}, "
            f"unexpected={unexpected}"
        )
    return missing
