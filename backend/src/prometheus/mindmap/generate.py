"""Generate, validate (one retry), fill and save an item's knowledge-tree mind map
(PLAN 15.4.2, 15.4.9): the skeleton first, then retrieval-grounded detail on the leaves."""

import json

from prometheus import paths
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.mindmap import enrich, markdown, prompt, tree
from prometheus.report.outline import extract_outline


def _report_html(data_dir, item_id: str, row: dict) -> str:
    """The run's report copy, or the library's once a finished run's cache was cleaned."""
    report = paths.report_file(data_dir, item_id)
    if not report.is_file() and row.get("library_path"):
        report = paths.library_folder(data_dir, row["library_path"]) / paths.LIBRARY_FILES["html"]
    return report.read_text(encoding="utf-8")


def generate_for_item(data_dir, item_id: str, row: dict, llm: dict, *,
                      node_exe: str, pi_cli: str) -> bool:
    """Write mindmap.json + mindmap.md and mark the item ok, or mark it failed."""
    work = paths.work_dir(data_dir, item_id)
    html = _report_html(data_dir, item_id, row)
    outline = extract_outline(html)

    def ask(text: str) -> str:
        return one_shot.run_one_shot(
            work, prompt=text, provider=llm["provider"], model=llm["model"],
            api_key=llm.get("api_key") or "", thinking=llm.get("thinking") or "medium",
            node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
        )

    base = prompt.build_prompt(outline)
    errors: list = []
    parsed = None
    for _ in range(2):
        feedback = "\n\n上次输出的问题：" + "；".join(errors) if errors else ""
        try:
            text = ask(base + feedback)
        except Exception:  # noqa: BLE001 - PLAN 8.3: a mind map failure never fails the item
            items_store.update_item(data_dir, item_id, mindmap_status="failed")
            return False
        parsed = tree.parse_tree(text)
        errors = ["没有找到包含 root 的 JSON 对象"] if parsed is None else tree.validate_tree(parsed, outline)
        if not errors:
            break
    if errors:
        items_store.update_item(data_dir, item_id, mindmap_status="failed")
        return False
    parsed["root"].pop("summary", None)  # the root is the title only; not worth a retry
    try:
        parsed, stats = enrich.enrich_tree(parsed, html, ask=ask)
        parsed["enrichment"] = stats
    except Exception as exc:  # noqa: BLE001 - the skeleton alone is still a good mind map
        parsed["enrichment"] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    target = paths.mindmap_json(data_dir, item_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    exported = paths.mindmap_file(data_dir, item_id)
    exported.parent.mkdir(parents=True, exist_ok=True)
    exported.write_text(markdown.tree_to_markdown(parsed, row["platform"], row["video_id"]),
                        encoding="utf-8")
    items_store.update_item(data_dir, item_id, mindmap_status="ok")
    return True
