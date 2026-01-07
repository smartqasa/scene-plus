import aiofiles
import os
import tempfile
import asyncio
import logging
from typing import Any, Dict, List, Mapping

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

    if not isinstance(scenes, list):
        _LOGGER.warning("Invalid scenes data; expected list, got %s", type(scenes))
        return None

    for scene in scenes:
        if isinstance(scene, dict) and scene.get("id") == scene_id:
            return scene.get("entities", {})

    return None


def _write_scenes_file_sync(
    config_dir: str, scenes: List[Dict[str, Any]]
) -> None:
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


def _update_scenes_file_sync(
    config_dir: str,
    scene_id: str,
    state_attributes: Mapping[str, Dict[str, Any]],
) -> tuple[bool, str]:
    """Update scenes.yaml for a given scene ID (executor-only)."""
    path = os.path.join(config_dir, SCENES_FILE)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            scenes = yaml.load(fh) or []
    except FileNotFoundError:
        return False, "scenes.yaml not found"
    except Exception:
        _LOGGER.exception("Failed to load scenes.yaml")
        return False, "Failed to load scenes.yaml"

    if not isinstance(scenes, list):
        return False, "Invalid scenes data; expected a list of scenes"

    for idx, scene in enumerate(scenes):
        if isinstance(scene, dict) and scene.get("id") == scene_id:
            entities = dict(scene.get("entities", {}))

            for ent_id in list(entities):
                update = state_attributes.get(ent_id)
                if not update:
                    continue

                merged = dict(entities.get(ent_id, {}))

                if "attributes" in update:
                    merged.update(update["attributes"])
                if "state" in update:
                    merged["state"] = update["state"]

                entities[ent_id] = merged

            scene["entities"] = entities
            scenes[idx] = scene

            _write_scenes_file_sync(config_dir, scenes)
            return True, f"Scene {scene_id} updated"

    return False, f"Scene {scene_id} not found"


async def update_scene_entities(
    hass: HomeAssistant, scene_id: str
) -> Dict[str, Any]:
    """Update entities in scenes.yaml for a given scene ID."""
    async with CAPTURE_LOCK:
        state_attributes: Dict[str, Dict[str, Any]] = {}

        for state in hass.states.async_all():
            attrs = {
                k: safe_item(v)
                for k, v in state.attributes.items()
                if v is not None and k not in SCENE_ATTRIBUTE_EXCLUDE
            }

            state_attributes[state.entity_id] = {
                "state": str(state.state),
                "attributes": attrs,
            }

        try:
            success, message = await hass.async_add_executor_job(
                _update_scenes_file_sync,
                hass.config.config_dir,
                scene_id,
                state_attributes,
            )
            return {"success": success, "message": message}
        except Exception as err:
            _LOGGER.exception("Failed to update scenes.yaml")
            return {"success": False, "message": str(err)}
