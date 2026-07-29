from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sam31_trt.gi_client import InstinctSAMClient, InstinctSAMError


class Handler(BaseHTTPRequestHandler):
    last_request: dict[str, object] = {}
    requests: list[tuple[str, dict[str, object]]] = []

    def log_message(self, *_: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/status.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"fps":10.5}')
        elif self.path in {"/snapshot_raw.jpg", "/snapshot.jpg"}:
            body = b"jpeg"
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        Handler.last_request = json.loads(self.rfile.read(length))
        Handler.requests.append((self.path, Handler.last_request))
        if self.path == "/api/v1/mode":
            body = json.dumps({"mode": Handler.last_request["mode"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in {"/thresh", "/prompt", "/add_box"}:
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/api/v1/detect":
            self.send_error(404)
            return
        body = json.dumps(
            {
                "schema_version": 1,
                "width": 4,
                "height": 4,
                "detect_ms": 3.5,
                "objects": [
                    {
                        "label": "monitor",
                        "score": 0.9,
                        "mask": {"size": [4, 4], "counts": [0, 16]},
                    }
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class InstinctSAMClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = InstinctSAMClient(
            f"http://127.0.0.1:{cls.server.server_port}", timeout=2.0
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_status(self) -> None:
        self.assertEqual(self.client.status()["fps"], 10.5)

    def test_snapshot_routes(self) -> None:
        self.assertEqual(self.client.raw_jpeg(), b"jpeg")
        self.assertEqual(self.client.track_jpeg(), b"jpeg")

    def test_detect_contract(self) -> None:
        response = self.client.detect(b"jpeg", "monitor", 0.4, 3)
        self.assertEqual(response.objects[0].label, "monitor")
        self.assertEqual(Handler.last_request["text"], "monitor")
        self.assertEqual(Handler.last_request["max_objects"], 3)

    def test_sets_unified_mode(self) -> None:
        self.assertEqual(self.client.set_mode("hybrid")["mode"], "hybrid")
        with self.assertRaisesRegex(ValueError, "native or hybrid"):
            self.client.set_mode("invalid")

    def test_vendor_prompt_and_box_payloads(self) -> None:
        Handler.requests.clear()
        self.client.set_prompt("monitor", 0.4)
        self.client.add_box(0.1, 0.2, 0.8, 0.9)
        self.assertEqual(
            Handler.requests,
            [
                ("/thresh", {"detect": 0.4}),
                ("/prompt", {"text": "monitor"}),
                ("/add_box", {"box": [0.1, 0.2, 0.8, 0.9]}),
            ],
        )

    def test_http_error_is_contextual(self) -> None:
        with self.assertRaisesRegex(InstinctSAMError, "HTTP 404"):
            self.client.reset()
