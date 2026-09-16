"""Dependency-free local server for the interactive Pre-Silicon Bench."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
BENCH_ROOT = ROOT.parent
sys.path.insert(0, str(BENCH_ROOT))

from gui.simulation import run_simulation  # noqa: E402


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "PreSiliconBench/1.0"

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, filename: str) -> None:
        path = ROOT / filename
        if not path.is_file():
            self._json(404, {"error": "not found"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if route == "/api/status":
            self._json(
                200,
                {
                    "name": "Pre-Silicon Bench",
                    "mode": "local",
                    "bench_root": str(BENCH_ROOT),
                    "tools": {tool: shutil.which(tool) is not None for tool in ("iverilog", "ngspice")},
                },
            )
            return
        self._file({"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}.get(route, ""))

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/simulate":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError("request is too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(200, run_simulation(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except Exception as error:  # keep the local UI useful while exposing the failure
            self._json(500, {"error": f"simulation failed: {error}"})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[gui] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Pre-Silicon Bench GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Pre-Silicon Bench GUI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GUI")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
