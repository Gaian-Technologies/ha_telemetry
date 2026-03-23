from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_telemetry"

CONF_SETUP_MODE: Final = "setup_mode"
CONF_HUB_URL: Final = "hub_url"
CONF_ENROLLMENT_TOKEN: Final = "enrollment_token"
CONF_SITE_ID: Final = "site_id"
CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_MQTT_USERNAME: Final = "mqtt_username"
CONF_MQTT_PASSWORD: Final = "mqtt_password"
CONF_CA_CERT_PATH: Final = "ca_cert_path"
CONF_TRANSPORT: Final = "transport"
CONF_ENTITY_IDS: Final = "entity_ids"
CONF_COMMAND_ENTITY_IDS: Final = "command_entity_ids"
CONF_TELEMETRY_INTERVAL_SECONDS: Final = "telemetry_interval_seconds"
CONF_HEARTBEAT_INTERVAL_SECONDS: Final = "heartbeat_interval_seconds"

SETUP_MODE_MANAGED: Final = "managed"
SETUP_MODE_ADVANCED: Final = "advanced"
TRANSPORT_TCP: Final = "tcp"
TRANSPORT_WEBSOCKETS: Final = "websockets"

DEFAULT_TOPIC_PREFIX: Final = "ha_telemetry/v1"
DEFAULT_PORT: Final = 8883
DEFAULT_TRANSPORT: Final = TRANSPORT_TCP
DEFAULT_TELEMETRY_INTERVAL_SECONDS: Final = 30
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final = 60

SITE_ID_PATTERN: Final = r"^[a-z0-9][a-z0-9_-]{1,63}$"

TELEMETRY_ATTRIBUTE_ALLOWLIST: Final[tuple[str, ...]] = (
    "device_class",
    "friendly_name",
    "icon",
    "state_class",
    "unit_of_measurement",
)

ALLOWED_COMMAND_SERVICES: Final[frozenset[str]] = frozenset(
    {
        "button.press",
        "cover.close_cover",
        "cover.open_cover",
        "cover.stop_cover",
        "homeassistant.toggle",
        "homeassistant.turn_off",
        "homeassistant.turn_on",
        "input_boolean.toggle",
        "input_boolean.turn_off",
        "input_boolean.turn_on",
        "input_number.set_value",
        "input_select.select_option",
        "number.set_value",
        "scene.turn_on",
        "select.select_option",
    }
)
