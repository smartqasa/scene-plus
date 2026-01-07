import aiofiles
import os
import tempfile
import asyncio
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Mapping

try:
    import fcntl
except ImportError:
    fcntl = None

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

        if not isinstance(scene, dict):
            _LOGGER.warning(
                "Skipping invalid scene entry; expected dict, got %s",
                type(scene),
            )
            continue

        if scene.get("id") == scene_id:
            return scene.get("entities", {})

    return None


@contextmanager
def _locked_scenes_file(config_dir: str):
    """Acquire an exclusive lock for scenes.yaml operations."""
    if fcntl is None:
        yield None
        return

    lock_path = os.path.join(config_dir, f"{SCENES_FILE}.lock")
    lock_file = open(lock_path, "a", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield lock_file
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def _load_scenes_file_sync(config_dir: str) -> List[Dict[str, Any]]:
    """Load scenes.yaml synchronously (executor-only)."""
    path = os.path.join(config_dir, SCENES_FILE)

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            content = file_handle.read()
        return yaml.load(content) or []
    except FileNotFoundError:
        _LOGGER.debug("scenes.yaml not found")
        return []
    except Exception:
        _LOGGER.exception("Failed to load scenes.yaml")
        return []


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


def _update_scenes_file_sync(
    config_dir: str,
    scene_id: str,
    state_attributes: Mapping[str, Dict[str, Any]],
) -> tuple[bool, str]:
    """Update scenes.yaml for a given scene ID (executor-only)."""
    with _locked_scenes_file(config_dir):
        scenes = _load_scenes_file_sync(config_dir)

        if not isinstance(scenes, list):
            _LOGGER.warning("Invalid scenes data; expected list, got %s", type(scenes))
            return False, "Invalid scenes data; expected a list of scenes"

        index = None
        for i, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                _LOGGER.warning(
                    "Skipping invalid scene entry; expected dict, got %s",
                    type(scene),
                )
                continue
            if scene.get("id") == scene_id:
                index = i
                break
        if index is None:
            return False, f"Scene {scene_id} not found"

        scene = scenes[index]
        entities = dict(scene.get("entities", {}))

        for ent_id in list(entities):
            update_data = state_attributes.get(ent_id)
            if update_data is None:
                continue

            existing_entry = entities.get(ent_id, {})
            if not isinstance(existing_entry, dict):
                existing_entry = {}

            merged_entry = dict(existing_entry)

            if "attributes" in update_data or "state" in update_data:
                if "attributes" in update_data:
                    merged_entry["attributes"] = update_data["attributes"]
                if "state" in update_data:
                    merged_entry["state"] = update_data["state"]
            else:
                merged_entry["attributes"] = update_data

            if "attributes" not in merged_entry:
                merged_entry["attributes"] = {}

            entities[ent_id] = merged_entry

        scene["entities"] = entities
        scenes[index] = scene

        _write_scenes_file_sync(config_dir, scenes)
        return True, f"Scene {scene_id} updated"


async def update_scene_entities(
    hass: HomeAssistant, scene_id: str
) -> Dict[str, Any]:
    """Update entities in scenes.yaml for a given scene ID."""

    async with CAPTURE_LOCK:
        state_attributes: Dict[str, Dict[str, Any]] = {}
        for state in hass.states.async_all():
            attributes = {
                k: safe_item(v)
                for k, v in state.attributes.items()
                if v is not None and k not in SCENE_ATTRIBUTE_EXCLUDE
            }

            state_attributes[state.entity_id] = {
                "state": str(state.state),
                "attributes": attributes,
            }

        try:
            success, message = await hass.async_add_executor_job(
                _update_scenes_file_sync,
                hass.config.config_dir,
                scene_id,
                state_attributes,
            )
            return {
                "success": success,
                "message": message,
            }
        except Exception as err:
            _LOGGER.exception("Failed to write scenes.yaml")
            return {
                "success": False,
                "message": str(err),
            }
