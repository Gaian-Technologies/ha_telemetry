from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import ManagedEnrollmentResult


class EnrollmentError(Exception):
    """Raised when managed enrollment fails."""


async def async_enroll_managed_site(
    hass: HomeAssistant,
    *,
    hub_url: str,
    enrollment_token: str,
    site_id: str | None = None,
) -> ManagedEnrollmentResult:
    session = async_get_clientsession(hass)
    request_body: dict[str, Any] = {"invite_code": enrollment_token.strip()}
    if site_id:
        request_body["site_id"] = site_id

    url = f"{hub_url.rstrip('/')}/api/v1/enrollment"
    try:
        async with asyncio.timeout(15):
            async with session.post(url, json=request_body) as response:
                payload = await response.json(content_type=None)
    except TimeoutError as err:
        raise EnrollmentError("enrollment_timeout") from err
    except Exception as err:
        raise EnrollmentError("enrollment_request_failed") from err

    if response.status != 200:
        if isinstance(payload, dict) and payload.get("detail"):
            detail = payload["detail"]
            if isinstance(detail, dict) and detail.get("error"):
                raise EnrollmentError(str(detail["error"]))
        raise EnrollmentError("enrollment_failed")

    try:
        return ManagedEnrollmentResult(
            site_id=str(payload["site_id"]).strip(),
            mqtt_host=str(payload["mqtt_host"]).strip(),
            mqtt_port=int(payload["mqtt_port"]),
            mqtt_transport=str(payload.get("mqtt_transport", "tcp")).strip(),
            mqtt_topic_prefix=str(payload["mqtt_topic_prefix"]).strip("/"),
            mqtt_username=str(payload["mqtt_username"]).strip(),
            mqtt_password=str(payload["mqtt_password"]),
            hub_url=str(payload.get("hub_url", hub_url)).strip().rstrip("/"),
            commands_allowed=bool(payload.get("commands_allowed", False)),
        )
    except (KeyError, TypeError, ValueError) as err:
        raise EnrollmentError("invalid_enrollment_response") from err
