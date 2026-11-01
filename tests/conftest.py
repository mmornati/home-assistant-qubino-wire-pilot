"""Fixtures for Qubino Wire Pilot tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable the custom integration in every test."""
    return
