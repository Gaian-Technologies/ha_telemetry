from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CA_CERT_PATH,
    CONF_CLIENT_CERT_PATH,
    CONF_CLIENT_KEY_PATH,
    CONF_COMMAND_ENTITY_IDS,
    CONF_ENTITY_IDS,
    CONF_HEARTBEAT_INTERVAL_SECONDS,
    CONF_SITE_ID,
    CONF_TELEMETRY_INTERVAL_SECONDS,
    CONF_TOPIC_PREFIX,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_TELEMETRY_INTERVAL_SECONDS,
    DEFAULT_TOPIC_PREFIX,
)


def resolve_config_path(hass: HomeAssistant, configured_path: str) -> str:
    path = Path(configured_path)
    if not path.is_absolute():
        path = Path(hass.config.path(configured_path))
    return str(path)


def normalize_entity_ids(entity_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(entity_ids)))


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


@dataclass(slots=True, frozen=True)
class EntrySettings:
    host: str
    port: int
    site_id: str
    topic_prefix: str
    ca_cert_path: str
    client_cert_path: str
    client_key_path: str
    entity_ids: tuple[str, ...]
    command_entity_ids: tuple[str, ...]
    telemetry_interval_seconds: int
    heartbeat_interval_seconds: int

    @classmethod
    def from_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> "EntrySettings":
        merged = dict(entry.data)
        merged.update(entry.options)
        return cls.from_mapping(hass, merged)

    @classmethod
    def from_mapping(cls, hass: HomeAssistant, data: dict[str, Any]) -> "EntrySettings":
        return cls(
            host=str(data[CONF_HOST]).strip(),
            port=int(data.get(CONF_PORT, DEFAULT_PORT)),
            site_id=str(data[CONF_SITE_ID]).strip(),
            topic_prefix=str(data.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)).strip("/"),
            ca_cert_path=resolve_config_path(hass, str(data[CONF_CA_CERT_PATH]).strip()),
            client_cert_path=resolve_config_path(hass, str(data[CONF_CLIENT_CERT_PATH]).strip()),
            client_key_path=resolve_config_path(hass, str(data[CONF_CLIENT_KEY_PATH]).strip()),
            entity_ids=normalize_entity_ids(data.get(CONF_ENTITY_IDS, [])),
            command_entity_ids=normalize_entity_ids(data.get(CONF_COMMAND_ENTITY_IDS, [])),
            telemetry_interval_seconds=_positive_int(
                data.get(CONF_TELEMETRY_INTERVAL_SECONDS),
                DEFAULT_TELEMETRY_INTERVAL_SECONDS,
            ),
            heartbeat_interval_seconds=_positive_int(
                data.get(CONF_HEARTBEAT_INTERVAL_SECONDS),
                DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
            ),
        )


@dataclass(slots=True)
class DesiredConfig:
    enabled: bool
    telemetry_interval_seconds: int
    heartbeat_interval_seconds: int
    config_version: int

    @classmethod
    def from_settings(cls, settings: EntrySettings) -> "DesiredConfig":
        return cls(
            enabled=True,
            telemetry_interval_seconds=settings.telemetry_interval_seconds,
            heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
            config_version=0,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any], settings: EntrySettings) -> "DesiredConfig":
        return cls(
            enabled=bool(payload.get("enabled", True)),
            telemetry_interval_seconds=_positive_int(
                payload.get("telemetry_interval_seconds"),
                settings.telemetry_interval_seconds,
            ),
            heartbeat_interval_seconds=_positive_int(
                payload.get("heartbeat_interval_seconds"),
                settings.heartbeat_interval_seconds,
            ),
            config_version=int(payload.get("config_version", 0)),
        )
