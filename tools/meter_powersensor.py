"""Temporary script to capture and analyse Powersensor UDP traffic from a live device."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections import Counter, defaultdict
from typing import Any


def capture(
    host: str,
    port: int,
    duration: float,
    subscribe_ttl: int,
) -> list[dict[str, Any]]:
    """Subscribe and collect JSON messages for the given duration."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    server = (host, port)
    sock.connect(server)
    sock.send(f"subscribe({subscribe_ttl})\n".encode())

    messages: list[dict[str, Any]] = []
    deadline = time.monotonic() + duration
    print(f"Connected to {host}:{port}, capturing for {duration}s...", flush=True)

    while time.monotonic() < deadline:
        try:
            raw = sock.recv(4096)
        except TimeoutError:
            continue
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"Non-JSON payload ({len(raw)} bytes): {raw!r} ({exc})", flush=True)
            continue
        messages.append(msg)
        print(json.dumps(msg, sort_keys=True), flush=True)

    sock.close()
    return messages


def summarise(messages: list[dict[str, Any]]) -> None:
    """Print a structural summary of captured messages."""
    if not messages:
        print("\nNo messages captured.", flush=True)
        return

    type_counts = Counter(m.get("type") for m in messages)
    device_counts = Counter(
        (m.get("type"), m.get("device"), m.get("subtype")) for m in messages
    )
    keys_by_signature: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for msg in messages:
        signature = (msg.get("type"), msg.get("device"), msg.get("subtype"))
        keys_by_signature[signature].update(msg.keys())

    print("\n=== Summary ===", flush=True)
    print(f"Total messages: {len(messages)}", flush=True)
    print(f"By type: {dict(type_counts)}", flush=True)
    print(f"By (type, device, subtype): {dict(device_counts)}", flush=True)

    for signature, keys in sorted(keys_by_signature.items()):
        print(f"\nSignature {signature}:", flush=True)
        print(f"  keys: {sorted(keys)}", flush=True)
        samples = [m for m in messages if (m.get("type"), m.get("device"), m.get("subtype")) == signature]
        print(f"  sample: {json.dumps(samples[0], sort_keys=True)}", flush=True)

    macs = sorted({m.get("mac") for m in messages if m.get("mac")})
    if macs:
        print(f"\nMAC addresses seen: {macs}", flush=True)


def main() -> None:
    """Run the Powersensor traffic meter."""
    parser = argparse.ArgumentParser(description="Meter live Powersensor UDP output")
    parser.add_argument("--host", default="192.168.0.100")
    parser.add_argument("--port", type=int, default=49476)
    parser.add_argument("--duration", type=float, default=90.0)
    parser.add_argument("--subscribe-ttl", type=int, default=180)
    args = parser.parse_args()

    try:
        messages = capture(args.host, args.port, args.duration, args.subscribe_ttl)
    except OSError as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    summarise(messages)


if __name__ == "__main__":
    main()
