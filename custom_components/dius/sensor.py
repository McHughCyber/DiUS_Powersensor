"""Sensor platform for DiUS_Powersensor."""

from __future__ import annotations

import logging
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
from .const import SENSORS
from .const import SENSOR_ENERGY_NAME_PATTERN
from .const import U_CONV
from .const import W_ADJ
from .entity import DiusEntity
from .enums import Msg_keys
from .enums import Msg_values

POWER_WATT = UnitOfPower.WATT
ENERGY_KWH = UnitOfEnergy.KILO_WATT_HOUR

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass
class DiusSensorDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    measurement_type: str = "power"


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = []

    # Check if we have the new data structure (multiple sensors)
    sensors_data = coordinator.data.get("sensors", {})
    plugs_data = coordinator.data.get("plugs", {})

    _LOGGER.debug(
        "Setting up sensors. Available sensors: %s, Available plugs: %s",
        list(sensors_data.keys()),
        list(plugs_data.keys()),
    )

    # If we have the new structure with multiple sensors
    if sensors_data or plugs_data:
        # Create sensors for each detected sensor device
        for mac, sensor_data in sensors_data.items():
            # Check if this specific sensor is enabled in options
            sensor_key = f"sensor_{mac}"
            if entry.options.get(sensor_key, True):  # Default to enabled
                # Create a more descriptive name using the last 4 characters of MAC
                sensor_name = f"Power Sensor {mac[-4:].upper()}"
                desc = DiusSensorDescription(
                    key=sensor_key,
                    name=sensor_name,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=POWER_WATT,
                    measurement_type="power",
                )
                device = DiusSensor(coordinator, entry, desc, mac, "sensor")
                devices.append(device)
                _LOGGER.debug(
                    "Created sensor entity with unique_id: %s, name: %s",
                    device._attr_unique_id,
                    sensor_name,
                )

            energy_key = SENSOR_ENERGY_NAME_PATTERN.format(mac=mac)
            if entry.options.get(energy_key, True):
                energy_name = f"Power Sensor {mac[-4:].upper()} Energy"
                desc = DiusSensorDescription(
                    key=energy_key,
                    name=energy_name,
                    device_class=SensorDeviceClass.ENERGY,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    native_unit_of_measurement=ENERGY_KWH,
                    measurement_type="energy",
                )
                device = DiusEnergySensor(coordinator, entry, desc, mac, "sensor")
                devices.append(device)
                _LOGGER.debug(
                    "Created sensor energy entity with unique_id: %s, name: %s",
                    device._attr_unique_id,
                    energy_name,
                )

        # Create sensors for each detected plug device
        for mac, plug_data in plugs_data.items():
            # Check if this specific plug is enabled in options
            plug_key = f"plug_{mac}"
            if entry.options.get(plug_key, True):  # Default to enabled
                # Create a more descriptive name using the last 4 characters of MAC
                plug_name = f"Power Plug {mac[-4:].upper()}"
                desc = DiusSensorDescription(
                    key=plug_key,
                    name=plug_name,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=POWER_WATT,
                    measurement_type="power",
                )
                device = DiusSensor(coordinator, entry, desc, mac, "plug")
                devices.append(device)
                _LOGGER.debug(
                    "Created plug entity with unique_id: %s, name: %s",
                    device._attr_unique_id,
                    plug_name,
                )

    # Fallback to old structure for backward compatibility
    else:
        _LOGGER.debug("Using fallback structure for backward compatibility")
        for sens in SENSORS:
            if entry.options.get(sens) is True:
                desc = DiusSensorDescription(
                    key=sens,
                    name=sens,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=POWER_WATT,
                    measurement_type="power",
                )
                device = DiusSensor(coordinator, entry, desc)
                devices.append(device)
                _LOGGER.debug(
                    "Created fallback entity with unique_id: %s", device._attr_unique_id
                )

    _LOGGER.debug("Total devices to add: %d", len(devices))
    async_add_devices(devices, False)


