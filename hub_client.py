"""HTTP client helpers for managed enrollment against the public hub API."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientConnectionError, ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import ManagedEnrollmentResult

INVALID_TOKEN_ERRORS = {
    "invalid_invite",
    "invite_expired",
    "invite_exhausted",
    "invite_revoked",
}


class EnrollmentError(Exception):
    """Raised when managed enrollment fails."""

    def __init__(self, translation_key: str) -> None:
        super().__init__(translation_key)
        self.translation_key = translation_key


async def async_enroll_managed_site(
    hass: HomeAssistant,
    *,
    hub_url: str,
    enrollment_token: str,
    site_id: str | None = None,
) -> ManagedEnrollmentResult:
    """Exchange an enrollment token for MQTT connection details."""

    cleaned_hub_url = _normalize_hub_url(hub_url)
    session = async_get_clientsession(hass)
    request_body: dict[str, Any] = {"enrollment_token": enrollment_token.strip()}
    if site_id:
        # Reauth passes the existing site ID so the hub rotates credentials for
        # that site instead of issuing a new identity.
        request_body["site_id"] = site_id

    url = f"{cleaned_hub_url}/api/v1/enrollment"
    try:
        async with asyncio.timeout(15):
            async with session.post(url, json=request_body) as response:
                payload = await _read_json_response(response)
    except TimeoutError as err:
        raise EnrollmentError("hub_timeout") from err
    except ClientConnectionError as err:
        raise EnrollmentError("cannot_reach_hub") from err
    except ClientError as err:
        raise EnrollmentError("hub_request_failed") from err
    except EnrollmentError:
        raise
    except Exception as err:
        raise EnrollmentError("hub_request_failed") from err

    if response.status != 200:
        raise EnrollmentError(_map_error_payload(payload))

    try:
        mqtt_transport = str(payload.get("mqtt_transport", "tcp")).strip()
        if mqtt_transport != "tcp":
            raise EnrollmentError("unsupported_mqtt_transport")

        return ManagedEnrollmentResult(
            site_id=str(payload["site_id"]).strip(),
            mqtt_host=str(payload["mqtt_host"]).strip(),
            mqtt_port=int(payload["mqtt_port"]),
            mqtt_topic_prefix=str(payload["mqtt_topic_prefix"]).strip("/"),
            mqtt_username=str(payload["mqtt_username"]).strip(),
            mqtt_password=str(payload["mqtt_password"]),
            hub_url=str(payload.get("hub_url", cleaned_hub_url)).strip().rstrip("/"),
            commands_allowed=bool(payload.get("commands_allowed", False)),
        )
    except EnrollmentError:
        raise
    except (KeyError, TypeError, ValueError) as err:
        raise EnrollmentError("invalid_enrollment_response") from err


async def _read_json_response(response) -> Any:
    try:
        return await response.json(content_type=None)
    except Exception as err:
        raise EnrollmentError("invalid_enrollment_response") from err


def _normalize_hub_url(hub_url: str) -> str:
    cleaned = hub_url.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise EnrollmentError("invalid_hub_url")
    return cleaned


def _map_error_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            error_code = detail.get("error")
            if isinstance(error_code, str):
                if error_code in INVALID_TOKEN_ERRORS:
                    return "invalid_enrollment_token"
                return "hub_rejected_enrollment"
    return "hub_rejected_enrollment"
