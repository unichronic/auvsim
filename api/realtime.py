"""Vercel Function adapter for bounded real-time frame previews."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from gui.realtime import run_realtime


MAX_REQUEST_BYTES = 1_000_000


class handler(BaseHTTPRequestHandler):  # noqa: N801 - required by Vercel's Python runtime
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("request is too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(200, run_realtime(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except Exception as error:  # keep a bad frame from becoming a blank UI state
            self._json(500, {"error": f"realtime simulation failed: {error}"})

    def do_GET(self) -> None:  # noqa: N802
        self._json(405, {"error": "POST a realtime frame stream"})
