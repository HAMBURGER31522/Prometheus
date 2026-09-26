"""Generate, validate (one retry) and save an item's mind map (PLAN 8.8)."""

from prometheus import paths
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.mindmap import markdown
from prometheus.report.outline import extract_outline


def generate_for_item(data_dir, item_id: str, row: dict, llm: dict, *,
                      node_exe: str, pi_cli: str) -> bool:
    """Write mindmap.md and mark the item ok, or mark it failed. Returns success."""
    work = paths.work_dir(data_dir, item_id)
    html = paths.report_file(data_dir, item_id).read_text(encoding="utf-8")
    outline = extract_outline(html)
    prompt = markdown.build_mindmap_prompt(outline, row["platform"], row["video_id"])
    errors: list = []
    text = ""
    for _ in range(2):
        feedback = "\n上次输出的问题：" + "；".join(errors) if errors else ""
        text = one_shot.run_one_shot(
            work, prompt=prompt + feedback,
            provider=llm["provider"], model=llm["model"],
            api_key=llm.get("api_key") or "", thinking=llm.get("thinking") or "low",
            node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
        )
        errors = markdown.validate_mindmap(
            text, expect_title=row["report_title"] or outline["title"],
        )
        if not errors:
            break
    if errors:
        items_store.update_item(data_dir, item_id, mindmap_status="failed")
        return False
    target = paths.mindmap_file(data_dir, item_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    items_store.update_item(data_dir, item_id, mindmap_status="ok")
    return True
