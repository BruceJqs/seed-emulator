#!/usr/bin/env python3
"""Live victim-side dashboard for the Smurf/Fraggle attack example."""

from __future__ import annotations

import argparse
import os
import socket
import time
from collections import Counter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize directed-broadcast amplification at the victim.")
    parser.add_argument("--mode", choices=["smurf", "fraggle"], default="smurf")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--source-prefix", default="10.152.0.", help="amplifier source prefix")
    parser.add_argument("--request-count", type=int, default=3, help="spoofed requests expected")
    parser.add_argument("--udp-port", type=int, default=7000, help="victim UDP port for Fraggle replies")
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
    mode: str,
    elapsed: float,
    total_replies: int,
    previous_total: int,
    sources: Counter[str],
    request_count: int,
    source_prefix: str,
    clear: bool,
    total_bytes: int = 0,
) -> None:
    if clear:
        os.system("clear")

    unique_sources = len(sources)
    replies_per_second = total_replies - previous_total
    amplification = total_replies / max(request_count, 1)

    title = "SMURF ATTACK MONITOR" if mode == "smurf" else "FRAGGLE ATTACK MONITOR"
    protocol = "ICMP echo replies" if mode == "smurf" else "UDP replies"

    print(title)
    print("=" * len(title))
    print(f"Victim view: {protocol} from {source_prefix}*")
    print()
    print(f"elapsed seconds        : {elapsed:0.1f}")
    print(f"spoofed requests       : {request_count}")
    print(f"{protocol} received".ljust(24) + f": {total_replies}")
    print(f"unique amplifier hosts : {unique_sources}")
    print(f"estimated amplification: {amplification:0.1f}x")
    print(f"replies in last window : {replies_per_second}")
    if mode == "fraggle":
        print(f"UDP response bytes     : {total_bytes}")
    print()
    print("Top replying hosts")
    print("------------------")
    if not sources:
        print("(no replies yet)")
    else:
        for source, count in sources.most_common(12):
            print(f"{source:<16} {count:>5} replies")
    print()
    print("Start this monitor on the victim, then trigger the matching attack from AS150.")
    print(flush=True)


def main() -> int:
    args = parse_args()

    if args.mode == "smurf":
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", args.udp_port))
    sock.settimeout(0.2)

    sources: Counter[str] = Counter()
    bytes_by_source: Counter[str] = Counter()
    started = time.monotonic()
    next_render = started
    previous_total = 0

    while True:
        now = time.monotonic()
        elapsed = now - started
        if elapsed >= args.duration:
            break

        try:
            packet, client = sock.recvfrom(65535)
        except socket.timeout:
            packet = b""

        if packet:
            if args.mode == "smurf":
                parsed = parse_icmp(packet)
                if parsed is not None:
                    source, icmp_type = parsed
                    if icmp_type == 0 and source.startswith(args.source_prefix):
                        sources[source] += 1
            else:
                source = client[0]
                if source.startswith(args.source_prefix):
                    sources[source] += 1
                    bytes_by_source[source] += len(packet)

        now = time.monotonic()
        if now >= next_render:
            total = sum(sources.values())
            render(
                mode=args.mode,
                elapsed=now - started,
                total_replies=total,
                previous_total=previous_total,
                sources=sources,
                request_count=args.request_count,
                source_prefix=args.source_prefix,
                clear=not args.no_clear,
                total_bytes=sum(bytes_by_source.values()),
            )
            previous_total = total
            next_render = now + args.refresh

    total = sum(sources.values())
    render(
        mode=args.mode,
        elapsed=time.monotonic() - started,
        total_replies=total,
        previous_total=previous_total,
        sources=sources,
        request_count=args.request_count,
        source_prefix=args.source_prefix,
        clear=not args.no_clear,
        total_bytes=sum(bytes_by_source.values()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
