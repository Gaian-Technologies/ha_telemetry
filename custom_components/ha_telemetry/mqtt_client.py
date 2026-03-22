from __future__ import annotations

import asyncio
import json
import logging
import ssl
import threading
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant
from paho.mqtt import client as mqtt

from .models import EntrySettings
from .protocol import command_request_topic, desired_topic

LOGGER = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]
ConnectionHandler = Callable[[bool], Awaitable[None]]


def _create_paho_client(settings: EntrySettings, client_id: str) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
    )
    client.enable_logger(LOGGER)
    client.tls_set(
        ca_certs=settings.ca_cert_path,
        certfile=settings.client_cert_path,
        keyfile=settings.client_key_path,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    client.tls_insecure_set(False)
    return client


async def async_validate_connection(hass: HomeAssistant, settings: EntrySettings) -> bool:
    return await hass.async_add_executor_job(_validate_connection_sync, settings)


def _validate_connection_sync(settings: EntrySettings) -> bool:
    connected = threading.Event()
    result: dict[str, int | None] = {"reason_code": None}
    client = _create_paho_client(settings, f"{settings.site_id}-validate-{uuid.uuid4().hex[:8]}")

    def on_connect(
        validation_client: mqtt.Client,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        result["reason_code"] = int(reason_code)
        connected.set()
        validation_client.disconnect()

    client.on_connect = on_connect

    try:
        client.connect(settings.host, settings.port, keepalive=20)
        client.loop_start()
        if not connected.wait(timeout=10):
            return False
        return result["reason_code"] == 0
    except Exception:
        LOGGER.exception("Failed to validate MQTT connection for site %s", settings.site_id)
        return False
    finally:
        try:
            client.loop_stop()
        except Exception:
            LOGGER.debug("MQTT validation loop stop raised during cleanup", exc_info=True)


class TelemetryMqttClient:
    def __init__(
        self,
        hass: HomeAssistant,
        settings: EntrySettings,
        on_connected: ConnectionHandler,
        on_desired: MessageHandler,
        on_command: MessageHandler,
    ) -> None:
        self._hass = hass
        self._settings = settings
        self._on_connected = on_connected
        self._on_desired = on_desired
        self._on_command = on_command
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: mqtt.Client | None = None
        self._connected = asyncio.Event()

    async def async_start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._client = await asyncio.to_thread(_create_paho_client, self._settings, self._settings.site_id)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        await asyncio.to_thread(self._connect_sync)

    async def async_stop(self) -> None:
        if self._client is None:
            return
        await asyncio.to_thread(self._disconnect_sync)

    async def async_publish_json(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        retain: bool = False,
        qos: int = 1,
    ) -> None:
        if self._client is None:
            raise RuntimeError("MQTT client has not been started")
        if not self._connected.is_set():
            raise RuntimeError("MQTT client is not connected")

        raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        await asyncio.to_thread(self._publish_sync, topic, raw_payload, qos, retain)

    def _subscribe_sync(self) -> None:
        assert self._client is not None
        subscriptions = [
            (desired_topic(self._settings.topic_prefix, self._settings.site_id), 1),
            (command_request_topic(self._settings.topic_prefix, self._settings.site_id), 1),
        ]
        for topic, qos in subscriptions:
            result, _mid = self._client.subscribe(topic, qos=qos)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT subscribe failed for {topic} with rc={result}")

    def _connect_sync(self) -> None:
        assert self._client is not None
        self._client.connect(self._settings.host, self._settings.port, keepalive=60)
        self._client.loop_start()

    def _disconnect_sync(self) -> None:
        assert self._client is not None
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()

    def _publish_sync(self, topic: str, raw_payload: str, qos: int, retain: bool) -> None:
        assert self._client is not None
        message = self._client.publish(topic, payload=raw_payload, qos=qos, retain=retain)
        message.wait_for_publish()
        if message.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed with rc={message.rc}")

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if int(reason_code) != 0:
            LOGGER.error("MQTT connection failed with reason code %s", reason_code)
            return

        self._connected.set()
        try:
            self._subscribe_sync()
        except Exception:
            LOGGER.exception("Failed to subscribe to MQTT topics for site %s", self._settings.site_id)
            return

        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._on_connected(True), self._loop)

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _disconnect_flags: Any,
        _reason_code: Any,
        _properties: Any,
    ) -> None:
        self._connected.clear()
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._on_connected(False), self._loop)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        if self._loop is None:
            return

        asyncio.run_coroutine_threadsafe(
            self._dispatch_message(message.topic, message.payload),
            self._loop,
        )

    async def _dispatch_message(self, topic: str, payload: bytes) -> None:
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except Exception:
            LOGGER.exception("Failed to decode MQTT message for site %s", self._settings.site_id)
            return

        if topic == desired_topic(self._settings.topic_prefix, self._settings.site_id):
            await self._on_desired(decoded)
            return

        if topic == command_request_topic(self._settings.topic_prefix, self._settings.site_id):
            await self._on_command(decoded)
            return

        LOGGER.warning("Ignoring MQTT message on unexpected topic %s", topic)
