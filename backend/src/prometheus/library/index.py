"""AI-readable indexes of the library (PLAN 15.4.1, after the PDC idea).

Two channels over the same content: 精读.html for people, and for AI a layered
set of plain files - llms.txt (overview) -> index.json / <分类>/_index.md
(catalogue) -> <分类>/<日期 标题>/精读.md (one article).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from prometheus import paths
from prometheus.library import categories as categories_store
from prometheus.library import items as items_store

CATEGORY_INDEX = "_index.md"


def _published(data_dir) -> list:
    names = {c["id"]: c["name"] for c in categories_store.list_categories(data_dir)}
    entries = []
    # Anything with a library folder is published, even while a regeneration runs.
    for row in items_store.list_items(data_dir):
        library_path = row.get("library_path")
        if not library_path or not (Path(data_dir) / library_path).is_dir():
            continue
        folder_name = library_path.split("/")[-1]
        entries.append({
            "id": row["id"],
            "title": row["report_title"] or row["source_title"] or row["video_id"],
            "category": names.get(row["category_id"]) or "未分类",
            "tags": json.loads(row["tags"]) if row.get("tags") else [],
            "description": row.get("description") or "",
            "date": folder_name[:10],
            "source": {
                "platform": row["platform"], "url": row["source_url"],
                "uploader": row.get("uploader") or "", "title": row.get("source_title") or "",
                "duration_s": row.get("duration_s"),
            },
            "paths": {role: f"{library_path}/{name}" for role, name in paths.LIBRARY_FILES.items()},
            "folder": library_path,
        })
    return sorted(entries, key=lambda entry: (entry["category"], entry["date"], entry["title"]))


def rebuild(data_dir) -> None:
    root = Path(data_dir)
    entries = _published(data_dir)
    items = [{k: v for k, v in entry.items() if k != "folder"} for entry in entries]
    (root / "index.json").write_text(
        json.dumps({"generated_at": datetime.now(UTC).isoformat(), "items": items},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_category: dict = {}
    for entry in entries:
        by_category.setdefault(entry["folder"].split("/")[0], []).append(entry)

    lines = [
        "# Prometheus 知识库", "",
        ("> 由 Prometheus 从 B 站 / YouTube 视频整理的精读知识库。"
         "每篇包含精读（HTML 给人看，Markdown 给 AI 读）、思维导图和原样字幕。"), "",
        "## 怎么读", "",
        "- 全部条目的元数据（标题、分类、标签、摘要、来源、文件路径）：[index.json](index.json)",
        f"- 某个分类的目录：`<分类>/{CATEGORY_INDEX}`",
        "- 单篇正文（给 AI 读）：`<分类>/<日期 标题>/精读.md`，开头的 YAML 是元数据", "",
        "## 分类", "",
    ]
    for folder, group in sorted(by_category.items()):
        lines.append(f"- [{group[0]['category']}]({folder}/{CATEGORY_INDEX})：{len(group)} 篇")
    (root / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for folder, group in by_category.items():
        rows = [f"# {group[0]['category']}", "", f"共 {len(group)} 篇。", ""]
        for entry in group:
            article = entry["folder"].split("/", 1)[1]
            line = f"- {entry['date']} [{entry['title']}]({article}/精读.md)"
            if entry["description"]:
                line += f" —— {entry['description']}"
            if entry["tags"]:
                line += f"（{'、'.join(entry['tags'])}）"
            rows.append(line)
        (root / folder / CATEGORY_INDEX).write_text("\n".join(rows) + "\n", encoding="utf-8")
