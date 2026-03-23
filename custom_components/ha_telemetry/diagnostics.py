from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MQTT_PASSWORD
from .manager import TelemetryManager


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    manager: TelemetryManager = entry.runtime_data
    merged = dict(entry.data)
    merged.update(entry.options)

    if CONF_MQTT_PASSWORD in merged:
        merged[CONF_MQTT_PASSWORD] = "<redacted>"

    return {
        "config": merged,
        "runtime": manager.diagnostics(),
    }
