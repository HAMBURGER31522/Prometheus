"""settings.json persistence, model profiles and key masking (PLAN 8.9, 15.4.8).

Model profiles are the source of truth (``llm_profiles``). ``llm`` is the active profile
in the shape every stage has always read (provider / model / api_key / thinking /
custom), derived on load and written alongside for anyone reading the file. A body that
only carries ``llm`` (older clients) edits the active profile.
"""

import json
from urllib.parse import urlparse

from prometheus import paths

BUILTIN = {"deepseek": "DeepSeek", "zhipu": "智谱"}

DEFAULT_PROFILE = {
    "id": "default", "name": "DeepSeek", "kind": "deepseek", "base_url": "", "protocol": "openai",
    "api_key": "", "model": "deepseek-flash", "supports_images": False, "thinking": "medium",
}

DEFAULTS = {
    "llm_profiles": {"active": "default", "items": [DEFAULT_PROFILE]},
    # 「云端」 is 必剪 and needs nothing else (PLAN 15.2-7); DashScope fields are gone.
    "asr": {"backend": "local"},
    "network": {"proxy": "", "youtube_cookies_file": ""},
    "figures_default": True,
}


def _copy(value):
    return json.loads(json.dumps(value))


def _merge(defaults: dict, overrides: dict) -> dict:
    merged = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _known_asr(settings: dict) -> dict:
    """Drop asr fields older versions stored (dashscope_api_key, cloud_model)."""
    settings["asr"] = {key: settings["asr"][key] for key in DEFAULTS["asr"]}
    return settings


def _profile_from_llm(llm: dict, base: dict | None = None) -> dict:
    """An old single-model setting (or an edit in that shape) as a profile."""
    custom = llm.get("custom") or {}
    provider = llm.get("provider") or "deepseek"
    kind = provider if provider in BUILTIN else "custom"
    profile = dict(base or DEFAULT_PROFILE)
    profile.update(
        kind=kind, model=llm.get("model", profile["model"]), api_key=llm.get("api_key", profile["api_key"]),
        thinking=llm.get("thinking") or profile["thinking"], base_url=custom.get("base_url", ""),
        protocol=custom.get("protocol") or "openai", supports_images=bool(custom.get("supports_images", False)),
    )
    if base is None:
        profile["name"] = BUILTIN.get(kind) or urlparse(profile["base_url"]).hostname or "自定义"
    return profile


def _llm_view(profile: dict) -> dict:
    kind = profile["kind"]
    return {
        "provider": kind if kind in BUILTIN else "custom",
        "model": profile["model"], "api_key": profile["api_key"], "thinking": profile["thinking"],
        "custom": {"base_url": profile["base_url"], "supports_images": profile["supports_images"],
                   "protocol": profile["protocol"]},
    }


def _normalize(settings: dict) -> dict:
    profiles = settings.get("llm_profiles") or {}
    items = [{**DEFAULT_PROFILE, **item} for item in profiles.get("items") or []]
    items = [{field: item[field] for field in DEFAULT_PROFILE} for item in items] or [dict(DEFAULT_PROFILE)]
    active = profiles.get("active")
    if not any(item["id"] == active for item in items):
        active = items[0]["id"]
    settings["llm_profiles"] = {"active": active, "items": items}
    settings["llm"] = _llm_view(next(item for item in items if item["id"] == active))
    return settings


def load(data_dir) -> dict:
    file = paths.settings_file(data_dir)
    stored = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}
    if "llm_profiles" not in stored and stored.get("llm"):
        stored["llm_profiles"] = {"active": "default", "items": [_profile_from_llm(stored["llm"])]}
    stored.pop("llm", None)
    return _known_asr(_normalize(_merge(_copy(DEFAULTS), stored)))


def save(data_dir, settings) -> None:
    incoming = _copy(settings)
    if "llm_profiles" not in incoming and incoming.get("llm"):
        current = load(data_dir)["llm_profiles"]
        items = [
            _profile_from_llm(incoming["llm"], base=item) if item["id"] == current["active"] else item
            for item in current["items"]
        ]
        incoming["llm_profiles"] = {"active": current["active"], "items": items}
    incoming.pop("llm", None)
    merged = _known_asr(_normalize(_merge(_copy(DEFAULTS), incoming)))
    paths.settings_file(data_dir).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def mask(secret: str) -> str:
    return f"****{secret[-4:]}" if secret else ""


def masked(settings: dict) -> dict:
    shown = _copy(settings)
    if shown.get("llm", {}).get("api_key"):
        shown["llm"]["api_key"] = mask(shown["llm"]["api_key"])
    for profile in (shown.get("llm_profiles") or {}).get("items", []):
        profile["api_key"] = mask(profile.get("api_key", ""))
    return shown


def restore_secrets(incoming: dict, stored: dict) -> dict:
    """Masked keys round-trip unchanged; anything else is a new literal value."""
    merged = _copy(incoming)
    stored_llm = stored.get("llm") or {}
    if (incoming.get("llm") or {}).get("api_key") == mask(stored_llm.get("api_key", "")):
        merged["llm"]["api_key"] = stored_llm.get("api_key", "")
    saved = {item["id"]: item for item in (stored.get("llm_profiles") or {}).get("items", [])}
    for profile in (merged.get("llm_profiles") or {}).get("items", []):
        before = saved.get(profile.get("id"))
        if before and profile.get("api_key") == mask(before.get("api_key", "")):
            profile["api_key"] = before.get("api_key", "")
    return merged


def stored_key(data_dir, profile: dict) -> str:
    """The real key for a profile whose key arrives masked (the settings page never sees it)."""
    key = profile.get("api_key", "")
    for item in load(data_dir)["llm_profiles"]["items"]:
        if item["id"] == profile.get("id") and key == mask(item["api_key"]):
            return item["api_key"]
    return key
