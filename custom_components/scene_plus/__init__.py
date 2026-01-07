from homeassistant.core import HomeAssistant

from .services_scene import register_scene_services


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the scene_plus integration."""
    register_scene_services(hass)
    return True
