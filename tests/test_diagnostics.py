"""Tests for aTick diagnostics module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PIN

from custom_components.deembot_atick.const import DOMAIN
from custom_components.deembot_atick.device import ATickBTDevice
from custom_components.deembot_atick.diagnostics import (
    async_get_config_entry_diagnostics,
)


class TestDiagnostics:
    """Test diagnostics functionality."""

    @pytest.mark.asyncio
    async def test_diagnostics_output(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_config_entry_data: dict,
        mock_config_entry_options: dict,
    ) -> None:
        """Test diagnostics returns expected data."""
        # Create a real device for testing
        device = ATickBTDevice(mock_ble_device)
        device.data["counter_a_value"] = 100.0
        device.data["counter_b_value"] = 50.0
        device.data["counter_a_ratio"] = 1.0
        device.data["counter_b_ratio"] = 1.0
        device.data["counter_a_offset"] = 0.0
        device.data["counter_b_offset"] = 0.0

        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.device = device
        mock_coordinator._was_unavailable = False

        # Create mock entry
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.version = 1
        entry.domain = DOMAIN
        entry.title = "aTick Device"
        entry.data = mock_config_entry_data
        entry.options = mock_config_entry_options

        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        # Check structure
        assert "entry" in result
        assert "device" in result
        assert "coordinator" in result

        # Check entry data
        assert result["entry"]["entry_id"] == "test_entry_id"
        assert result["entry"]["title"] == "aTick Device"

        # Check sensitive data is redacted (value is **REDACTED**, not the actual value)
        assert result["entry"]["data"][CONF_PIN] == "**REDACTED**"
        assert result["entry"]["data"][CONF_ADDRESS] == "**REDACTED**"
        assert "123456" not in str(result["entry"]["data"])

        # Check device data
        assert result["device"]["data"]["counter_a_value"] == 100.0
        assert result["device"]["data"]["counter_b_value"] == 50.0

        # Check device info
        assert result["device"]["info"]["name"] == "aTick_Test"

        # Check connection status
        assert result["device"]["connection"]["connection_failures"] == 0
        assert result["device"]["connection"]["use_device_ratio"] is False

        # Check coordinator status
        assert result["coordinator"]["was_unavailable"] is False
        assert result["coordinator"]["address"] == "**REDACTED**"

    @pytest.mark.asyncio
    async def test_diagnostics_with_none_values(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_config_entry_data: dict,
        mock_config_entry_options: dict,
    ) -> None:
        """Test diagnostics handles None values correctly."""
        device = ATickBTDevice(mock_ble_device)
        # Counter values are None by default

        mock_coordinator = MagicMock()
        mock_coordinator.device = device
        mock_coordinator._was_unavailable = True

        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.version = 1
        entry.domain = DOMAIN
        entry.title = "aTick Device"
        entry.data = mock_config_entry_data
        entry.options = mock_config_entry_options

        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}

        result = await async_get_config_entry_diagnostics(hass, entry)

        # None values should be preserved
        assert result["device"]["data"]["counter_a_value"] is None
        assert result["device"]["data"]["counter_b_value"] is None
