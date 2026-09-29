"""Pi models.json generation (PLAN 8.9, 15.4.10)."""

import json
import shutil
from pathlib import Path

import video_report_agent
from prometheus import paths
from prometheus.llm import catalogue_update, pi_catalogue
from prometheus.settings import store


def ensure_models_json(data_dir) -> None:
    target = paths.models_json(data_dir)
    if target.is_file():
        return
    defaults = Path(video_report_agent.__file__).parent / "defaults" / "models.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(defaults, target)


PROTOCOL_APIS = {"openai": "openai-completions", "anthropic": "anthropic-messages"}


def custom_base_url(custom: dict) -> str:
    """Pi appends /v1/messages for anthropic-messages, so drop a trailing /v1 there."""
    base = str((custom or {}).get("base_url", "")).rstrip("/")
    if (custom or {}).get("protocol") == "anthropic" and base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


def model_fields(data_dir, profile: dict, *, pi_cli=None) -> tuple:
    """(source, models.json fields) Pi runs a profile's model with (PLAN 15.4.10).

    A built-in provider runs what this models.json defines for it, else Pi's own entry;
    a custom one gets what the bundled catalogues know (pi_catalogue.lookup).
    """
    model_id = str(profile.get("model") or "")
    kind = profile.get("kind")
    if kind in store.BUILTIN:
        target = paths.models_json(data_dir)
        document = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        for entry in ((document.get("providers") or {}).get(kind) or {}).get("models") or []:
            if entry.get("id") == model_id:
                return "pi", {name: entry[name] for name in pi_catalogue.NUMBERS if entry.get(name) is not None}
        return pi_catalogue.lookup(model_id, api=PROTOCOL_APIS["openai"], pi_cli=pi_cli, provider=kind,
                                   fresh=catalogue_update.catalogue_folder(data_dir))
    api = PROTOCOL_APIS.get(profile.get("protocol") or "openai", PROTOCOL_APIS["openai"])
    return pi_catalogue.lookup(model_id, api=api, base_url=profile.get("base_url", ""), pi_cli=pi_cli,
                               fresh=catalogue_update.catalogue_folder(data_dir))


def refresh_custom_provider(data_dir, *, pi_cli=None) -> bool:
    """Rewrite the custom provider from the saved settings at startup (PLAN 15.4.10): installs
    from before the model parameters would otherwise keep Pi's 128k / 16k defaults until 保存."""
    llm = store.load(data_dir)["llm"]
    if llm["provider"] != "custom":
        return False
    apply_custom_provider(data_dir, llm.get("custom"), pi_cli=pi_cli)
    return True


def apply_custom_provider(data_dir, custom: dict, *, pi_cli=None) -> None:
    """Write the custom provider into models.json (PLAN 8.9, 15.2-2) with the model's context,
    output, thinking levels and compat filled in; the profile's own numbers win (PLAN 15.4.10).
    """
    target = paths.models_json(data_dir)
    document = json.loads(target.read_text(encoding="utf-8"))
    settings = store.load(data_dir)
    model_id = settings["llm"]["model"]
    profiles = settings["llm_profiles"]
    active = next(item for item in profiles["items"] if item["id"] == profiles["active"])
    supports_images = bool((custom or {}).get("supports_images", False))
    inputs = ["text", "image"] if supports_images else ["text"]
    protocol = (custom or {}).get("protocol") or "openai"
    source, fields = model_fields(data_dir, {"kind": "custom", "model": model_id, "protocol": protocol,
                                        "base_url": (custom or {}).get("base_url", "")}, pi_cli=pi_cli)
    if source != "pi" and active.get("thinking") in ("xhigh", "max"):
        # Pi runs xhigh / max only for a model whose map names them; the catalogue always lags the
        # vendors, so a model it lacks gets the chosen level as it is (PLAN 15.4.12, user 2026-09-29).
        fields["thinkingLevelMap"] = {"xhigh": "xhigh", "max": "max"}
    own = {"contextWindow": active["context_window"], "maxTokens": active["max_tokens"]}
    fields.update({name: value for name, value in own.items() if value})
    document.setdefault("providers", {})["custom"] = {
        "baseUrl": custom_base_url(custom),
        "api": PROTOCOL_APIS[protocol],
        "apiKey": "$PI_API_KEY",
        "models": [
            {"id": model_id, "name": model_id, "reasoning": True, "input": inputs, **fields},
        ],
    }
    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8",
    )
