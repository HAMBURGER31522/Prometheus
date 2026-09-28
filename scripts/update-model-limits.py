"""Refresh the models.dev snapshot the backend uses for context and output limits (PLAN 15.4.10).

    python scripts/update-model-limits.py [saved api.json]

Without an argument it downloads https://models.dev/api.json. For each model id (the last path
segment, lower-case, like the settings page's vision snapshot from app/scripts) it keeps the
context and output limits most providers agree on; a tie goes to the smaller pair, so Pi is
never told a host serves more than it does. Pi's own catalogue is still asked first
(prometheus.llm.pi_catalogue); this only covers the models it does not know.
"""

import json
import sys
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SOURCE = "https://models.dev/api.json"
TARGET = Path(__file__).resolve().parents[1] / "backend" / "src" / "prometheus" / "llm" / "model-limits.json"


def load(argv: list) -> tuple:
    if argv:
        saved = Path(argv[0])
        fetched = datetime.fromtimestamp(saved.stat().st_mtime, UTC).date()
        return json.loads(saved.read_text(encoding="utf-8")), fetched
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "Prometheus"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8")), datetime.now(UTC).date()


def limits(catalogue: dict) -> dict:
    seen = {}
    for provider in catalogue.values():
        for key, model in (provider.get("models") or {}).items():
            limit = model.get("limit") or {}
            pair = (limit.get("context"), limit.get("output"))
            if not all(isinstance(value, int) and value > 0 for value in pair):
                continue
            name = str(model.get("id") or key).split("/")[-1].lower()
            seen.setdefault(name, Counter())[pair] += 1
    return {name: list(min(counts, key=lambda pair: (-counts[pair], pair))) for name, counts in sorted(seen.items())}


def main(argv: list) -> None:
    catalogue, fetched = load(argv)
    snapshot = {"source": SOURCE, "date": fetched.isoformat(), "limits": limits(catalogue)}
    TARGET.write_bytes((json.dumps(snapshot, separators=(",", ":")) + "\n").encode("utf-8"))
    print(f"{len(snapshot['limits'])} models -> {TARGET}")


if __name__ == "__main__":
    main(sys.argv[1:])
