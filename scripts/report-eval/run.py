"""Evaluate 精读 reports on real items (PLAN 15.4.11 「评测」, E14).

    python scripts/report-eval/run.py <data dir> [--items ID ...] [--report ID=PATH ...]
        [--label NAME] [--out acceptance-output/report-eval] [--thinking low] [--questions-only] [--fake]

Calls the model configured in the data dir (settings → 模型) unless --fake: per item one call per
~5-minute block for the questions (only the first time: they are kept in <out>/questions and every
later report of the item meets the same ones), then about one call per 20 questions to answer, one
per 20 to grade, one per 10 sampled sentences and one per 10 supplements. Transcript text stays
under <out> (not tracked); <out>/summary-<label>.md is what goes into docs/report-eval.md.
"""

import argparse
import json
import sys
from pathlib import Path

from prometheus import paths
from prometheus import runtime as runtime_mod
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.report import evaluation
from prometheus.report.chunks import load_units
from prometheus.settings import store


def fake_ask(prompt: str) -> str:
    """Deterministic replies of the right shape, for tests and dry runs."""
    if "出 4 道" in prompt:
        # The first transcript line starts "[unit-…": the JSON example above it has "[\"unit-…".
        start = prompt.find("[unit-")
        unit = prompt[start + 1:prompt.find(" ", start)] if start >= 0 else "unit-000001"
        return json.dumps({"questions": [{"q": "这一段讲了什么", "answer": "见原文", "units": [unit]}]},
                          ensure_ascii=False)
    numbers = [str(number) for number in range(1, 41)]
    if '"answers"' in prompt:
        return json.dumps({"answers": dict.fromkeys(numbers, "未提及")}, ensure_ascii=False)
    if '"grades"' in prompt:
        return json.dumps({"grades": dict.fromkeys(numbers, "未提及")}, ensure_ascii=False)
    verdict = "不矛盾" if "不矛盾" in prompt else "有依据"
    return json.dumps({"verdicts": dict.fromkeys(numbers, verdict)}, ensure_ascii=False)


def model_ask(data_dir: Path, work: Path, thinking: str):
    # Pi runs with `work` as its working directory: a relative config dir would point elsewhere
    # there and the custom provider would be unknown.
    data_dir, work = Path(data_dir).resolve(), Path(work).resolve()
    runtime = runtime_mod.resolve(None)
    llm = store.load(data_dir)["llm"]
    work.mkdir(parents=True, exist_ok=True)

    def ask(prompt: str) -> str:
        for attempt in range(2):  # a failed call is tried once more, then left unanswered
            try:
                return one_shot.run_one_shot(
                    work, prompt=prompt, provider=llm["provider"], model=llm["model"],
                    api_key=llm.get("api_key") or "", thinking=thinking,
                    node_exe=str(runtime.node), pi_cli=str(runtime.pi_cli), agent_dir=paths.pi_config_dir(data_dir),
                )
            except one_shot.OneShotError as exc:
                if attempt:
                    print(f"  调用失败，跳过：{str(exc)[:160]}", file=sys.stderr)
        return ""

    return ask


def summary(result: dict) -> str:
    qa, faithful, supplements = result["qa"], result["faithfulness"], result["supplements"]
    citation, components, cost = result["citation"], result["components"], result["cost"]
    points = result["points_coverage"]
    shown = {name: count for name, count in components.items() if count and name != "total"}
    return "\n".join([
        f"### {result['title']}（{result['label']}）",
        (f"- 闭卷问答：{qa['score']:.1%}（正确 {qa['correct']}、部分正确 {qa['partial']}、未提及 {qa['missing']}、"
         f"错误 {qa['wrong']}，共 {qa['total']} 题）"),
        (f"- 忠实度抽检：{faithful['sampled']} 句，有依据 {faithful['有依据']}、部分有依据 {faithful['部分有依据']}、"
         f"无依据 {faithful['无依据']}"),
        f"- 补充说明：{supplements['checked']} 条，与视频矛盾 {supplements['矛盾']} 条",
        f"- 要点覆盖：{'无（没有要点账本）' if points is None else f'{points:.1%}'}",
        f"- 引用覆盖：{citation['share']:.1%}，最长一段没有引用 {citation['longest_gap_min']:.1f} 分钟",
        f"- 组件：共 {components['total']}（{'、'.join(f'{k} {v}' for k, v in shown.items()) or '无'}）",
        f"- 字数：报告 {result['cjk']['report']} 个汉字，转写 {result['cjk']['transcript']} 个汉字",
        (f"- 调用：{cost['calls']} 次，输入约 {cost['tokens_in']} token、输出约 {cost['tokens_out']} token，"
         f"按 claude-opus-4-8 官方价估算约 {cost['usd']:.2f} 美元（估算）"),
        "",
    ])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--items", nargs="*", default=[])
    parser.add_argument("--report", action="append", default=[], help="ID=PATH: evaluate this HTML instead")
    parser.add_argument("--label", default="current")
    parser.add_argument("--out", type=Path, default=Path("acceptance-output/report-eval"))
    parser.add_argument("--thinking", default="low")
    parser.add_argument("--questions-only", action="store_true")
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args(argv)

    overrides = dict(entry.split("=", 1) for entry in args.report)
    ask = fake_ask if args.fake else model_ask(args.data_dir, args.out / "work", args.thinking)
    rows = [row for row in items_store.list_items(args.data_dir, status="done")
            if not args.items or row["id"] in args.items]
    lines = []
    for row in rows:
        cache = paths.cache_dir(args.data_dir, row["id"])
        units = load_units(cache / "canonical-transcript.jsonl")
        questions_file = args.out / "questions" / f"{row['id']}.json"
        title = row.get("report_title") or row["id"]
        print(f"{title}：{len(units)} 个转写单元", file=sys.stderr)
        if args.questions_only:
            evaluation.ensure_questions(units, questions_file, ask)
            continue
        report = Path(overrides.get(row["id"]) or
                      paths.library_folder(args.data_dir, row["library_path"]) / paths.LIBRARY_FILES["html"])
        keypoints = cache / "keypoints.json"
        points = [p["id"] for p in json.loads(keypoints.read_text(encoding="utf-8"))["points"]] \
            if keypoints.is_file() else None
        result = evaluation.evaluate_report(units, report.read_text(encoding="utf-8"), questions_file, ask,
                                            points=points)
        result.update(id=row["id"], title=title, label=args.label, report=str(report))
        target = args.out / "results" / f"{row['id']}-{args.label}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))
        lines.append(summary(result))
    if lines:
        (args.out / f"summary-{args.label}.md").write_bytes("\n".join(lines).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
