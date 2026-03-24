from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .manager import TelemetryManager
from .models import EntrySettings


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    manager: TelemetryManager = entry.runtime_data
    settings = EntrySettings.from_entry(hass, entry)

    return {
        "config": {
            "hub_url": settings.hub_url,
            "host": settings.host,
            "port": settings.port,
            "site_id": settings.site_id,
            "topic_prefix": settings.topic_prefix,
            "mqtt_password": "<redacted>",
            "entity_ids": list(settings.entity_ids),
            "command_entity_ids": list(settings.command_entity_ids),
            "telemetry_interval_seconds": settings.telemetry_interval_seconds,
            "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
        },
        "runtime": manager.diagnostics(),
    }
