#!/usr/bin/env python3
"""Probe an HTTP service externally and report its health to Traffic Visualizer."""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure access to an HTTP service.")
    parser.add_argument("--target", required=True, help="HTTP URL to probe")
    parser.add_argument("--report-to", required=True, help="Traffic Visualizer /api/impact URL")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=0.8)
    args = parser.parse_args()
    if args.interval <= 0 or args.timeout <= 0:
        parser.error("--interval and --timeout must be greater than zero")

    try:
        while True:
            cycle_started = time.monotonic()
            sample = measure(args.target, args.timeout)
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
