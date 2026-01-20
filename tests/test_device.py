"""Tests for aTick device module."""
from __future__ import annotations

import pytest
from bleak.backends.device import BLEDevice

from custom_components.deembot_atick.device import ATickBTDevice


def test_device_initialization(mock_ble_device: BLEDevice) -> None:
    """Test device initialization."""
    device = ATickBTDevice(mock_ble_device)

    assert device.base_unique_id == "AA:BB:CC:DD:EE:FF"
    assert device.name == "aTick_Test"
    assert device.data["counter_a_value"] is None
    assert device.data["counter_b_value"] is None
    assert device.data["counter_a_ratio"] == 0.01
    assert device.data["counter_b_ratio"] == 0.01
    assert device.data["counter_a_offset"] == 0.0
    assert device.data["counter_b_offset"] == 0.0


def test_device_with_custom_poll_interval(mock_ble_device: BLEDevice) -> None:
    """Test device initialization with custom poll interval."""
    custom_interval = 7200
    device = ATickBTDevice(mock_ble_device, poll_interval=custom_interval)

    assert device._poll_interval == custom_interval


def test_is_encrypted_with_short_data() -> None:
    """Test is_encrypted returns False for short data."""
    short_data = bytes([0x00, 0x01, 0x02])
    assert ATickBTDevice.is_encrypted(short_data) is False


def test_is_encrypted_with_unencrypted_data() -> None:
    """Test is_encrypted returns False for unencrypted data."""
    unencrypted_data = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x00])
    assert ATickBTDevice.is_encrypted(unencrypted_data) is False


def test_is_encrypted_with_encrypted_data() -> None:
    """Test is_encrypted returns True for encrypted data."""
    # Bit 4 set in byte 7
    encrypted_data = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x10])
    assert ATickBTDevice.is_encrypted(encrypted_data) is True


def test_truncate_float() -> None:
    """Test float truncation."""
    assert ATickBTDevice.truncate_float(123.456789, 2) == 123.45
    assert ATickBTDevice.truncate_float(0.999, 2) == 0.99
    assert ATickBTDevice.truncate_float(100.001, 3) == 100.001


def test_midLittleEndian() -> None:
    """Test middle little endian byte order conversion."""
    # Test conversion: bytes [0,1,2,3] -> [2,3,0,1]
    result = ATickBTDevice.midLittleEndian("00112233")
    assert result == "22330011"


def test_get_counter_value_with_ratio(mock_ble_device: BLEDevice) -> None:
    """Test getting counter value with ratio applied."""
    device = ATickBTDevice(mock_ble_device)

    # Set raw counter value
    device.data["counter_a_value"] = 100.0
    device.data["counter_a_ratio"] = 0.01
    device.data["counter_a_offset"] = 0.0

    # Should return 100.0 * 0.01 + 0.0 = 1.0
    result = device.get_counter_value_with_ratio("counter_a_value")
    assert result == 1.0


def test_get_counter_value_with_ratio_and_offset(mock_ble_device: BLEDevice) -> None:
    """Test getting counter value with ratio and offset applied."""
    device = ATickBTDevice(mock_ble_device)

    # Set raw counter value
    device.data["counter_b_value"] = 100.0
    device.data["counter_b_ratio"] = 0.01
    device.data["counter_b_offset"] = 10.0

    # Should return 100.0 * 0.01 + 10.0 = 11.0
    result = device.get_counter_value_with_ratio("counter_b_value")
    assert result == 11.0


def test_get_counter_value_with_none_value(mock_ble_device: BLEDevice) -> None:
    """Test getting counter value when value is None."""
    device = ATickBTDevice(mock_ble_device)

    # Counter value is None by default
    result = device.get_counter_value_with_ratio("counter_a_value")
    assert result is None


def test_parse_adv_values_counters_with_short_data(mock_ble_device: BLEDevice) -> None:
    """Test parsing advertisement with data too short."""
    device = ATickBTDevice(mock_ble_device)

    short_data = bytes([0x00, 0x01])
    result = device.parseAdvValuesCounters(short_data, "123456", "AA:BB:CC:DD:EE:FF")

    assert result == [0.0, 0.0]


def test_parse_adv_values_counters_with_none_data(mock_ble_device: BLEDevice) -> None:
    """Test parsing advertisement with None data."""
    device = ATickBTDevice(mock_ble_device)

    result = device.parseAdvValuesCounters(None, "123456", "AA:BB:CC:DD:EE:FF")

    assert result == [0.0, 0.0]


def test_active_poll_needed_initial(mock_ble_device: BLEDevice) -> None:
    """Test that active poll is needed initially."""
    device = ATickBTDevice(mock_ble_device, poll_interval=3600)

    # Should need poll on first call
    assert device.active_poll_needed(None) is True


def test_active_poll_needed_after_recent_poll(mock_ble_device: BLEDevice) -> None:
    """Test that active poll is not needed after recent poll."""
    device = ATickBTDevice(mock_ble_device, poll_interval=3600)

    # Recent poll (60 seconds ago)
    assert device.active_poll_needed(60.0) is False


def test_active_poll_needed_after_old_poll(mock_ble_device: BLEDevice) -> None:
    """Test that active poll is needed after interval expires."""
    device = ATickBTDevice(mock_ble_device, poll_interval=3600)

    # Old poll (2 hours ago)
    assert device.active_poll_needed(7200.0) is True
