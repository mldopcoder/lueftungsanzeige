"""Knöpfe: Lüften starten / beenden, Lernen zurücksetzen."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
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
            StartButton(room, "start", "Lüften starten"),
            StopButton(room, "stop", "Lüften beenden"),
            DeleteButton(room, "delete", "Ausgewählte Lüftung löschen"),
            ResetButton(room, "reset", "Gelerntes zurücksetzen"),
        ]
    )


class StartButton(RoomEntity, ButtonEntity):
    _attr_icon = "mdi:window-open-variant"

    async def async_press(self) -> None:
        self.room.start()


class StopButton(RoomEntity, ButtonEntity):
    _attr_icon = "mdi:window-closed-variant"

    async def async_press(self) -> None:
        self.room.end("manuell")


class DeleteButton(RoomEntity, ButtonEntity):
    """Löscht die im Auswahlfeld gewählte gelernte Lüftung."""

    _attr_icon = "mdi:delete-outline"

    async def async_press(self) -> None:
        self.room.delete_selected()


class ResetButton(RoomEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restore"
    _attr_entity_registry_enabled_default = False

    async def async_press(self) -> None:
        self.room.reset_learning()
