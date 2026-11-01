"""Tests for the Qubino Wire Pilot config flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.qubino_wire_pilot.const import DOMAIN


async def test_user_flow(hass: HomeAssistant) -> None:
    """The user step creates an entry with the options, at minor version 2."""
    hass.states.async_set("light.radiateur", "off")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "heater": "light.radiateur",
            "sensor": "sensor.temperature",
            "power_sensor": "sensor.power",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.minor_version == 2
    assert entry.options["heater"] == "light.radiateur"
    assert entry.options["power_sensor"] == "sensor.power"
    assert entry.options["value_eco"] == 25
