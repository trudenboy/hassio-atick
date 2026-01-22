"""Tests for aTick integration init module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.config_entries import ConfigEntry

from custom_components.deembot_atick import (
    SERVICE_RESET_COUNTER,
    SERVICE_SET_COUNTER_VALUE,
    _get_counter_context,
    async_setup_entry,
    async_setup_services,
    async_unload_entry,
    async_unload_services,
)
from custom_components.deembot_atick.const import DOMAIN, CounterType


class TestGetCounterContext:
    """Test _get_counter_context helper function."""

    def test_entity_not_found(self, hass: MagicMock) -> None:
        """Test returns None when entity not found."""
        mock_entity_registry = MagicMock()
        mock_entity_registry.async_get.return_value = None

        with patch(
            "custom_components.deembot_atick.er.async_get",
            return_value=mock_entity_registry,
        ):
            coordinator, counter_type = _get_counter_context(hass, "sensor.nonexistent")

        assert coordinator is None
        assert counter_type is None

    def test_entity_wrong_platform(self, hass: MagicMock) -> None:
        """Test returns None when entity is not aTick platform."""
        mock_entity_registry = MagicMock()
        mock_entry = MagicMock()
        mock_entry.platform = "other_platform"
        mock_entity_registry.async_get.return_value = mock_entry

        with patch(
            "custom_components.deembot_atick.er.async_get",
            return_value=mock_entity_registry,
        ):
            coordinator, counter_type = _get_counter_context(hass, "sensor.some_entity")

        assert coordinator is None
        assert counter_type is None

    def test_coordinator_not_found(self, hass: MagicMock) -> None:
        """Test returns None when coordinator not found."""
        mock_entity_registry = MagicMock()
        mock_entry = MagicMock()
        mock_entry.platform = DOMAIN
        mock_entry.config_entry_id = "missing_entry"
        mock_entity_registry.async_get.return_value = mock_entry

        hass.data = {DOMAIN: {}}

        with patch(
            "custom_components.deembot_atick.er.async_get",
            return_value=mock_entity_registry,
        ):
            coordinator, counter_type = _get_counter_context(
                hass, "sensor.some_counter_a"
            )

        assert coordinator is None
        assert counter_type is None

    def test_counter_type_not_determined(self, hass: MagicMock) -> None:
        """Test returns None when counter type cannot be determined."""
        mock_entity_registry = MagicMock()
        mock_entry = MagicMock()
        mock_entry.platform = DOMAIN
        mock_entry.config_entry_id = "test_entry"
        mock_entity_registry.async_get.return_value = mock_entry

        mock_coordinator = MagicMock()
        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

        with patch(
            "custom_components.deembot_atick.er.async_get",
            return_value=mock_entity_registry,
        ):
            # Entity ID without counter_a or counter_b
            coordinator, counter_type = _get_counter_context(hass, "sensor.some_rssi")

        assert coordinator is None
        assert counter_type is None

    def test_successful_context(self, hass: MagicMock) -> None:
        """Test returns coordinator and counter type when found."""
        mock_entity_registry = MagicMock()
        mock_entry = MagicMock()
        mock_entry.platform = DOMAIN
        mock_entry.config_entry_id = "test_entry"
        mock_entity_registry.async_get.return_value = mock_entry

        mock_coordinator = MagicMock()
        hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

        with patch(
            "custom_components.deembot_atick.er.async_get",
            return_value=mock_entity_registry,
        ):
            coordinator, counter_type = _get_counter_context(
                hass, "sensor.atick_counter_a_value"
            )

        assert coordinator == mock_coordinator
        assert counter_type == CounterType.A


class TestAsyncSetupServices:
    """Test service setup."""

    @pytest.mark.asyncio
    async def test_services_registered(self, hass: MagicMock) -> None:
        """Test services are registered."""
        hass.services = MagicMock()
        hass.services.has_service.return_value = False

        await async_setup_services(hass)

        # Should register both services
        assert hass.services.async_register.call_count == 2

        # Verify service names
        call_args = [call[0] for call in hass.services.async_register.call_args_list]
        service_names = [args[1] for args in call_args]

        assert SERVICE_SET_COUNTER_VALUE in service_names
        assert SERVICE_RESET_COUNTER in service_names

    @pytest.mark.asyncio
    async def test_services_not_registered_twice(self, hass: MagicMock) -> None:
        """Test services are not registered if already exist."""
        hass.services = MagicMock()
        hass.services.has_service.return_value = True

        await async_setup_services(hass)

        hass.services.async_register.assert_not_called()


class TestAsyncUnloadServices:
    """Test service unloading."""

    @pytest.mark.asyncio
    async def test_services_removed(self, hass: MagicMock) -> None:
        """Test services are removed."""
        hass.services = MagicMock()
        hass.services.has_service.return_value = True

        await async_unload_services(hass)

        assert hass.services.async_remove.call_count == 2

    @pytest.mark.asyncio
    async def test_services_not_removed_if_not_exist(self, hass: MagicMock) -> None:
        """Test services not removed if they don't exist."""
        hass.services = MagicMock()
        hass.services.has_service.return_value = False

        await async_unload_services(hass)

        hass.services.async_remove.assert_not_called()


