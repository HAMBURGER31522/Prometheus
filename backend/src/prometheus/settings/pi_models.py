"""Pi models.json generation (PLAN 8.9)."""

import json
import shutil
from pathlib import Path

import video_report_agent
from prometheus import paths
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


def apply_custom_provider(data_dir, custom: dict) -> None:
    """Write the custom provider into models.json (PLAN 8.9, 15.2-2)."""
    target = paths.models_json(data_dir)
    document = json.loads(target.read_text(encoding="utf-8"))
    model_id = store.load(data_dir)["llm"]["model"]
    supports_images = bool((custom or {}).get("supports_images", False))
    inputs = ["text", "image"] if supports_images else ["text"]
    document.setdefault("providers", {})["custom"] = {
        "baseUrl": custom_base_url(custom),
        "api": PROTOCOL_APIS[(custom or {}).get("protocol") or "openai"],
        "apiKey": "$PI_API_KEY",
        "models": [
            {"id": model_id, "name": model_id, "reasoning": True, "input": inputs},
        ],
    }
    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8",
    )
