from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InstinctSAMError(RuntimeError):
    pass


@dataclass(frozen=True)
class DetectObject:
    label: str
    score: float
    mask: dict[str, Any]


@dataclass(frozen=True)
class DetectResponse:
    width: int
    height: int
    detect_ms: float
    objects: tuple[DetectObject, ...]


class InstinctSAMClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8767", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        expect_json: bool = True,
    ) -> Any:
        data = None
        headers: dict[str, str] = {}
        method = "GET"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        request = Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise InstinctSAMError(
                f"{method} {path} returned HTTP {error.code}: {detail}"
            ) from error
        except (TimeoutError, URLError) as error:
            raise InstinctSAMError(f"{method} {path} failed: {error}") from error
        if not expect_json:
            return body
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise InstinctSAMError(f"{method} {path} returned invalid JSON") from error

    def status(self) -> dict[str, Any]:
        value = self._request("/status.json")
        if not isinstance(value, dict):
            raise InstinctSAMError("/status.json did not return an object")
        return value

    def raw_jpeg(self) -> bytes:
        return self._request("/raw.jpg", expect_json=False)

    def track_jpeg(self) -> bytes:
        return self._request("/track.jpg", expect_json=False)

    def set_prompt(self, text: str, confidence: float = 0.5) -> dict[str, Any]:
        value = self._request(
            "/prompt", {"text": text, "confidence": float(confidence)}
        )
        return value if isinstance(value, dict) else {"response": value}

    def add_box(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> dict[str, Any]:
        value = self._request(
            "/add_box",
            {"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1)},
        )
        return value if isinstance(value, dict) else {"response": value}

    def reset(self) -> dict[str, Any]:
        value = self._request("/reset", {})
        return value if isinstance(value, dict) else {"response": value}

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in {"native", "hybrid"}:
            raise ValueError("mode must be native or hybrid")
        value = self._request("/api/v1/mode", {"mode": mode})
        return value if isinstance(value, dict) else {"response": value}

    def detect(
        self,
        jpeg: bytes,
        text: str,
        confidence: float = 0.5,
        max_objects: int = 8,
    ) -> DetectResponse:
        value = self._request(
            "/api/v1/detect",
            {
                "image_jpeg_b64": base64.b64encode(jpeg).decode("ascii"),
                "text": text,
                "confidence": float(confidence),
                "max_objects": int(max_objects),
            },
        )
        if not isinstance(value, dict) or int(value.get("schema_version", 0)) != 1:
            raise InstinctSAMError("detect response has an unsupported schema")
        objects = value.get("objects")
        if not isinstance(objects, list):
            raise InstinctSAMError("detect response objects must be a list")
        parsed: list[DetectObject] = []
        for item in objects:
            if not isinstance(item, dict) or not isinstance(item.get("mask"), dict):
                raise InstinctSAMError("detect response contains an invalid object")
            parsed.append(
                DetectObject(
                    label=str(item.get("label", "")),
                    score=float(item.get("score", 0.0)),
                    mask=item["mask"],
                )
            )
        return DetectResponse(
            width=int(value["width"]),
            height=int(value["height"]),
            detect_ms=float(value.get("detect_ms", 0.0)),
            objects=tuple(parsed),
        )
