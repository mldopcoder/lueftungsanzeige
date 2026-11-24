"""Einrichtung über die Oberfläche: ein Eintrag pro Raum."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
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
    DEFAULT_OUTDOOR_CO2,
    DEFAULT_RECOMMEND,
    DEFAULT_TARGET_CO2,
    DEFAULT_TOLERANCE,
    DOMAIN,
    MODE_CO2,
    MODE_HUMIDITY,
)


def _number(minimum: float, maximum: float, step: float, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _optional(key: str, current: dict[str, Any]) -> vol.Optional:
    if current.get(key):
        return vol.Optional(key, description={"suggested_value": current[key]})
    return vol.Optional(key)


def _schema(mode: str, current: dict[str, Any], include_sensor: bool) -> vol.Schema:
    sensor_sel = EntitySelector(EntitySelectorConfig(domain="sensor"))
    temp_sel = EntitySelector(
        EntitySelectorConfig(domain="sensor", device_class="temperature")
    )
    fields: dict[Any, Any] = {}

    if include_sensor:
        fields[vol.Required(CONF_SENSOR)] = sensor_sel

    if mode == MODE_CO2:
        fields[
            vol.Required(CONF_TARGET, default=current.get(CONF_TARGET, DEFAULT_TARGET_CO2))
        ] = _number(500, 1500, 50, "ppm")
        fields[
            vol.Required(
                CONF_RECOMMEND,
                default=current.get(CONF_RECOMMEND, DEFAULT_RECOMMEND[MODE_CO2]),
            )
        ] = _number(600, 2500, 50, "ppm")
        fields[
            vol.Required(
                CONF_OUTDOOR_CO2,
                default=current.get(CONF_OUTDOOR_CO2, DEFAULT_OUTDOOR_CO2),
            )
        ] = _number(350, 500, 5, "ppm")
    else:
        fields[_optional(CONF_OUTDOOR_SENSOR, current)] = sensor_sel
        fields[
            vol.Required(
                CONF_TOLERANCE, default=current.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)
            )
        ] = _number(0.1, 3.0, 0.1, "g/m³")
        fields[
            vol.Required(
                CONF_RECOMMEND,
                default=current.get(CONF_RECOMMEND, DEFAULT_RECOMMEND[MODE_HUMIDITY]),
            )
        ] = _number(0.5, 5.0, 0.1, "g/m³")

    fields[
        vol.Required(CONF_DELAY, default=current.get(CONF_DELAY, DEFAULT_DELAY))
    ] = _number(0, 15, 0.5, "min")
    fields[_optional(CONF_WINDOW, current)] = EntitySelector(
        EntitySelectorConfig(
            domain="binary_sensor", device_class=["window", "door", "opening"]
        )
    )
    fields[_optional(CONF_ROOM_TEMP, current)] = temp_sel
    fields[_optional(CONF_OUTDOOR_TEMP, current)] = temp_sel
    return vol.Schema(fields)


class LueftungConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_MODE, default=MODE_CO2): SelectSelector(
                    SelectSelectorConfig(
                        options=[MODE_CO2, MODE_HUMIDITY],
                        translation_key="mode",
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        mode = self._data[CONF_MODE]
        if user_input is not None:
            if mode == MODE_HUMIDITY and not user_input.get(CONF_OUTDOOR_SENSOR):
                errors[CONF_OUTDOOR_SENSOR] = "outdoor_required"
            else:
                await self.async_set_unique_id(user_input[CONF_SENSOR])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data={**self._data, **user_input}
                )

        return self.async_show_form(
            step_id="sensors",
            data_schema=_schema(mode, user_input or {}, include_sensor=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return LueftungOptionsFlow()


class LueftungOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        mode = self.config_entry.data[CONF_MODE]
        errors: dict[str, str] = {}
        if user_input is not None:
            if mode == MODE_HUMIDITY and not user_input.get(CONF_OUTDOOR_SENSOR):
                errors[CONF_OUTDOOR_SENSOR] = "outdoor_required"
            else:
                return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(mode, current, include_sensor=False),
            errors=errors,
        )
