"""UDP mock Powersensor server for integration tests."""

from __future__ import annotations

import argparse
import json
import socket


def sensor_payload() -> bytes:
    """Return a sample sensor instant_power JSON payload."""
    payload = {
        "mac": "2cf4320aaaa",
        "device": "sensor",
        "summation": 21931891707,
        "duration": 30,
        "type": "instant_power",
        "batteryMicrovolt": 4143072,
        "unit": "U",
        "starttime": 1653477217,
        "power": 93184,
    }
    return json.dumps(payload).encode("utf-8")


def run_server(host: str, port: int, interval: float) -> None:
    """Listen for UDP packets and periodically emit sensor payloads."""
    address = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(address)
    print(f"mock_powersensor listening on {host}:{port}", flush=True)

    try:
        while True:
            sock.settimeout(interval)
            try:
                _data, client = sock.recvfrom(1024)
            except TimeoutError:
                client = address
            sock.sendto(sensor_payload(), client)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


def main() -> None:
    """Run the mock Powersensor UDP server."""
    parser = argparse.ArgumentParser(description="Mock Powersensor UDP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=49476)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    run_server(args.host, args.port, args.interval)


if __name__ == "__main__":
    main()
