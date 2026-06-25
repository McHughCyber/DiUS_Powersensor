"""UDP mock Powersensor server aligned with live device behaviour."""

from __future__ import annotations

import argparse
import copy
import json
import socket
import time
from pathlib import Path
from typing import Any

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "powersensor_messages.json"
)

SUBSCRIBE_PREFIX = b"subscribe"


def load_fixture_messages() -> dict[str, dict[str, Any]]:
    """Load representative message shapes captured from a live gateway."""
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def encode_payload(payload: dict[str, Any]) -> bytes:
    """Serialise a message the same way the gateway does."""
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def sensor_payloads(
    templates: dict[str, dict[str, Any]],
    starttime: int,
    power_delta: int = 0,
) -> list[bytes]:
    """Build instant_power sensor payloads for each configured sensor."""
    payloads: list[bytes] = []
    for key in ("sensor_house_net", "sensor_solar"):
        message = copy.deepcopy(templates[key])
        message["starttime"] = starttime
        message["power"] = int(message["power"]) + power_delta
        message["summation"] = int(message["summation"]) + power_delta * message["duration"]
        payloads.append(encode_payload(message))
    return payloads


def plug_payload(
    template: dict[str, Any],
    starttime: float,
    count: int,
    power_jitter: float = 0.0,
) -> bytes:
    """Build a single plug instant_power payload."""
    message = copy.deepcopy(template)
    message["starttime"] = starttime
    message["count"] = count
    message["power"] = float(message["power"]) + power_jitter
    message["summation"] = float(message["summation"]) + message["power"] * message["duration"]
    return encode_payload(message)


def subscription_payload(subtype: str) -> bytes:
    """Build subscription warning/expiry payloads."""
    return encode_payload({"type": "subscription", "subtype": subtype})


def run_server(
    host: str,
    port: int,
    plug_interval: float,
    sensor_interval: float,
    subscription_cycle: float | None,
) -> None:
    """Listen for subscribe requests and emit realistic gateway traffic."""
    templates = load_fixture_messages()
    address = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(address)
    print(
        f"mock_powersensor listening on {host}:{port} "
        f"(plug every {plug_interval}s, sensors every {sensor_interval}s)",
        flush=True,
    )

    subscribers: set[tuple[str, int]] = set()
    plug_count = 12
    sensor_tick = 0
    started = time.monotonic()
    last_plug_emit = 0.0
    last_sensor_emit = 0.0
    last_subscription_emit = 0.0

    try:
        while True:
            sock.settimeout(0.1)
            try:
                data, client = sock.recvfrom(1024)
            except TimeoutError:
                client = None
            else:
                if data.startswith(SUBSCRIBE_PREFIX):
                    subscribers.add(client)
                    print(f"subscriber added: {client}", flush=True)

            if not subscribers:
                continue

            now = time.monotonic()
            elapsed = now - started

            if now - last_plug_emit >= plug_interval:
                plug_count += 1
                for client in subscribers:
                    sock.sendto(
                        plug_payload(
                            templates["plug"],
                            starttime=time.time(),
                            count=plug_count,
                            power_jitter=(plug_count % 3) * 0.05,
                        ),
                        client,
                    )
                last_plug_emit = now

            if now - last_sensor_emit >= sensor_interval:
                sensor_tick += 1
                starttime = int(time.time())
                for payload in sensor_payloads(
                    templates,
                    starttime=starttime,
                    power_delta=sensor_tick,
                ):
                    for client in subscribers:
                        sock.sendto(payload, client)
                last_sensor_emit = now

            if (
                subscription_cycle is not None
                and now - last_subscription_emit >= subscription_cycle
            ):
                for client in subscribers:
                    sock.sendto(subscription_payload("warning"), client)
                last_subscription_emit = now

            if elapsed > 3600:
                started = now
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


def main() -> None:
    """Run the mock Powersensor UDP server."""
    parser = argparse.ArgumentParser(description="Mock Powersensor UDP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=49476)
    parser.add_argument(
        "--plug-interval",
        type=float,
        default=1.0,
        help="Seconds between plug instant_power messages (live device ~1s)",
    )
    parser.add_argument(
        "--sensor-interval",
        type=float,
        default=30.0,
        help="Seconds between sensor instant_power bursts (live device ~30s)",
    )
    parser.add_argument(
        "--subscription-cycle",
        type=float,
        default=None,
        help="Optional seconds between subscription warning messages",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Deprecated alias for --plug-interval",
    )
    args = parser.parse_args()
    plug_interval = args.plug_interval if args.interval is None else args.interval
    run_server(
        args.host,
        args.port,
        plug_interval,
        args.sensor_interval,
        args.subscription_cycle,
    )


if __name__ == "__main__":
    main()
