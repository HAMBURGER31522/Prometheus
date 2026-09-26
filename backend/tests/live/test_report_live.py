"""M4/M6 live: real report generation, finalization, classification and mindmap
for the fixed M3 sample video (docs/acceptance.md), via any OpenAI-compatible
provider configured through the custom-provider path (D-25).

Credentials: PROMETHEUS_TEST_LLM_KEY (relay/provider key), optional
PROMETHEUS_TEST_LLM_BASE_URL / PROMETHEUS_TEST_LLM_MODEL overrides.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest
from prometheus import paths
from prometheus.library import categories as categories_store
from prometheus.library import db
from prometheus.library import items as items_store
from prometheus.report import mindmap as mindmap_mod
from prometheus.report import one_shot as one_shot_mod
from prometheus.report import workspace as workspace_mod
from prometheus.report.finalize import finalize_report
from prometheus.settings import pi_models, store
from prometheus.transcribe import components
from prometheus.transcribe import local as local_mod
from prometheus.transcribe.audio import to_wav
from prometheus.transcribe.transcript import build_transcript_md

pytestmark = pytest.mark.live

BV = "BV1bZhQ6VEQK"  # fixed sample, docs/acceptance.md
KEY = os.getenv("PROMETHEUS_TEST_LLM_KEY", "")
BASE_URL = os.getenv("PROMETHEUS_TEST_LLM_BASE_URL", "https://oapi.firedog.dev/v1")
MODEL = os.getenv("PROMETHEUS_TEST_LLM_MODEL", "gpt-6-sol")
PROXY = os.getenv("PROMETHEUS_TEST_PROXY", "")
NODE = os.getenv("PROMETHEUS_NODE") or "node"
PI_CLI = os.getenv("PROMETHEUS_PI_CLI") or (
    "E:/tools/Prometheus-Desktop/pi/node_modules/@earendil-works"
    "/pi-coding-agent/dist/bundle/cli.js"
)
DATA_DIR = Path(
    os.getenv("PROMETHEUS_TEST_DATA_DIR", "acceptance-output/live-data")
).resolve()

requires_key = pytest.mark.skipif(not KEY, reason="PROMETHEUS_TEST_LLM_KEY 未设置")


def _settings() -> dict:
    return {
        "llm": {
            "provider": "custom", "model": MODEL, "api_key": KEY, "thinking": "low",
            "custom": {"base_url": BASE_URL, "supports_images": False},
        },
        "asr": {"backend": "local", "dashscope_api_key": "", "cloud_model": "paraformer-v2"},
        "network": {"proxy": PROXY, "youtube_cookies_file": ""},
        "figures_default": False,
    }


def _ingest_and_transcribe():
    """Resolve → download → wav → local ASR → transcript.md for the fixed sample."""
    data_dir = paths.init_data_dir(DATA_DIR)
    db.init_db(data_dir)
    item_id = hashlib.sha1(f"bilibili:{BV}".encode()).hexdigest()[:32]
    work = paths.work_dir(data_dir, item_id)
    if (work / "transcript.md").is_file():
        stray = items_store.find_by_video(data_dir, "bilibili", BV)
        if stray is not None and stray["id"] != item_id:
            # Earlier attempts inserted the row under a generated id; realign it.
            items_store.delete_item(data_dir, stray["id"])
            stray = None
        if stray is None:
            info = json.loads((work / "source.info.json").read_text(encoding="utf-8"))
            items_store.create_item(
                data_dir, platform="bilibili", video_id=BV,
                source_url=f"https://www.bilibili.com/video/{BV}/",
                figures=0, status="done", item_id=item_id,
            )
            items_store.update_item(
                data_dir, item_id, source_title=info.get("title"),
                uploader=info.get("uploader"), duration_s=info.get("duration"),
                status="done",
            )
        row = items_store.get_item(data_dir, item_id)
        assert row is not None
        return data_dir, item_id, work, row, "zh"
    work.mkdir(parents=True, exist_ok=True)
    row = {
        "id": item_id, "platform": "bilibili", "video_id": BV,
        "source_url": f"https://www.bilibili.com/video/{BV}/", "figures": 0,
    }
    settings = store.load(data_dir)
    from prometheus.ingest import download as download_mod
    from prometheus.ingest import resolve as resolve_mod

    row.update(resolve_mod.resolve_stage(work, row, settings, NODE))
    audio = download_mod.download_stage(work, row, settings, NODE, media="audio")
    wav = to_wav(audio, work / "audio.wav")
    components.install_components(data_dir, proxy=PROXY)
    asr_path = local_mod.transcribe_local(data_dir, item_id, wav)
    payload = json.loads(asr_path.read_text(encoding="utf-8"))
    metadata = {
        "title": row["source_title"], "uploader": row["uploader"] or "",
        "attribution": f"Bilibili；{row['uploader'] or ''}；《{row['source_title']}》",
        "url": row["source_url"], "video_id": BV, "platform": "bilibili",
        "duration_s": row["duration_s"] or 0.0,
    }
    build_transcript_md(work, asr_path, metadata)
    items_store.create_item(
        data_dir, platform="bilibili", video_id=BV,
        source_url=row["source_url"], figures=0, status="done", item_id=item_id,
    )
    items_store.update_item(
        data_dir, item_id, source_title=row["source_title"], uploader=row["uploader"],
        duration_s=row["duration_s"], status="done",
    )
    row = items_store.get_item(data_dir, item_id)
    return data_dir, item_id, work, row, payload.get("language")


@requires_key
def test_report_generate_finalize_classify_mindmap():
    data_dir, item_id, work, row, language = _ingest_and_transcribe()
    store.save(data_dir, _settings())
    pi_models.ensure_models_json(data_dir)
    pi_models.apply_custom_provider(data_dir, _settings()["llm"]["custom"])

    report = workspace_mod.run_report_stage(
        data_dir, item_id, row, store.load(data_dir),
        node_exe=NODE, pi_cli=PI_CLI,
    )
    assert report.is_file()
    final = paths.report_file(data_dir, item_id)
    title = finalize_report(report, final, work)
    html = final.read_text(encoding="utf-8")
    assert title, "finalize must extract the h1 report title"
    assert html.count("data-source-units") >= 10
    assert "section-time" in html
    assert "Bilibili；" in html
    assert "{{VIDEO_DESCRIPTION}}" not in html
    import re

    assert not re.search(
        r"<(?:img|script|link|iframe)\b[^>]*?\b(?:src|href)\s*=\s*['\"](?:https?:)?//",
        html, re.IGNORECASE,
    )
    items_store.update_item(data_dir, item_id, report_title=title)

    outline = mindmap_mod.extract_outline(html)
    h2_titles = [section["title"] for section in outline["sections"]]
    existing = [c["name"] for c in categories_store.list_categories(data_dir)]
    llm = store.load(data_dir)["llm"]

    def one_shot(work_dir, *, prompt, **kwargs):
        return one_shot_mod.run_one_shot(
            work_dir, prompt=prompt, provider=llm["provider"], model=llm["model"],
            api_key=llm.get("api_key") or "", thinking=llm.get("thinking") or "low",
            node_exe=NODE, pi_cli=PI_CLI, agent_dir=paths.pi_config_dir(data_dir),
        )

    from prometheus.report.classify import classify_report

    category = classify_report(
        work, title, outline["intro"][:500], h2_titles, existing, one_shot=one_shot,
    )
    category_id = categories_store.ensure_category(data_dir, category)
    items_store.update_item(data_dir, item_id, category_id=category_id)
    row = items_store.get_item(data_dir, item_id)
    assert row["category_id"] is not None

    prompt = mindmap_mod.build_mindmap_prompt(outline, "bilibili", BV)
    mindmap_text = one_shot(work, prompt=prompt)
    errors = mindmap_mod.validate_mindmap(
        mindmap_text, expect_title=title, branch_count=(3, 7),
    )
    assert not errors, f"mindmap validation failed: {errors}"
    target = paths.mindmap_file(data_dir, item_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(mindmap_text + "\n", encoding="utf-8")
    items_store.update_item(data_dir, item_id, mindmap_status="ok")
