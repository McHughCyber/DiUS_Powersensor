"""Normalized models for DiUS PowerSensor messages."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from .enums import Msg_keys
from .enums import Msg_values

DEVICE_TYPE_SENSOR = Msg_values.sensor.value
DEVICE_TYPE_PLUG = Msg_values.plug.value

CONNECTION_STOPPED = "stopped"
CONNECTION_CONNECTING = "connecting"
CONNECTION_SUBSCRIBED = "subscribed"
CONNECTION_RECEIVING = "receiving"
CONNECTION_EXPIRED = "expired"
CONNECTION_RECONNECTING = "reconnecting"
CONNECTION_FAILED = "failed"

DEFAULT_STALE_TIMEOUT_SECONDS = 600
DEFAULT_WATCHDOG_TIMEOUT_SECONDS = 240
SUMMATION_TO_KWH = 1_000_000


@dataclass(frozen=True)
class ConnectionSnapshot:
    """Connection state exposed to Home Assistant."""

    state: str = CONNECTION_STOPPED
    reconnects: int = 0
    last_message_at: float | None = None
    last_subscribe_at: float | None = None
    last_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class DiusDeviceData:
    """Normalized device data for one sensor or plug."""

    key: str
    mac: str
    device_type: str
    role: str | None
    power_w: float | None
    unit: str | None
    duration_s: float | None
    starttime: float | None
    summation: float | None
    count: int | None
    last_seen: float
    raw: dict[str, Any]

    @property
    def is_sensor(self) -> bool:
        """Return whether this device is a PowerSensor."""
        return self.device_type == DEVICE_TYPE_SENSOR

    @property
    def is_plug(self) -> bool:
        """Return whether this device is a plug."""
        return self.device_type == DEVICE_TYPE_PLUG

    @property
    def is_solar(self) -> bool:
        """Return whether this sensor is reporting solar production."""
        return self.role == "solar"

    @property
    def sample_id(self) -> tuple[Any, ...]:
        """Return a stable identity for the current sample."""
        return (
            self.mac,
            self.device_type,
            self.starttime,
            self.count,
            self.duration_s,
            self.power_w,
            self.summation,
        )

    @property
    def summation_kwh(self) -> float | None:
        """Return device summation converted to kWh when present."""
        if self.summation is None:
            return None
        return max(self.summation, 0.0) / SUMMATION_TO_KWH

    def is_stale(self, now: float, stale_timeout_seconds: float) -> bool:
        """Return whether this device has not reported recently enough."""
        return now - self.last_seen > stale_timeout_seconds

    def as_dict(self, *, include_raw: bool = True) -> dict[str, Any]:
        """Return a serializable representation."""
        data = asdict(self)
        if not include_raw:
            data.pop("raw", None)
        return data


@dataclass(frozen=True)
class DiusSnapshot:
    """Integration data snapshot consumed by entities and diagnostics."""

    devices: dict[str, DiusDeviceData]
    connection: ConnectionSnapshot
    counters: dict[str, int]
    stale_timeout_seconds: float = DEFAULT_STALE_TIMEOUT_SECONDS

    def as_dict(self, *, include_raw: bool = True) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "devices": {
                key: device.as_dict(include_raw=include_raw)
                for key, device in self.devices.items()
            },
            "connection": self.connection.as_dict(),
            "counters": dict(self.counters),
            "stale_timeout_seconds": self.stale_timeout_seconds,
        }


def device_key(device_type: str, mac: str) -> str:
    """Return the stable key for a device."""
    return f"{device_type}_{mac}"


def entity_key(device: DiusDeviceData, measurement: str) -> str:
    """Return the stable key for an entity option/unique id suffix."""
    return f"{device.key}_{measurement}"


def parse_float(value: Any) -> float | None:
    """Parse a float from a sensor payload field."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    """Parse an int from a sensor payload field."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_instant_power_message(
    msg: dict[str, Any],
    *,
    now: float,
    u_conv: float,
    w_adj: float,
) -> DiusDeviceData | None:
    """Normalize an instant_power message into a device model."""
    if msg.get(Msg_keys.type.value) != Msg_values.instant_power.value:
        return None

    mac = msg.get(Msg_keys.mac.value)
    device_type = msg.get(Msg_keys.device.value)
    if not mac or device_type not in {DEVICE_TYPE_SENSOR, DEVICE_TYPE_PLUG}:
        return None

    unit = msg.get(Msg_keys.unit.value)
    power_w = parse_float(msg.get(Msg_keys.power.value))
    if power_w is not None and unit == Msg_values.U.value and u_conv > 0:
        power_w = power_w / u_conv
    if power_w is not None and device_type == DEVICE_TYPE_SENSOR:
        power_w += w_adj

    return DiusDeviceData(
        key=device_key(device_type, mac),
        mac=str(mac),
        device_type=device_type,
        role=msg.get("role"),
        power_w=power_w,
        unit=unit,
        duration_s=parse_float(msg.get(Msg_keys.duration.value)),
        starttime=parse_float(msg.get(Msg_keys.starttime.value)),
        summation=parse_float(msg.get(Msg_keys.summation.value)),
        count=parse_int(msg.get(Msg_keys.count.value)),
        last_seen=now,
        raw=dict(msg),
    )
