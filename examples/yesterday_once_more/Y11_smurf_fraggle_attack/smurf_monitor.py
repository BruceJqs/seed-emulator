#!/usr/bin/env python3
"""Count ICMP echo replies that arrive at the Smurf victim."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor ICMP echo replies at the Smurf victim.")
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--source-prefix", default="10.152.0.", help="count replies from this source prefix")
    parser.add_argument("--output", default="/tmp/smurf-monitor.json")
    return parser.parse_args()


def parse_icmp(packet: bytes) -> tuple[str, int] | None:
    if len(packet) < 28:
        return None

    ihl = (packet[0] & 0x0F) * 4
    if len(packet) < ihl + 8 or packet[9] != socket.IPPROTO_ICMP:
        return None

    source = socket.inet_ntoa(packet[12:16])
    icmp_type = packet[ihl]
    return source, icmp_type


def main() -> int:
    args = parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    sock.settimeout(0.5)

    deadline = time.monotonic() + args.duration
    replies: list[str] = []
    total_icmp = 0

    while time.monotonic() < deadline:
        try:
            packet, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue

        parsed = parse_icmp(packet)
        if parsed is None:
            continue

        source, icmp_type = parsed
        total_icmp += 1
        if icmp_type == 0 and source.startswith(args.source_prefix):
            replies.append(source)

    summary = {
        "duration": args.duration,
        "source_prefix": args.source_prefix,
        "reply_count": len(replies),
        "unique_reply_sources": sorted(set(replies)),
        "total_icmp_seen": total_icmp,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
