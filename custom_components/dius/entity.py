"""Base DiUS entity classes."""

from __future__ import annotations

import time

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .const import DOMAIN
from .models import CONNECTION_STOPPED
from .models import DiusDeviceData


class DiusEntity(CoordinatorEntity):
    """Base entity for DiUS devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, device: DiusDeviceData) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.device_key = device.key
        self._device = device

    @property
    def device(self) -> DiusDeviceData | None:
        """Return the latest device model."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.devices.get(self.device_key)

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        if not self.coordinator.data:
            return False
        device = self.device
        if device is None:
            return False
        if self.coordinator.data.connection.state == CONNECTION_STOPPED:
            return False
        return not device.is_stale(
            time.time(),
            self.coordinator.data.stale_timeout_seconds,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        device = self.device or self._device
        mac_suffix = device.mac[-4:].upper()
        name_prefix = "Power Plug" if device.is_plug else "Power Sensor"
        return DeviceInfo(
            configuration_url=ATTRIBUTION,
            identifiers={(DOMAIN, device.key)},
            name=f"{name_prefix} {mac_suffix}",
            manufacturer="DiUS",
        )
