"""Setup-time entity validation hook for project-specific integration variants."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


def validate_selected_entities(hass: HomeAssistant, entity_ids: tuple[str, ...]) -> str | None:
    """Accept the selected entities.

    The generic integration does not impose project-specific requirements on
    the chosen entities. Branded derivatives can replace this module with
    stricter validation rules without changing the core config-flow structure.
    """

    del hass, entity_ids
    return None
