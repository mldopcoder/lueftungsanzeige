"""Gemeinsame Basis für alle Entitäten eines Raums."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity

from .room import VentilationRoom


class RoomEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, room: VentilationRoom, key: str, name: str) -> None:
        self.room = room
        self._attr_unique_id = f"{room.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = room.device_info

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.room.add_listener(self.async_write_ha_state))
