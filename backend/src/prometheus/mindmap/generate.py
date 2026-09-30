"""Generate, validate (one retry), fill and save an item's knowledge-tree mind map
(PLAN 15.4.2, 15.4.9): the skeleton first, then retrieval-grounded detail on the leaves."""

import json

from prometheus import paths
from prometheus.agents import runs
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.mindmap import enrich, markdown, prompt, tree
from prometheus.report.outline import extract_outline

# The same report can pass on a later try (BV1EJ4m1t7Zs, 2026-09-30: two tries failed, the next run passed at
# once): the second and third tries both mend the tree before them (PLAN 15.4.15-9).
TRIES = 3
REASON_CHARS = 500


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
            node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir), agent=runs.agent_of(llm),
        )

    base = prompt.build_prompt(outline)
    errors: list = []
    parsed = None
    kept = None  # the latest (tree, small problems) with nothing worse (PLAN 15.4.15-11)
    for _ in range(TRIES):
        feedback = "\n\n上次输出的问题：" + "；".join(errors) if errors else ""
        if errors and parsed is not None:  # edit the last tree: a fresh one slips elsewhere
            feedback = ("\n\n上次输出的 JSON：\n" + json.dumps(parsed, ensure_ascii=False) + feedback
                        + "\n请在上次输出的基础上只修改这些问题，其余保持不变，仍然只输出完整的 JSON。")
        try:
            text = ask(base + feedback)
        except Exception as exc:  # noqa: BLE001 - PLAN 8.3: a mind map failure never fails the item
            if kept is not None:  # a tree with only small problems is already there: keep it
                break
            reason = f"调用出错：{type(exc).__name__}: {exc}"[:REASON_CHARS]
            items_store.update_item(data_dir, item_id, mindmap_status="failed", mindmap_error=reason)
            return False
        parsed = tree.parse_tree(text)
        if parsed is None:
            errors = ["没有找到包含 root 的 JSON 对象"]
        else:
            major, minor = tree.check_tree(parsed, outline)
            errors = major + minor
            if not major:
                kept = (parsed, minor)
        if not errors:
            break
    small: list = []
    if errors and kept is not None:  # only small problems left: the map is kept with them
        parsed, small = kept
    elif errors:  # the map page says which checks it failed (PLAN 15.4.15-9)
        reason = ("没通过检查：" + "；".join(errors))[:REASON_CHARS]
        items_store.update_item(data_dir, item_id, mindmap_status="failed", mindmap_error=reason)
        return False
    parsed["root"].pop("summary", None)  # the root is the title only; not worth a retry
    if small:
        parsed["problems"] = small
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
    items_store.update_item(data_dir, item_id, mindmap_status="ok", mindmap_error=None)
    return True
