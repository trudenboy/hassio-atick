"""Tests for aTick device module."""

from __future__ import annotations

import pytest
from bleak.backends.device import BLEDevice

from custom_components.deembot_atick.const import CounterType
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
    assert ATickBTDevice._truncate_float(123.456789, 2) == 123.45
    assert ATickBTDevice._truncate_float(0.999, 2) == 0.99
    assert ATickBTDevice._truncate_float(100.001, 3) == 100.001


def test_mid_little_endian() -> None:
    """Test middle little endian byte order conversion."""
    # Test conversion: bytes [0,1,2,3] -> [2,3,0,1]
    result = ATickBTDevice._mid_little_endian("00112233")
    assert result == "22330011"


def test_get_counter_value_with_ratio_string_key(mock_ble_device: BLEDevice) -> None:
    """Test getting counter value with ratio applied using string key."""
    device = ATickBTDevice(mock_ble_device)

    # Set raw counter value
    device.data["counter_a_value"] = 100.0
    device.data["counter_a_ratio"] = 0.01
    device.data["counter_a_offset"] = 0.0

    # Should return 100.0 * 0.01 + 0.0 = 1.0
    result = device.get_counter_value_with_ratio("counter_a_value")
    assert result == 1.0


def test_get_counter_value_with_ratio_enum(mock_ble_device: BLEDevice) -> None:
    """Test getting counter value with ratio applied using CounterType enum."""
    device = ATickBTDevice(mock_ble_device)

    # Set raw counter value
    device.data["counter_a_value"] = 100.0
    device.data["counter_a_ratio"] = 0.01
    device.data["counter_a_offset"] = 0.0

    # Should return 100.0 * 0.01 + 0.0 = 1.0
    result = device.get_counter_value_with_ratio(CounterType.A)
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
    result = device._parse_adv_values_counters(
        short_data, "123456", "AA:BB:CC:DD:EE:FF"
    )

    assert result == [0.0, 0.0]


def test_parse_adv_values_counters_with_none_data(mock_ble_device: BLEDevice) -> None:
    """Test parsing advertisement with None data."""
    device = ATickBTDevice(mock_ble_device)

    result = device._parse_adv_values_counters(None, "123456", "AA:BB:CC:DD:EE:FF")

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


def test_counter_type_enum() -> None:
    """Test CounterType enum properties."""
    assert CounterType.A.value_key == "counter_a_value"
    assert CounterType.A.ratio_key == "counter_a_ratio"
    assert CounterType.A.offset_key == "counter_a_offset"

    assert CounterType.B.value_key == "counter_b_value"
    assert CounterType.B.ratio_key == "counter_b_ratio"
    assert CounterType.B.offset_key == "counter_b_offset"


def test_counter_type_from_entity_id() -> None:
    """Test CounterType.from_entity_id method."""
    assert CounterType.from_entity_id("sensor.atick_123_counter_a") == CounterType.A
    assert CounterType.from_entity_id("sensor.atick_123_counter_b") == CounterType.B
    assert CounterType.from_entity_id("sensor.atick_123_rssi") is None


@pytest.mark.asyncio
async def test_set_counter_value(mock_ble_device: BLEDevice) -> None:
    """Test setting counter value."""
    device = ATickBTDevice(mock_ble_device)

    # Set initial ratios
    device.data["counter_a_ratio"] = 0.01
    device.data["counter_a_offset"] = 0.0

    # Set displayed value of 1.5 m³
    await device.set_counter_value(CounterType.A, 1.5)

    # Raw value should be 1.5 / 0.01 = 150.0
    assert device.data["counter_a_value"] == 150.0


@pytest.mark.asyncio
async def test_set_counter_value_with_offset(mock_ble_device: BLEDevice) -> None:
    """Test setting counter value with offset."""
    device = ATickBTDevice(mock_ble_device)

    # Set initial ratios and offset
    device.data["counter_b_ratio"] = 0.01
    device.data["counter_b_offset"] = 10.0

    # Set displayed value of 15.0 m³
    await device.set_counter_value(CounterType.B, 15.0)

    # Raw value should be (15.0 - 10.0) / 0.01 = 500.0
    assert device.data["counter_b_value"] == 500.0


def test_backoff_initial_state(mock_ble_device: BLEDevice) -> None:
    """Test that backoff is not active initially."""
    device = ATickBTDevice(mock_ble_device)

    assert device._connection_failures == 0
    assert device._last_connection_failure == 0.0

    # Should not raise
    device._check_backoff()


def test_backoff_after_failures(mock_ble_device: BLEDevice) -> None:
    """Test that backoff activates after multiple failures."""
    device = ATickBTDevice(mock_ble_device)

    # Simulate 5 failures
    for _ in range(5):
        device._record_failure()

    assert device._connection_failures == 5

    # Should raise BleakError due to backoff
    from bleak.exc import BleakError

    with pytest.raises(BleakError, match="Connection backoff active"):
        device._check_backoff()


def test_backoff_reset(mock_ble_device: BLEDevice) -> None:
    """Test that backoff resets after successful connection."""
    device = ATickBTDevice(mock_ble_device)

    # Simulate failures
    for _ in range(5):
        device._record_failure()

    assert device._connection_failures == 5

    # Reset backoff
    device._reset_backoff()

    assert device._connection_failures == 0
    assert device._last_connection_failure == 0.0

    # Should not raise
    device._check_backoff()


def test_update_ble_device(mock_ble_device: BLEDevice) -> None:
    """Test updating BLE device reference."""
    from unittest.mock import MagicMock

    device = ATickBTDevice(mock_ble_device)

    assert device._ble_device.address == "AA:BB:CC:DD:EE:FF"

    # Create new mock BLE device with different address
    new_ble_device = MagicMock(spec=BLEDevice)
    new_ble_device.address = "11:22:33:44:55:66"
    new_ble_device.name = "aTick_New"

    # Update BLE device reference
    device.update_ble_device(new_ble_device)

    assert device._ble_device.address == "11:22:33:44:55:66"
    assert device._ble_device.name == "aTick_New"
