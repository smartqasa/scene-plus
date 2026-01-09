# Scene Plus

Scene Plus is a Home Assistant custom integration that extends the `scene`
domain with services for reading and updating scene entities. It captures the
current state of a scene's entities and persists updates back to `scenes.yaml`,
making it easy to keep scenes in sync without hand-editing YAML.

## ✨ Features

- Retrieve entity IDs stored in any Home Assistant scene.
- Update a scene with current entity states and attributes.
- Reload scenes from `scenes.yaml` without restarting Home Assistant.
- Uses `ruamel.yaml` for safe YAML parsing and formatting.
- Service responses include success/error details for automation-friendly
  workflows.

## 📥 Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Navigate to **Integrations**.
3. Search for **Scene Plus**.
4. Download and restart Home Assistant.

### Manual

1. Copy `custom_components/scene_plus/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## ⚙️ Usage

All services live under the `scene_plus` domain.

### Get entities in a scene

```yaml
service: scene_plus.get_entities
target:
  entity_id: scene.adjustable_living_room
```

**Response**

```json
{
  "success": true,
  "scene_id": "living_room_relax_scene",
  "entities": [
    "light.recessed_lights",
    "light.accent_strip_lights",
    "switch.fireplace_relay"
  ]
}
```

### Update a scene with current entity states

```yaml
service: scene_plus.update
target:
  entity_id: living_room_relax_scene
```

**Response**

```json
{
  "success": true,
  "updated": 6,
  "scene_id": "living_room_relax_scene"
}
```

### Reload scenes from `scenes.yaml`

```yaml
service: scene_plus.reload
```

## 🔧 Requirements

- Home Assistant with the built-in `scene` integration enabled.
- `ruamel.yaml` is installed automatically via the integration requirements.

## 🧭 Troubleshooting

- Ensure the target entity is a valid `scene.*` entity.
- If updates are not visible, call `scene_plus.reload` to reload scenes.