class DiusSensor(DiusEntity, SensorEntity):
    """dius Sensor class."""

    entity_description: DiusSensorDescription

    def __init__(
        self,
        coordinator,
        config_entry,
        description: DiusSensorDescription,
        mac: str = None,
        device_type: str = None,
    ):
        super().__init__(coordinator, config_entry, description, mac)
        if mac:
            self._attr_unique_id = f"{mac}_{description.key}"
        self._config = config_entry
        self.entity_description = description
        self._mac = mac
        self._device_type = device_type
        self._extra_attr = {}
        self._attr_name = None
        self._power: float | None = None
        # Try to extract device type and MAC from coordinator data
        if coordinator.data and (self._mac is None or self._device_type is None):
            data = coordinator.data.get(description.key)
            if data:
                if self._mac is None:
                    self._mac = data.get(Msg_keys.mac.value)
                # Determine device type from key
                if self._device_type is None:
                    if description.key == Msg_values.plug.value:
                        self._device_type = "plug"
                    elif description.key == Msg_values.sensor.value:
                        self._device_type = "sensor"

    @property
    def native_value(self):
        """Return the native measurement."""
        data = None

        # Handle new multi-sensor structure
        if self._device_type and self._mac:
            device_data = self.coordinator.data.get(f"{self._device_type}s", {})
            if self._mac in device_data:
                data = device_data[self._mac]

        # Fallback to old structure for backward compatibility
        else:
            if self.coordinator.data.get(self.entity_description.key) is not None:
                data = self.coordinator.data.get(self.entity_description.key)

        if data:
            power = data.get(Msg_keys.power.value)
            if power is None:
                self._power = None
                return self._power

            if data.get(Msg_keys.unit, "") == "U":
                conversion = self._config.options.get(U_CONV)
                if conversion:
                    power = power / conversion
                else:
                    _LOGGER.debug("Missing conversion factor for unit 'U'; skipping.")
            if (
                self._device_type == "sensor"
                or self.entity_description.key == Msg_values.sensor.value
            ):
                power += self._config.options.get(W_ADJ, 0)
            self._power = round(power)

        return self._power

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if (
            self._device_type == "plug"
            or self.entity_description.key == Msg_values.plug.value
        ):
            return PLUG_ICON
        if (
            self._device_type == "sensor"
            or self.entity_description.key == Msg_values.sensor.value
        ):
            return MAIN_ICON
        return MAIN_ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = None

        # Handle new multi-sensor structure
        if self._device_type and self._mac:
            device_data = self.coordinator.data.get(f"{self._device_type}s", {})
            if self._mac in device_data:
                data = device_data[self._mac] | {
                    "HA_reconnects": self.coordinator.data.get("reconnects")
                }

        # Fallback to old structure for backward compatibility
        else:
            if self.coordinator.data.get(self.entity_description.key) is not None:
                data = self.coordinator.data.get(self.entity_description.key) | {
                    "HA_reconnects": self.coordinator.data.get("reconnects")
                }

        return data


class DiusEnergySensor(DiusEntity, SensorEntity, RestoreEntity):
    """Energy sensor derived from power samples."""

    entity_description: DiusSensorDescription

    def __init__(self, coordinator, config_entry, description, mac: str, device_type: str):
        super().__init__(coordinator, config_entry, description, mac)
        self._attr_unique_id = f"{mac}_{description.key}"
        self._mac = mac
        self._device_type = device_type
        self._energy_kwh: float = 0.0
        self._last_starttime: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore previous energy state when available."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._energy_kwh = float(last_state.state)
            except ValueError:
                _LOGGER.debug("Could not restore energy state '%s'", last_state.state)

    @property
    def native_value(self):
        """Return the cumulative energy value in kWh."""
        device_data = self.coordinator.data.get(f"{self._device_type}s", {})
        data = device_data.get(self._mac)
        if not data:
            return round(self._energy_kwh, 6)

        if data.get("role") != "solar":
            return round(self._energy_kwh, 6)

        power = data.get(Msg_keys.power.value)
        if power is None:
            return round(self._energy_kwh, 6)

        starttime = data.get(Msg_keys.starttime.value)
        duration = data.get(Msg_keys.duration.value)
        elapsed_seconds = 0.0

        try:
            power_value = float(power)
        except (TypeError, ValueError):
            return round(self._energy_kwh, 6)

        try:
            if duration is not None and float(duration) > 0:
                elapsed_seconds = float(duration)
            elif starttime is not None:
                current_starttime = float(starttime)
                if self._last_starttime is not None and current_starttime > self._last_starttime:
                    elapsed_seconds = current_starttime - self._last_starttime
                self._last_starttime = current_starttime
        except (TypeError, ValueError):
            elapsed_seconds = 0.0

        if elapsed_seconds <= 0:
            return round(self._energy_kwh, 6)

        increment_kwh = max(power_value, 0.0) * elapsed_seconds / 3600000
        if increment_kwh > 0:
            self._energy_kwh += increment_kwh

        return round(self._energy_kwh, 6)

    @property
    def icon(self):
        """Return icon for energy sensor."""
        return MAIN_ICON
