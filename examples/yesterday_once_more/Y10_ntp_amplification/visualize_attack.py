#!/usr/bin/env python3
"""Live victim-side dashboard for the NTP-like amplification example."""

from __future__ import annotations

import argparse
import os
import socket
import time
from collections import Counter, defaultdict
from typing import DefaultDict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize NTP-like UDP amplification at the victim.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--expected-requests", type=int, default=3)
    parser.add_argument("--request-size", type=int, default=36, help="estimated attacker request size in bytes")
    parser.add_argument("--refresh", type=float, default=1.0)
    parser.add_argument("--no-clear", action="store_true", help="do not clear the terminal between updates")
    return parser.parse_args()


def render(
    elapsed: float,
    packet_count: int,
    previous_packet_count: int,
    total_bytes: int,
    previous_total_bytes: int,
    packets_by_source: Counter[str],
    bytes_by_source: DefaultDict[str, int],
    expected_requests: int,
    request_size: int,
    clear: bool,
) -> None:
    if clear:
        os.system("clear")

    unique_sources = len(packets_by_source)
    packets_last_window = packet_count - previous_packet_count
    bytes_last_window = total_bytes - previous_total_bytes
    estimated_request_bytes = max(expected_requests, 0) * max(request_size, 1)
    byte_amplification = total_bytes / max(estimated_request_bytes, 1)

    print("NTP-LIKE AMPLIFICATION MONITOR")
    print("==============================")
    print("Victim view: UDP responses from lab amplifiers")
    print()
    print(f"elapsed seconds           : {elapsed:0.1f}")
    print(f"expected trigger requests : {expected_requests}")
    print(f"estimated request bytes   : {estimated_request_bytes}")
    print(f"UDP packets received      : {packet_count}")
    print(f"total response bytes      : {total_bytes}")
    print(f"unique amplifiers         : {unique_sources}")
    print(f"estimated byte amp        : {byte_amplification:0.1f}x")
    print(f"packets in last window    : {packets_last_window}")
    print(f"bytes in last window      : {bytes_last_window}")
    print()
    print("Top amplifiers")
    print("--------------")
    if not packets_by_source:
        print("(no UDP responses yet)")
    else:
        for source, packets in packets_by_source.most_common(12):
            print(f"{source:<16} {packets:>5} packets {bytes_by_source[source]:>8} bytes")
    print()
    print("Start this monitor on the victim, then trigger the attack from AS150.")
    print(flush=True)


def main() -> int:
    args = parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.2)

    packets_by_source: Counter[str] = Counter()
    bytes_by_source: DefaultDict[str, int] = defaultdict(int)
    packet_count = 0
    total_bytes = 0
    previous_packet_count = 0
    previous_total_bytes = 0
    started = time.monotonic()
    next_render = started

    while True:
        now = time.monotonic()
        elapsed = now - started
        if elapsed >= args.duration:
            break

        try:
            payload, source = sock.recvfrom(65535)
        except socket.timeout:
            payload = b""
            source = ("", 0)

        if payload:
            source_ip = source[0]
            packet_count += 1
            total_bytes += len(payload)
            packets_by_source[source_ip] += 1
            bytes_by_source[source_ip] += len(payload)

        now = time.monotonic()
        if now >= next_render:
            render(
                elapsed=now - started,
                packet_count=packet_count,
                previous_packet_count=previous_packet_count,
                total_bytes=total_bytes,
                previous_total_bytes=previous_total_bytes,
                packets_by_source=packets_by_source,
                bytes_by_source=bytes_by_source,
                expected_requests=args.expected_requests,
                request_size=args.request_size,
                clear=not args.no_clear,
            )
            previous_packet_count = packet_count
            previous_total_bytes = total_bytes
            next_render = now + args.refresh

    render(
        elapsed=time.monotonic() - started,
        packet_count=packet_count,
        previous_packet_count=previous_packet_count,
        total_bytes=total_bytes,
        previous_total_bytes=previous_total_bytes,
        packets_by_source=packets_by_source,
        bytes_by_source=bytes_by_source,
        expected_requests=args.expected_requests,
        request_size=args.request_size,
        clear=not args.no_clear,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
