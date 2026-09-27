"""Fake pipeline for E2E: completes all stages from fixtures (PLAN 12/M2).

PROMETHEUS_FAKE=1 is a development/E2E mode; the fixtures live in
backend/tests/fixtures/ (PLAN section 6) and ship only with the source tree.
"""

import json
import re
import shutil
from pathlib import Path

from prometheus import paths
from prometheus.library import categories as categories_store
from prometheus.library import items as items_store
from prometheus.library import publish as publish_mod
from prometheus.mindmap import enrich
from prometheus.mindmap.markdown import tree_to_markdown

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def _fixture(name: str) -> Path:
    return FIXTURES / name


def _fake_fill(prompt: str) -> str:
    """A diligent model for the leaf-filling step (PLAN 15.4.9): each detail is the opening
    of the evidence it was given, so the real retrieval and checks run in fake mode too."""
    details = {}
    for chunk in prompt.split('要点（编号 "')[1:]:
        leaf_id = chunk.split('"', 1)[0]
        evidence = chunk.split("资料：", 1)[1]
        details[leaf_id] = re.sub(r"\s+", "", evidence)[:150]
    return json.dumps(details, ensure_ascii=False)


def build_impls(data_dir):
    """Stage implementations that copy committed fixtures into the item layout."""

    def resolve(ctx):
        info = json.loads(_fixture("source.info.json").read_text(encoding="utf-8"))
        (paths.work_dir(data_dir, ctx.item_id) / "source.info.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        items_store.update_item(
            data_dir, ctx.item_id,
            source_title=info["source_title"], uploader=info["uploader"],
            duration_s=info["duration_s"],
        )

    def download(ctx):
        return None

    def transcribe(ctx):
        segments = json.loads(_fixture("segments.json").read_text(encoding="utf-8"))
        segments_file = paths.segments_file(data_dir, ctx.item_id)
        segments_file.write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
        from prometheus.subtitle import format as subtitle_format

        paths.srt_file(data_dir, ctx.item_id).parent.mkdir(parents=True, exist_ok=True)
        paths.srt_file(data_dir, ctx.item_id).write_text(
            subtitle_format.to_srt(segments), encoding="utf-8",
        )

    def transcript(ctx):
        shutil.copy2(_fixture("transcript.md"), paths.work_dir(data_dir, ctx.item_id) / "transcript.md")

    def frames(ctx):
        return None

    def report(ctx):
        shutil.copy2(
            _fixture("report.html"), paths.work_dir(data_dir, ctx.item_id) / "report.html",
        )

    def finalize(ctx):
        html = (_fixture("report.html")).read_text(encoding="utf-8")
        target = paths.report_file(data_dir, ctx.item_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        title = re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""
        items_store.update_item(data_dir, ctx.item_id, report_title=title)

    def subtitle_fix(ctx):
        # The fixture segments stand in for both the raw and the corrected transcript.
        segments = paths.segments_file(data_dir, ctx.item_id)
        if segments.is_file():  # tests may swap out the stages that write it
            shutil.copy2(segments, paths.raw_segments_file(data_dir, ctx.item_id))
        items_store.update_item(data_dir, ctx.item_id, subtitle_status="ok")

    def mindmap(ctx):
        tree = json.loads(_fixture("mindmap.json").read_text(encoding="utf-8"))
        html = _fixture("report.html").read_text(encoding="utf-8")
        tree, stats = enrich.enrich_tree(tree, html, ask=_fake_fill)
        tree["enrichment"] = stats
        paths.mindmap_json(data_dir, ctx.item_id).write_text(
            json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        row = items_store.get_item(data_dir, ctx.item_id)
        target = paths.mindmap_file(data_dir, ctx.item_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(tree_to_markdown(tree, row["platform"], row["video_id"]), encoding="utf-8")
        items_store.update_item(data_dir, ctx.item_id, mindmap_status="ok")

    def classify(ctx):
        category_id = categories_store.ensure_category(data_dir, "未分类")
        items_store.update_item(
            data_dir, ctx.item_id, category_id=category_id,
            tags='["示例"]', description="假流水线生成的示例条目。",
        )

    return {
        "resolve": resolve,
        "download": download,
        "transcribe": transcribe,
        "transcript": transcript,
        "frames": frames,
        "report": report,
        "finalize": finalize,
        "subtitle_fix": subtitle_fix,
        "mindmap": mindmap,
        "classify": classify,
        "publish": lambda ctx: publish_mod.publish(data_dir, ctx.item_id),
    }
