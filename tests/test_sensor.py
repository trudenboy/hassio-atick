"""Tests for aTick sensor module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfVolume

from custom_components.deembot_atick.const import DOMAIN, CounterType
from custom_components.deembot_atick.device import ATickBTDevice
from custom_components.deembot_atick.sensor import (
    ENTITIES,
    ATickRSSISensor,
    ATickWaterCounterSensor,
)


@pytest.fixture
def mock_coordinator(mock_ble_device: BLEDevice) -> MagicMock:
    """Return a mock coordinator."""
    from custom_components.deembot_atick.coordinator import ATickDataUpdateCoordinator

    coordinator = MagicMock(spec=ATickDataUpdateCoordinator)
    coordinator.address = "AA:BB:CC:DD:EE:FF"

    device = ATickBTDevice(mock_ble_device)
    device.data["counter_a_value"] = 100.0
    device.data["counter_b_value"] = 50.0
    device.data["counter_a_ratio"] = 1.0
    device.data["counter_b_ratio"] = 1.0
    device.data["counter_a_offset"] = 0.0
    device.data["counter_b_offset"] = 0.0

    coordinator.device = device
    return coordinator


class TestSensorDescriptions:
    """Test sensor descriptions."""

    def test_entities_count(self) -> None:
        """Test that we have 2 counter entities defined."""
        assert len(ENTITIES) == 2

    def test_counter_a_description(self) -> None:
        """Test Counter A sensor description."""
        counter_a = ENTITIES[0]

        assert counter_a.key == CounterType.A.value_key
        assert counter_a.translation_key == CounterType.A.value_key
        assert counter_a.device_class == SensorDeviceClass.WATER
        assert counter_a.native_unit_of_measurement == UnitOfVolume.CUBIC_METERS
        assert counter_a.state_class == SensorStateClass.TOTAL
        assert counter_a.suggested_display_precision == 2

    def test_counter_b_description(self) -> None:
        """Test Counter B sensor description."""
        counter_b = ENTITIES[1]

        assert counter_b.key == CounterType.B.value_key
        assert counter_b.translation_key == CounterType.B.value_key
        assert counter_b.device_class == SensorDeviceClass.WATER
        assert counter_b.native_unit_of_measurement == UnitOfVolume.CUBIC_METERS
        assert counter_b.state_class == SensorStateClass.TOTAL
        assert counter_b.suggested_display_precision == 2


class TestATickWaterCounterSensor:
    """Test ATickWaterCounterSensor class."""

    def test_sensor_initialization(self, mock_coordinator: MagicMock) -> None:
        """Test sensor initialization."""
        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])

        assert sensor.entity_description == ENTITIES[0]
        assert sensor._attr_unique_id == "AA:BB:CC:DD:EE:FF-counter_a_value"
        assert "Counter A" in sensor._attr_name
        assert sensor._attr_icon == "mdi:counter"
        assert sensor._attr_device_class == SensorDeviceClass.WATER
        assert sensor._attr_native_unit_of_measurement == UnitOfVolume.CUBIC_METERS
        assert sensor._attr_state_class == SensorStateClass.TOTAL

    def test_native_value_with_ratio(self, mock_coordinator: MagicMock) -> None:
        """Test native_value applies ratio correctly."""
        # Set specific values
        mock_coordinator.device.data["counter_a_value"] = 100.0
        mock_coordinator.device.data["counter_a_ratio"] = 0.01
        mock_coordinator.device.data["counter_a_offset"] = 0.0

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])

        # Should return 100.0 * 0.01 + 0.0 = 1.0
        assert sensor.native_value == 1.0

    def test_native_value_with_ratio_and_offset(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test native_value applies ratio and offset correctly."""
        mock_coordinator.device.data["counter_b_value"] = 100.0
        mock_coordinator.device.data["counter_b_ratio"] = 0.01
        mock_coordinator.device.data["counter_b_offset"] = 10.0

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[1])

        # Should return 100.0 * 0.01 + 10.0 = 11.0
        assert sensor.native_value == 11.0

    def test_native_value_when_none(self, mock_coordinator: MagicMock) -> None:
        """Test native_value returns None when counter value is None."""
        mock_coordinator.device.data["counter_a_value"] = None

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])

        assert sensor.native_value is None

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restore_state(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test state restoration when entity is added to Home Assistant."""
        # Clear the counter value to trigger restoration
        mock_coordinator.device.data["counter_a_value"] = None
        mock_coordinator.device.data["counter_a_ratio"] = 1.0

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])
        sensor.hass = hass

        # Mock last state
        mock_state = MagicMock()
        mock_state.state = "75.5"

        with patch.object(
            sensor, "async_get_last_state", new_callable=AsyncMock
        ) as mock_get_state:
            mock_get_state.return_value = mock_state

            # Mock parent method
            with patch.object(
                ATickWaterCounterSensor.__bases__[2],
                "async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        # With ratio 1.0, raw value should equal restored value
        assert mock_coordinator.device.data["counter_a_value"] == 75.5

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restore_with_ratio(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test state restoration with ratio conversion."""
        mock_coordinator.device.data["counter_a_value"] = None
        mock_coordinator.device.data["counter_a_ratio"] = 0.01

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])
        sensor.hass = hass

        mock_state = MagicMock()
        mock_state.state = "1.5"  # Displayed value

        with patch.object(
            sensor, "async_get_last_state", new_callable=AsyncMock
        ) as mock_get_state:
            mock_get_state.return_value = mock_state

            with patch.object(
                ATickWaterCounterSensor.__bases__[2],
                "async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        # Raw value should be 1.5 / 0.01 = 150.0
        assert mock_coordinator.device.data["counter_a_value"] == 150.0

    @pytest.mark.asyncio
    async def test_async_added_to_hass_no_restore_when_value_exists(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test no restoration when counter value already exists."""
        mock_coordinator.device.data["counter_a_value"] = 100.0

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])
        sensor.hass = hass

        with patch.object(
            sensor, "async_get_last_state", new_callable=AsyncMock
        ) as mock_get_state:
            with patch.object(
                ATickWaterCounterSensor.__bases__[2],
                "async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        # Should not call async_get_last_state
        mock_get_state.assert_not_called()

        # Value should remain unchanged
        assert mock_coordinator.device.data["counter_a_value"] == 100.0

    @pytest.mark.asyncio
    async def test_async_added_to_hass_invalid_state(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test restoration with invalid state value."""
        mock_coordinator.device.data["counter_a_value"] = None

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])
        sensor.hass = hass

        mock_state = MagicMock()
        mock_state.state = "invalid"  # Not a number

        with patch.object(
            sensor, "async_get_last_state", new_callable=AsyncMock
        ) as mock_get_state:
            mock_get_state.return_value = mock_state

            with patch.object(
                ATickWaterCounterSensor.__bases__[2],
                "async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        # Should set to 0.0 on error
        assert mock_coordinator.device.data["counter_a_value"] == 0.0

    @pytest.mark.asyncio
    async def test_async_added_to_hass_negative_value(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test restoration rejects negative values."""
        mock_coordinator.device.data["counter_a_value"] = None
        mock_coordinator.device.data["counter_a_ratio"] = 1.0

        sensor = ATickWaterCounterSensor(mock_coordinator, ENTITIES[0])
        sensor.hass = hass

        mock_state = MagicMock()
        mock_state.state = "-10.0"  # Negative not allowed

        with patch.object(
            sensor, "async_get_last_state", new_callable=AsyncMock
        ) as mock_get_state:
            mock_get_state.return_value = mock_state

            with patch.object(
                ATickWaterCounterSensor.__bases__[2],
                "async_added_to_hass",
                new_callable=AsyncMock,
            ):
                await sensor.async_added_to_hass()

        # Should set to 0.0 for negative value
        assert mock_coordinator.device.data["counter_a_value"] == 0.0


class TestATickRSSISensor:
    """Test ATickRSSISensor class."""

    def test_sensor_initialization(self, mock_coordinator: MagicMock) -> None:
        """Test RSSI sensor initialization."""
        sensor = ATickRSSISensor(mock_coordinator)

        assert sensor.entity_description.key == "rssi"
        assert sensor._attr_unique_id == "AA:BB:CC:DD:EE:FF-rssi"
        assert "Bluetooth signal" in sensor._attr_name
        assert (
            sensor.entity_description.device_class == SensorDeviceClass.SIGNAL_STRENGTH
        )
        assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert sensor.entity_description.entity_registry_enabled_default is False

    def test_native_value_with_service_info(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test native_value returns RSSI from service info."""
        sensor = ATickRSSISensor(mock_coordinator)
        sensor.hass = hass

        mock_service_info = MagicMock()
        mock_service_info.rssi = -65

        with patch(
            "custom_components.deembot_atick.sensor.async_last_service_info",
            return_value=mock_service_info,
        ):
            # Clear cached property
            if "native_value" in sensor.__dict__:
                del sensor.__dict__["native_value"]

            result = sensor.native_value

        assert result == -65

    def test_native_value_no_service_info(
        self, mock_coordinator: MagicMock, hass: MagicMock
    ) -> None:
        """Test native_value returns None when no service info."""
        sensor = ATickRSSISensor(mock_coordinator)
        sensor.hass = hass

        with patch(
            "custom_components.deembot_atick.sensor.async_last_service_info",
            return_value=None,
        ):
            if "native_value" in sensor.__dict__:
                del sensor.__dict__["native_value"]

            result = sensor.native_value

        assert result is None


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_creates_sensors(
        self,
        hass: MagicMock,
        mock_coordinator: MagicMock,
        mock_config_entry_data: dict,
    ) -> None:
        """Test that setup creates all sensor entities."""
        from homeassistant.config_entries import ConfigEntry

        from custom_components.deembot_atick.sensor import async_setup_entry

        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"

        hass.data = {DOMAIN: {"test_entry_id": mock_coordinator}}

        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(hass, entry, capture_entities)

        # Should add 3 sensors: Counter A, Counter B, and RSSI
        assert len(added_entities) == 3

        # Check types
        counter_sensors = [
            e for e in added_entities if isinstance(e, ATickWaterCounterSensor)
        ]
        rssi_sensors = [e for e in added_entities if isinstance(e, ATickRSSISensor)]

        assert len(counter_sensors) == 2
        assert len(rssi_sensors) == 1
