#!/usr/bin/env python3
"""Trigger the lab NTP-like amplification demonstration."""

from __future__ import annotations

import argparse
import json
import socket
import time
from typing import Dict, List


DEFAULT_AMPLIFIERS = ["10.152.0.71", "10.160.0.71", "10.171.0.71"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger the NTP-like amplification lab.")
    parser.add_argument("--amplifier", action="append", dest="amplifiers", help="amplifier IP; repeatable")
    parser.add_argument("--port", type=int, default=123, help="amplifier UDP port")
    parser.add_argument("--trigger", default="monlist", help="direct query trigger")
    parser.add_argument("--reflect", action="store_true", help="ask amplifiers to send responses to the victim")
    parser.add_argument("--token", default="seedemu-lab", help="reflection token configured on amplifiers")
    parser.add_argument("--victim", default="10.151.0.71", help="victim IP for reflection mode")
    parser.add_argument("--victim-port", type=int, default=9000, help="victim UDP port for reflection mode")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    return parser.parse_args()


def send_direct_query(sock: socket.socket, target: str, port: int, trigger: str, timeout: float) -> Dict[str, object]:
    request = trigger.encode()
    sock.settimeout(timeout)
    started = time.monotonic()
    sock.sendto(request, (target, port))
    try:
        response, source = sock.recvfrom(65535)
        elapsed = time.monotonic() - started
        return {
            "amplifier": target,
            "source": f"{source[0]}:{source[1]}",
            "request_bytes": len(request),
            "response_bytes": len(response),
            "amplification": round(len(response) / max(len(request), 1), 2),
            "elapsed_seconds": round(elapsed, 3),
            "status": "response",
        }
    except socket.timeout:
        return {
            "amplifier": target,
            "request_bytes": len(request),
            "response_bytes": 0,
            "amplification": 0,
            "status": "timeout",
        }


def send_reflection_request(sock: socket.socket, target: str, port: int, args: argparse.Namespace) -> Dict[str, object]:
    request = f"reflect {args.token} {args.victim} {args.victim_port}".encode()
    sock.sendto(request, (target, port))
    return {
        "amplifier": target,
        "victim": f"{args.victim}:{args.victim_port}",
        "request_bytes": len(request),
        "status": "sent",
    }


def main() -> int:
    args = parse_args()
    amplifiers = args.amplifiers or DEFAULT_AMPLIFIERS
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    results: List[Dict[str, object]] = []
    for amplifier in amplifiers:
        if args.reflect:
            results.append(send_reflection_request(sock, amplifier, args.port, args))
        else:
            results.append(send_direct_query(sock, amplifier, args.port, args.trigger, args.timeout))

    if args.json:
        print(json.dumps({"results": results}, indent=2, sort_keys=True))
    else:
        for item in results:
            print(item)

    return 0 if all(item["status"] in {"response", "sent"} for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
