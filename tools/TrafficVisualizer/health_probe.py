#!/usr/bin/env python3
"""Probe an HTTP service externally and report its health to Traffic Visualizer."""

from __future__ import annotations

import argparse
import json
from queue import Empty, SimpleQueue
from threading import Thread
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def measure(target: str, timeout: float) -> dict[str, object]:
    started = time.monotonic()
    try:
        with urlopen(target, timeout=timeout) as response:
            response.read()
            success = response.status == 200
    except (HTTPError, URLError, OSError, TimeoutError):
        success = False

    if not success:
        return {"success": False}
    return {
        "success": True,
        "latency_ms": round((time.monotonic() - started) * 1000, 2),
    }


def report(destination: str, sample: dict[str, object], timeout: float) -> None:
    body = json.dumps(sample).encode("utf-8")
    request = Request(
        destination,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        response.read()


def bandwidth_url(target: str, byte_count: int) -> str:
    parsed = urlsplit(target)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["bytes"] = str(byte_count)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def measure_bandwidth(target: str, byte_count: int, timeout: float) -> dict[str, object]:
    started = time.monotonic()
    received = 0
    try:
        with urlopen(bandwidth_url(target, byte_count), timeout=timeout) as response:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                received += len(chunk)
            success = response.status == 200 and received == byte_count
    except (HTTPError, URLError, OSError, TimeoutError):
        success = False

    if not success:
        return {
            "bandwidth_success": False,
            "downloaded_bytes": received,
        }
    elapsed = max(time.monotonic() - started, 0.000001)
    return {
        "bandwidth_success": True,
        "throughput_mbps": round(received * 8 / elapsed / 1_000_000, 3),
        "downloaded_bytes": received,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure access to an HTTP service.")
    parser.add_argument("--target", required=True, help="HTTP URL to probe")
    parser.add_argument("--report-to", required=True, help="Traffic Visualizer /api/impact URL")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=0.8)
    parser.add_argument("--bandwidth-url", help="optional HTTP bandwidth-test endpoint")
    parser.add_argument("--bandwidth-bytes", type=int, default=256 * 1024)
    parser.add_argument("--bandwidth-interval", type=float, default=5.0)
    parser.add_argument("--bandwidth-timeout", type=float, default=3.0)
    args = parser.parse_args()
    if args.interval <= 0 or args.timeout <= 0:
        parser.error("--interval and --timeout must be greater than zero")
    if args.bandwidth_url and (
        args.bandwidth_bytes < 1
        or args.bandwidth_interval <= 0
        or args.bandwidth_timeout <= 0
    ):
        parser.error("bandwidth byte count, interval, and timeout must be greater than zero")

    bandwidth_results: SimpleQueue[dict[str, object]] = SimpleQueue()
    next_bandwidth_probe = 0.0
    bandwidth_probe_running = False

    def run_bandwidth_probe() -> None:
        bandwidth_results.put(
            measure_bandwidth(
                args.bandwidth_url,
                args.bandwidth_bytes,
                args.bandwidth_timeout,
            )
        )

    try:
        while True:
            cycle_started = time.monotonic()
            sample = measure(args.target, args.timeout)
            if bandwidth_probe_running:
                try:
                    sample.update(bandwidth_results.get_nowait())
                    bandwidth_probe_running = False
                    next_bandwidth_probe = time.monotonic() + args.bandwidth_interval
                except Empty:
                    pass
            if (
                args.bandwidth_url
                and not bandwidth_probe_running
                and cycle_started >= next_bandwidth_probe
            ):
                Thread(target=run_bandwidth_probe, daemon=True).start()
                bandwidth_probe_running = True
            try:
                report(args.report_to, sample, args.timeout)
            except (HTTPError, URLError, OSError, TimeoutError) as error:
                print(f"could not report health sample: {error}", flush=True)
            remaining = args.interval - (time.monotonic() - cycle_started)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
