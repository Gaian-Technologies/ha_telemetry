"""Home Assistant config flow for the managed hub enrollment workflow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .countries import build_country_selector, normalize_country
from .const import (
    CONF_COUNTRY,
    CONF_ENROLLMENT_TOKEN,
    CONF_ENTITY_IDS,
    CONF_HEARTBEAT_INTERVAL_SECONDS,
    CONF_HUB_URL,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_USERNAME,
    CONF_SITE_ID,
    CONF_TELEMETRY_INTERVAL_SECONDS,
    CONF_TOPIC_PREFIX,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_TELEMETRY_INTERVAL_SECONDS,
    DOMAIN,
)
from .hub_client import EnrollmentError, async_enroll_managed_site
from .models import EntrySettings, normalize_entity_ids
from .mqtt_client import async_validate_connection


class EntitySelectionError(Exception):
    """Raised when the entity selection is invalid."""


class CountrySelectionError(Exception):
    """Raised when the country selection is invalid."""


class CannotConnectError(Exception):
    """Raised when the MQTT broker connection test fails."""


class HATelemetryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create, reauth, and reconfigure entries for a single managed site."""

    VERSION = 5

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                cleaned = await _validate_setup(self.hass, user_input)
            except EntitySelectionError as err:
                errors["base"] = str(err)
            except CountrySelectionError as err:
                errors["base"] = str(err)
            except EnrollmentError as err:
                errors["base"] = err.translation_key
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(cleaned[CONF_SITE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=cleaned[CONF_SITE_ID], data=cleaned)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reauth_entry()
        defaults = {CONF_HUB_URL: entry.data.get(CONF_HUB_URL, "")}
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updates = await _validate_reauth(self.hass, entry, user_input)
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
            step_id="reauth",
            data_schema=_build_reauth_schema(user_input or defaults),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        defaults = _entry_defaults(entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updates = _validate_reconfigure(user_input)
            except EntitySelectionError as err:
                errors["base"] = str(err)
            except CountrySelectionError as err:
                errors["base"] = str(err)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=updates,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema(defaults),
            errors=errors,
        )


def _entry_defaults(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    merged = dict(entry.data)
    merged.update(entry.options)
    return merged


def _build_shared_entity_fields(defaults: dict[str, Any]) -> dict:
    country = str(defaults.get(CONF_COUNTRY, "") or "").strip()
    country_field = (
        vol.Required(CONF_COUNTRY, default=country)
        if country
        else vol.Required(CONF_COUNTRY)
    )
    return {
        country_field: build_country_selector(),
        vol.Required(
            CONF_ENTITY_IDS,
            default=defaults.get(CONF_ENTITY_IDS, []),
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


def _build_user_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HUB_URL, default=defaults.get(CONF_HUB_URL, "")): selector.TextSelector(),
            vol.Required(CONF_ENROLLMENT_TOKEN, default=defaults.get(CONF_ENROLLMENT_TOKEN, "")): selector.TextSelector(),
            **_build_shared_entity_fields(defaults),
        }
    )


def _build_reauth_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HUB_URL, default=defaults.get(CONF_HUB_URL, "")): selector.TextSelector(),
            vol.Required(CONF_ENROLLMENT_TOKEN, default=""): selector.TextSelector(),
        }
    )


def _build_reconfigure_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HUB_URL, default=defaults.get(CONF_HUB_URL, "")): selector.TextSelector(),
            **_build_shared_entity_fields(defaults),
        }
    )


def _validate_entity_selection(user_input: dict[str, Any]) -> tuple[str, ...]:
    entity_ids = normalize_entity_ids(user_input.get(CONF_ENTITY_IDS, []))
    if not entity_ids:
        raise EntitySelectionError("entity_ids_required")
    return entity_ids


def _normalize_shared(user_input: dict[str, Any]) -> dict[str, Any]:
    entity_ids = _validate_entity_selection(user_input)
    try:
        country = normalize_country(str(user_input.get(CONF_COUNTRY, "") or ""))
    except ValueError as err:
        raise CountrySelectionError(str(err)) from err
    return {
        CONF_COUNTRY: country,
        CONF_ENTITY_IDS: list(entity_ids),
        CONF_TELEMETRY_INTERVAL_SECONDS: int(user_input.get(CONF_TELEMETRY_INTERVAL_SECONDS, DEFAULT_TELEMETRY_INTERVAL_SECONDS)),
        CONF_HEARTBEAT_INTERVAL_SECONDS: int(user_input.get(CONF_HEARTBEAT_INTERVAL_SECONDS, DEFAULT_HEARTBEAT_INTERVAL_SECONDS)),
    }


def _managed_entry_data(local_settings: dict[str, Any], enrollment) -> dict[str, Any]:
    # Country, entity selection, and local publish cadence stay
    # Home-Assistant-side settings; the hub owns broker identity and topic
    # namespace.
    return {
        CONF_HUB_URL: enrollment.hub_url,
        CONF_HOST: enrollment.mqtt_host,
        CONF_PORT: enrollment.mqtt_port,
        CONF_SITE_ID: enrollment.site_id,
        CONF_TOPIC_PREFIX: enrollment.mqtt_topic_prefix,
        CONF_MQTT_USERNAME: enrollment.mqtt_username,
        CONF_MQTT_PASSWORD: enrollment.mqtt_password,
        **local_settings,
    }


async def _validate_setup(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_shared(user_input)
    hub_url = str(user_input[CONF_HUB_URL]).strip().rstrip("/")
    enrollment_token = str(user_input[CONF_ENROLLMENT_TOKEN]).strip()

    enrollment = await async_enroll_managed_site(
        hass,
        hub_url=hub_url,
        enrollment_token=enrollment_token,
    )

    cleaned = _managed_entry_data(normalized, enrollment)
    settings = EntrySettings.from_mapping(hass, cleaned)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError
    return cleaned


async def _validate_reauth(hass, entry: config_entries.ConfigEntry, user_input: dict[str, Any]) -> dict[str, Any]:
    hub_url = str(user_input[CONF_HUB_URL]).strip().rstrip("/")
    enrollment_token = str(user_input[CONF_ENROLLMENT_TOKEN]).strip()
    site_id = str(entry.data[CONF_SITE_ID]).strip()

    # Reauth rotates credentials for the existing site instead of provisioning a
    # second site record for the same Home Assistant instance.
    enrollment = await async_enroll_managed_site(
        hass,
        hub_url=hub_url,
        enrollment_token=enrollment_token,
        site_id=site_id,
    )

    local_settings = {
        CONF_COUNTRY: str(entry.data.get(CONF_COUNTRY, "")).strip(),
        CONF_ENTITY_IDS: list(entry.data.get(CONF_ENTITY_IDS, [])),
        CONF_TELEMETRY_INTERVAL_SECONDS: int(entry.data.get(CONF_TELEMETRY_INTERVAL_SECONDS, DEFAULT_TELEMETRY_INTERVAL_SECONDS)),
        CONF_HEARTBEAT_INTERVAL_SECONDS: int(entry.data.get(CONF_HEARTBEAT_INTERVAL_SECONDS, DEFAULT_HEARTBEAT_INTERVAL_SECONDS)),
    }
    updated = _managed_entry_data(local_settings, enrollment)
    settings = EntrySettings.from_mapping(hass, updated)
    if not await async_validate_connection(hass, settings):
        raise CannotConnectError
    return updated


def _validate_reconfigure(user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_shared(user_input)
    normalized[CONF_HUB_URL] = str(user_input[CONF_HUB_URL]).strip().rstrip("/")
    return normalized
