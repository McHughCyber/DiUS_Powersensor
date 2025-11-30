"""Sensor platform for DiUS_Powersensor."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfPower

from .const import DOMAIN
from .const import MAIN_ICON
from .const import PLUG_ICON
from .const import SENSORS
from .const import U_CONV
from .const import W_ADJ
from .entity import DiusEntity
from .enums import Msg_keys
from .enums import Msg_values

POWER_WATT = UnitOfPower.WATT


@dataclass
class DiusSensorDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for sens in SENSORS:
        if entry.options.get(sens) is True:
            desc = DiusSensorDescription(
                key=sens,
                name=sens,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=POWER_WATT,
            )
            async_add_devices([DiusSensor(coordinator, entry, desc)], False)


class DiusSensor(DiusEntity, SensorEntity):
    """dius Sensor class."""

    entity_description: DiusSensorDescription

    def __init__(self, coordinator, config_entry, description: DiusSensorDescription):
        super().__init__(coordinator, config_entry, description)
        self._config = config_entry
        self.entity_description = description
        self._extra_attr = {}
        self._attr_name = None
        self._power: float | None = None
        self._device_type = None
        self._mac = None
        # Try to extract device type and MAC from coordinator data
        if coordinator.data:
            data = coordinator.data.get(description.key)
            if data:
                self._mac = data.get(Msg_keys.mac.value)
                # Determine device type from key
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
            self._power = data.get(Msg_keys.power.value)
            if data.get(Msg_keys.unit, "") == "U":
                self._power = self._power / self._config.options.get(U_CONV)
            if (
                self._device_type == "sensor"
                or self.entity_description.key == Msg_values.sensor.value
            ):
                self._power += self._config.options.get(W_ADJ)
            self._power = round(self._power)

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
