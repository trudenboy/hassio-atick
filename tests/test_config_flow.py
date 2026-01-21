"""Tests for aTick config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResultType

from custom_components.deembot_atick.config_flow import (
    OptionsFlowHandler,
    is_atick_device,
)
from custom_components.deembot_atick.const import DOMAIN, UUID_SERVICE_AG


def test_is_atick_device_by_uuid() -> None:
    """Test device detection by service UUID."""
    discovery_info = MagicMock(spec=BluetoothServiceInfoBleak)
    discovery_info.service_uuids = [UUID_SERVICE_AG.lower()]
    discovery_info.name = "SomeOtherName"

    assert is_atick_device(discovery_info) is True


def test_is_atick_device_by_name() -> None:
    """Test device detection by name prefix."""
    discovery_info = MagicMock(spec=BluetoothServiceInfoBleak)
    discovery_info.service_uuids = []
    discovery_info.name = "aTick_Device"

    assert is_atick_device(discovery_info) is True


def test_is_atick_device_not_atick() -> None:
    """Test device detection returns False for non-aTick device."""
    discovery_info = MagicMock(spec=BluetoothServiceInfoBleak)
    discovery_info.service_uuids = ["some-other-uuid"]
    discovery_info.name = "SomeOtherDevice"

    assert is_atick_device(discovery_info) is False


def test_is_atick_device_no_name() -> None:
    """Test device detection when name is None."""
    discovery_info = MagicMock(spec=BluetoothServiceInfoBleak)
    discovery_info.service_uuids = []
    discovery_info.name = None

    assert is_atick_device(discovery_info) is False


class TestOptionsFlow:
    """Test options flow for aTick integration."""

    def _create_options_flow(
        self, mock_config_entry_data, mock_config_entry_options
    ) -> OptionsFlowHandler:
        """Create an options flow with a mock config entry."""
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=0,
            domain=DOMAIN,
            title="Test aTick",
            data=mock_config_entry_data,
            options=mock_config_entry_options,
            source=config_entries.SOURCE_USER,
            unique_id="AA:BB:CC:DD:EE:FF",
        )

        return OptionsFlowHandler(entry)

    async def test_options_flow_init(
        self, hass, mock_config_entry_data, mock_config_entry_options
    ):
        """Test the initial options form."""
        flow = self._create_options_flow(
            mock_config_entry_data, mock_config_entry_options
        )
        result = await flow.async_step_init()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_update(
        self, hass, mock_config_entry_data, mock_config_entry_options
    ):
        """Test updating options."""
        flow = self._create_options_flow(
            mock_config_entry_data, mock_config_entry_options
        )

        result = await flow.async_step_init(
            user_input={
                "poll_interval": 7200,
                "counter_a_offset": 10.5,
                "counter_b_offset": 20.3,
            }
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["poll_interval"] == 7200
        assert result["data"]["counter_a_offset"] == 10.5
        assert result["data"]["counter_b_offset"] == 20.3

    async def test_options_flow_invalid_poll_interval(
        self, hass, mock_config_entry_data, mock_config_entry_options
    ):
        """Test validation of poll interval (too short)."""
        flow = self._create_options_flow(
            mock_config_entry_data, mock_config_entry_options
        )

        result = await flow.async_step_init(
            user_input={
                "poll_interval": 30,  # Too short (min is 60)
                "counter_a_offset": 0.0,
                "counter_b_offset": 0.0,
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert "poll_interval_too_short" in result["errors"].values()

    async def test_options_flow_negative_offset(
        self, hass, mock_config_entry_data, mock_config_entry_options
    ):
        """Test validation of negative offset."""
        flow = self._create_options_flow(
            mock_config_entry_data, mock_config_entry_options
        )

        result = await flow.async_step_init(
            user_input={
                "poll_interval": 3600,
                "counter_a_offset": -10.0,  # Negative not allowed
                "counter_b_offset": 0.0,
            }
        )

        assert result["type"] == FlowResultType.FORM
        assert "offset_negative" in result["errors"].values()
