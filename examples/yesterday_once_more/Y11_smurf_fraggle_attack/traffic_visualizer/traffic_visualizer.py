#!/usr/bin/env python3
"""Count tcpdump output lines and publish the count over HTTP."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading
from typing import Any
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent


class PacketCounter:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.total = 0
        self.last_second = 0
        self.current_second = 0
        self.status = "starting"
        self.error = ""

    def increment(self) -> None:
        with self.lock:
            self.total += 1
            self.current_second += 1

    def finish_second(self) -> None:
        with self.lock:
            self.last_second = self.current_second
            self.current_second = 0

    def reset(self) -> None:
        with self.lock:
            self.total = 0
            self.last_second = 0
            self.current_second = 0

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "total_packets": self.total,
                "packets_last_second": self.last_second,
                "status": self.status,
                "error": self.error,
            }


def capture_packets(config: dict[str, Any], counter: PacketCounter) -> None:
    command = [
        "tcpdump",
        "-i",
        str(config.get("interface", "any")),
        "-Q",
        "in",
        "-n",
        "-l",
        "-q",
        str(config.get("capture_filter", "")),
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        counter.status = "error"
        counter.error = str(error)
        return

    counter.status = "running"
    assert process.stdout is not None
    for line in process.stdout:
        if line.strip():
            counter.increment()

    counter.status = "error"
    counter.error = f"tcpdump exited with status {process.wait()}"


def sample_each_second(counter: PacketCounter) -> None:
    event = threading.Event()
    while not event.wait(1.0):
        counter.finish_second()


def make_handler(counter: PacketCounter, dashboard: bytes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html; charset=utf-8", dashboard)
            elif path == "/api/stats":
                self._send_json(200, counter.snapshot())
            elif path == "/healthz":
                status = 200 if counter.status != "error" else 503
                self._send_json(status, {"status": counter.status})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/reset":
                self._send_json(404, {"error": "not found"})
                return
            counter.reset()
            self._send_json(200, {"status": "reset"})

        def log_message(self, _format: str, *_args: Any) -> None:
            pass

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Count packets observed by tcpdump.")
    parser.add_argument("--config", default=str(SCRIPT_DIR / "config.json"))
    parser.add_argument("--dashboard", default=str(SCRIPT_DIR / "dashboard.html"))
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    dashboard = Path(args.dashboard).read_bytes()
    counter = PacketCounter()

    threading.Thread(target=capture_packets, args=(config, counter), daemon=True).start()
    threading.Thread(target=sample_each_second, args=(counter,), daemon=True).start()

    address = (str(config.get("web_host", "0.0.0.0")), int(config.get("web_port", 8080)))
    server = ThreadingHTTPServer(address, make_handler(counter, dashboard))
    print(f"Traffic Visualizer listening on http://{address[0]}:{address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
