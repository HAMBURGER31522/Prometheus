"""Generate, validate (one retry) and save an item's knowledge-tree mind map (PLAN 15.4.2)."""

import json

from prometheus import paths
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.mindmap import markdown, prompt, tree
from prometheus.report.outline import extract_outline


def generate_for_item(data_dir, item_id: str, row: dict, llm: dict, *,
                      node_exe: str, pi_cli: str) -> bool:
    """Write mindmap.json + mindmap.md and mark the item ok, or mark it failed."""
    work = paths.work_dir(data_dir, item_id)
    outline = extract_outline(paths.report_file(data_dir, item_id).read_text(encoding="utf-8"))
    base = prompt.build_prompt(outline)
    errors: list = []
    parsed = None
    for _ in range(2):
        feedback = "\n\n上次输出的问题：" + "；".join(errors) if errors else ""
        text = one_shot.run_one_shot(
            work, prompt=base + feedback,
            provider=llm["provider"], model=llm["model"],
            api_key=llm.get("api_key") or "", thinking=llm.get("thinking") or "low",
            node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
        )
        parsed = tree.parse_tree(text)
        errors = ["没有找到包含 root 的 JSON 对象"] if parsed is None else tree.validate_tree(parsed, outline)
        if not errors:
            break
    if errors:
        items_store.update_item(data_dir, item_id, mindmap_status="failed")
        return False
    target = paths.mindmap_json(data_dir, item_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    exported = paths.mindmap_file(data_dir, item_id)
    exported.parent.mkdir(parents=True, exist_ok=True)
    exported.write_text(markdown.tree_to_markdown(parsed, row["platform"], row["video_id"]),
                        encoding="utf-8")
    items_store.update_item(data_dir, item_id, mindmap_status="ok")
    return True
