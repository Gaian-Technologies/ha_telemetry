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
    CONF_COMMAND_ENTITY_IDS,
    CONF_ENROLLMENT_TOKEN,
    CONF_ENTITY_IDS,
    CONF_HEARTBEAT_INTERVAL_SECONDS,
    CONF_HUB_URL,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_SETUP_MODE,
    CONF_SITE_ID,
    CONF_TELEMETRY_INTERVAL_SECONDS,
    CONF_TOPIC_PREFIX,
    CONF_TRANSPORT,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_TELEMETRY_INTERVAL_SECONDS,
    DEFAULT_TOPIC_PREFIX,
    DEFAULT_TRANSPORT,
    DOMAIN,
    SETUP_MODE_ADVANCED,
    SETUP_MODE_MANAGED,
    SITE_ID_PATTERN,
    TRANSPORT_TCP,
    TRANSPORT_WEBSOCKETS,
)
from .hub_client import EnrollmentError, async_enroll_managed_site
from .models import EntrySettings, normalize_entity_ids, resolve_config_path
from .mqtt_client import async_validate_connection

SITE_ID_RE = re.compile(SITE_ID_PATTERN)
TRANSPORT_OPTIONS = [TRANSPORT_TCP, TRANSPORT_WEBSOCKETS]


class InvalidSiteIdError(Exception):
    """Raised when the configured site ID is invalid."""


class MissingFileError(Exception):
    """Raised when a custom CA file cannot be found."""


class EntitySelectionError(Exception):
    """Raised when the entity selection is invalid."""


class CannotConnectError(Exception):
    """Raised when the MQTT broker connection test fails."""


class HATelemetryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, _user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="user", menu_options=[SETUP_MODE_MANAGED, SETUP_MODE_ADVANCED])

    async def async_step_managed(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                cleaned = await _validate_managed_setup(self.hass, user_input)
            except MissingFileError:
                errors["base"] = "missing_file"
            except EntitySelectionError as err:
                errors["base"] = str(err)
            except MissingFileError:
                errors["base"] = "missing_file"
            except MissingFileError:
                errors["base"] = "missing_file"
            except EnrollmentError as err:
                errors["base"] = err.translation_key
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(cleaned[CONF_SITE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=cleaned[CONF_SITE_ID], data=cleaned)

        return self.async_show_form(
            step_id=SETUP_MODE_MANAGED,
            data_schema=_build_managed_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_advanced(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                cleaned = await _validate_advanced_setup(self.hass, user_input)
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
            step_id=SETUP_MODE_ADVANCED,
            data_schema=_build_advanced_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]):
        entry = self._get_reauth_entry()
        mode = str(entry.data.get(CONF_SETUP_MODE, SETUP_MODE_ADVANCED))
        if mode == SETUP_MODE_MANAGED:
            return await self.async_step_reauth_managed()
        return await self.async_step_reauth_advanced()

    async def async_step_reauth_managed(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reauth_entry()
        defaults = {
            CONF_HUB_URL: entry.data.get(CONF_HUB_URL, ""),
            CONF_CA_CERT_PATH: entry.data.get(CONF_CA_CERT_PATH, ""),
        }
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updates = await _validate_managed_reauth(self.hass, entry, user_input)
            except EnrollmentError as err:
                errors["base"] = err.translation_key
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=updates,
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_managed",
            data_schema=_build_managed_reauth_schema(user_input or defaults),
            errors=errors,
        )

    async def async_step_reauth_advanced(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reauth_entry()
        defaults = _entry_defaults(entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updates = await _validate_advanced_reauth(self.hass, entry, user_input)
            except MissingFileError:
                errors["base"] = "missing_file"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=updates,
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_advanced",
            data_schema=_build_advanced_reauth_schema(defaults),
            errors=errors,
        )

    async def async_step_reconfigure(self, _user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        mode = str(entry.data.get(CONF_SETUP_MODE, SETUP_MODE_ADVANCED))
        if mode == SETUP_MODE_MANAGED:
            return await self.async_step_reconfigure_managed()
        return await self.async_step_reconfigure_advanced()

    async def async_step_reconfigure_managed(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        defaults = _entry_defaults(entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updates = _validate_managed_reconfigure(self.hass, user_input)
            except EntitySelectionError as err:
                errors["base"] = str(err)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=updates,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure_managed",
            data_schema=_build_managed_reconfigure_schema(defaults),
            errors=errors,
        )

    async def async_step_reconfigure_advanced(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        defaults = _entry_defaults(entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updates = await _validate_advanced_reconfigure(self.hass, entry, user_input)
            except MissingFileError:
                errors["base"] = "missing_file"
            except EntitySelectionError as err:
                errors["base"] = str(err)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=updates,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure_advanced",
            data_schema=_build_advanced_reconfigure_schema(defaults),
            errors=errors,
        )


def _entry_defaults(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    merged = dict(entry.data)
    merged.update(entry.options)
    return merged


def _build_shared_entity_fields(defaults: dict[str, Any]) -> dict:
    return {
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


def _build_managed_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HUB_URL, default=defaults.get(CONF_HUB_URL, "")): selector.TextSelector(),
            vol.Required(CONF_ENROLLMENT_TOKEN, default=defaults.get(CONF_ENROLLMENT_TOKEN, "")): selector.TextSelector(),
            vol.Optional(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
            **_build_shared_entity_fields(defaults),
        }
    )


def _build_managed_reauth_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HUB_URL, default=defaults.get(CONF_HUB_URL, "")): selector.TextSelector(),
            vol.Required(CONF_ENROLLMENT_TOKEN, default=""): selector.TextSelector(),
            vol.Optional(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
        }
    )


def _build_managed_reconfigure_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HUB_URL, default=defaults.get(CONF_HUB_URL, "")): selector.TextSelector(),
            vol.Optional(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
            **_build_shared_entity_fields(defaults),
        }
    )


def _build_advanced_schema(defaults: dict[str, Any]) -> vol.Schema:
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
            vol.Required(
                CONF_MQTT_USERNAME,
                default=defaults.get(CONF_MQTT_USERNAME, defaults.get(CONF_SITE_ID, "")),
            ): selector.TextSelector(),
            vol.Required(CONF_MQTT_PASSWORD, default=defaults.get(CONF_MQTT_PASSWORD, "")): selector.TextSelector(),
            vol.Optional(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
            vol.Required(
                CONF_TRANSPORT,
                default=defaults.get(CONF_TRANSPORT, DEFAULT_TRANSPORT),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TRANSPORT_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            **_build_shared_entity_fields(defaults),
        }
    )


def _build_advanced_reauth_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): selector.TextSelector(),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_MQTT_USERNAME, default=defaults.get(CONF_MQTT_USERNAME, "")): selector.TextSelector(),
            vol.Required(CONF_MQTT_PASSWORD, default=defaults.get(CONF_MQTT_PASSWORD, "")): selector.TextSelector(),
            vol.Optional(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
            vol.Required(
                CONF_TRANSPORT,
                default=defaults.get(CONF_TRANSPORT, DEFAULT_TRANSPORT),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TRANSPORT_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _build_advanced_reconfigure_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): selector.TextSelector(),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_TOPIC_PREFIX,
                default=defaults.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX),
            ): selector.TextSelector(),
            vol.Required(CONF_MQTT_USERNAME, default=defaults.get(CONF_MQTT_USERNAME, "")): selector.TextSelector(),
            vol.Required(CONF_MQTT_PASSWORD, default=defaults.get(CONF_MQTT_PASSWORD, "")): selector.TextSelector(),
            vol.Optional(CONF_CA_CERT_PATH, default=defaults.get(CONF_CA_CERT_PATH, "")): selector.TextSelector(),
            vol.Required(
                CONF_TRANSPORT,
                default=defaults.get(CONF_TRANSPORT, DEFAULT_TRANSPORT),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TRANSPORT_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            **_build_shared_entity_fields(defaults),
        }
    )


