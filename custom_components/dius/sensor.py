"""Sensor platform for DiUS_Powersensor."""

from __future__ import annotations

import logging
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

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass
class DiusSensorDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = []
    
    # Check if we have the new data structure (multiple sensors)
    sensors_data = coordinator.data.get("sensors", {})
    plugs_data = coordinator.data.get("plugs", {})
    
    _LOGGER.debug("Setting up sensors. Available sensors: %s, Available plugs: %s", 
                  list(sensors_data.keys()), list(plugs_data.keys()))
    
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
                )
                device = DiusSensor(coordinator, entry, desc, mac, "sensor")
                devices.append(device)
                _LOGGER.debug("Created sensor entity with unique_id: %s, name: %s", device._attr_unique_id, sensor_name)
        
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
                )
                device = DiusSensor(coordinator, entry, desc, mac, "plug")
                devices.append(device)
                _LOGGER.debug("Created plug entity with unique_id: %s, name: %s", device._attr_unique_id, plug_name)
    
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
                )
                device = DiusSensor(coordinator, entry, desc)
                devices.append(device)
                _LOGGER.debug("Created fallback entity with unique_id: %s", device._attr_unique_id)
    
    _LOGGER.debug("Total devices to add: %d", len(devices))
    async_add_devices(devices, False)


class DiusSensor(DiusEntity, SensorEntity):
    """dius Sensor class."""

    entity_description: DiusSensorDescription

    def __init__(self, coordinator, config_entry, description: DiusSensorDescription, mac: str = None, device_type: str = None):
        super().__init__(coordinator, config_entry, description, mac)
        self._config = config_entry
        self.entity_description = description
        self._mac = mac
        self._device_type = device_type
        self._extra_attr = {}
        self._attr_name = None
        self._power: float | None = None

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
            if self._device_type == "sensor" or self.entity_description.key == Msg_values.sensor.value:
                self._power += self._config.options.get(W_ADJ)
            self._power = round(self._power)
        
        return self._power

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self._device_type == "plug" or self.entity_description.key == Msg_values.plug.value:
            return PLUG_ICON
        if self._device_type == "sensor" or self.entity_description.key == Msg_values.sensor.value:
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
