#!/usr/bin/env python3
"""Reusable tcpdump packet counter with a small HTTP dashboard."""

from __future__ import annotations

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
IP_TOTAL_LENGTH = re.compile(r"\bIP\s+\(.*?\blength\s+(\d+)\)")


def parse_ip_total_length(line: str) -> int | None:
    """Return tcpdump's decoded IPv4 Total Length value."""
    match = IP_TOTAL_LENGTH.search(line)
    return int(match.group(1)) if match is not None else None


class PacketCounter:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.total = 0
        self.last_second = 0
        self.current_second = 0
        self.total_ip_bytes = 0
        self.ip_bytes_last_second = 0
        self.current_second_ip_bytes = 0
        self.status = "starting"
        self.error = ""

    def increment(self, ip_bytes: int) -> None:
        with self.lock:
            self.total += 1
            self.current_second += 1
            self.total_ip_bytes += ip_bytes
            self.current_second_ip_bytes += ip_bytes

    def finish_second(self) -> None:
        with self.lock:
            self.last_second = self.current_second
            self.ip_bytes_last_second = self.current_second_ip_bytes
            self.current_second = 0
            self.current_second_ip_bytes = 0

    def reset(self) -> None:
        with self.lock:
            self.total = 0
            self.last_second = 0
            self.current_second = 0
            self.total_ip_bytes = 0
            self.ip_bytes_last_second = 0
            self.current_second_ip_bytes = 0

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "total_packets": self.total,
                "packets_last_second": self.last_second,
                "total_ip_bytes": self.total_ip_bytes,
                "ip_bytes_last_second": self.ip_bytes_last_second,
                "average_ip_packet_size": (
                    round(self.total_ip_bytes / self.total) if self.total else 0
                ),
                "average_ip_packet_size_last_second": (
                    round(self.ip_bytes_last_second / self.last_second)
                    if self.last_second
                    else 0
                ),
                "status": self.status,
                "error": self.error,
            }


