"""Publishing a finished item into the readable library + AI indexes (PLAN 15.4.1)."""

import json
import re

from conftest import BV_URL, wait_for_status
from prometheus import paths


def _done(client):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    row = wait_for_status(client, item_id, "done")
    assert row.get("library_path"), "library_path not recorded"
    return row


def _front_matter(markdown: str) -> dict:
    match = re.match(r"---\n(.*?)\n---\n", markdown, re.DOTALL)
    assert match, "精读.md must start with a YAML front matter block"
    return dict(line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line)


def test_done_item_becomes_a_readable_folder(client):
    row = _done(client)
    data_dir = client.app.state.data_dir
    assert row["library_path"], "library_path is recorded"
    folder = data_dir / row["library_path"]
    category, name = row["library_path"].split("/")
    assert category == "未分类"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} .+", name)
    assert sorted(p.name for p in folder.iterdir()) == sorted(paths.LIBRARY_FILES.values())

    meta = _front_matter((folder / "精读.md").read_text(encoding="utf-8"))
    assert {"title", "date", "category", "tags", "description", "source_url",
            "platform", "uploader", "duration_s"} <= set(meta)
    assert meta["source_url"] == row["source_url"]

    shortcut = (folder / "来源.url").read_text(encoding="utf-8")
    assert shortcut.startswith("[InternetShortcut]")
    assert f"URL={row['source_url']}" in shortcut

    lines = (folder / "字幕.txt").read_text(encoding="utf-8").splitlines()
    assert lines and all(re.match(r"\[\d{2}:\d{2}:\d{2}\] ", line) for line in lines)
    assert "-->" in (folder / "字幕.srt").read_text(encoding="utf-8")
    assert "<html" in (folder / "精读.html").read_text(encoding="utf-8")


def test_library_indexes_list_the_item(client):
    row = _done(client)
    data_dir = client.app.state.data_dir
    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    entry = next(item for item in index["items"] if item["id"] == row["id"])
    assert entry["title"] == row["report_title"]
    assert entry["category"] == "未分类"
    assert entry["paths"]["html"] == f"{row['library_path']}/精读.html"
    llms = (data_dir / "llms.txt").read_text(encoding="utf-8")
    assert "未分类" in llms and "index.json" in llms
    category_index = (data_dir / "未分类" / "_index.md").read_text(encoding="utf-8")
    assert row["report_title"] in category_index


def test_content_endpoints_read_from_the_library(client):
    row = _done(client)
    folder = client.app.state.data_dir / row["library_path"]
    (folder / "精读.html").write_text("<html><body>edited in library</body></html>", encoding="utf-8")
    report = client.get(f"/api/items/{row['id']}/report")
    assert report.status_code == 200 and "edited in library" in report.text
