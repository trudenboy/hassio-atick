import logging
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er, config_validation as cv

from .const import DOMAIN, ACTIVE_POLL_INTERVAL
from .coordinator import ATickDataUpdateCoordinator
from .device import ATickBTDevice

_LOGGER = logging.getLogger(__name__)

# Options configuration constants
CONF_POLL_INTERVAL = "poll_interval"
CONF_COUNTER_A_OFFSET = "counter_a_offset"
CONF_COUNTER_B_OFFSET = "counter_b_offset"

# Service constants
SERVICE_SET_COUNTER_VALUE = "set_counter_value"
SERVICE_RESET_COUNTER = "reset_counter"
ATTR_VALUE = "value"

# Service schemas
SERVICE_SET_COUNTER_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(float), vol.Range(min=0)),
})

SERVICE_RESET_COUNTER_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_VALUE, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0)),
})

PLATFORMS = [
    Platform.SENSOR
]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for aTick integration."""

    async def handle_set_counter_value(call: ServiceCall) -> None:
        """Handle the set_counter_value service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        value = call.data[ATTR_VALUE]

        entity_reg = er.async_get(hass)
        entity_entry = entity_reg.async_get(entity_id)

        if not entity_entry:
            _LOGGER.error("Entity %s not found", entity_id)
            return

        if entity_entry.platform != DOMAIN:
            _LOGGER.error("Entity %s is not an aTick entity", entity_id)
            return

        # Get coordinator from hass data
        coordinator = hass.data[DOMAIN].get(entity_entry.config_entry_id)
        if not coordinator:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)
            return

        # Determine which counter this is (A or B)
        if "counter_a" in entity_id:
            counter_key = "counter_a_value"
        elif "counter_b" in entity_id:
            counter_key = "counter_b_value"
        else:
            _LOGGER.error("Could not determine counter type for entity %s", entity_id)
            return

        # Get ratio and offset to convert displayed value to raw value
        ratio = coordinator.device.data.get(counter_key.replace('_value', '_ratio'), 1.0)
        offset = coordinator.device.data.get(counter_key.replace('_value', '_offset'), 0.0)

        # Convert from displayed value (with ratio and offset) to raw value
        raw_value = (value - offset) / ratio if ratio != 0 else value

        # Set the raw value
        coordinator.device.data[counter_key] = raw_value

        _LOGGER.info(
            "Set %s to %s m³ (raw: %s, ratio: %s, offset: %s)",
            counter_key, value, raw_value, ratio, offset
        )

        # Trigger update
        coordinator.async_set_updated_data(None)

    async def handle_reset_counter(call: ServiceCall) -> None:
        """Handle the reset_counter service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        value = call.data[ATTR_VALUE]

        entity_reg = er.async_get(hass)
        entity_entry = entity_reg.async_get(entity_id)

        if not entity_entry:
            _LOGGER.error("Entity %s not found", entity_id)
            return

        if entity_entry.platform != DOMAIN:
            _LOGGER.error("Entity %s is not an aTick entity", entity_id)
            return

        # Get coordinator from hass data
        coordinator = hass.data[DOMAIN].get(entity_entry.config_entry_id)
        if not coordinator:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)
            return

        # Determine which counter this is (A or B)
        if "counter_a" in entity_id:
            counter_key = "counter_a_value"
        elif "counter_b" in entity_id:
            counter_key = "counter_b_value"
        else:
            _LOGGER.error("Could not determine counter type for entity %s", entity_id)
            return

        # Get ratio and offset
        ratio = coordinator.device.data.get(counter_key.replace('_value', '_ratio'), 1.0)
        offset = coordinator.device.data.get(counter_key.replace('_value', '_offset'), 0.0)

        # Convert reset value to raw value
        raw_value = (value - offset) / ratio if ratio != 0 else value

        # Reset the counter
        coordinator.device.data[counter_key] = raw_value

        _LOGGER.info("Reset %s to %s m³ (raw: %s)", counter_key, value, raw_value)

        # Trigger update
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    assert entry.unique_id is not None
    hass.data.setdefault(DOMAIN, {})

    # Set up services (only once for all entries)
    await async_setup_services(hass)

    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), False)

    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find BT Device with address {address}")

    # Get options with defaults
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, ACTIVE_POLL_INTERVAL)
    counter_a_offset = entry.options.get(CONF_COUNTER_A_OFFSET, 0.0)
    counter_b_offset = entry.options.get(CONF_COUNTER_B_OFFSET, 0.0)

    # Create device with custom poll interval
    device = ATickBTDevice(ble_device, poll_interval=poll_interval)
    device.data['counter_a_offset'] = counter_a_offset
    device.data['counter_b_offset'] = counter_b_offset

    coordinator = ATickDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        logger=_LOGGER,
        ble_device=ble_device,
        device=device,
        connectable=True
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(coordinator.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    device_info = entry.data.get('device_info')

    if device_info:
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={
                (DOMAIN, entry.unique_id)
            },
            connections={
                (dr.CONNECTION_BLUETOOTH, address)
            },
            name=entry.title,
            model=device_info.get('model'),
            manufacturer=device_info.get('manufacturer'),
            sw_version=device_info.get('firmware_version')
        )

    return True

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok
