"""Tests for aTick coordinator module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import CoreState
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.deembot_atick.coordinator import ATickDataUpdateCoordinator
from custom_components.deembot_atick.device import ATickBTDevice


@pytest.fixture
def mock_service_info() -> BluetoothServiceInfoBleak:
    """Return a mock BluetoothServiceInfoBleak."""
    service_info = MagicMock(spec=BluetoothServiceInfoBleak)
    device = MagicMock(spec=BLEDevice)
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "aTick_Test"
    service_info.device = device
    service_info.advertisement = MagicMock()
    return service_info


@pytest.fixture
def mock_atick_device(mock_ble_device: BLEDevice) -> ATickBTDevice:
    """Return a mock ATickBTDevice."""
    device = ATickBTDevice(mock_ble_device)
    return device


class TestATickDataUpdateCoordinator:
    """Test ATickDataUpdateCoordinator class."""

    def _create_coordinator(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
    ) -> ATickDataUpdateCoordinator:
        """Create a coordinator for testing."""
        from homeassistant.config_entries import ConfigEntry

        from custom_components.deembot_atick.const import DOMAIN

        entry = MagicMock(spec=ConfigEntry)
        entry.data = mock_config_entry_data
        entry.entry_id = "test_entry_id"
        entry.domain = DOMAIN

        import logging

        coordinator = ATickDataUpdateCoordinator(
            hass=hass,
            entry=entry,
            logger=logging.getLogger(__name__),
            ble_device=mock_ble_device,
            device=mock_atick_device,
            connectable=True,
        )

        return coordinator

    def test_coordinator_initialization(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
    ) -> None:
        """Test coordinator initialization."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        assert coordinator.device == mock_atick_device
        assert coordinator._config == mock_config_entry_data
        assert coordinator._was_unavailable is True

    def test_needs_poll_when_hass_running(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _needs_poll returns True when hass is running and poll needed."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        # Mock hass state as running
        hass.state = CoreState.running

        # Mock device poll needed
        mock_atick_device.active_poll_needed = MagicMock(return_value=True)

        # Mock bluetooth device lookup
        with patch(
            "custom_components.deembot_atick.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ):
            result = coordinator._needs_poll(mock_service_info, 7200.0)

        assert result is True

    def test_needs_poll_when_hass_not_running(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _needs_poll returns False when hass is not running."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        # Mock hass state as not running
        hass.state = CoreState.starting

        with patch(
            "custom_components.deembot_atick.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ):
            result = coordinator._needs_poll(mock_service_info, 7200.0)

        assert result is False

    def test_needs_poll_when_poll_not_needed(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _needs_poll returns False when device poll not needed."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        hass.state = CoreState.running

        # Device says poll not needed (recent poll)
        mock_atick_device.active_poll_needed = MagicMock(return_value=False)

        with patch(
            "custom_components.deembot_atick.coordinator.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ):
            result = coordinator._needs_poll(mock_service_info, 60.0)

        assert result is False

    def test_needs_poll_when_no_ble_device(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _needs_poll returns False when BLE device not available."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        hass.state = CoreState.running
        mock_atick_device.active_poll_needed = MagicMock(return_value=True)

        # No BLE device available
        with patch(
            "custom_components.deembot_atick.coordinator.bluetooth.async_ble_device_from_address",
            return_value=None,
        ):
            result = coordinator._needs_poll(mock_service_info, 7200.0)

        assert result is False

    @pytest.mark.asyncio
    async def test_async_update_success(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _async_update succeeds."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        # Mock device update methods
        mock_atick_device.update_ble_device = MagicMock()
        mock_atick_device.active_full_update = AsyncMock()

        await coordinator._async_update(mock_service_info)

        mock_atick_device.update_ble_device.assert_called_once_with(
            mock_service_info.device
        )
        mock_atick_device.active_full_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_failure(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _async_update raises UpdateFailed on error."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        mock_atick_device.update_ble_device = MagicMock()
        mock_atick_device.active_full_update = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with pytest.raises(UpdateFailed, match="Connection failed"):
            await coordinator._async_update(mock_service_info)

    def test_handle_unavailable(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _async_handle_unavailable sets was_unavailable flag."""
        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        # Reset flag
        coordinator._was_unavailable = False

        # Mock parent method
        with patch.object(
            ATickDataUpdateCoordinator.__bases__[0],
            "_async_handle_unavailable",
            return_value=None,
        ):
            coordinator._async_handle_unavailable(mock_service_info)

        assert coordinator._was_unavailable is True

    def test_handle_bluetooth_event_with_changed_data(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _async_handle_bluetooth_event processes changed data."""
        from homeassistant.components.bluetooth import BluetoothChange

        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        # Mock device methods
        parsed_adv = {"counter_a": 100.0, "counter_b": 50.0}
        mock_atick_device.parse_advertisement_data = MagicMock(return_value=parsed_adv)
        mock_atick_device.is_advertisement_changed = MagicMock(return_value=True)
        mock_atick_device.update_from_advertisement = MagicMock()

        # Mock parent method
        with patch.object(
            ATickDataUpdateCoordinator.__bases__[0],
            "_async_handle_bluetooth_event",
            return_value=None,
        ):
            coordinator._async_handle_bluetooth_event(
                mock_service_info, BluetoothChange.ADVERTISEMENT
            )

        mock_atick_device.update_from_advertisement.assert_called_once_with(parsed_adv)
        assert coordinator._was_unavailable is False

    def test_handle_bluetooth_event_no_parsed_data(
        self,
        hass: MagicMock,
        mock_ble_device: BLEDevice,
        mock_atick_device: ATickBTDevice,
        mock_config_entry_data: dict,
        mock_service_info: BluetoothServiceInfoBleak,
    ) -> None:
        """Test _async_handle_bluetooth_event with no parsed data."""
        from homeassistant.components.bluetooth import BluetoothChange

        coordinator = self._create_coordinator(
            hass, mock_ble_device, mock_atick_device, mock_config_entry_data
        )

        # Parse returns None
        mock_atick_device.parse_advertisement_data = MagicMock(return_value=None)
        mock_atick_device.update_from_advertisement = MagicMock()

        with patch.object(
            ATickDataUpdateCoordinator.__bases__[0],
            "_async_handle_bluetooth_event",
            return_value=None,
        ):
            coordinator._async_handle_bluetooth_event(
                mock_service_info, BluetoothChange.ADVERTISEMENT
            )

        mock_atick_device.update_from_advertisement.assert_not_called()
