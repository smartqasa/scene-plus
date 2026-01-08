from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_GET_ENTITIES,
    SERVICE_UPDATE,
    SERVICE_RELOAD,
)
from .utilities import (
    get_scene_entities,
    update_scene_entities,
)
from .helpers import retrieve_scene_id

ServiceResponse = dict[str, Any]


def register_scene_services(hass: HomeAssistant) -> None:
    """Register scene_plus services."""

    async def handle_get(call: ServiceCall) -> ServiceResponse:
        entity_ids = call.data.get("entity_id", [])
        if not entity_ids:
            return {"success": False, "error": "entity_id is required"}

        entity_id = entity_ids[0]
        scene_id = await retrieve_scene_id(hass, entity_id)

        if scene_id is None:
            return {"success": True, "entities": [], "scene_id": None}

        entities = await get_scene_entities(hass, scene_id)
        return {
            "success": True,
            "entities": list(entities.keys()) if entities else [],
            "scene_id": scene_id,
        }

    async def handle_update(call: ServiceCall) -> ServiceResponse:
        entity_ids = call.data.get("entity_id", [])
        if not entity_ids:
            return {"success": False, "error": "entity_id is required"}

        entity_id = entity_ids[0]
        scene_id = await retrieve_scene_id(hass, entity_id)

        if scene_id is None:
            return {"success": False, "error": "Scene not found for entity"}

        return await update_scene_entities(hass, scene_id)

    async def handle_reload(call: ServiceCall) -> ServiceResponse:
        try:
            await hass.services.async_call(
                "scene",
                "reload",
                blocking=True,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        return {"success": True}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ENTITIES,
        handle_get,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): vol.All(
                    cv.ensure_list,
                    [cv.entity_id],
                    vol.Length(min=1),
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE,
        handle_update,
        schema=vol.Schema(
            {
                vol.Required("entity_id"): vol.All(
                    cv.ensure_list,
                    [cv.entity_id],
                    vol.Length(min=1),
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD,
        handle_reload,
        schema=vol.Schema({}),
    )
