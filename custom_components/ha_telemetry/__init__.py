from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .manager import TelemetryManager
from .models import EntrySettings


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    settings = EntrySettings.from_entry(hass, entry)
    manager = TelemetryManager(hass, entry, settings)

    try:
        await manager.async_start()
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to initialize MQTT client for {settings.site_id}") from err

    hass.data[DOMAIN][entry.entry_id] = manager
    entry.runtime_data = manager
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager: TelemetryManager = hass.data[DOMAIN].pop(entry.entry_id)
    await manager.async_stop()
    entry.runtime_data = None
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
