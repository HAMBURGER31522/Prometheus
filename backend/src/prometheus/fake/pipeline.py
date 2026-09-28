"""Fake pipeline for E2E: completes all stages from fixtures (PLAN 12/M2).

PROMETHEUS_FAKE=1 is a development/E2E mode; the fixtures live in
backend/tests/fixtures/ (PLAN section 6) and ship only with the source tree.
"""

import json
import re
import shutil
from pathlib import Path

from prometheus import paths
from prometheus.ingest.download import IngestError
from prometheus.library import categories as categories_store
from prometheus.library import items as items_store
from prometheus.library import publish as publish_mod
from prometheus.mindmap import enrich
from prometheus.mindmap.markdown import tree_to_markdown
from prometheus.subtitle import fix as subtitle_fix_mod
from prometheus.subtitle import paragraphs as subtitle_paragraphs

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
DICTIONARY_SAMPLE = FIXTURES / "ecdict.sample.csv"  # installed instead of the 23 MB ECDICT (PLAN 15.4.9)
# In fake mode this link fails in the download stage with Bilibili's risk control (PLAN 15.4.10 / E13 ②).
RISK_CONTROL_VIDEO = "BV412RiskCtl"


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


def _fake_fix(prompt: str) -> str:
    """A careful model for subtitle correction: keeps every text as it is and, when asked to
    translate (the English sample), joins the Chinese of the fixtures/segments.en.json fragments
    that make up each paragraph."""
    mark = subtitle_fix_mod.SEGMENTS_MARK
    batch = json.loads(prompt[prompt.index(mark) + len(mark):])
    if "中文翻译" not in prompt:
        return json.dumps(batch, ensure_ascii=False)
    english = json.loads(_fixture("segments.en.json").read_text(encoding="utf-8"))

    def translate(text: str) -> str:
        return "".join(segment["zh"] for segment in english if segment["text"] in text)

    return json.dumps({key: {"text": text, "zh": translate(text)} for key, text in batch.items()},
                      ensure_ascii=False)


def _english(data_dir, item_id: str) -> bool:
    """In fake mode a YouTube link stands for an English video (PLAN 15.4.9 / E12 ②)."""
    return items_store.get_item(data_dir, item_id)["platform"] == "youtube"


def build_impls(data_dir):
    """Stage implementations that copy committed fixtures into the item layout."""

    def resolve(ctx):
        info = json.loads(_fixture("source.info.json").read_text(encoding="utf-8"))
        if _english(data_dir, ctx.item_id):
            info = {**info, "source_title": "An English sample", "uploader": "English Sample Channel"}
        (paths.work_dir(data_dir, ctx.item_id) / "source.info.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        items_store.update_item(
            data_dir, ctx.item_id,
            source_title=info["source_title"], uploader=info["uploader"],
            duration_s=info["duration_s"],
        )

    def download(ctx):
        if items_store.get_item(data_dir, ctx.item_id)["video_id"] == RISK_CONTROL_VIDEO:
            # yt-dlp's own words for a 412 on the video page, wrapped like the real download stage.
            raise IngestError("DOWNLOAD_FAILURE", (
                f"ERROR: [BiliBili] {RISK_CONTROL_VIDEO}: Unable to download webpage: HTTP Error 412: "
                "Precondition Failed (caused by <HTTPError 412: Precondition Failed>)"
            ))

    def transcribe(ctx):
        segments = json.loads(_fixture("segments.json").read_text(encoding="utf-8"))
        if _english(data_dir, ctx.item_id):
            english = json.loads(_fixture("segments.en.json").read_text(encoding="utf-8"))
            segments = [{key: segment[key] for key in ("start", "end", "text")} for segment in english]
            (paths.work_dir(data_dir, ctx.item_id) / "asr.json").write_text(
                json.dumps({"language": "en", "segments": []}), encoding="utf-8")
        segments = subtitle_paragraphs.save(data_dir, ctx.item_id, segments)  # like a real transcription
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
        # A 完整 report also leaves its coverage (PLAN 15.4.11): the reader's 「要点 10/11」.
        shutil.copy2(_fixture("coverage.json"), paths.coverage_file(data_dir, ctx.item_id))

    def finalize(ctx):
        html = (_fixture("report.html")).read_text(encoding="utf-8")
        target = paths.report_file(data_dir, ctx.item_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        title = re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""
        items_store.update_item(data_dir, ctx.item_id, report_title=title)

    def subtitle_fix(ctx):
        # The real stage with a fake model: texts stay as they are, the English sample is translated.
        if not paths.segments_file(data_dir, ctx.item_id).is_file():  # tests may swap out its writer
            items_store.update_item(data_dir, ctx.item_id, subtitle_status="ok")
            return
        subtitle_fix_mod.fix_for_item(data_dir, ctx.item_id, items_store.get_item(data_dir, ctx.item_id), {},
                                      node_exe="", pi_cli="", ask=_fake_fix)

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
        # Like the real stage: only the first completion files the item (15.4.10).
        row = items_store.get_item(data_dir, ctx.item_id)
        category_id = row.get("category_id") or categories_store.ensure_category(data_dir, "未分类")
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
