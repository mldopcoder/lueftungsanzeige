"""Lüftungsanzeige – zeigt pro Raum, wie lange noch gelüftet werden muss."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .room import VentilationRoom

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

type LueftungConfigEntry = ConfigEntry[VentilationRoom]


async def async_setup_entry(hass: HomeAssistant, entry: LueftungConfigEntry) -> bool:
    room = VentilationRoom(hass, entry)
    await room.async_setup()
    entry.runtime_data = room
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LueftungConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: LueftungConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