def _validate_entity_selection(user_input: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    entity_ids = normalize_entity_ids(user_input.get(CONF_ENTITY_IDS, []))
    command_entity_ids = normalize_entity_ids(user_input.get(CONF_COMMAND_ENTITY_IDS, []))
    if not entity_ids:
        raise EntitySelectionError("entity_ids_required")
    if not set(command_entity_ids).issubset(set(entity_ids)):
        raise EntitySelectionError("command_entities_not_subset")
    return entity_ids, command_entity_ids


def _normalize_shared(user_input: dict[str, Any]) -> dict[str, Any]:
    entity_ids, command_entity_ids = _validate_entity_selection(user_input)
    return {
        CONF_ENTITY_IDS: list(entity_ids),
        CONF_COMMAND_ENTITY_IDS: list(command_entity_ids),
        CONF_TELEMETRY_INTERVAL_SECONDS: int(user_input.get(CONF_TELEMETRY_INTERVAL_SECONDS, DEFAULT_TELEMETRY_INTERVAL_SECONDS)),
        CONF_HEARTBEAT_INTERVAL_SECONDS: int(user_input.get(CONF_HEARTBEAT_INTERVAL_SECONDS, DEFAULT_HEARTBEAT_INTERVAL_SECONDS)),
    }


def _validate_optional_ca_path(hass, configured_path: str | None) -> str:
    cleaned = str(configured_path or "").strip()
    if not cleaned:
        return ""
    resolved = Path(resolve_config_path(hass, cleaned))
    if not resolved.exists():
        raise MissingFileError
    return cleaned


async def _validate_managed_setup(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_shared(user_input)
    hub_url = str(user_input[CONF_HUB_URL]).strip().rstrip("/")
    enrollment_token = str(user_input[CONF_ENROLLMENT_TOKEN]).strip()

    enrollment = await async_enroll_managed_site(
        hass,
        hub_url=hub_url,
        enrollment_token=enrollment_token,
    )

    normalized.update(
        {
            CONF_SETUP_MODE: SETUP_MODE_MANAGED,
            CONF_HUB_URL: enrollment.hub_url,
            CONF_HOST: enrollment.mqtt_host,
            CONF_PORT: enrollment.mqtt_port,
            CONF_SITE_ID: enrollment.site_id,
            CONF_TOPIC_PREFIX: enrollment.mqtt_topic_prefix,
            CONF_MQTT_USERNAME: enrollment.mqtt_username,
            CONF_MQTT_PASSWORD: enrollment.mqtt_password,
            CONF_TRANSPORT: enrollment.mqtt_transport,
            CONF_CA_CERT_PATH: _validate_optional_ca_path(hass, user_input.get(CONF_CA_CERT_PATH)),
        }
    )

    settings = EntrySettings.from_mapping(hass, normalized)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError

    return normalized


async def _validate_advanced_setup(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_shared(user_input)
    site_id = str(user_input[CONF_SITE_ID]).strip()
    if not SITE_ID_RE.fullmatch(site_id):
        raise InvalidSiteIdError

    normalized.update(
        {
            CONF_SETUP_MODE: SETUP_MODE_ADVANCED,
            CONF_HUB_URL: "",
            CONF_HOST: str(user_input[CONF_HOST]).strip(),
            CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
            CONF_SITE_ID: site_id,
            CONF_TOPIC_PREFIX: str(user_input.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)).strip("/"),
            CONF_MQTT_USERNAME: str(user_input[CONF_MQTT_USERNAME]).strip(),
            CONF_MQTT_PASSWORD: str(user_input[CONF_MQTT_PASSWORD]),
            CONF_TRANSPORT: str(user_input.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)).strip(),
            CONF_CA_CERT_PATH: _validate_optional_ca_path(hass, user_input.get(CONF_CA_CERT_PATH)),
        }
    )

    settings = EntrySettings.from_mapping(hass, normalized)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError

    return normalized


async def _validate_managed_reauth(hass, entry: config_entries.ConfigEntry, user_input: dict[str, Any]) -> dict[str, Any]:
    hub_url = str(user_input[CONF_HUB_URL]).strip().rstrip("/")
    enrollment_token = str(user_input[CONF_ENROLLMENT_TOKEN]).strip()
    site_id = str(entry.data[CONF_SITE_ID]).strip()

    enrollment = await async_enroll_managed_site(
        hass,
        hub_url=hub_url,
        enrollment_token=enrollment_token,
        site_id=site_id,
    )

    updated = dict(entry.data)
    updated.update(
        {
            CONF_HUB_URL: enrollment.hub_url,
            CONF_HOST: enrollment.mqtt_host,
            CONF_PORT: enrollment.mqtt_port,
            CONF_TOPIC_PREFIX: enrollment.mqtt_topic_prefix,
            CONF_MQTT_USERNAME: enrollment.mqtt_username,
            CONF_MQTT_PASSWORD: enrollment.mqtt_password,
            CONF_TRANSPORT: enrollment.mqtt_transport,
            CONF_CA_CERT_PATH: _validate_optional_ca_path(hass, user_input.get(CONF_CA_CERT_PATH)),
        }
    )
    settings = EntrySettings.from_mapping(hass, updated)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError
    return updated


async def _validate_advanced_reauth(hass, entry: config_entries.ConfigEntry, user_input: dict[str, Any]) -> dict[str, Any]:
    updated = dict(entry.data)
    updated.update(
        {
            CONF_HOST: str(user_input[CONF_HOST]).strip(),
            CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
            CONF_MQTT_USERNAME: str(user_input[CONF_MQTT_USERNAME]).strip(),
            CONF_MQTT_PASSWORD: str(user_input[CONF_MQTT_PASSWORD]),
            CONF_CA_CERT_PATH: _validate_optional_ca_path(hass, user_input.get(CONF_CA_CERT_PATH)),
            CONF_TRANSPORT: str(user_input.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)).strip(),
        }
    )
    settings = EntrySettings.from_mapping(hass, updated)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError
    return updated


