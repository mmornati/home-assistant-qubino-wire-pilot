"""Tests for the pilot wire value to preset mapping."""

import pytest

from custom_components.qubino_wire_pilot.climate import (
    preset_for_value,
    thresholds_from_config,
)
from custom_components.qubino_wire_pilot.const import PILOT_ORDERS

DEFAULTS = thresholds_from_config({})


@pytest.mark.parametrize(
    ("value", "additional_modes", "expected"),
    [
        (0, False, "none"),
        (10, False, "none"),
        (11, False, "away"),
        (20, False, "away"),
        (21, False, "eco"),
        (25, False, "eco"),
        (30, False, "eco"),
        (31, False, "comfort"),
        (31, True, "comfort-2"),
        (40, True, "comfort-2"),
        (41, True, "comfort-1"),
        (50, True, "comfort-1"),
        (51, True, "comfort"),
        (99, True, "comfort"),
        (45, False, "comfort"),
    ],
)
def test_preset_for_value(value: int, additional_modes: bool, expected: str) -> None:
    """Device values map to the order of the Qubino manual."""
    assert preset_for_value(value, DEFAULTS, additional_modes) == expected


def test_eco_bound_follows_a_high_eco_setting() -> None:
    """An eco setting above the frost/comfort -2 midpoint still reads as eco."""
    thresholds = {**DEFAULTS, "eco": 35}
    assert preset_for_value(35, thresholds, True) == "eco"
    assert preset_for_value(36, thresholds, True) == "comfort-2"


@pytest.mark.parametrize("additional_modes", [False, True])
def test_round_trip_through_brightness(additional_modes: bool) -> None:
    """Each order sent as a brightness reads back as the same order."""
    for preset, _, _ in PILOT_ORDERS:
        if preset in ("comfort-1", "comfort-2") and not additional_modes:
            continue
        brightness = round(DEFAULTS[preset] * 255 / 99)
        value = round(brightness / 255 * 99)
        assert preset_for_value(value, DEFAULTS, additional_modes) == preset
