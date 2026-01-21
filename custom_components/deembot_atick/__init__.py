"""Home Assistant integration for Deembot aTick BLE water meter."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import ACTIVE_POLL_INTERVAL, DEFAULT_COUNTER_RATIO, DOMAIN, CounterType
from .coordinator import ATickDataUpdateCoordinator
from .device import ATickBTDevice

_LOGGER = logging.getLogger(__name__)

# Options configuration constants
CONF_POLL_INTERVAL = "poll_interval"
CONF_USE_DEVICE_RATIO = "use_device_ratio"
CONF_COUNTER_A_RATIO = "counter_a_ratio"
CONF_COUNTER_B_RATIO = "counter_b_ratio"
CONF_COUNTER_A_OFFSET = "counter_a_offset"
CONF_COUNTER_B_OFFSET = "counter_b_offset"

# Service constants
SERVICE_SET_COUNTER_VALUE = "set_counter_value"
SERVICE_RESET_COUNTER = "reset_counter"
ATTR_VALUE = "value"

# Service schemas
SERVICE_SET_COUNTER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VALUE): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)

SERVICE_RESET_COUNTER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_VALUE, default=0.0): vol.All(
            vol.Coerce(float), vol.Range(min=0)
        ),
    }
)

PLATFORMS = [Platform.SENSOR]


def _get_counter_context(
    hass: HomeAssistant, entity_id: str
) -> tuple[ATickDataUpdateCoordinator, CounterType] | tuple[None, None]:
    """Get coordinator and counter type for an entity.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to look up

    Returns:
        Tuple of (coordinator, counter_type) or (None, None) if not found
    """
    entity_reg = er.async_get(hass)
    entity_entry = entity_reg.async_get(entity_id)

    if not entity_entry:
        _LOGGER.error("Entity %s not found", entity_id)
        return None, None

    if entity_entry.platform != DOMAIN:
        _LOGGER.error("Entity %s is not an aTick entity", entity_id)
        return None, None

    coordinator = hass.data[DOMAIN].get(entity_entry.config_entry_id)
    if not coordinator:
        _LOGGER.error("Coordinator not found for entity %s", entity_id)
        return None, None

    counter_type = CounterType.from_entity_id(entity_id)
    if counter_type is None:
        _LOGGER.error("Could not determine counter type for entity %s", entity_id)
        return None, None

    return coordinator, counter_type


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for aTick integration."""

    async def handle_set_counter_value(call: ServiceCall) -> None:
        """Handle the set_counter_value service call."""
        entity_id: str = call.data[ATTR_ENTITY_ID]
        value: float = call.data[ATTR_VALUE]

        coordinator, counter_type = _get_counter_context(hass, entity_id)
        if coordinator is None or counter_type is None:
            return

        await coordinator.device.set_counter_value(counter_type, value)
        coordinator.async_set_updated_data(None)

    async def handle_reset_counter(call: ServiceCall) -> None:
        """Handle the reset_counter service call."""
        entity_id: str = call.data[ATTR_ENTITY_ID]
        value: float = call.data[ATTR_VALUE]

        coordinator, counter_type = _get_counter_context(hass, entity_id)
        if coordinator is None or counter_type is None:
            return

        await coordinator.device.set_counter_value(counter_type, value)
        _LOGGER.info("Reset %s to %s m³", counter_type.value_key, value)
        coordinator.async_set_updated_data(None)

    # Register services only once
    if not hass.services.has_service(DOMAIN, SERVICE_SET_COUNTER_VALUE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_COUNTER_VALUE,
            handle_set_counter_value,
            schema=SERVICE_SET_COUNTER_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RESET_COUNTER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET_COUNTER,
            handle_reset_counter,
            schema=SERVICE_RESET_COUNTER_SCHEMA,
        )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services when last config entry is removed."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_COUNTER_VALUE):
        hass.services.async_remove(DOMAIN, SERVICE_SET_COUNTER_VALUE)

    if hass.services.has_service(DOMAIN, SERVICE_RESET_COUNTER):
        hass.services.async_remove(DOMAIN, SERVICE_RESET_COUNTER)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up aTick from a config entry."""
    assert entry.unique_id is not None
    hass.data.setdefault(DOMAIN, {})

    # Set up services (only once for all entries)
    await async_setup_services(hass)

    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), False)

    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find BT Device with address {address}")

    # Get options with defaults (ensure correct types)
    poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, ACTIVE_POLL_INTERVAL))
    use_device_ratio = bool(entry.options.get(CONF_USE_DEVICE_RATIO, False))
    counter_a_ratio = float(
        entry.options.get(CONF_COUNTER_A_RATIO, DEFAULT_COUNTER_RATIO)
    )
    counter_b_ratio = float(
        entry.options.get(CONF_COUNTER_B_RATIO, DEFAULT_COUNTER_RATIO)
    )
    counter_a_offset = float(entry.options.get(CONF_COUNTER_A_OFFSET, 0.0))
    counter_b_offset = float(entry.options.get(CONF_COUNTER_B_OFFSET, 0.0))

    # Create device with custom poll interval
    device = ATickBTDevice(
        ble_device, poll_interval=poll_interval, use_device_ratio=use_device_ratio
    )
    device.data["counter_a_ratio"] = counter_a_ratio
    device.data["counter_b_ratio"] = counter_b_ratio
    device.data["counter_a_offset"] = counter_a_offset
    device.data["counter_b_offset"] = counter_b_offset

    coordinator = ATickDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        logger=_LOGGER,
        ble_device=ble_device,
        device=device,
        connectable=True,
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register device BEFORE platform setup
    device_info = entry.data.get("device_info")
    if device_info:
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
            name=entry.title,
            model=device_info.get("model"),
            manufacturer=device_info.get("manufacturer"),
            sw_version=device_info.get("firmware_version"),
        )

    entry.async_on_unload(coordinator.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: ATickDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)

        # Cleanup device resources
        await coordinator.device.cleanup()

        # Remove services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            await async_unload_services(hass)

    return unload_ok
