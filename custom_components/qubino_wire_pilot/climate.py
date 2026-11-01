"""Platform for Qubino Wire Pilot."""

from __future__ import annotations

from itertools import pairwise
import logging
import math
from typing import Any

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON as LIGHT_SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import voluptuous as vol

from .const import (
    CONF_ADDITIONAL_MODES,
    CONF_HEATER,
    CONF_POWER_SENSOR,
    CONF_SENSOR,
    DOMAIN,
    PILOT_ORDERS,
    PLATFORMS,
    POWER_HEATING_THRESHOLD,
    PRESET_COMFORT_1,
    PRESET_COMFORT_2,
)

_LOGGER = logging.getLogger(__name__)

INVALID_STATES = (STATE_UNAVAILABLE, STATE_UNKNOWN)


def _validate_percentage_order(config: dict) -> dict:
    """Validate that percentage thresholds are in ascending order."""
    values = [(key, config.get(key, default)) for _, key, default in PILOT_ORDERS]
    for (key, value), (next_key, next_value) in pairwise(values):
        if value >= next_value:
            raise vol.Invalid(
                f"{key} ({value}) must be less than {next_key} ({next_value})"
            )
    return config


_PERCENTAGE = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))

# Base schema dict - used for extending CLIMATE_PLATFORM_SCHEMA
_PLATFORM_SCHEMA_DICT = {
    vol.Required(CONF_HEATER): cv.entity_id,
    vol.Optional(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_POWER_SENSOR): cv.entity_id,
    vol.Optional(CONF_ADDITIONAL_MODES, default=False): cv.boolean,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    # Custom percentage thresholds (0-100)
    **{vol.Optional(key): _PERCENTAGE for _, key, _ in PILOT_ORDERS},
}

# Used for config entries. Unknown option keys are dropped rather than
# rejected, so an entry written by another version still sets up.
PLATFORM_SCHEMA_COMMON = vol.All(
    vol.Schema(_PLATFORM_SCHEMA_DICT, extra=vol.REMOVE_EXTRA),
    _validate_percentage_order,
)

PLATFORM_SCHEMA = vol.All(
    CLIMATE_PLATFORM_SCHEMA.extend(_PLATFORM_SCHEMA_DICT),
    _validate_percentage_order,
)


def thresholds_from_config(config: ConfigType) -> dict[str, int]:
    """Return the configured value of each pilot wire order, by preset."""
    return {
        preset: int(config.get(key, default)) for preset, key, default in PILOT_ORDERS
    }


def preset_for_value(
    value: int, thresholds: dict[str, int], additional_modes: bool
) -> str:
    """Return the pilot wire order matching a heater value (0-99).

    Each configured value is the upper bound of its order, except eco: the
    Qubino keeps eco up to the middle of the frost to comfort -2 gap (30 with
    the defaults), so values between the eco setting and that bound are eco.
    """
    if value <= thresholds[PRESET_NONE]:
        return PRESET_NONE
    if value <= thresholds[PRESET_AWAY]:
        return PRESET_AWAY
    eco_upper = max(
        thresholds[PRESET_ECO],
        (thresholds[PRESET_AWAY] + thresholds[PRESET_COMFORT_2]) / 2,
    )
    if value <= eco_upper:
        return PRESET_ECO
    if additional_modes:
        if value <= thresholds[PRESET_COMFORT_2]:
            return PRESET_COMFORT_2
        if value <= thresholds[PRESET_COMFORT_1]:
            return PRESET_COMFORT_1
    return PRESET_COMFORT


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await _async_setup_config(
        hass,
        PLATFORM_SCHEMA_COMMON(dict(config_entry.options)),
        config_entry.entry_id,
        async_add_entities,
        device=async_entity_id_to_device(hass, config_entry.options[CONF_HEATER]),
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the wire pilot climate platform from YAML."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_config(
        hass, config, config.get(CONF_UNIQUE_ID), async_add_entities
    )


