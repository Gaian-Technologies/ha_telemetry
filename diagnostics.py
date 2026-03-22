from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CA_CERT_PATH, CONF_CLIENT_CERT_PATH, CONF_CLIENT_KEY_PATH
from .manager import TelemetryManager


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    manager: TelemetryManager = entry.runtime_data
    merged = dict(entry.data)
    merged.update(entry.options)

    for key in (CONF_CA_CERT_PATH, CONF_CLIENT_CERT_PATH, CONF_CLIENT_KEY_PATH):
        if key in merged:
            merged[key] = "<redacted>"

    return {
        "config": merged,
        "runtime": manager.diagnostics(),
    }
