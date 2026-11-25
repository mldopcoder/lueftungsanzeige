"""Auswahlfeld: gelernte Lüftungen eines Raums (zum gezielten Löschen)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LueftungConfigEntry
from .entity import RoomEntity

NONE_LABEL = "Keine gelernten Lüftungen"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LueftungConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SessionSelect(entry.runtime_data, "sessions", "Gelernte Lüftung")])


class SessionSelect(RoomEntity, SelectEntity):
    """Neueste zuerst; Auswahl + Knopf „Ausgewählte Lüftung löschen“."""

    _attr_icon = "mdi:format-list-bulleted"

    def _labels(self) -> dict[str, int]:
        return {
            self.room.session_label(s): s["ts"] for s in reversed(self.room.sessions)
        }

    @property
    def options(self) -> list[str]:
        labels = list(self._labels())
        return labels or [NONE_LABEL]

    @property
    def current_option(self) -> str | None:
        labels = self._labels()
        if not labels:
            return NONE_LABEL
        for label, ts in labels.items():
            if ts == self.room.selected_ts:
                return label
        return next(iter(labels))  # Standard: neueste Lüftung

    async def async_select_option(self, option: str) -> None:
        self.room.select_session(self._labels().get(option))