async def _async_setup_config(
    hass: HomeAssistant,
    config: ConfigType,
    unique_id: str | None,
    async_add_entities: AddEntitiesCallback,
    device: DeviceEntry | None = None,
) -> None:
    """Set up the wire pilot climate platform."""
    async_add_entities(
        [
            QubinoWirePilotClimate(
                hass,
                config.get(CONF_NAME),
                config[CONF_HEATER],
                config.get(CONF_SENSOR),
                config.get(CONF_POWER_SENSOR),
                config.get(CONF_ADDITIONAL_MODES, False),
                unique_id,
                thresholds_from_config(config),
                device,
            )
        ]
    )


class QubinoWirePilotExtraStoredData(ExtraStoredData):
    """Extra data restored across restarts."""

    def __init__(self, last_preset: str | None) -> None:
        """Initialize the stored data."""
        self.last_preset = last_preset

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored data."""
        return {"last_preset": self.last_preset}


class QubinoWirePilotClimate(ClimateEntity, RestoreEntity):
    """Representation of a Qubino Wire Pilot device."""

    _attr_should_poll = False
    _attr_translation_key = "qubino_wire_pilot"
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        hass: HomeAssistant,
        name: str | None,
        heater_entity_id: str,
        sensor_entity_id: str | None,
        power_sensor_entity_id: str | None,
        additional_modes: bool,
        unique_id: str | None,
        thresholds: dict[str, int],
        device: DeviceEntry | None = None,
    ) -> None:
        """Initialize the climate device."""
        heater_entity = er.async_get(hass).async_get(heater_entity_id)
        self._attr_has_entity_name = (
            heater_entity.has_entity_name if heater_entity else False
        )
        self.device_entry = device
        if name:
            self._attr_name = name

        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self.power_sensor_entity_id = power_sensor_entity_id
        self.additional_modes = additional_modes
        self._thresholds = thresholds
        self._cur_temperature: float | None = None
        self._last_preset: str | None = None

        self._attr_unique_id = unique_id or f"qubino_wire_pilot_{heater_entity_id}"

    @property
    def _watched_entities(self) -> dict[str, str]:
        """Return the source entities, keyed by their role."""
        entities = {"heater": self.heater_entity_id}
        if self.sensor_entity_id:
            entities["sensor"] = self.sensor_entity_id
        if self.power_sensor_entity_id:
            entities["power_sensor"] = self.power_sensor_entity_id
        return entities

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        if (extra := await self.async_get_last_extra_data()) is not None:
            last_preset = extra.as_dict().get("last_preset")
            if last_preset in self._on_presets:
                self._last_preset = last_preset

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                list(self._watched_entities.values()),
                self._async_source_changed,
            )
        )

        @callback
        def _async_startup(_: HomeAssistant) -> None:
            """Read the sources once Home Assistant has started."""
            for role, entity_id in self._watched_entities.items():
                self._async_check_missing(role, entity_id)
            if self.sensor_entity_id is not None:
                sensor_state = self.hass.states.get(self.sensor_entity_id)
                if sensor_state and sensor_state.state not in INVALID_STATES:
                    self._async_update_temp(sensor_state)
            self._async_remember_preset()
            self.async_write_ha_state()

        self.async_on_remove(async_at_started(self.hass, _async_startup))

    async def async_will_remove_from_hass(self) -> None:
        """Drop the repair issues of this thermostat."""
        for role in ("heater", "sensor", "power_sensor"):
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(role))

    @property
    def extra_restore_state_data(self) -> QubinoWirePilotExtraStoredData:
        """Return the data to restore after a restart."""
        return QubinoWirePilotExtraStoredData(self._last_preset)

    def _issue_id(self, role: str) -> str:
        return f"missing_{role}_{self.unique_id}"

    @callback
    def _async_check_missing(self, role: str, entity_id: str) -> None:
        """Raise a repair issue when a source entity does not exist."""
        if self.hass.states.get(entity_id) is not None:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id(role))
            return
        _LOGGER.warning(
            "%s: %s entity %s does not exist", self.entity_id, role, entity_id
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_id(role),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"missing_{role}",
            translation_placeholders={
                "entity_id": entity_id,
                "thermostat": self.entity_id,
            },
        )

    @property
    def available(self) -> bool:
        """Return True if the heater can be controlled."""
        state = self.hass.states.get(self.heater_entity_id)
        return state is not None and state.state not in INVALID_STATES

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._cur_temperature

    @property
    def heater_value(self) -> int | None:
        """Return the pilot wire value of the heater (0-99)."""
        state = self.hass.states.get(self.heater_entity_id)
        if state is None or state.state in INVALID_STATES:
            return None

        brightness = state.attributes.get(ATTR_BRIGHTNESS)
        if brightness is None:
            return 0
        return round(brightness / 255 * 99)

    # Presets
    @property
    def _on_presets(self) -> list[str]:
        """Presets that keep the heater on."""
        if self.additional_modes:
            return [
                PRESET_COMFORT,
                PRESET_COMFORT_1,
                PRESET_COMFORT_2,
                PRESET_ECO,
                PRESET_AWAY,
            ]
        return [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

    @property
    def preset_modes(self) -> list[str]:
        """List of available preset modes.

        "none" stays available: it is the pilot wire "off" order and is
        reported whenever the thermostat is off.
        """
        return [*self._on_presets, PRESET_NONE]

    @property
    def preset_mode(self) -> str | None:
        """Return the current pilot wire order."""
        value = self.heater_value
        if value is None:
            return None
        return preset_for_value(value, self._thresholds, self.additional_modes)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode not in self.preset_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_preset",
                translation_placeholders={
                    "preset": preset_mode,
                    "presets": ", ".join(self.preset_modes),
                },
            )
        await self._async_set_heater_value(self._thresholds[preset_mode])

    # Modes
    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, off mode."""
        value = self.heater_value
        if value is None:
            return None
        if value <= self._thresholds[PRESET_NONE]:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return what the radiator is doing.

        With a power sensor, heating means the radiator draws power.
        Without one, every order but frost protection counts as heating.
        """
        preset = self.preset_mode
        if preset is None:
            return None
        if preset == PRESET_NONE:
            return HVACAction.OFF
        if self.power_sensor_entity_id:
            power = self.hass.states.get(self.power_sensor_entity_id)
            try:
                watts = float(power.state) if power else math.nan
            except ValueError:
                watts = math.nan
            if math.isfinite(watts):
                if watts > POWER_HEATING_THRESHOLD:
                    return HVACAction.HEATING
                return HVACAction.IDLE
        if preset == PRESET_AWAY:
            return HVACAction.IDLE
        return HVACAction.HEATING

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_set_heater_value(self._thresholds[PRESET_NONE])
            return
        if hvac_mode != HVACMode.HEAT:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_hvac_mode",
                translation_placeholders={"hvac_mode": str(hvac_mode)},
            )
        if self.hvac_mode == HVACMode.HEAT:
            return
        preset = (
            self._last_preset
            if self._last_preset in self._on_presets
            else PRESET_COMFORT
        )
        await self._async_set_heater_value(self._thresholds[preset])

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle state changes of the heater and sensors."""
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        for role, watched in self._watched_entities.items():
            if watched == entity_id:
                self._async_check_missing(role, entity_id)

        if (
            entity_id == self.sensor_entity_id
            and new_state is not None
            and new_state.state not in INVALID_STATES
        ):
            self._async_update_temp(new_state)
        if entity_id == self.heater_entity_id:
            self._async_remember_preset()
        self.async_write_ha_state()

    @callback
    def _async_remember_preset(self) -> None:
        """Remember the last order that kept the heater on."""
        preset = self.preset_mode
        if preset in self._on_presets:
            self._last_preset = preset

    @callback
    def _async_update_temp(self, state: State) -> None:
        try:
            cur_temp = float(state.state)
            if not math.isfinite(cur_temp):
                raise ValueError(f"Sensor has illegal state {state.state}")
            self._cur_temperature = cur_temp
        except ValueError as ex:
            _LOGGER.error("Unable to update from temperature sensor: %s", ex)

    async def _async_set_heater_value(self, value: int) -> None:
        """Send a pilot wire value (0-99) to the heater."""
        data = {
            ATTR_ENTITY_ID: self.heater_entity_id,
            ATTR_BRIGHTNESS: round(value * 255 / 99),
        }
        await self.hass.services.async_call(
            LIGHT_DOMAIN, LIGHT_SERVICE_TURN_ON, data, blocking=True
        )
