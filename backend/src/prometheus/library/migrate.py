"""Move a legacy items/<id> data dir into the readable library (PLAN 15.4.1).

Up to M8 the data dir held prometheus.db, config/, logs/, models/, runtime/ and
items/<32-hex id>/{report,mindmap,subtitle,work}. Every step checks whether its
source still exists, so an interrupted migration simply continues on next start.
"""

import re
import shutil
from pathlib import Path

from prometheus import paths
from prometheus.library import db, publish
from prometheus.library import items as items_store

_LEGACY_DIRS = ("config", "logs", "models", "runtime")
_ITEM_ID = re.compile(r"^[0-9a-f]{32}$")


def _legacy_items(root: Path) -> list:
    folder = root / "items"
    if not folder.is_dir():
        return []
    return [child for child in sorted(folder.iterdir()) if child.is_dir() and _ITEM_ID.match(child.name)]


def _move(source: Path, target: Path) -> None:
    """Move a file or folder; folders merge into an existing target."""
    if not source.exists():
        return
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return
    if source.is_dir() and target.is_dir():
        for child in list(source.iterdir()):
            _move(child, target / child.name)
        shutil.rmtree(source, ignore_errors=True)


def migrate_legacy_layout(data_dir) -> bool:
    """Returns True when anything was migrated."""
    root = Path(data_dir)
    legacy_db = root / "prometheus.db"
    items = _legacy_items(root)
    if not legacy_db.is_file() and not items:
        return False

    _move(legacy_db, paths.db_path(root))
    for name in _LEGACY_DIRS:
        _move(root / name, paths.internal_dir(root) / name)
    paths.init_data_dir(root)
    db.init_db(root)  # schema v1 -> v2

    for item in items:
        item_id = item.name
        _move(item / "work", paths.cache_dir(root, item_id))
        _move(item / "subtitle" / "segments.json", paths.segments_file(root, item_id))
        _move(item / "report" / "report.html", paths.report_file(root, item_id))
        _move(item / "mindmap" / "mindmap.md", paths.mindmap_file(root, item_id))
        _move(item / "subtitle" / "subtitle.srt", paths.srt_file(root, item_id))
        row = items_store.get_item(root, item_id)
        if row and row["status"] == "done" and not row.get("library_path"):
            publish.publish(root, item_id)
        shutil.rmtree(item, ignore_errors=True)
    items_root = root / "items"
    if items_root.is_dir() and not any(items_root.iterdir()):
        items_root.rmdir()
    return True
