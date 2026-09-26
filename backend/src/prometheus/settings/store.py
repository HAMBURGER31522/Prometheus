"""settings.json persistence and key masking (PLAN 8.9)."""

import json

from prometheus import paths

DEFAULTS = {
    "llm": {
        "provider": "deepseek", "model": "deepseek-flash", "api_key": "",
        "thinking": "low",
        "custom": {"base_url": "", "supports_images": False},
    },
    "asr": {"backend": "local", "dashscope_api_key": "", "cloud_model": "paraformer-v2"},
    "network": {"proxy": "", "youtube_cookies_file": ""},
    "figures_default": True,
}

_SECRET_FIELDS = (("llm", "api_key"), ("asr", "dashscope_api_key"))


def _merge(defaults: dict, overrides: dict) -> dict:
    merged = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load(data_dir) -> dict:
    file = paths.settings_file(data_dir)
    if not file.is_file():
        return json.loads(json.dumps(DEFAULTS))
    stored = json.loads(file.read_text(encoding="utf-8"))
    return _merge(DEFAULTS, stored)


def save(data_dir, settings) -> None:
    merged = _merge(DEFAULTS, settings)
    paths.settings_file(data_dir).write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def mask(secret: str) -> str:
    return f"****{secret[-4:]}" if secret else ""


def masked(settings: dict) -> dict:
    shown = json.loads(json.dumps(settings))
    for section, field in _SECRET_FIELDS:
        secret = shown.get(section, {}).get(field, "")
        if secret:
            shown[section][field] = mask(secret)
    return shown


def restore_secrets(incoming: dict, stored: dict) -> dict:
    """Masked keys round-trip unchanged; anything else is a new literal value."""
    merged = json.loads(json.dumps(incoming))
    for section, field in _SECRET_FIELDS:
        incoming_value = (incoming.get(section) or {}).get(field)
        stored_value = (stored.get(section) or {}).get(field, "")
        if incoming_value == mask(stored_value):
            merged[section][field] = stored_value
    return merged