class TestAsyncSetupEntry:
    """Test entry setup."""

    @pytest.mark.asyncio
    async def test_setup_entry_success(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_config_entry_data: dict,
        mock_config_entry_options: dict,
    ) -> None:
        """Test successful entry setup."""
        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "AA:BB:CC:DD:EE:FF"
        entry.entry_id = "test_entry_id"
        entry.title = "aTick Device"
        entry.data = mock_config_entry_data
        entry.options = mock_config_entry_options
        entry.async_on_unload = MagicMock()

        hass.data = {}
        hass.services = MagicMock()
        hass.services.has_service.return_value = False
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        with patch(
            "custom_components.deembot_atick.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ), patch("custom_components.deembot_atick.dr.async_get") as mock_dr, patch(
            "custom_components.deembot_atick.coordinator.ATickDataUpdateCoordinator.async_start",
            return_value=MagicMock(),
        ):
            mock_dr.return_value.async_get_or_create = MagicMock()

            result = await async_setup_entry(hass, entry)

        assert result is True
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_setup_entry_no_ble_device(
        self,
        hass: MagicMock,
        mock_config_entry_data: dict,
        mock_config_entry_options: dict,
    ) -> None:
        """Test entry setup fails when BLE device not found."""
        from homeassistant.exceptions import ConfigEntryNotReady

        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "AA:BB:CC:DD:EE:FF"
        entry.entry_id = "test_entry_id"
        entry.data = mock_config_entry_data
        entry.options = mock_config_entry_options

        hass.data = {}
        hass.services = MagicMock()
        hass.services.has_service.return_value = False

        with patch(
            "custom_components.deembot_atick.bluetooth.async_ble_device_from_address",
            return_value=None,
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_setup_entry_options_defaults(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_config_entry_data: dict,
    ) -> None:
        """Test entry setup uses default options when not provided."""
        entry = MagicMock(spec=ConfigEntry)
        entry.unique_id = "AA:BB:CC:DD:EE:FF"
        entry.entry_id = "test_entry_id"
        entry.title = "aTick Device"
        entry.data = mock_config_entry_data
        entry.options = {}  # Empty options
        entry.async_on_unload = MagicMock()

        hass.data = {}
        hass.services = MagicMock()
        hass.services.has_service.return_value = False
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        with patch(
            "custom_components.deembot_atick.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ), patch("custom_components.deembot_atick.dr.async_get") as mock_dr, patch(
            "custom_components.deembot_atick.coordinator.ATickDataUpdateCoordinator.async_start",
            return_value=MagicMock(),
        ):
            mock_dr.return_value.async_get_or_create = MagicMock()

            result = await async_setup_entry(hass, entry)

        assert result is True

        # Check that coordinator was created with defaults
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.device.data["counter_a_ratio"] == 1.0
        assert coordinator.device.data["counter_b_ratio"] == 1.0
        assert coordinator.device.data["counter_a_offset"] == 0.0
        assert coordinator.device.data["counter_b_offset"] == 0.0


class TestAsyncUnloadEntry:
    """Test entry unloading."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, hass: MagicMock) -> None:
        """Test successful entry unload."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"

        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.cleanup = AsyncMock()

        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services = MagicMock()
        hass.services.has_service.return_value = True

        result = await async_unload_entry(hass, entry)

        assert result is True
        mock_coordinator.device.cleanup.assert_called_once()

        # Should remove services since this was last entry
        assert hass.services.async_remove.call_count == 2

    @pytest.mark.asyncio
    async def test_unload_entry_keeps_services_if_other_entries(
        self, hass: MagicMock
    ) -> None:
        """Test services not removed if other entries exist."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"

        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.cleanup = AsyncMock()

        # Multiple entries exist
        hass.data = {
            DOMAIN: {
                "test_entry_id": mock_coordinator,
                "other_entry_id": MagicMock(),
            }
        }
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services = MagicMock()

        result = await async_unload_entry(hass, entry)

        assert result is True

        # Should NOT remove services since other entries exist
        hass.services.async_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_unload_entry_failure(self, hass: MagicMock) -> None:
        """Test entry unload failure."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"

        mock_coordinator = MagicMock()
        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        result = await async_unload_entry(hass, entry)

        assert result is False

        # Coordinator should NOT be removed on failure
        assert "test_entry_id" in hass.data[DOMAIN]
