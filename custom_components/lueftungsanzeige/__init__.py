"""Lüftungsanzeige – zeigt pro Raum, wie lange noch gelüftet werden muss."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .room import VentilationRoom

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SELECT]

SERVICE_ADD_SESSION = "lueftung_nachtragen"
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("raum"): cv.string,
        vol.Required("start"): cv.datetime,
        vol.Required("dauer_min"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=120)),
        vol.Required("startwert"): vol.Coerce(float),
        vol.Required("tiefpunkt"): vol.Coerce(float),
    }
)

type LueftungConfigEntry = ConfigEntry[VentilationRoom]


async def async_setup_entry(hass: HomeAssistant, entry: LueftungConfigEntry) -> bool:
    room = VentilationRoom(hass, entry)
    await room.async_setup()
    entry.runtime_data = room
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LueftungConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: LueftungConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Dienst „Lüftung nachtragen“: eine Lüftung von Hand ins Gelernte eintragen."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_SESSION):
        return

    async def _add_session(call: ServiceCall) -> None:
        name = call.data["raum"].strip().lower()
        room: VentilationRoom | None = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED and (
                entry.title.lower() == name or entry.entry_id == call.data["raum"]
            ):
                room = entry.runtime_data
                break
        if room is None:
            raise ServiceValidationError(f"Raum '{call.data['raum']}' nicht gefunden")

        start = dt_util.as_utc(call.data["start"])  # ohne Zeitzone = HA-Zeitzone
        if not room.add_manual_session(
            start.timestamp(),
            call.data["dauer_min"],
            call.data["startwert"],
            call.data["tiefpunkt"],
        ):
            raise ServiceValidationError(
                "Werte ergeben keine sinnvolle Lüftung (Tiefpunkt zu nah am Außenwert?)"
            )

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_SESSION, _add_session, schema=SERVICE_SCHEMA
    )
