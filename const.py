from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_telemetry"

CONF_COUNTRY: Final = "country"
CONF_HUB_URL: Final = "hub_url"
CONF_ENROLLMENT_TOKEN: Final = "enrollment_token"
CONF_SITE_ID: Final = "site_id"
CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_MQTT_USERNAME: Final = "mqtt_username"
CONF_MQTT_PASSWORD: Final = "mqtt_password"
CONF_ENTITY_IDS: Final = "entity_ids"
CONF_TELEMETRY_INTERVAL_SECONDS: Final = "telemetry_interval_seconds"
CONF_HEARTBEAT_INTERVAL_SECONDS: Final = "heartbeat_interval_seconds"

TRANSPORT_TCP: Final = "tcp"

DEFAULT_TOPIC_PREFIX: Final = "ha_telemetry/v1"
DEFAULT_PORT: Final = 8883
DEFAULT_TELEMETRY_INTERVAL_SECONDS: Final = 30
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final = 60

TELEMETRY_ATTRIBUTE_ALLOWLIST: Final[tuple[str, ...]] = (
    "device_class",
    "friendly_name",
    "icon",
    "state_class",
    "unit_of_measurement",
)
