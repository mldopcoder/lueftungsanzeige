"""Logik pro Raum: Lüftung erfassen, Restzeit schätzen, aus Lüftungen lernen.

Modell: Beim Lüften nähert sich der Raumwert exponentiell dem Außenwert:
    v(t) = außen + (v0 - außen) * exp(-k * t)
k (1/min) ist die Luftwechselrate. Sie wird pro Raum aus jeder Lüftung gelernt
und während einer laufenden Lüftung mit den neuen Messwerten nachgeschärft.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import logging
import math
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from .const import (
    AGE_DECAY,
    CONF_MODE,
    CONF_OUTDOOR_CO2,
    CONF_OUTDOOR_SENSOR,
    CONF_OUTDOOR_TEMP,
    CONF_RECOMMEND,
    CONF_ROOM_TEMP,
    CONF_SENSOR,
    CONF_TARGET,
    CONF_TOLERANCE,
    CONF_WINDOW,
    CONF_DELAY,
    DEFAULT_DELAY,
    DEFAULT_K,
    DEFAULT_OUTDOOR_CO2,
    DEFAULT_PRIOR_WEIGHT,
    DEFAULT_RECOMMEND,
    DEFAULT_TARGET_CO2,
    DEFAULT_TOLERANCE,
    DOMAIN,
    DT_SCALE,
    EVENT_ENDED,
    EVENT_TARGET_REACHED,
    FOLLOW_UP,
    HISTORY_WINDOW,
    K_MAX,
    K_MIN,
    MAX_DURATION,
    MAX_SESSIONS,
    MIN_DROP,
    MIN_LEARN_DURATION,
    MODE_CO2,
    OPTIONAL_KEYS,
    PRIOR_WEIGHT,
    RISE,
    STORAGE_VERSION,
    TICK,
)

_LOGGER = logging.getLogger(__name__)


def _to_float(state) -> float | None:
    if state is None:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class VentilationRoom:
    """Ein Raum mit Lüftungsanzeige."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry_id = entry.entry_id

        cfg = dict(entry.data)
        if entry.options:
            for key in OPTIONAL_KEYS:
                cfg.pop(key, None)
            cfg.update(entry.options)

        self.name: str = cfg[CONF_NAME]
        self.mode: str = cfg[CONF_MODE]
        self.sensor: str = cfg[CONF_SENSOR]
        self.outdoor_sensor: str | None = cfg.get(CONF_OUTDOOR_SENSOR)
        self.room_temp_sensor: str | None = cfg.get(CONF_ROOM_TEMP)
        self.outdoor_temp_sensor: str | None = cfg.get(CONF_OUTDOOR_TEMP)
        self.window: str | None = cfg.get(CONF_WINDOW)
        # Messwerte gelten als um diese Zeit früher gemessen
        self.delay_s = float(cfg.get(CONF_DELAY, DEFAULT_DELAY)) * 60
        self.target_co2 = float(cfg.get(CONF_TARGET, DEFAULT_TARGET_CO2))
        self.outdoor_co2 = float(cfg.get(CONF_OUTDOOR_CO2, DEFAULT_OUTDOOR_CO2))
        self.tolerance = float(cfg.get(CONF_TOLERANCE, DEFAULT_TOLERANCE))
        self.recommend = float(cfg.get(CONF_RECOMMEND, DEFAULT_RECOMMEND[self.mode]))

        self.unit = "ppm" if self.mode == MODE_CO2 else "g/m³"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Lüftung {self.name}",
            manufacturer="Lüftungsanzeige",
            model="CO2" if self.mode == MODE_CO2 else "Feuchte",
        )

        self.history: deque[tuple[float, float]] = deque()
        self.sessions: list[dict] = []
        self.last_session: dict | None = None

        # laufende Lüftung
        self.active = False
        self.session_start = 0.0
        self.start_value = 0.0
        self.session_target = 0.0
        self.session_baseline: float | None = None
        self.session_dt: float | None = None
        self.session_min = 0.0
        self.session_min_ts = 0.0
        self.target_reached = False
        self.session_needed = False
        self.points: list[tuple[float, float]] = []
        # Nachlauf: Lüftung ist vorbei, verspätete Messwerte werden noch gesammelt
        self.closing = False
        self.close_ts = 0.0
        self.close_reason = ""
        self._cancel_finalize: Callable[[], None] | None = None

        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")

    # ------------------------------------------------------------ Lifecycle
    async def async_setup(self) -> None:
        data = await self._store.async_load()
        if data:
            self.sessions = data.get("sessions", [])

        value = _to_float(self.hass.states.get(self.sensor))
        if value is not None:
            self._add_history(time.time(), value)

        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.sensor], self._handle_sensor
            )
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._tick, TICK)
        )
        if self.window:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self.window], self._handle_window
                )
            )

    @callback
    def _handle_window(self, event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if new_state is None or old_state is None:
            return
        if old_state.state == "off" and new_state.state == "on":
            self.start()
        elif old_state.state == "on" and new_state.state == "off":
            self.end("Fenster geschlossen")

    async def async_shutdown(self) -> None:
        if self.closing:
            self._finalize()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._store_data())

    @callback
    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)

        @callback
        def remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return remove

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    def _store_data(self) -> dict:
        return {"sessions": self.sessions}

    # ------------------------------------------------------------ Messwerte
    @callback
    def _add_history(self, ts: float, value: float) -> None:
        self.history.append((ts, value))
        cutoff = time.time() - HISTORY_WINDOW
        while len(self.history) > 1 and self.history[0][0] < cutoff:
            self.history.popleft()

    @callback
    def _handle_sensor(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        value = _to_float(new_state)
        if value is None:
            return
        ts = new_state.last_updated.timestamp() - self.delay_s
        self._add_history(ts, value)
        if self.active:
            if ts > self.session_start:
                self.points.append((ts, value))
                self._check_session(ts, value)
            elif not self.points:
                # Wert wurde noch vor dem Öffnen gemessen -> besserer Startwert
                self.start_value = value
                self.session_min = value
                self.target_reached = value <= self.session_target
        elif self.closing and ts <= self.session_start and not self.points:
            self.start_value = value
            self.session_min = value
        elif self.closing and self.session_start < ts <= self.close_ts:
            # verspäteter Wert, der noch während der Lüftung gemessen wurde
            self.points.append((ts, value))
            if value < self.session_min:
                self.session_min = value
                self.session_min_ts = ts
        self._notify()

    @property
    def last_value(self) -> float | None:
        return self.history[-1][1] if self.history else None

    def outdoor_value(self) -> float | None:
        if self.mode == MODE_CO2:
            return self.outdoor_co2
        if not self.outdoor_sensor:
            return None
        return _to_float(self.hass.states.get(self.outdoor_sensor))

    def delta_t(self) -> float | None:
        if not self.room_temp_sensor or not self.outdoor_temp_sensor:
            return None
        room = _to_float(self.hass.states.get(self.room_temp_sensor))
        out = _to_float(self.hass.states.get(self.outdoor_temp_sensor))
        if room is None or out is None:
            return None
        return room - out

    def baseline(self) -> float | None:
        """Tiefster Wert der letzten 3 h (Bad: Zustand vor dem Duschen)."""
        if not self.history:
            return None
        cutoff = time.time() - HISTORY_WINDOW
        values = [v for ts, v in self.history if ts >= cutoff]
        return min(values) if values else self.history[-1][1]

    def _target(self, baseline: float | None) -> float | None:
        if self.mode == MODE_CO2:
            return self.target_co2
        if baseline is None:
            return None
        target = baseline + self.tolerance
        out = self.outdoor_value()
        if out is not None:
            # unter den Außenwert kommt man durch Lüften nicht
            target = max(target, out + 1.0)
        return target

    # ------------------------------------------------------------ Lernen / Schätzen
    def k_prior(self, dt: float | None = None) -> float:
        """Gelernte Luftwechselrate (gewichtetes geometrisches Mittel)."""
        default = DEFAULT_K[self.mode]
        num = DEFAULT_PRIOR_WEIGHT * math.log(default)
        den = DEFAULT_PRIOR_WEIGHT
        for age, session in enumerate(reversed(self.sessions)):
            weight = AGE_DECAY**age
            sdt = session.get("dt")
            if dt is not None and sdt is not None:
                weight *= math.exp(-(((dt - sdt) / DT_SCALE) ** 2)) + 0.05
            num += weight * math.log(session["k"])
            den += weight
        return math.exp(num / den)

    def k_live(self) -> tuple[float, int] | None:
        """Luftwechselrate aus den Messwerten der laufenden Lüftung."""
        out = self.outdoor_value()
        if out is None or self.start_value - out <= 0:
            return None
        sxy = sxx = 0.0
        n = 0
        for ts, value in self.points:
            if ts > self.session_min_ts:
                break  # nur bis zum Tiefpunkt, danach war das Fenster wohl zu
            if value - out <= 0:
                continue
            t = (ts - self.session_start) / 60
            if t <= 0:
                continue
            y = math.log((value - out) / (self.start_value - out))
            sxy += t * y
            sxx += t * t
            n += 1
        if n == 0 or sxx == 0:
            return None
        k = -sxy / sxx
        return max(K_MIN, min(K_MAX, k)), n

    def k_current(self) -> float:
        prior = self.k_prior(self.session_dt if self.active else self.delta_t())
        if not self.active:
            return prior
        live = self.k_live()
        if live is None:
            return prior
        k_l, n = live
        k = (prior * PRIOR_WEIGHT + k_l * n) / (PRIOR_WEIGHT + n)
        return max(K_MIN, min(K_MAX, k))

    def value_now(self) -> float | None:
        """Aktuell geschätzter Raumwert (Sensoren melden nur alle paar Minuten)."""
        if not self.history:
            return None
        ts, value = self.history[-1]
        if not self.active:
            return value
        out = self.outdoor_value()
        if out is None or value <= out:
            return value
        ref = max(ts, self.session_start)
        minutes = max(0.0, (time.time() - ref) / 60)
        return out + (value - out) * math.exp(-self.k_current() * minutes)

    def remaining_minutes(self) -> float | None:
        if not self.active:
            return None
        out = self.outdoor_value()
        target = self.session_target
        value = self.value_now()
        if out is None or value is None or target <= out:
            return None
        if value <= target:
            return 0.0
        return math.log((value - out) / (target - out)) / self.k_current()

    def recommended_minutes(self) -> float | None:
        """Wie lange man jetzt lüften müsste."""
        if self.active:
            return self.remaining_minutes()
        value = self.last_value
        out = self.outdoor_value()
        target = self._target(self.baseline())
        if value is None or out is None or target is None or target <= out:
            return None
        if value <= target:
            return 0.0
        return math.log((value - out) / (target - out)) / self.k_prior(self.delta_t())

    def recommended(self) -> bool:
        # Während des Nachlaufs zeigt der Sensor noch alte Werte von vor dem Lüften
        if self.active or self.closing:
            return False
        value = self.last_value
        if value is None:
            return False
        if self.mode == MODE_CO2:
            return value >= self.recommend
        base = self.baseline()
        out = self.outdoor_value()
        if base is None:
            return False
        worth_it = out is None or value - out > 1.0
        return value - base >= self.recommend and worth_it

    # ------------------------------------------------------------ Sitzung
    @callback
    def start(self) -> None:
        value = self.last_value
        if value is None:
            _LOGGER.warning("%s: kein Messwert, Lüftung kann nicht starten", self.name)
            return
        if self.active:
            return
        if self.closing:
            self._finalize()  # vorherige Lüftung jetzt auswerten
        # War Lüften beim Öffnen überhaupt nötig? (vor active=True prüfen)
        self.session_needed = self.recommended()
        self.active = True
        self.session_start = time.time()
        self.start_value = value
        self.session_baseline = self.baseline()
        self.session_target = self._target(self.session_baseline) or value
        self.session_dt = self.delta_t()
        self.session_min = value
        self.session_min_ts = self.session_start
        self.target_reached = value <= self.session_target
        self.points = []
        self._notify()

    @callback
    def _check_session(self, ts: float, value: float) -> None:
        if value < self.session_min:
            self.session_min = value
            self.session_min_ts = ts
        if not self.target_reached and value <= self.session_target:
            self._reach_target()
        if self.window:
            return  # mit Fensterkontakt beendet das Schließen die Lüftung
        dropped = self.start_value - self.session_min >= MIN_DROP[self.mode]
        if dropped and value >= self.session_min + RISE[self.mode]:
            self.end("Fenster geschlossen erkannt")

    @callback
    def _reach_target(self) -> None:
        self.target_reached = True
        value = self.value_now()
        self.hass.bus.async_fire(
            EVENT_TARGET_REACHED,
            {
                "raum": self.name,
                "entry_id": self.entry_id,
                "noetig": self.session_needed,
                "wert": None if value is None else round(value, 1 if self.mode != MODE_CO2 else None),
                "einheit": self.unit,
                "dauer_min": round((time.time() - self.session_start) / 60, 1),
            },
        )

    @callback
    def _tick(self, _now) -> None:
        if not self.active:
            return
        if not self.window and time.time() - self.session_start > MAX_DURATION:
            self.end("Zeitlimit")
            return
        remaining = self.remaining_minutes()
        if remaining == 0 and not self.target_reached:
            self._reach_target()
        self._notify()

    @callback
    def end(self, reason: str = "manuell") -> None:
        if not self.active:
            return
        self.active = False
        self.closing = True
        self.close_ts = time.time()
        self.close_reason = reason
        # Sensoren liefern verspätet: erst nach dem Nachlauf auswerten
        self._cancel_finalize = async_call_later(
            self.hass, self.delay_s + FOLLOW_UP, self._finalize_cb
        )
        self._notify()

    @callback
    def _finalize_cb(self, _now) -> None:
        self._cancel_finalize = None
        self._finalize()

    @callback
    def _finalize(self) -> None:
        if not self.closing:
            return
        if self._cancel_finalize:
            self._cancel_finalize()
            self._cancel_finalize = None
        self.closing = False
        duration = (self.close_ts - self.session_start) / 60
        learned = self._learn(duration)
        self.last_session = {
            "grund": self.close_reason,
            "dauer_min": round(duration, 1),
            "start": self.start_value,
            "tiefpunkt": self.session_min,
            "messwerte": len(self.points),
            "gelernt": learned,
        }
        self.hass.bus.async_fire(
            EVENT_ENDED,
            {"raum": self.name, "entry_id": self.entry_id, **self.last_session},
        )
        self._notify()

    def _learn(self, duration_min: float) -> bool:
        if duration_min * 60 < MIN_LEARN_DURATION:
            return False
        if self.start_value - self.session_min < MIN_DROP[self.mode]:
            return False
        live = self.k_live()
        if live is None:
            return False
        k, n = live
        self.sessions.append(
            {
                "ts": round(self.session_start),
                "k": round(k, 4),
                "n": n,
                "dt": None if self.session_dt is None else round(self.session_dt, 1),
                "dauer_min": round(duration_min, 1),
                "start": self.start_value,
                "tiefpunkt": self.session_min,
            }
        )
        del self.sessions[:-MAX_SESSIONS]
        self._store.async_delay_save(self._store_data, 5)
        return True

    @callback
    def reset_learning(self) -> None:
        self.sessions = []
        self._store.async_delay_save(self._store_data, 1)
        self._notify()
