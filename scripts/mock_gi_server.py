#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np


def rectangle_rle(
    height: int, width: int, x0: int, y0: int, x1: int, y1: int
) -> dict[str, object]:
    flat = [
        int(x0 <= x <= x1 and y0 <= y <= y1)
        for x in range(width)
        for y in range(height)
    ]
    counts: list[int] = []
    value = 0
    run = 0
    for item in flat:
        if item == value:
            run += 1
        else:
            counts.append(run)
            run = 1
            value = item
    counts.append(run)
    return {"size": [height, width], "counts": counts}


class MockState:
    def __init__(self) -> None:
        self.mode = "native"
        self.prompt = ""
        self.frame = np.full((480, 640, 3), 32, dtype=np.uint8)
        cv2.rectangle(self.frame, (160, 100), (480, 380), (80, 180, 240), -1)
        ok, encoded = cv2.imencode(".jpg", self.frame)
        if not ok:
            raise RuntimeError("failed to encode mock frame")
        self.jpeg = encoded.tobytes()


class Handler(BaseHTTPRequestHandler):
    state = MockState()

    def log_message(self, format: str, *args: object) -> None:
        pass

    def send_json(self, value: object) -> None:
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/status.json":
            self.send_json(
                {
                    "backend": "mock",
                    "tracker_backend": "mock-native",
                    "fps": 20.0,
                    "latency_ms": 5.0,
                    "mode": self.state.mode,
                }
            )
            return
        if self.path in {"/raw.jpg", "/track.jpg"}:
            body = self.state.jpeg
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        value = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/v1/mode":
            self.state.mode = value["mode"]
            self.send_json({"mode": self.state.mode})
        elif self.path == "/api/v1/detect":
            self.send_json(
                {
                    "schema_version": 1,
                    "width": 640,
                    "height": 480,
                    "detect_ms": 5.0,
                    "objects": [
                        {
                            "label": value["text"],
                            "score": 0.99,
                            "mask": rectangle_rle(480, 640, 160, 100, 480, 380),
                        }
                    ],
                }
            )
        elif self.path == "/prompt":
            self.state.prompt = value["text"]
            self.send_json({"object_count": 1})
        elif self.path in {"/add_box", "/reset"}:
            self.send_json({"success": True})
        else:
            self.send_error(404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=28767)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"mock InstinctSAM listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
