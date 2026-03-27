"""Typed runtime models for the managed Home Assistant integration workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .countries import normalize_country
from .const import (
    CONF_COUNTRY,
    CONF_ENTITY_IDS,
    CONF_HEARTBEAT_INTERVAL_SECONDS,
    CONF_HUB_URL,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_SITE_ID,
    CONF_TELEMETRY_INTERVAL_SECONDS,
    CONF_TOPIC_PREFIX,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_TELEMETRY_INTERVAL_SECONDS,
    DEFAULT_TOPIC_PREFIX,
    TRANSPORT_TCP,
)


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
    """Resolved integration settings for one enrolled Home Assistant site."""

    country: str
    hub_url: str
    host: str
    port: int
    site_id: str
    topic_prefix: str
    mqtt_username: str
    mqtt_password: str
    entity_ids: tuple[str, ...]
    telemetry_interval_seconds: int
    heartbeat_interval_seconds: int

    @property
    def transport(self) -> str:
        return TRANSPORT_TCP

    @classmethod
    def from_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> "EntrySettings":
        merged = dict(entry.data)
        merged.update(entry.options)
        return cls.from_mapping(hass, merged)

    @classmethod
    def from_mapping(cls, hass: HomeAssistant, data: dict[str, Any]) -> "EntrySettings":
        del hass
        raw_country = str(data.get(CONF_COUNTRY, "") or "").strip()
        return cls(
            country=normalize_country(raw_country) if raw_country else "",
            hub_url=str(data.get(CONF_HUB_URL, "")).strip().rstrip("/"),
            host=str(data[CONF_HOST]).strip(),
            port=int(data.get(CONF_PORT, DEFAULT_PORT)),
            site_id=str(data[CONF_SITE_ID]).strip(),
            topic_prefix=str(data.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)).strip("/"),
            mqtt_username=str(data[CONF_MQTT_USERNAME]).strip(),
            mqtt_password=str(data[CONF_MQTT_PASSWORD]),
            entity_ids=normalize_entity_ids(data.get(CONF_ENTITY_IDS, [])),
            telemetry_interval_seconds=_positive_int(
                data.get(CONF_TELEMETRY_INTERVAL_SECONDS),
                DEFAULT_TELEMETRY_INTERVAL_SECONDS,
            ),
            heartbeat_interval_seconds=_positive_int(
                data.get(CONF_HEARTBEAT_INTERVAL_SECONDS),
                DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
            ),
        )


@dataclass(slots=True, frozen=True)
class ManagedEnrollmentResult:
    """Broker credentials and hub metadata returned by enrollment."""

    site_id: str
    mqtt_host: str
    mqtt_port: int
    mqtt_topic_prefix: str
    mqtt_username: str
    mqtt_password: str
    hub_url: str


@dataclass(slots=True)
class DesiredConfig:
    """Hub-controlled behavior that the integration applies locally."""

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
