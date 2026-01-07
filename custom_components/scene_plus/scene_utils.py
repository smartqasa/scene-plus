import aiofiles
import os
import tempfile
import asyncio
import logging
from typing import Any, Dict, List

from ruamel.yaml import YAML
from homeassistant.core import HomeAssistant

from .const import SCENES_FILE
from .helpers import safe_item

_LOGGER = logging.getLogger(__name__)

yaml = YAML(typ="rt")
yaml.allow_unicode = True
yaml.default_flow_style = False

SCENE_ATTRIBUTE_EXCLUDE = {
    "device_id",
    "area_id",
    "zone_id",
}

CAPTURE_LOCK = asyncio.Lock()


async def load_scenes_file(hass: HomeAssistant) -> List[Dict[str, Any]]:
    """Load scenes.yaml asynchronously."""
    path = os.path.join(hass.config.config_dir, SCENES_FILE)

    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        return yaml.load(content) or []
    except FileNotFoundError:
        _LOGGER.debug("scenes.yaml not found")
        return []
    except Exception:
        _LOGGER.exception("Failed to load scenes.yaml")
        return []


async def get_scene_entities(
    hass: HomeAssistant, scene_id: str
) -> Dict[str, Any] | None:
    """Return entity dict from a scene ID."""
    scenes = await load_scenes_file(hass)

    for scene in scenes:
        if scene.get("id") == scene_id:
            return scene.get("entities", {})

    return None


def _write_scenes_file_sync(config_dir: str, scenes: List[Dict[str, Any]]) -> None:
    """Write scenes.yaml atomically (executor-only)."""
    path = os.path.join(config_dir, SCENES_FILE)

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        dir=config_dir,
        encoding="utf-8",
    )
    try:
        yaml.dump(scenes, tmp)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, path)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


async def update_scene_entities(
    hass: HomeAssistant, scene_id: str
) -> Dict[str, Any]:
    """Update entities in scenes.yaml for a given scene ID."""

    async with CAPTURE_LOCK:
        scenes = await load_scenes_file(hass)

        index = next(
            (i for i, s in enumerate(scenes) if s.get("id") == scene_id),
            None,
        )
        if index is None:
            return {
                "success": False,
                "message": f"Scene {scene_id} not found",
            }

        scene = scenes[index]
        entities = dict(scene.get("entities", {}))

        for ent_id in list(entities):
            state = hass.states.get(ent_id)
            if not state:
                continue

            attributes = {
                k: safe_item(v)
                for k, v in state.attributes.items()
                if v is not None and k not in SCENE_ATTRIBUTE_EXCLUDE
            }

            attributes["state"] = str(state.state)
            entities[ent_id] = attributes

        scene["entities"] = entities
        scenes[index] = scene

        try:
            await hass.async_add_executor_job(
                _write_scenes_file_sync,
                hass.config.config_dir,
                scenes,
            )
            return {
                "success": True,
                "message": f"Scene {scene_id} updated",
            }
        except Exception as err:
            _LOGGER.exception("Failed to write scenes.yaml")
            return {
                "success": False,
                "message": str(err),
            }
