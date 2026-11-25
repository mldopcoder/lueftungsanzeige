"""Sensoren: Restlüftzeit, empfohlene Lüftungsdauer, Lernstand."""

from __future__ import annotations

import math
import time

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfTime
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
            RemainingSensor(room, "restzeit", "Restlüftzeit"),
            RecommendedSensor(room, "empfohlen_dauer", "Empfohlene Lüftungsdauer"),
            LearningSensor(room, "lernstand", "Gelernte Lüftungen"),
        ]
    )


def _round(value: float | None) -> int | None:
    return None if value is None else int(math.ceil(value))


class RemainingSensor(RoomEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-sand"

    @property
    def native_value(self) -> int | None:
        return _round(self.room.remaining_minutes())

    @property
    def extra_state_attributes(self) -> dict:
        r = self.room
        attrs = {"aktiv": r.active, "auswertung_laeuft": r.closing, "einheit": r.unit}
        if r.active:
            value_now = r.value_now()
            attrs.update(
                {
                    "startwert": r.start_value,
                    "zielwert": round(r.session_target, 2),
                    "geschaetzt_jetzt": None if value_now is None else round(value_now, 2),
                    "ziel_erreicht": r.target_reached,
                    "noetig": r.session_needed,
                    "laeuft_seit_min": round((time.time() - r.session_start) / 60, 1),
                    "k_aktuell": round(r.k_current(), 4),
                }
            )
        if r.last_session:
            attrs["letzte_lueftung"] = r.last_session
        return attrs


class RecommendedSensor(RoomEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:window-open-variant"

    @property
    def native_value(self) -> int | None:
        return _round(self.room.recommended_minutes())


class LearningSensor(RoomEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:school"

    @property
    def native_value(self) -> int:
        return len(self.room.sessions)

    @property
    def extra_state_attributes(self) -> dict:
        k = self.room.k_prior(self.room.delta_t())
        return {
            "k_gelernt": round(k, 4),
            "halbwertszeit_min": round(math.log(2) / k, 1),
            "letzte_lueftungen": self.room.sessions[-5:],
        }
