from __future__ import annotations

import logging
from functools import cached_property

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorEntityDescription,
                                             SensorStateClass)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                                 EntityCategory, UnitOfVolume)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ATickDataUpdateCoordinator
from .base_entity import BaseEntity
from .const import DOMAIN, CounterType

_LOGGER = logging.getLogger(__name__)

ENTITIES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=CounterType.A.value_key,
        translation_key=CounterType.A.value_key,
        name="Counter A",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=CounterType.B.value_key,
        translation_key=CounterType.B.value_key,
        name="Counter B",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ATickDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [ATickRSSISensor(coordinator)]

    for description in ENTITIES:
        sensors.append(ATickWaterCounterSensor(coordinator, description))

    async_add_entities(sensors)


class ATickWaterCounterSensor(BaseEntity, SensorEntity, RestoreEntity):
    def __init__(
        self,
        coordinator: ATickDataUpdateCoordinator,
        sensor_description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)

        self.entity_description = sensor_description

        self._attr_unique_id = (
            f"{self._device.base_unique_id}-{self.entity_description.key}"
        )
        self._attr_name = self._device.name + " " + self.entity_description.name
        self._attr_icon = "mdi:counter"
        self._attr_device_class = self.entity_description.device_class
        self._attr_native_unit_of_measurement = (
            self.entity_description.native_unit_of_measurement
        )
        self._attr_state_class = self.entity_description.state_class
        self._attr_suggested_display_precision = (
            self.entity_description.suggested_display_precision
        )

    async def async_added_to_hass(self) -> None:
        """Restore last state when entity is added to Home Assistant."""
        if self._device.data.get(self.entity_description.key) is None:
            if last_state := await self.async_get_last_state():
                try:
                    restored_value_with_ratio = float(last_state.state)
                    if restored_value_with_ratio >= 0:  # Validate non-negative value
                        # Convert back to raw value (divide by ratio)
                        # since we store raw values and apply ratio on display
                        ratio_key = self.entity_description.key.replace(
                            "_value", "_ratio"
                        )
                        ratio = self._device.data.get(ratio_key, 1.0)

                        # Avoid division by zero
                        if ratio != 0:
                            raw_value = restored_value_with_ratio / ratio
                        else:
                            raw_value = restored_value_with_ratio

                        self._device.data[self.entity_description.key] = raw_value
                        _LOGGER.info(
                            "Restored %s: %s m³ (raw: %s, ratio: %s)",
                            self.entity_description.key,
                            restored_value_with_ratio,
                            raw_value,
                            ratio,
                        )
                    else:
                        _LOGGER.warning(
                            "Invalid restored value for %s: %s (negative value)",
                            self.entity_description.key,
                            restored_value_with_ratio,
                        )
                        self._device.data[self.entity_description.key] = 0.0
                except (ValueError, TypeError) as err:
                    _LOGGER.warning(
                        "Could not restore state for %s: %s. Setting to 0.0",
                        self.entity_description.key,
                        err,
                    )
                    self._device.data[self.entity_description.key] = 0.0

        await super().async_added_to_hass()

    @property
    def native_value(self) -> float | None:
        """Return the counter value with ratio (multiplier) applied."""
        return self._device.get_counter_value_with_ratio(self.entity_description.key)


class ATickRSSISensor(BaseEntity, SensorEntity):
    def __init__(self, coordinator: ATickDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

        self.entity_description = SensorEntityDescription(
            key="rssi",
            translation_key="bluetooth_signal",
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

        self._attr_unique_id = (
            f"{self._device.base_unique_id}-{self.entity_description.key}"
        )
        self._attr_name = self._device.name + " Bluetooth signal"

    @cached_property
    def native_value(self) -> str | int | None:
        if service_info := async_last_service_info(self.hass, self._address, False):
            return service_info.rssi

        return None