class ImpactTracker:
    """Store a short rolling window of externally measured service health."""

    def __init__(self, max_samples: int = 60) -> None:
        if max_samples < 1:
            raise ValueError("impact_max_samples must be at least 1")
        self.lock = threading.Lock()
        self.samples: deque[dict[str, Any]] = deque(maxlen=max_samples)

    def record(self, payload: dict[str, Any]) -> None:
        success = payload.get("success")
        if not isinstance(success, bool):
            raise ValueError("success must be a boolean")

        latency = payload.get("latency_ms")
        if success:
            if (
                not isinstance(latency, (int, float))
                or isinstance(latency, bool)
                or not math.isfinite(latency)
                or latency < 0
            ):
                raise ValueError("a successful probe requires a non-negative latency_ms")
            latency = round(float(latency), 2)
        else:
            latency = None

        bandwidth_success = payload.get("bandwidth_success")
        throughput = payload.get("throughput_mbps")
        downloaded_bytes = payload.get("downloaded_bytes")
        if bandwidth_success is None:
            throughput = None
            downloaded_bytes = None
        elif not isinstance(bandwidth_success, bool):
            raise ValueError("bandwidth_success must be a boolean")
        elif bandwidth_success:
            if (
                not isinstance(throughput, (int, float))
                or isinstance(throughput, bool)
                or not math.isfinite(throughput)
                or throughput < 0
            ):
                raise ValueError("a successful bandwidth probe requires throughput_mbps")
            if (
                not isinstance(downloaded_bytes, int)
                or isinstance(downloaded_bytes, bool)
                or downloaded_bytes < 1
            ):
                raise ValueError("a successful bandwidth probe requires positive downloaded_bytes")
            throughput = round(float(throughput), 3)
        else:
            throughput = None
            downloaded_bytes = int(downloaded_bytes or 0)

        sample = {
            "timestamp_ms": round(time.time() * 1000),
            "success": success,
            "latency_ms": latency,
            "bandwidth_success": bandwidth_success,
            "throughput_mbps": throughput,
            "downloaded_bytes": downloaded_bytes,
        }
        with self.lock:
            self.samples.append(sample)

    def reset(self) -> None:
        with self.lock:
            self.samples.clear()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            samples = list(self.samples)

        successful = [sample for sample in samples if sample["success"]]
        bandwidth_samples = [
            sample for sample in samples if sample["bandwidth_success"] is not None
        ]
        successful_bandwidth = [
            sample for sample in bandwidth_samples if sample["bandwidth_success"]
        ]
        latest = samples[-1] if samples else None
        latest_bandwidth = bandwidth_samples[-1] if bandwidth_samples else None
        return {
            "sample_count": len(samples),
            "failure_count": len(samples) - len(successful),
            "success_rate": round(len(successful) * 100 / len(samples), 1) if samples else 0,
            "latest_success": latest["success"] if latest else None,
            "latest_latency_ms": latest["latency_ms"] if latest else None,
            "average_latency_ms": (
                round(sum(sample["latency_ms"] for sample in successful) / len(successful), 2)
                if successful
                else None
            ),
            "last_probe_age_seconds": (
                round(max(0, time.time() - latest["timestamp_ms"] / 1000), 2)
                if latest
                else None
            ),
            "bandwidth_sample_count": len(bandwidth_samples),
            "bandwidth_failure_count": len(bandwidth_samples) - len(successful_bandwidth),
            "latest_bandwidth_success": (
                latest_bandwidth["bandwidth_success"] if latest_bandwidth else None
            ),
            "latest_throughput_mbps": (
                latest_bandwidth["throughput_mbps"] if latest_bandwidth else None
            ),
            "average_throughput_mbps": (
                round(
                    sum(sample["throughput_mbps"] for sample in successful_bandwidth)
                    / len(successful_bandwidth),
                    3,
                )
                if successful_bandwidth
                else None
            ),
            "last_bandwidth_age_seconds": (
                round(max(0, time.time() - latest_bandwidth["timestamp_ms"] / 1000), 2)
                if latest_bandwidth
                else None
            ),
            "samples": samples,
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
        "-v",
        "-s",
        "96",
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
        ip_bytes = parse_ip_total_length(line)
        if ip_bytes is not None:
            counter.increment(ip_bytes)

    counter.status = "error"
    counter.error = f"tcpdump exited with status {process.wait()}"


def sample_each_second(counter: PacketCounter) -> None:
    event = threading.Event()
    while not event.wait(1.0):
        counter.finish_second()


def make_handler(
    counter: PacketCounter,
    dashboard: bytes,
    frontend_config: dict[str, Any],
    extension_js: bytes,
    extension_css: bytes,
    impact_tracker: ImpactTracker | None = None,
):
    impact = impact_tracker or ImpactTracker()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html; charset=utf-8", dashboard)
            elif path == "/extension.js":
                self._send(200, "text/javascript; charset=utf-8", extension_js)
            elif path == "/extension.css":
                self._send(200, "text/css; charset=utf-8", extension_css)
            elif path == "/api/config":
                self._send_json(200, {"api_version": 1, "frontend": frontend_config})
            elif path == "/api/stats":
                stats = counter.snapshot()
                stats["impact"] = impact.snapshot()
                self._send_json(200, stats)
            elif path == "/api/impact":
                self._send_json(200, impact.snapshot())
            elif path == "/healthz":
                status = 200 if counter.status != "error" else 503
                self._send_json(status, {"status": counter.status})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/impact":
                try:
                    impact.record(self._read_json())
                except (ValueError, json.JSONDecodeError) as error:
                    self._send_json(400, {"error": str(error)})
                    return
                self._send_json(200, {"status": "recorded"})
                return
            if path == "/api/reset":
                counter.reset()
                impact.reset()
                self._send_json(200, {"status": "reset"})
                return
            self._send_json(404, {"error": "not found"})

        def log_message(self, _format: str, *_args: Any) -> None:
            pass

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 1 or content_length > 4096:
                raise ValueError("request body must be between 1 and 4096 bytes")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def load_frontend(config: dict[str, Any], config_path: Path):
    configured = config.get("frontend", {})
    if not isinstance(configured, dict):
        raise ValueError("frontend configuration must be a JSON object")

    frontend = {
        "title": str(configured.get("title", "Traffic Visualizer")),
        "subtitle": str(configured.get("subtitle", "Packets observed")),
        "accent_color": str(configured.get("accent_color", "#38bdf8")),
        "options": configured.get("options", {}),
    }
    if not isinstance(frontend["options"], dict):
        raise ValueError("frontend.options must be a JSON object")

    def read_optional(name: str) -> bytes:
        value = configured.get(name)
        if not value:
            return b""
        path = Path(str(value))
        if not path.is_absolute():
            path = config_path.parent / path
        return path.read_bytes()

    return frontend, read_optional("extension_js"), read_optional("extension_css")


def main() -> int:
    parser = argparse.ArgumentParser(description="Count packets observed by tcpdump.")
    parser.add_argument("--config", default=str(SCRIPT_DIR / "config.json"))
    parser.add_argument("--dashboard", default=str(SCRIPT_DIR / "dashboard.html"))
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    dashboard = Path(args.dashboard).read_bytes()
    frontend_config, extension_js, extension_css = load_frontend(config, config_path)
    counter = PacketCounter()
    impact_tracker = ImpactTracker(int(config.get("impact_max_samples", 60)))

    threading.Thread(target=capture_packets, args=(config, counter), daemon=True).start()
    threading.Thread(target=sample_each_second, args=(counter,), daemon=True).start()

    address = (str(config.get("web_host", "0.0.0.0")), int(config.get("web_port", 8080)))
    server = ThreadingHTTPServer(
        address,
        make_handler(
            counter,
            dashboard,
            frontend_config,
            extension_js,
            extension_css,
            impact_tracker,
        ),
    )
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
