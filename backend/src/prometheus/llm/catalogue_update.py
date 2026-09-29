"""Updating the model catalogue from pi.dev (PLAN 15.4.12).

The bundled Pi's catalogue (pi-ai's providers/data) is frozen at its release; Pi refreshes it from
pi.dev itself only when it runs online and only for providers with credentials, and the app runs
it offline through the custom provider. So the app fetches the same public files for every
provider Pi ships, keeps them in the data dir, and pi_catalogue.lookup prefers them. Nothing here
calls a model or sends a key.
"""

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from prometheus import paths
from prometheus.llm import pi_catalogue

URL = "https://pi.dev/api/models/providers/{}"
MAX_AGE = timedelta(days=1)
USER_AGENT = "Prometheus (model catalogue)"
_STAMP = "updated.json"


def catalogue_folder(data_dir) -> Path:
    return paths.pi_config_dir(data_dir) / "catalog"


def bundled_providers(pi_cli) -> list:
    """The provider files of the bundled catalogue: which providers there are to fetch."""
    directory = pi_catalogue.catalogue_dir(pi_cli)
    return sorted(path for path in directory.glob("*.json") if not path.name.startswith(".")) if directory else []


def _fetch(url: str, *, proxy: str = ""):
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy.strip() else []
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.build_opener(*handlers).open(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def updated_at(data_dir):
    try:
        return json.loads((catalogue_folder(data_dir) / _STAMP).read_text(encoding="utf-8")).get("updated_at")
    except (OSError, ValueError):
        return None


def due(data_dir, *, now=None) -> bool:
    stamp = updated_at(data_dir)
    if not stamp:
        return True
    return (now or datetime.now(UTC)) - datetime.fromisoformat(stamp) >= MAX_AGE


def refresh(data_dir, *, pi_cli, fetch=None, proxy: str = "", now=None) -> dict:
    """Fetch every bundled provider's catalogue; one that fails keeps its last file."""
    fetch = fetch or _fetch
    folder = catalogue_folder(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    fetched, failed = 0, []
    for file in bundled_providers(pi_cli):
        try:
            catalogue = fetch(URL.format(file.stem), proxy=proxy)
        except (OSError, ValueError):  # urllib's errors are OSErrors; a broken body a ValueError
            failed.append(file.stem)
            continue
        if not isinstance(catalogue, dict):
            failed.append(file.stem)
            continue
        (folder / file.name).write_bytes(json.dumps(catalogue, ensure_ascii=False).encode("utf-8"))
        fetched += 1
    if fetched:
        stamp = {"updated_at": (now or datetime.now(UTC)).isoformat()}
        (folder / _STAMP).write_bytes(json.dumps(stamp).encode("utf-8"))
    return {"updated_at": updated_at(data_dir), "providers": fetched, "failed": failed}
