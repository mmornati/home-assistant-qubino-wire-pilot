"""Tests for the Qubino Wire Pilot thermostat."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
    mock_restore_cache_with_extra_data,
)

from custom_components.qubino_wire_pilot.const import DOMAIN

HEATER = "light.radiateur"
SENSOR = "sensor.temperature_sensor_salle_bain_etage_temperature_2"
POWER = "sensor.energy_meter_radiateur_power"
CLIMATE = "climate.radiateur_thermostat"
ENTRY_ID = "01KEMAQ94HF5Y74P7BNE4TEVVC"

# Options of the entry running on the author's box, written by v4.0.0
BOX_OPTIONS = {
    "heater": HEATER,
    "sensor": SENSOR,
    "value_comfort": 99.0,
    "value_comfort_1": 50.0,
    "value_comfort_2": 40.0,
    "value_eco": 25.0,
    "value_frost": 20.0,
    "value_off": 10.0,
}


def brightness(value: int) -> int:
    """Return the light brightness of a pilot wire value."""
    return round(value * 255 / 99)


async def setup_entry(
    hass: HomeAssistant, options: dict[str, Any] | None = None, **kwargs: Any
) -> MockConfigEntry:
    """Set up a thermostat entry driving light.radiateur."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="radiateur",
        options=BOX_OPTIONS if options is None else options,
        version=1,
        minor_version=kwargs.pop("minor_version", 2),
        **kwargs,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture(autouse=True)
def heater_device(hass: HomeAssistant) -> dr.DeviceEntry:
    """Register the Qubino light, the sensor states and the thermostat entity id."""
    zwave_entry = MockConfigEntry(domain="zwave_js")
    zwave_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=zwave_entry.entry_id,
        identifiers={("zwave_js", "4239033004-22")},
        manufacturer="Qubino",
        model="ZMNHJD",
        name="Radiateur",
    )
    er.async_get(hass).async_get_or_create(
        "light",
        "zwave_js",
        "4239033004.22-38-0-currentValue",
        suggested_object_id="radiateur",
        config_entry=zwave_entry,
        device_id=device.id,
    )
    er.async_get(hass).async_get_or_create(
        CLIMATE_DOMAIN, DOMAIN, ENTRY_ID, suggested_object_id="radiateur_thermostat"
    )
    hass.states.async_set(HEATER, "on", {"brightness": brightness(20)})
    hass.states.async_set(SENSOR, "19.35")
    return device


async def test_setup_with_box_options(hass: HomeAssistant) -> None:
    """The entry stored by v4.0.0 sets up and reads the heater."""
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(CLIMATE)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == "away"
    assert state.attributes["current_temperature"] == 19.4
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_unknown_options_are_ignored(hass: HomeAssistant) -> None:
    """Options written by another version do not break the setup."""
    entry = await setup_entry(hass, {**BOX_OPTIONS, "from_the_future": 1})
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(CLIMATE).state == HVACMode.HEAT


async def test_migration_from_minor_version_1(
    hass: HomeAssistant, heater_device: dr.DeviceEntry
) -> None:
    """A v1.1 entry drops the device the helper created and uses the heater's."""
    device_registry = dr.async_get(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="radiateur",
        options=BOX_OPTIONS,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    helper_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "copied-qubino-identity")},
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert device_registry.async_get(helper_device.id) is None
    climate_entry = er.async_get(hass).async_get(CLIMATE)
    assert climate_entry.device_id == heater_device.id


async def test_unavailable_heater(hass: HomeAssistant) -> None:
    """The thermostat is unavailable while the heater is."""
    await setup_entry(hass)
    hass.states.async_set(HEATER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).state == STATE_UNAVAILABLE

    hass.states.async_set(HEATER, "off")
    await hass.async_block_till_done()
    state = hass.states.get(CLIMATE)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_PRESET_MODE] == "none"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF


@pytest.mark.parametrize(
    ("preset", "value"),
    [("comfort", 99), ("eco", 25), ("away", 20), ("none", 10)],
)
async def test_set_preset(hass: HomeAssistant, preset: str, value: int) -> None:
    """Presets send the configured value as an integer brightness."""
    await setup_entry(hass)
    calls = async_mock_service(hass, "light", "turn_on")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_PRESET_MODE: preset},
        blocking=True,
    )
    assert calls[-1].data == {ATTR_ENTITY_ID: HEATER, "brightness": brightness(value)}


async def test_unavailable_preset_is_rejected(hass: HomeAssistant) -> None:
    """Comfort -1 without additional modes raises instead of turning off."""
    await setup_entry(hass)
    calls = async_mock_service(hass, "light", "turn_on")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: CLIMATE, ATTR_PRESET_MODE: "comfort-1"},
            blocking=True,
        )
    assert not calls


async def test_heat_restores_last_preset(hass: HomeAssistant) -> None:
    """Turning heat back on resumes the last order instead of comfort."""
    await setup_entry(hass)
    hass.states.async_set(HEATER, "on", {"brightness": brightness(25)})
    await hass.async_block_till_done()
    hass.states.async_set(HEATER, "off")
    await hass.async_block_till_done()
    calls = async_mock_service(hass, "light", "turn_on")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert calls[-1].data["brightness"] == brightness(25)


async def test_last_preset_survives_restart(hass: HomeAssistant) -> None:
    """The last order is restored after a restart."""
    mock_restore_cache_with_extra_data(
        hass, [(State(CLIMATE, HVACMode.OFF), {"last_preset": "eco"})]
    )
    hass.states.async_set(HEATER, "off")
    await setup_entry(hass)
    calls = async_mock_service(hass, "light", "turn_on")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert calls[-1].data["brightness"] == brightness(25)


async def test_heat_defaults_to_comfort(hass: HomeAssistant) -> None:
    """Without a known last order, heat means comfort."""
    hass.states.async_set(HEATER, "off")
    await setup_entry(hass)
    calls = async_mock_service(hass, "light", "turn_on")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert calls[-1].data["brightness"] == brightness(99)


async def test_missing_sensor_raises_repair_issue(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A sensor that does not exist is reported, and cleared once it appears."""
    entry = await setup_entry(
        hass,
        {**BOX_OPTIONS, "sensor": "sensor.old_zha_name"},
    )
    issue_registry = ir.async_get(hass)
    issue_id = f"missing_sensor_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert "sensor.old_zha_name does not exist" in caplog.text

    hass.states.async_set("sensor.old_zha_name", "20.1")
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert hass.states.get(CLIMATE).attributes["current_temperature"] == 20.1


async def test_hvac_action_from_power_sensor(hass: HomeAssistant) -> None:
    """With a power sensor, heating follows the power draw."""
    hass.states.async_set(HEATER, "on", {"brightness": brightness(99)})
    hass.states.async_set(POWER, "0.0")
    await setup_entry(hass, {**BOX_OPTIONS, "power_sensor": POWER})
    assert hass.states.get(CLIMATE).attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    hass.states.async_set(POWER, "1450.0")
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
