#!/usr/bin/env python3
"""Count UDP replies that arrive at the Fraggle victim."""

from __future__ import annotations

import argparse
import json
import socket
import time
from collections import Counter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor UDP replies at the Fraggle victim.")
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--source-prefix", default="10.152.0.", help="count replies from this source prefix")
    parser.add_argument("--port", type=int, default=7000, help="victim UDP port")
    parser.add_argument("--output", default="/tmp/fraggle-monitor.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(0.5)

    deadline = time.monotonic() + args.duration
    sources: Counter[str] = Counter()
    bytes_by_source: Counter[str] = Counter()
    total_udp = 0

    while time.monotonic() < deadline:
        try:
            data, client = sock.recvfrom(65535)
        except socket.timeout:
            continue

        source = client[0]
        total_udp += 1
        if source.startswith(args.source_prefix):
            sources[source] += 1
            bytes_by_source[source] += len(data)

    summary = {
        "duration": args.duration,
        "source_prefix": args.source_prefix,
        "listen_port": args.port,
        "reply_count": sum(sources.values()),
        "reply_bytes": sum(bytes_by_source.values()),
        "unique_reply_sources": sorted(sources),
        "replies_by_source": dict(sorted(sources.items())),
        "bytes_by_source": dict(sorted(bytes_by_source.items())),
        "total_udp_seen": total_udp,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
