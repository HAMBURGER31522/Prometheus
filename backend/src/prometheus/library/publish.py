"""Publish finished items into the readable library and keep folders in sync (PLAN 15.4.1).

The database records where each item lives (``library_path``); every operation
that changes a category or an item moves the folder with it and rebuilds the
indexes, so the files on disk always match what the app shows.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from prometheus import paths
from prometheus.library import categories as categories_store
from prometheus.library import index, layout
from prometheus.library import items as items_store
from prometheus.report.markdown_export import report_to_markdown
from prometheus.subtitle import convert as subtitle_convert
from prometheus.subtitle import format as subtitle_format


def _category_name(data_dir, category_id) -> str:
    for category in categories_store.list_categories(data_dir):
        if category["id"] == category_id:
            return category["name"]
    return layout.UNCATEGORIZED


def _local_date(iso: str | None) -> str:
    moment = datetime.fromisoformat(iso).astimezone() if iso else datetime.now().astimezone()
    return moment.strftime("%Y-%m-%d")


def _yaml(value) -> str:
    return json.dumps(value, ensure_ascii=False)  # JSON scalars/arrays are valid YAML


def _front_matter(row: dict, category: str, date: str) -> str:
    meta = {
        "title": row["report_title"] or row["source_title"] or row["video_id"],
        "date": date,
        "category": category,
        "tags": json.loads(row["tags"]) if row.get("tags") else [],
        "description": row.get("description") or "",
        "source_url": row["source_url"],
        "platform": row["platform"],
        "uploader": row.get("uploader") or "",
        "duration_s": row.get("duration_s"),
    }
    lines = ["---"]
    for key, value in meta.items():
        text = value if key == "source_url" else _yaml(value)
        lines.append(f"{key}: {text}")
    return "\n".join(lines + ["---", ""])


def _remove_if_empty(folder: Path) -> None:
    """Drop a category folder that holds nothing but its generated index."""
    if not folder.is_dir():
        return
    leftovers = [p for p in folder.iterdir() if p.name != index.CATEGORY_INDEX]
    if not leftovers:
        shutil.rmtree(folder, ignore_errors=True)


def _relative(data_dir, folder: Path) -> str:
    return folder.relative_to(Path(data_dir)).as_posix()


def _place(data_dir, row: dict, category: str, date: str) -> Path:
    """Where the item's folder goes, moving an existing one when the name changed."""
    root = Path(data_dir)
    parent = root / layout.category_folder_name(category)
    parent.mkdir(parents=True, exist_ok=True)
    wanted = layout.item_folder_name(date, row["report_title"] or row["source_title"] or row["video_id"])
    current = root / row["library_path"] if row.get("library_path") else None
    if current is not None and current.is_dir():
        if current.parent == parent and current.name.split(" (")[0] == wanted:
            return current
        target = layout.unique_child(parent, wanted)
        shutil.move(str(current), str(target))
        _remove_if_empty(current.parent)
        return target
    return layout.unique_child(parent, wanted)


def publish(data_dir, item_id: str) -> Path:
    """Write the six library files for a finished item and record where they are."""
    row = items_store.get_item(data_dir, item_id)
    category = _category_name(data_dir, row["category_id"])
    date = _local_date(row.get("finished_at"))
    folder = _place(data_dir, row, category, date)
    folder.mkdir(parents=True, exist_ok=True)
    names = paths.LIBRARY_FILES

    report = paths.report_file(data_dir, item_id)
    if report.is_file():
        shutil.copy2(report, folder / names["html"])
    if (folder / names["html"]).is_file():
        html = (folder / names["html"]).read_text(encoding="utf-8")
        (folder / names["md"]).write_text(
            _front_matter(row, category, date) + "\n" + report_to_markdown(html), encoding="utf-8",
        )
    mindmap = paths.mindmap_file(data_dir, item_id)
    if mindmap.is_file():
        shutil.copy2(mindmap, folder / names["mindmap"])
    segments_file = paths.segments_file(data_dir, item_id)
    asr_file = paths.cache_dir(data_dir, item_id) / "asr.json"
    if not segments_file.is_file() and asr_file.is_file():
        # Items from before segments.json existed only kept the raw ASR result.
        asr = json.loads(asr_file.read_text(encoding="utf-8"))
        segments_file.write_text(json.dumps(subtitle_convert.segments_from_asr(asr), ensure_ascii=False),
                                 encoding="utf-8")
    if segments_file.is_file():
        segments = json.loads(segments_file.read_text(encoding="utf-8"))
        (folder / names["srt"]).write_text(subtitle_format.to_srt(segments), encoding="utf-8")
        (folder / names["txt"]).write_text(subtitle_format.to_txt(segments), encoding="utf-8")
    (folder / names["url"]).write_text(
        f"[InternetShortcut]\nURL={row['source_url']}\n", encoding="utf-8",
    )
    items_store.update_item(data_dir, item_id, library_path=_relative(data_dir, folder))
    index.rebuild(data_dir)
    return folder


def report_html(data_dir, item_id: str, row: dict) -> str:
    """The run's report copy, or the library's once a finished run's cache was cleaned."""
    report = paths.report_file(data_dir, item_id)
    if not report.is_file() and row.get("library_path"):
        report = paths.library_folder(data_dir, row["library_path"]) / paths.LIBRARY_FILES["html"]
    return report.read_text(encoding="utf-8")


def files_missing(data_dir, row: dict) -> bool:
    library_path = row.get("library_path")
    return row["status"] == "done" and bool(library_path) and not (Path(data_dir) / library_path).is_dir()


def move_item(data_dir, item_id: str, category_id) -> None:
    items_store.update_item(data_dir, item_id, category_id=category_id)
    row = items_store.get_item(data_dir, item_id)
    if not row.get("library_path") or files_missing(data_dir, row):
        index.rebuild(data_dir)
        return
    folder = _place(data_dir, row, _category_name(data_dir, category_id),
                    row["library_path"].split("/")[-1][:10])
    items_store.update_item(data_dir, item_id, library_path=_relative(data_dir, folder))
    index.rebuild(data_dir)


def rename_category(data_dir, category_id, name: str) -> None:
    old_name = _category_name(data_dir, category_id)
    categories_store.rename_category(data_dir, category_id, name)
    old_folder = Path(data_dir) / layout.category_folder_name(old_name)
    for row in items_store.list_items(data_dir, category_id=category_id):
        if row.get("library_path") and not files_missing(data_dir, row):
            move_item(data_dir, row["id"], category_id)
    _remove_if_empty(old_folder)
    index.rebuild(data_dir)


def merge_categories(data_dir, category_id, into_id) -> None:
    source_folder = Path(data_dir) / layout.category_folder_name(_category_name(data_dir, category_id))
    for row in items_store.list_items(data_dir, category_id=category_id):
        move_item(data_dir, row["id"], into_id)
    categories_store.delete_category(data_dir, category_id)
    _remove_if_empty(source_folder)
    index.rebuild(data_dir)


def remove_item(data_dir, item_id: str) -> None:
    row = items_store.get_item(data_dir, item_id)
    if row is None:
        return
    items_store.delete_item(data_dir, item_id)
    if row.get("library_path"):
        folder = Path(data_dir) / row["library_path"]
        shutil.rmtree(folder, ignore_errors=True)
        _remove_if_empty(folder.parent)
    index.rebuild(data_dir)


def delete_category(data_dir, category_id) -> None:
    folder = Path(data_dir) / layout.category_folder_name(_category_name(data_dir, category_id))
    categories_store.delete_category(data_dir, category_id)
    _remove_if_empty(folder)
    index.rebuild(data_dir)
