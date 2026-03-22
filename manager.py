from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.event import async_track_time_interval

from .const import ALLOWED_COMMAND_SERVICES, TELEMETRY_ATTRIBUTE_ALLOWLIST
from .models import DesiredConfig, EntrySettings
from .mqtt_client import TelemetryMqttClient
from .protocol import (
    COMMAND_REQUEST_SCHEMA,
    DESIRED_SCHEMA,
    build_command_ack_payload,
    build_heartbeat_payload,
    build_reported_payload,
    build_telemetry_payload,
    command_ack_topic,
    heartbeat_topic,
    reported_topic,
    telemetry_topic,
)

LOGGER = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class TelemetryManager:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, settings: EntrySettings) -> None:
        self.hass = hass
        self.entry = entry
        self.settings = settings
        self._desired = DesiredConfig.from_settings(settings)
        self._sequence = 0
        self._connected = False
        self._telemetry_unsub: Callable[[], None] | None = None
        self._heartbeat_unsub: Callable[[], None] | None = None
        self._mqtt_client = TelemetryMqttClient(
            hass=hass,
            settings=settings,
            on_connected=self._async_handle_connection_state,
            on_desired=self._async_handle_desired,
            on_command=self._async_handle_command,
        )

    async def async_start(self) -> None:
        self._reschedule_heartbeat()
        self._reschedule_telemetry()
        await self._mqtt_client.async_start()

    async def async_stop(self) -> None:
        self._cancel_schedules()
        await self._mqtt_client.async_stop()

    async def _async_handle_connection_state(self, connected: bool) -> None:
        self._connected = connected
        await self._async_publish_reported_state()
        if connected:
            await self._async_publish_heartbeat()

    async def _async_handle_desired(self, payload: dict[str, Any]) -> None:
        if payload.get("schema") != DESIRED_SCHEMA:
            LOGGER.warning("Ignoring desired payload with unexpected schema: %s", payload.get("schema"))
            return

        if payload.get("site_id") != self.settings.site_id:
            LOGGER.warning("Ignoring desired payload for another site: %s", payload)
            return

        self._desired = DesiredConfig.from_payload(payload, self.settings)
        self._reschedule_heartbeat()
        self._reschedule_telemetry()
        await self._async_publish_reported_state()
        if self._desired.enabled:
            await self._async_publish_telemetry()

    async def _async_handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("schema") != COMMAND_REQUEST_SCHEMA:
            LOGGER.warning("Ignoring command payload with unexpected schema: %s", payload.get("schema"))
            return

        if payload.get("site_id") != self.settings.site_id:
            LOGGER.warning("Ignoring command targeted at another site: %s", payload)
            return

        command_id = str(payload.get("command_id", "")).strip()
        entity_id = str(payload.get("entity_id", "")).strip()
        service = str(payload.get("service", "")).strip()

        if not command_id or not entity_id or not service:
            LOGGER.warning("Ignoring malformed command payload: %s", payload)
            return

        if entity_id not in self.settings.entity_ids or entity_id not in self.settings.command_entity_ids:
            await self._async_publish_command_ack(
                command_id=command_id,
                entity_id=entity_id,
                service=service,
                status="rejected",
                reason="entity_not_command_enabled",
            )
            return

        if service not in ALLOWED_COMMAND_SERVICES:
            await self._async_publish_command_ack(
                command_id=command_id,
                entity_id=entity_id,
                service=service,
                status="rejected",
                reason="service_not_allowed",
            )
            return

        service_data = payload.get("service_data") or {}
        if not isinstance(service_data, dict):
            await self._async_publish_command_ack(
                command_id=command_id,
                entity_id=entity_id,
                service=service,
                status="rejected",
                reason="service_data_must_be_an_object",
            )
            return

        domain, service_name = service.split(".", 1)
        command_data = dict(service_data)
        command_data["entity_id"] = entity_id

        try:
            await self.hass.services.async_call(
                domain,
                service_name,
                command_data,
                blocking=True,
            )
        except Exception as err:
            LOGGER.exception("Remote command execution failed for %s", entity_id)
            await self._async_publish_command_ack(
                command_id=command_id,
                entity_id=entity_id,
                service=service,
                status="failed",
                reason=str(err),
            )
            return

        await self._async_publish_command_ack(
            command_id=command_id,
            entity_id=entity_id,
            service=service,
            status="completed",
        )

    async def _async_telemetry_tick(self, _now) -> None:
        await self._async_publish_telemetry()

    async def _async_heartbeat_tick(self, _now) -> None:
        await self._async_publish_heartbeat()

    async def _async_publish_telemetry(self) -> None:
        if not self._desired.enabled:
            return

        self._sequence += 1
        payload = build_telemetry_payload(
            self.settings,
            self._desired,
            self._sequence,
            self._build_telemetry_items(),
        )
        await self._async_publish(telemetry_topic(self.settings.topic_prefix, self.settings.site_id), payload)

    async def _async_publish_reported_state(self) -> None:
        payload = build_reported_payload(self.settings, self._desired, self._connected)
        await self._async_publish(reported_topic(self.settings.topic_prefix, self.settings.site_id), payload)

    async def _async_publish_heartbeat(self) -> None:
        payload = build_heartbeat_payload(
            self.settings,
            self._desired,
            self._connected,
            self._sequence,
        )
        await self._async_publish(heartbeat_topic(self.settings.topic_prefix, self.settings.site_id), payload)

    async def _async_publish_command_ack(
        self,
        command_id: str,
        entity_id: str,
        service: str,
        status: str,
        reason: str | None = None,
    ) -> None:
        payload = build_command_ack_payload(
            site_id=self.settings.site_id,
            command_id=command_id,
            entity_id=entity_id,
            service=service,
            status=status,
            reason=reason,
        )
        await self._async_publish(command_ack_topic(self.settings.topic_prefix, self.settings.site_id), payload)

    async def _async_publish(self, topic: str, payload: dict[str, Any], *, retain: bool = False) -> None:
        try:
            await self._mqtt_client.async_publish_json(topic, payload, retain=retain)
        except RuntimeError:
            LOGGER.debug("Skipping publish while MQTT is disconnected for topic %s", topic)

    def _reschedule_telemetry(self) -> None:
        if self._telemetry_unsub is not None:
            self._telemetry_unsub()
            self._telemetry_unsub = None

        if not self._desired.enabled:
            return

        self._telemetry_unsub = async_track_time_interval(
            self.hass,
            self._async_telemetry_tick,
            timedelta(seconds=self._desired.telemetry_interval_seconds),
        )

    def _reschedule_heartbeat(self) -> None:
        if self._heartbeat_unsub is not None:
            self._heartbeat_unsub()
            self._heartbeat_unsub = None

        self._heartbeat_unsub = async_track_time_interval(
            self.hass,
            self._async_heartbeat_tick,
            timedelta(seconds=self._desired.heartbeat_interval_seconds),
        )

    def _cancel_schedules(self) -> None:
        if self._telemetry_unsub is not None:
            self._telemetry_unsub()
            self._telemetry_unsub = None
        if self._heartbeat_unsub is not None:
            self._heartbeat_unsub()
            self._heartbeat_unsub = None

    def _build_telemetry_items(self) -> list[dict[str, Any]]:
        return [
            self._serialize_state(entity_id, self.hass.states.get(entity_id))
            for entity_id in self.settings.entity_ids
        ]

    def _serialize_state(self, entity_id: str, state: State | None) -> dict[str, Any]:
        if state is None:
            return {
                "entity_id": entity_id,
                "state": STATE_UNKNOWN,
                "available": False,
                "attributes": {},
                "last_changed": None,
                "last_updated": None,
            }

        return {
            "entity_id": entity_id,
            "state": state.state,
            "available": state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE),
            "attributes": {
                key: _json_safe(state.attributes[key])
                for key in TELEMETRY_ATTRIBUTE_ALLOWLIST
                if key in state.attributes
            },
            "last_changed": state.last_changed.isoformat(),
            "last_updated": state.last_updated.isoformat(),
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "site_id": self.settings.site_id,
            "topic_prefix": self.settings.topic_prefix,
            "selected_entity_count": len(self.settings.entity_ids),
            "command_entity_count": len(self.settings.command_entity_ids),
            "desired_config": {
                "enabled": self._desired.enabled,
                "telemetry_interval_seconds": self._desired.telemetry_interval_seconds,
                "heartbeat_interval_seconds": self._desired.heartbeat_interval_seconds,
                "config_version": self._desired.config_version,
            },
        }
