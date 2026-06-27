#!/usr/bin/env python3
"""Live victim-side dashboard for the Smurf attack example."""

from __future__ import annotations

import argparse
import os
import socket
import time
from collections import Counter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize Smurf amplification at the victim.")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--source-prefix", default="10.152.0.", help="amplifier source prefix")
    parser.add_argument("--request-count", type=int, default=3, help="spoofed requests expected")
    parser.add_argument("--refresh", type=float, default=1.0, help="dashboard refresh interval")
    parser.add_argument("--no-clear", action="store_true", help="do not clear the terminal between updates")
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


def render(
    elapsed: float,
    total_replies: int,
    previous_total: int,
    sources: Counter[str],
    request_count: int,
    source_prefix: str,
    clear: bool,
) -> None:
    if clear:
        os.system("clear")

    unique_sources = len(sources)
    replies_per_second = total_replies - previous_total
    amplification = total_replies / max(request_count, 1)

    print("SMURF ATTACK MONITOR")
    print("====================")
    print(f"Victim view: ICMP echo replies from {source_prefix}*")
    print()
    print(f"elapsed seconds        : {elapsed:0.1f}")
    print(f"spoofed requests       : {request_count}")
    print(f"ICMP replies received  : {total_replies}")
    print(f"unique amplifier hosts : {unique_sources}")
    print(f"estimated amplification: {amplification:0.1f}x")
    print(f"replies in last window : {replies_per_second}")
    print()
    print("Top replying hosts")
    print("------------------")
    if not sources:
        print("(no replies yet)")
    else:
        for source, count in sources.most_common(12):
            print(f"{source:<16} {count:>5} replies")
    print()
    print("Start this monitor on the victim, then trigger the attack from AS150.")
    print(flush=True)


def main() -> int:
    args = parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    sock.settimeout(0.2)

    sources: Counter[str] = Counter()
    started = time.monotonic()
    next_render = started
    previous_total = 0

    while True:
        now = time.monotonic()
        elapsed = now - started
        if elapsed >= args.duration:
            break

        try:
            packet, _ = sock.recvfrom(65535)
        except socket.timeout:
            packet = b""

        if packet:
            parsed = parse_icmp(packet)
            if parsed is not None:
                source, icmp_type = parsed
                if icmp_type == 0 and source.startswith(args.source_prefix):
                    sources[source] += 1

        now = time.monotonic()
        if now >= next_render:
            total = sum(sources.values())
            render(
                elapsed=now - started,
                total_replies=total,
                previous_total=previous_total,
                sources=sources,
                request_count=args.request_count,
                source_prefix=args.source_prefix,
                clear=not args.no_clear,
            )
            previous_total = total
            next_render = now + args.refresh

    total = sum(sources.values())
    render(
        elapsed=time.monotonic() - started,
        total_replies=total,
        previous_total=previous_total,
        sources=sources,
        request_count=args.request_count,
        source_prefix=args.source_prefix,
        clear=not args.no_clear,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
