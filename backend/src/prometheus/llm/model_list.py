"""Model lists for the settings page (PLAN 15.4.8).

Only runs when the user presses 「获取模型列表」: one GET to the profile's endpoint. Built-in
providers (DeepSeek, 智谱) are listed from Pi's own catalogue instead. Tests replace
``_fetch_json``; development never calls a real relay (they ban accounts that get probed).
"""

import json
import urllib.request

from prometheus.llm.pi_models import custom_base_url
from prometheus.settings.store import BUILTIN

ANTHROPIC_VERSION = "2023-06-01"


class ModelListError(RuntimeError):
    code = "MODEL_LIST_FAILED"
    status = None
    reason = ""


def _fetch_json(url: str, headers: dict, *, proxy: str = ""):
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy.strip() else []
    request = urllib.request.Request(url, headers={**headers, "Accept": "application/json"})
    with urllib.request.build_opener(*handlers).open(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _ids(payload) -> list:
    rows = payload.get("data") or payload.get("models") or [] if isinstance(payload, dict) else payload
    ids = [row.get("id") or row.get("name") for row in rows if isinstance(row, dict)]
    return sorted({model for model in ids if isinstance(model, str) and model})


def _pi_rows(listing: str, provider: str) -> list:
    rows = [line.split() for line in (listing or "").splitlines()]
    return sorted({parts[1] for parts in rows if len(parts) >= 2 and parts[0] == provider})


def list_models(profile: dict, *, fetch=None, pi_listing=None, proxy: str = "") -> list:
    if profile.get("kind") in BUILTIN:
        return _pi_rows(pi_listing() if pi_listing else "", profile["kind"])
    fetch = fetch or _fetch_json
    key = profile.get("api_key", "")
    if profile.get("protocol") == "anthropic":
        url = custom_base_url({"base_url": profile.get("base_url", ""), "protocol": "anthropic"}) + "/v1/models"
        headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    else:
        url = str(profile.get("base_url", "")).rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {key}"}
    try:
        return _ids(fetch(url, headers, proxy=proxy))
    except (OSError, ValueError, KeyError) as exc:
        raise ModelListError(str(exc)[:200]) from exc
