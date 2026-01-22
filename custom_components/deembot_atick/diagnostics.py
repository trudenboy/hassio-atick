"""Diagnostics support for aTick integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ATickDataUpdateCoordinator

TO_REDACT = {CONF_PIN, CONF_ADDRESS, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ATickDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device

    # Collect device data
    device_data = {
        "counter_a_value": device.data.get("counter_a_value"),
        "counter_b_value": device.data.get("counter_b_value"),
        "counter_a_ratio": device.data.get("counter_a_ratio"),
        "counter_b_ratio": device.data.get("counter_b_ratio"),
        "counter_a_offset": device.data.get("counter_a_offset"),
        "counter_b_offset": device.data.get("counter_b_offset"),
    }

    # Collect device info
    device_info = {
        "name": device.name,
        "model": device.model,
        "manufacturer": device.manufacturer,
        "firmware_version": device.firmware_version,
    }

    # Collect connection status
    connection_status = {
        "connection_failures": device._connection_failures,
        "poll_interval": device._poll_interval,
        "use_device_ratio": device._use_device_ratio,
    }

    diagnostics_data = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device": {
            "data": device_data,
            "info": device_info,
            "connection": connection_status,
        },
        "coordinator": {
            "address": "**REDACTED**",
            "was_unavailable": coordinator._was_unavailable,
        },
    }

    return diagnostics_data
