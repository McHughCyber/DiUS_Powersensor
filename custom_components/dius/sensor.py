"""Sensor platform for DiUS_Powersensor."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.const import UnitOfPower
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .const import MAIN_ICON
from .const import PLUG_ICON
from .entity import DiusEntity
from .models import entity_key

POWER_WATT = UnitOfPower.WATT
ENERGY_KWH = UnitOfEnergy.KILO_WATT_HOUR

_LOGGER: logging.Logger = logging.getLogger(__package__)
MAX_TRACKED_SAMPLES = 256


@dataclass
class DiusSensorDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    measurement_type: str = "power"


POWER_MEASUREMENT = "power"
ENERGY_MEASUREMENT = "energy"

POWER_DESCRIPTION = DiusSensorDescription(
    key=POWER_MEASUREMENT,
    translation_key=POWER_MEASUREMENT,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=POWER_WATT,
    suggested_display_precision=0,
    measurement_type=POWER_MEASUREMENT,
)

ENERGY_DESCRIPTION = DiusSensorDescription(
    key=ENERGY_MEASUREMENT,
    translation_key=ENERGY_MEASUREMENT,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=ENERGY_KWH,
    suggested_display_precision=3,
    measurement_type=ENERGY_MEASUREMENT,
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up sensor platform with dynamic device discovery."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_entity_keys: set[str] = set()

    def add_new_entities() -> None:
        devices = []
        if not coordinator.data:
            return

        for device in coordinator.data.devices.values():
            power_key = entity_key(device, POWER_MEASUREMENT)
            if power_key not in known_entity_keys and entry.options.get(
                power_key, True
            ):
                known_entity_keys.add(power_key)
                devices.append(DiusPowerSensor(coordinator, entry, device))

            energy_key = entity_key(device, ENERGY_MEASUREMENT)
            if (
                device.is_sensor
                and device.is_solar
                and energy_key not in known_entity_keys
                and entry.options.get(energy_key, True)
            ):
                known_entity_keys.add(energy_key)
                devices.append(DiusEnergySensor(coordinator, entry, device))

        if devices:
            _LOGGER.debug("Adding %d DiUS entities", len(devices))
            async_add_devices(devices)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class DiusPowerSensor(DiusEntity, SensorEntity):
    """Power sensor entity."""

    entity_description = POWER_DESCRIPTION

    def __init__(self, coordinator, config_entry, device) -> None:
        """Initialize power sensor."""
        super().__init__(coordinator, config_entry, device)
        self._attr_unique_id = (
            f"{device.mac}_plug_power"
            if device.is_plug
            else f"{device.mac}_sensor_power"
        )
        self._attr_name = None

    @property
    def native_value(self):
        """Return the native power value in watts."""
        device = self.device
        if device is None or device.power_w is None:
            return None
        return round(device.power_w)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        device = self.device or self._device
        return PLUG_ICON if device.is_plug else MAIN_ICON

    @property
    def extra_state_attributes(self):
        """Return curated state attributes."""
        device = self.device
        if device is None:
            return None
        return _device_attributes(device, self.coordinator.data.connection.reconnects)


class DiusEnergySensor(DiusEntity, SensorEntity, RestoreEntity):
    """Energy sensor derived from solar samples or device summation."""

    entity_description = ENERGY_DESCRIPTION

    def __init__(self, coordinator, config_entry, device) -> None:
        """Initialize energy sensor."""
        super().__init__(coordinator, config_entry, device)
        self._attr_unique_id = f"{device.mac}_sensor_energy"
        self._attr_name = None
        self._derived_energy_kwh: float = 0.0
        self._sample_window: deque[tuple] = deque(maxlen=MAX_TRACKED_SAMPLES)

    async def async_added_to_hass(self) -> None:
        """Restore previous derived energy state when available."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._derived_energy_kwh = float(last_state.state)
            except ValueError:
                _LOGGER.debug("Could not restore energy state '%s'", last_state.state)

    @property
    def native_value(self):
        """Return cumulative energy in kWh."""
        device = self.device
        if device is None or not device.is_solar:
            return round(self._derived_energy_kwh, 6)

        summation_kwh = device.summation_kwh
        if summation_kwh is not None:
            return round(summation_kwh, 6)

        sample_id = device.sample_id
        if sample_id not in self._sample_window:
            self._sample_window.append(sample_id)
            increment_kwh = _derived_increment_kwh(device)
            if increment_kwh > 0:
                self._derived_energy_kwh += increment_kwh

        return round(self._derived_energy_kwh, 6)

    @property
    def icon(self):
        """Return icon for energy sensor."""
        return MAIN_ICON

    @property
    def extra_state_attributes(self):
        """Return curated state attributes."""
        device = self.device
        if device is None:
            return None
        return _device_attributes(device, self.coordinator.data.connection.reconnects)


def _derived_increment_kwh(device) -> float:
    """Return derived kWh increment for a device sample."""
    if device.power_w is None or device.duration_s is None or device.duration_s <= 0:
        return 0.0
    return max(device.power_w, 0.0) * device.duration_s / 3_600_000


def _device_attributes(device, reconnects: int) -> dict:
    """Return curated device attributes."""
    attrs = {
        "mac": device.mac,
        "device_type": device.device_type,
        "last_seen": device.last_seen,
        "HA_reconnects": reconnects,
    }
    optional_fields = {
        "role": device.role,
        "source": device.raw.get("source"),
        "unit": device.unit,
        "duration_s": device.duration_s,
        "starttime": device.starttime,
        "count": device.count,
        "summation": device.summation,
        "voltage": device.raw.get("voltage"),
        "current": device.raw.get("current"),
        "active_current": device.raw.get("active_current"),
        "reactive_current": device.raw.get("reactive_current"),
        "batteryMicrovolt": device.raw.get("batteryMicrovolt"),
    }
    attrs.update(
        {key: value for key, value in optional_fields.items() if value is not None}
    )
    return attrs
