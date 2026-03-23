from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from .models import DesiredConfig, EntrySettings

TELEMETRY_SCHEMA: Final = "telemetry_batch.v1"
DESIRED_SCHEMA: Final = "desired_config.v1"
REPORTED_SCHEMA: Final = "reported_state.v1"
HEARTBEAT_SCHEMA: Final = "heartbeat.v1"
COMMAND_REQUEST_SCHEMA: Final = "command_request.v1"
COMMAND_ACK_SCHEMA: Final = "command_ack.v1"


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def isoformat_utc(value: datetime | None = None) -> str:
    timestamp = value or utcnow()
    return timestamp.astimezone(UTC).isoformat()


def site_root(topic_prefix: str, site_id: str) -> str:
    return f"{topic_prefix.strip('/')}/sites/{site_id}"


def telemetry_topic(topic_prefix: str, site_id: str) -> str:
    return f"{site_root(topic_prefix, site_id)}/telemetry"


def desired_topic(topic_prefix: str, site_id: str) -> str:
    return f"{site_root(topic_prefix, site_id)}/desired"


def reported_topic(topic_prefix: str, site_id: str) -> str:
    return f"{site_root(topic_prefix, site_id)}/reported"


def heartbeat_topic(topic_prefix: str, site_id: str) -> str:
    return f"{site_root(topic_prefix, site_id)}/heartbeat"


def command_request_topic(topic_prefix: str, site_id: str) -> str:
    return f"{site_root(topic_prefix, site_id)}/commands/request"


def command_ack_topic(topic_prefix: str, site_id: str) -> str:
    return f"{site_root(topic_prefix, site_id)}/commands/ack"


def build_reported_payload(settings: EntrySettings, desired: DesiredConfig, connected: bool) -> dict[str, Any]:
    commands_enabled = desired.commands_enabled and bool(settings.command_entity_ids)
    return {
        "schema": REPORTED_SCHEMA,
        "site_id": settings.site_id,
        "connected": connected,
        "selected_entities": list(settings.entity_ids),
        "command_entities": list(settings.command_entity_ids),
        "telemetry_enabled": desired.enabled,
        "commands_enabled": commands_enabled,
        "telemetry_interval_seconds": desired.telemetry_interval_seconds,
        "heartbeat_interval_seconds": desired.heartbeat_interval_seconds,
        "applied_config_version": desired.config_version,
        "published_at": isoformat_utc(),
    }


def build_heartbeat_payload(
    settings: EntrySettings,
    desired: DesiredConfig,
    connected: bool,
    sequence: int,
) -> dict[str, Any]:
    return {
        "schema": HEARTBEAT_SCHEMA,
        "site_id": settings.site_id,
        "connected": connected,
        "telemetry_enabled": desired.enabled,
        "applied_config_version": desired.config_version,
        "sequence": sequence,
        "sent_at": isoformat_utc(),
    }


def build_telemetry_payload(
    settings: EntrySettings,
    desired: DesiredConfig,
    sequence: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": TELEMETRY_SCHEMA,
        "site_id": settings.site_id,
        "message_id": f"{settings.site_id}-{sequence}",
        "sent_at": isoformat_utc(),
        "sequence": sequence,
        "config_version": desired.config_version,
        "interval_seconds": desired.telemetry_interval_seconds,
        "items": items,
    }


def build_command_ack_payload(
    site_id: str,
    command_id: str,
    entity_id: str,
    service: str,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": COMMAND_ACK_SCHEMA,
        "site_id": site_id,
        "command_id": command_id,
        "entity_id": entity_id,
        "service": service,
        "status": status,
        "sent_at": isoformat_utc(),
    }
    if reason:
        payload["reason"] = reason
    return payload