def _validate_managed_reconfigure(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_shared(user_input)
    normalized[CONF_HUB_URL] = str(user_input[CONF_HUB_URL]).strip().rstrip("/")
    normalized[CONF_CA_CERT_PATH] = _validate_optional_ca_path(hass, user_input.get(CONF_CA_CERT_PATH))
    return normalized


async def _validate_advanced_reconfigure(hass, entry: config_entries.ConfigEntry, user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_shared(user_input)
    updated = dict(entry.data)
    updated.update(normalized)
    updated.update(
        {
            CONF_HOST: str(user_input[CONF_HOST]).strip(),
            CONF_PORT: int(user_input.get(CONF_PORT, DEFAULT_PORT)),
            CONF_TOPIC_PREFIX: str(user_input.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)).strip("/"),
            CONF_MQTT_USERNAME: str(user_input[CONF_MQTT_USERNAME]).strip(),
            CONF_MQTT_PASSWORD: str(user_input[CONF_MQTT_PASSWORD]),
            CONF_CA_CERT_PATH: _validate_optional_ca_path(hass, user_input.get(CONF_CA_CERT_PATH)),
            CONF_TRANSPORT: str(user_input.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)).strip(),
        }
    )
    settings = EntrySettings.from_mapping(hass, updated)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError
    return updated
