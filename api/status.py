"""Health endpoint for the hosted simulator."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):  # noqa: N801 - required by Vercel's Python runtime
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"name": "Pre-Silicon Bench", "mode": "vercel"}, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
