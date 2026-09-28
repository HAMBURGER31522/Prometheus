"""Model lists for the settings page (PLAN 15.4.8, 15.4.10).

Only runs when the user presses 「获取模型列表」: one GET to the profile's endpoint (two when
an OpenAI-style address without /v1 answers 404, as CC Switch does). Built-in providers
(DeepSeek, 智谱) are listed from Pi's own catalogue instead. A failure carries the HTTP
status and a short reason for the page. Tests replace ``_fetch_json``; development never
calls a real relay (they ban accounts that get probed).
"""

import importlib.metadata
import json
import urllib.error
import urllib.request

from prometheus.llm.pi_models import custom_base_url
from prometheus.settings.store import BUILTIN

ANTHROPIC_VERSION = "2023-06-01"


def _version() -> str:
    try:
        return importlib.metadata.version("prometheus-backend")
    except importlib.metadata.PackageNotFoundError:
        return "0"


# Python's default "Python-urllib/3.x" is what Cloudflare-fronted relays block first.
USER_AGENT = f"Prometheus/{_version()}"


class ModelListError(RuntimeError):
    code = "MODEL_LIST_FAILED"

    def __init__(self, reason: str, status: int | None = None, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason
        self.status = status


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


def _from_cloudflare(error: urllib.error.HTTPError, body: str) -> bool:
    """Cloudflare's own block page, rather than the API behind it answering 403."""
    if "cloudflare" in body.lower():
        return True
    server = str((error.headers or {}).get("server", "")).lower()
    try:
        json.loads(body)
    except ValueError:
        return "cloudflare" in server
    return False


def _http_reason(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", "replace")
    except (OSError, ValueError, AttributeError):
        body = ""
    if error.code == 403 and _from_cloudflare(error, body):
        return "请求被 Cloudflare 拦截"
    if error.code in (401, 403):
        return "Key 无效或无权限"
    if error.code == 404:
        return "这个地址没有模型列表接口"
    return "请求失败"


def _failure(exc: Exception) -> ModelListError:
    detail = str(exc)[:200]
    if isinstance(exc, urllib.error.HTTPError):
        return ModelListError(_http_reason(exc), exc.code, detail)
    if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError):
        return ModelListError("连接超时", None, detail)
    if isinstance(exc, OSError):
        return ModelListError("连不上这个地址", None, detail)
    return ModelListError("返回的不是模型列表", None, detail)


def list_models(profile: dict, *, fetch=None, pi_listing=None, proxy: str = "") -> list:
    if profile.get("kind") in BUILTIN:
        return _pi_rows(pi_listing() if pi_listing else "", profile["kind"])
    fetch = fetch or _fetch_json
    key = profile.get("api_key", "")
    if profile.get("protocol") == "anthropic":
        base = custom_base_url({"base_url": profile.get("base_url", ""), "protocol": "anthropic"})
        urls = [base + "/v1/models"]
        headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    else:
        base = str(profile.get("base_url", "")).rstrip("/")
        # An address given without /v1 may still serve the list there (CC Switch's second try).
        urls = [base + "/models"] + ([] if base.endswith("/v1") else [base + "/v1/models"])
        headers = {"Authorization": f"Bearer {key}"}
    headers["User-Agent"] = USER_AGENT
    for index, url in enumerate(urls):
        try:
            return _ids(fetch(url, headers, proxy=proxy))
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and index + 1 < len(urls):
                continue
            raise _failure(exc) from exc
        except (OSError, ValueError, KeyError, AttributeError, TypeError) as exc:
            raise _failure(exc) from exc
    return []
