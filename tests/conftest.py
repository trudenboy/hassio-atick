"""Common fixtures for aTick integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.core import HomeAssistant


@pytest.fixture
def hass() -> MagicMock:
    """Return a mock Home Assistant instance."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.data = {}
    return mock_hass


@pytest.fixture
def mock_ble_device() -> BLEDevice:
    """Return a mock BLE device."""
    device = MagicMock(spec=BLEDevice)
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "aTick_Test"
    return device


@pytest.fixture
def mock_config_entry_data() -> dict:
    """Return mock config entry data."""
    return {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_PIN: "123456",
        "device_info": {
            "model": "aTick Model",
            "manufacturer": "Deembot",
            "firmware_version": "1.0.0",
        },
    }


@pytest.fixture
def mock_config_entry_options() -> dict:
    """Return mock config entry options."""
    return {
        "poll_interval": 3600,
        "use_device_ratio": False,
        "counter_a_ratio": 1.0,
        "counter_b_ratio": 1.0,
        "counter_a_offset": 0.0,
        "counter_b_offset": 0.0,
    }


@pytest.fixture
def mock_bleak_client() -> Generator[AsyncMock, None, None]:
    """Mock BleakClient."""
    with patch(
        "custom_components.deembot_atick.device.BleakClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.is_connected = True
        client.read_gatt_char = AsyncMock()
        client.write_gatt_char = AsyncMock()
        client.disconnect = AsyncMock()
        yield client


@pytest.fixture
def mock_advertisement_data() -> dict:
    """Return mock advertisement data."""
    # Unencrypted data with counter values 123.45 and 67.89
    return {
        65535: bytes([0x00, 0x00, 0xF6, 0x42, 0x00, 0x00, 0x87, 0x42, 0x00]),
    }


@pytest.fixture
def mock_encrypted_advertisement_data() -> dict:
    """Return mock encrypted advertisement data."""
    # Encrypted flag set (bit 4 in byte 7)
    return {
        65535: bytes([0x00, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x10, 0x00]),
    }
