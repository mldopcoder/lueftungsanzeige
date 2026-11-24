"""Binärsensoren: Lüftung aktiv, Lüften empfohlen, Fenster zu."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LueftungConfigEntry
from .entity import RoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LueftungConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    room = entry.runtime_data
    async_add_entities(
        [
            ActiveSensor(room, "aktiv", "Lüftung aktiv"),
            RecommendSensor(room, "empfohlen", "Lüften empfohlen"),
            CloseSensor(room, "fenster_zu", "Fenster schließen"),
        ]
    )


class ActiveSensor(RoomEntity, BinarySensorEntity):
    _attr_icon = "mdi:window-open-variant"

    @property
    def is_on(self) -> bool:
        return self.room.active


class RecommendSensor(RoomEntity, BinarySensorEntity):
    _attr_icon = "mdi:air-filter"

    @property
    def is_on(self) -> bool:
        return self.room.recommended()


class CloseSensor(RoomEntity, BinarySensorEntity):
    """An, sobald das Ziel (geschätzt) erreicht ist und noch gelüftet wird."""

    _attr_icon = "mdi:window-closed-variant"

    @property
    def is_on(self) -> bool:
        return self.room.active and self.room.target_reached
