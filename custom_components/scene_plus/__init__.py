from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .services_scene import register_scene_services
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the scene_plus integration."""

    _LOGGER.info("Setting up %s integration", DOMAIN)

    hass.data.setdefault(DOMAIN, {})

    register_scene_services(hass)

    return True
