"""Evaluate the simple-to-rich mind map harness on real reports (PLAN 15.4.9, E12 ④).

    python scripts/mindmap-eval/run.py <data dir> [docs/mindmap-eval.md]

Regenerates the mind map of every finished item in the data dir with the model configured
there (settings → 模型), then writes the richness numbers and sample leaves. Calls the
user's model: roughly 2 skeleton calls plus one filling call per theme for each report.
"""

import json
import sys
import time
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from prometheus import paths
from prometheus import runtime as runtime_mod
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.mindmap import enrich, generate
from prometheus.mindmap import tree as tree_rules
from prometheus.settings import store

THRESHOLDS = {"coverage": 0.9, "grounding": 0.4}
LEVELS = ("root", "theme", "topic", "leaf")


def evaluate(data_dir: Path) -> list:
    runtime = runtime_mod.resolve(None)
    llm = store.load(data_dir)["llm"]
    log = {"calls": 0, "problems": []}
    real_call, real_validate, real_check = one_shot.run_one_shot, tree_rules.validate_tree, enrich.check_detail
    real_parse = enrich.first_json_object

    def counted(*args, **kwargs):
        log["calls"] += 1
        try:
            return real_call(*args, **kwargs)
        except Exception as exc:
            log["problems"].append(f"调用失败：{exc}"[:200])
            raise

    def validate(*args, **kwargs):
        errors = real_validate(*args, **kwargs)
        log["problems"] += [f"骨架：{error}" for error in errors]
        return errors

    def check(*args, **kwargs):
        problems = real_check(*args, **kwargs)
        log["problems"] += [f"详解：{problem}" for problem in problems]
        return problems

    def parse(text, accept):
        value = real_parse(text, accept)
        if value is None:
            log["problems"].append("详解：回复里没有可解析的 JSON（开头：" + text[:60].replace("|", "/") + "）")
        return value

    one_shot.run_one_shot, tree_rules.validate_tree, enrich.check_detail = counted, validate, check
    enrich.first_json_object = parse
    results = []
    try:
        for row in items_store.list_items(data_dir, status="done"):
            log.update(calls=0, problems=[])
            started = time.perf_counter()
            ok = generate.generate_for_item(data_dir, row["id"], row, llm,
                                            node_exe=str(runtime.node), pi_cli=str(runtime.pi_cli))
            seconds = time.perf_counter() - started
            tree = json.loads(paths.mindmap_json(data_dir, row["id"]).read_text(encoding="utf-8")) if ok else None
            results.append({"row": row, "ok": ok, "tree": tree, "calls": log["calls"], "seconds": seconds,
                            "problems": list(log["problems"])})
    finally:
        one_shot.run_one_shot, tree_rules.validate_tree, enrich.check_detail = real_call, real_validate, real_check
        enrich.first_json_object = real_parse
    return results


def _samples(tree: dict, count: int = 3) -> list:
    leaves = [leaf for _id, leaf in enrich._leaves(tree["root"], "0") if leaf.get("detail")]
    step = max(1, len(leaves) // count)
    return leaves[::step][:count]


def report(results: list, model: str) -> str:
    lines = [
        "# 导图「由简到繁」实测（R7c，PLAN 15.4.9）",
        "",
        f"- 日期：{datetime.now().astimezone().date().isoformat()}；模型：`{model}`（用户配置的模型）",
        "- 流程：骨架（15.4.2）→ 按主题检索填充（章节全文 + BM25 相关段落）→ 逐条校验 → 不合格重写一次",
        f"- 通过线（E12 ④）：detail 覆盖率 ≥ {THRESHOLDS['coverage']:.0%}，平均依据率 ≥ {THRESHOLDS['grounding']}，各层平均字数由内向外递增",
        "",
        "| 报告 | 要点数 | detail 覆盖率 | 平均依据率 | 具体信息覆盖率 | 重写 | 平均字数 根 / 主题 / 子题 / 要点 | 调用 | 耗时 | 结论 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        title = result["row"]["report_title"] or result["row"]["source_title"]
        if not result["ok"] or "coverage" not in (result["tree"] or {}).get("enrichment", {}):
            error = ((result["tree"] or {}).get("enrichment") or {}).get("error", "导图未生成")
            lines.append(f"| {title} | — | — | — | — | — | — | {result['calls']} | {result['seconds']:.0f}s | 失败：{error} |")
            continue
        stats = result["tree"]["enrichment"]
        levels = stats["chars_by_level"]
        chain = [levels[level] for level in LEVELS if level in levels]
        growing = all(a < b for a, b in pairwise(chain))
        passed = stats["coverage"] >= THRESHOLDS["coverage"] and stats["grounding"] >= THRESHOLDS["grounding"] and growing
        lines.append(
            f"| {title} | {stats['leaves']} | {stats['coverage']:.0%} | {stats['grounding']:.2f} | {stats['concrete']:.0%} | "
            f"{stats['rewrites']} | {' / '.join(str(levels.get(level, '—')) for level in LEVELS)} | {result['calls']} | "
            f"{result['seconds']:.0f}s | {'通过' if passed else '未通过'} |"
        )
    lines += ["", "## 校验记录（含重写前的问题）", ""]
    for result in results:
        title = result["row"]["report_title"] or result["row"]["source_title"]
        lines.append(f"- {title}：" + ("无" if not result["problems"] else ""))
        lines += [f"  - {problem}" for problem in result["problems"]]
    lines += ["", "## 要点示例（标题 · 摘要 · 详解）", ""]
    for result in results:
        if not result["tree"]:
            continue
        lines.append(f"### {result['row']['report_title']}")
        lines.append("")
        for leaf in _samples(result["tree"]):
            lines += [f"- **{leaf['label']}**：{leaf.get('summary', '')}", f"  {leaf['detail']}"]
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    data_dir = Path(argv[0]).resolve()  # pi's agent dir is read relative to the work dir
    out = Path(argv[1]) if len(argv) > 1 else Path("docs/mindmap-eval.md")
    results = evaluate(data_dir)
    text = report(results, store.load(data_dir)["llm"]["model"])
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
