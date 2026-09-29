"""What the bundled Pi catalogue and the models.dev snapshot know about a model (PLAN 15.4.10).

Pi runs a models.json model it knows nothing about with a 128k context, 16k output and
budget-based thinking. Its own catalogue (pi-ai's providers/data, shipped inside the bundled
Pi: ``{"<api>": {"<model id>": {...}}}`` per provider file) has the real numbers for the
models it ships; model-limits.json (scripts/update-model-limits.py) has the context and
output limits models.dev lists for many more.
"""

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

PI_AI_DATA = Path("@earendil-works") / "pi-ai" / "dist" / "providers" / "data"
SNAPSHOT = Path(__file__).with_name("model-limits.json")
NUMBERS = ("contextWindow", "maxTokens", "thinkingLevelMap")


def catalogue_dir(pi_cli) -> Path | None:
    """<pi-coding-agent>/dist/bundle/cli.js -> pi-ai's providers/data, nested (as bundled) or hoisted."""
    if not pi_cli or not Path(pi_cli).is_file():
        return None
    package = Path(pi_cli).parents[2]
    for data in (package / "node_modules" / PI_AI_DATA, package.parents[1] / PI_AI_DATA):
        if data.is_dir():
            return data
    return None


@lru_cache(maxsize=4)
def _index(directory: str) -> dict:
    """model id -> [(provider file, entry)], provider files in name order."""
    models = {}
    for file in sorted(Path(directory).glob("*.json")):
        if file.name.startswith("."):
            continue
        for api, entries in json.loads(file.read_text(encoding="utf-8")).items():
            for model_id, entry in entries.items():
                models.setdefault(model_id, []).append((file.stem, {"api": api, **entry}))
    return models


def _fresh(directory) -> dict:
    """The catalogues fetched from pi.dev (catalogue_update): ``{"<model id>": {..., "api": ...}}``
    per provider file. Not cached: an update replaces them while the app runs."""
    models: dict = {}
    if not directory or not Path(directory).is_dir():
        return models
    for file in sorted(Path(directory).glob("*.json")):
        if file.name.startswith(".") or file.name == "updated.json":
            continue
        try:
            entries = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for model_id, entry in (entries.items() if isinstance(entries, dict) else ()):
            if isinstance(entry, dict) and entry.get("api"):
                models.setdefault(model_id, []).append((file.stem, entry))
    return models


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["limits"]


def _site(url: str) -> str:
    """The last two labels of the host: api.moonshot.cn and platform.moonshot.cn are one site."""
    host = urlparse(str(url or "")).hostname or ""
    return ".".join(host.split(".")[-2:])


def lookup(model_id: str, *, api: str, base_url: str = "", pi_cli=None, provider=None, fresh=None) -> tuple:
    """(source, fields) for a models.json entry: "pi", "models.dev" or None (Pi's defaults).

    Among Pi's entries with this id, one for the profile's API wins, then one on the
    profile's own site, then the first provider file by name. compat only means something
    for the API it was written for, so an entry for another API gives its numbers only.
    ``provider`` limits the search to one provider file (the built-in DeepSeek). ``fresh`` is the
    folder of catalogues fetched from pi.dev (PLAN 15.4.12): their entry for a provider replaces
    the bundled one, and they know the models released since.
    """
    directory = catalogue_dir(pi_cli)
    newer = _fresh(fresh).get(model_id, [])
    replaced = {(name, entry["api"]) for name, entry in newer}
    bundled = _index(str(directory)).get(model_id, []) if directory else []
    candidates = [(name, entry) for name, entry in bundled if (name, entry["api"]) not in replaced] + newer
    candidates = [(name, entry) for name, entry in candidates if provider in (None, name)]
    if candidates:
        site = _site(base_url)
        _, entry = min(candidates, key=lambda candidate: (
            candidate[1]["api"] != api, not site or _site(candidate[1].get("baseUrl")) != site, candidate[0]))
        fields = {name: entry[name] for name in NUMBERS if entry.get(name) is not None}
        if entry["api"] == api and entry.get("compat"):
            fields["compat"] = entry["compat"]
        return "pi", fields
    limits = _snapshot().get(str(model_id).strip().split("/")[-1].lower())
    if limits:
        return "models.dev", {"contextWindow": limits[0], "maxTokens": limits[1]}
    return None, {}
