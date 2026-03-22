from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

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
    DOMAIN,
    SITE_ID_PATTERN,
)
from .models import EntrySettings, normalize_entity_ids, resolve_config_path
from .mqtt_client import async_validate_connection

SITE_ID_RE = re.compile(SITE_ID_PATTERN)


class InvalidSiteIdError(Exception):
    """Raised when the configured site ID is invalid."""


class MissingFileError(Exception):
    """Raised when one or more certificate files cannot be found."""


class EntitySelectionError(Exception):
    """Raised when the entity selection is invalid."""


class CannotConnectError(Exception):
    """Raised when the MQTT broker connection test fails."""


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): selector.TextSelector(),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_SITE_ID, default=defaults.get(CONF_SITE_ID, "")): selector.TextSelector(),
            vol.Required(
                CONF_TOPIC_PREFIX,
                default=defaults.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX),
            ): selector.TextSelector(),
            vol.Required(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
            vol.Required(
                CONF_CLIENT_CERT_PATH,
                default=defaults.get(CONF_CLIENT_CERT_PATH, ""),
            ): selector.TextSelector(),
            vol.Required(
                CONF_CLIENT_KEY_PATH,
                default=defaults.get(CONF_CLIENT_KEY_PATH, ""),
            ): selector.TextSelector(),
            vol.Required(
                CONF_ENTITY_IDS,
                default=defaults.get(CONF_ENTITY_IDS, []),
            ): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
            vol.Optional(
                CONF_COMMAND_ENTITY_IDS,
                default=defaults.get(CONF_COMMAND_ENTITY_IDS, []),
            ): selector.EntitySelector(selector.EntitySelectorConfig(multiple=True)),
            vol.Required(
                CONF_TELEMETRY_INTERVAL_SECONDS,
                default=defaults.get(CONF_TELEMETRY_INTERVAL_SECONDS, DEFAULT_TELEMETRY_INTERVAL_SECONDS),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(
                CONF_HEARTBEAT_INTERVAL_SECONDS,
                default=defaults.get(CONF_HEARTBEAT_INTERVAL_SECONDS, DEFAULT_HEARTBEAT_INTERVAL_SECONDS),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, mode=selector.NumberSelectorMode.BOX)),
        }
    )


async def _validate_input(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user_input)
    normalized[CONF_HOST] = str(user_input[CONF_HOST]).strip()
    normalized[CONF_PORT] = int(user_input.get(CONF_PORT, DEFAULT_PORT))
    normalized[CONF_SITE_ID] = str(user_input[CONF_SITE_ID]).strip()
    normalized[CONF_TOPIC_PREFIX] = str(user_input.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)).strip("/")
    normalized[CONF_ENTITY_IDS] = list(normalize_entity_ids(user_input.get(CONF_ENTITY_IDS, [])))
    normalized[CONF_COMMAND_ENTITY_IDS] = list(normalize_entity_ids(user_input.get(CONF_COMMAND_ENTITY_IDS, [])))

    if not SITE_ID_RE.fullmatch(normalized[CONF_SITE_ID]):
        raise InvalidSiteIdError

    if not normalized[CONF_ENTITY_IDS]:
        raise EntitySelectionError("entity_ids_required")

    if not set(normalized[CONF_COMMAND_ENTITY_IDS]).issubset(set(normalized[CONF_ENTITY_IDS])):
        raise EntitySelectionError("command_entities_not_subset")

    for key in (CONF_CA_CERT_PATH, CONF_CLIENT_CERT_PATH, CONF_CLIENT_KEY_PATH):
        resolved = Path(resolve_config_path(hass, str(user_input[key]).strip()))
        if not resolved.exists():
            raise MissingFileError

    settings = EntrySettings.from_mapping(hass, normalized)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError

    return normalized


class HATelemetryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                cleaned = await _validate_input(self.hass, user_input)
            except InvalidSiteIdError:
                errors[CONF_SITE_ID] = "invalid_site_id"
            except MissingFileError:
                errors["base"] = "missing_file"
            except EntitySelectionError as err:
                errors["base"] = str(err)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(cleaned[CONF_SITE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=cleaned[CONF_SITE_ID], data=cleaned)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return HATelemetryOptionsFlowHandler(config_entry)


class HATelemetryOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        defaults = dict(self.config_entry.data)
        defaults.update(self.config_entry.options)

        if user_input is not None:
            try:
                cleaned = await _validate_input(self.hass, user_input)
            except InvalidSiteIdError:
                errors[CONF_SITE_ID] = "invalid_site_id"
            except MissingFileError:
                errors["base"] = "missing_file"
            except EntitySelectionError as err:
                errors["base"] = str(err)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="", data=cleaned)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )
