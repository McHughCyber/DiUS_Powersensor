"""DiusEntity class"""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .const import DOMAIN
from .enums import Msg_keys


class DiusEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, description, mac: str = None):
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.entity_description = description
        self._mac = mac

        # Generate unique ID based on MAC and device type
        # Note: Do NOT include domain prefix as Home Assistant adds this automatically
        if mac:
            # Use MAC address as the unique identifier
            self._attr_unique_id = mac
        else:
            # Fallback for backward compatibility - use description key as unique ID
            self._attr_unique_id = description.key

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            configuration_url=ATTRIBUTION,
            identifiers={
                (DOMAIN, self._mac) if self._mac else (DOMAIN, self._attr_unique_id)
            },
            name=self.entity_description.name,
            manufacturer=DOMAIN,
        )
