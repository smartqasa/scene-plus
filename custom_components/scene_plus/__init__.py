from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import register_scene_services


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    """Set up the scene_plus integration."""

    hass.data.setdefault(DOMAIN, {})

    register_scene_services(hass)

    return True
