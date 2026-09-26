"""Finalize: description fill, image inlining, style injection, checks (PLAN 8.6)."""

import base64
import json

import pytest
from prometheus.report.finalize import (
    FinalizeError,
    extract_report_title,
    finalize_report,
)

TEMPLATE = """<html><head><title>t</title></head><body>
<h1>财政再平衡</h1>
<p>{{VIDEO_DESCRIPTION}}</p>
<figure class="report-figure"><img src="frames/f_000010.jpg"><figcaption>要点 · 00:10</figcaption></figure>
<p>结尾</p></body></html>"""


def _work(tmp_path, html=TEMPLATE, description="这是简介。"):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / "report.html").write_text(html, encoding="utf-8")
    # vendor reads <work>/download/source.info.json; PLAN 7 keeps a root copy
    (work / "source.info.json").write_text(
        json.dumps({"description": description}), encoding="utf-8",
    )
    (work / "download").mkdir(exist_ok=True)
    (work / "download" / "source.info.json").write_text(
        json.dumps({"description": description}), encoding="utf-8",
    )
    frames = work / "frames"
    frames.mkdir(exist_ok=True)
    (frames / "f_000010.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    return work


def test_finalize_fills_inline_and_extracts(tmp_path):
    work = _work(tmp_path)
    final = tmp_path / "report" / "report.html"
    title = finalize_report(work / "report.html", final, work)
    html = final.read_text(encoding="utf-8")
    assert "这是简介。" in html
    assert "{{VIDEO_DESCRIPTION}}" not in html
    encoded = base64.b64encode(b"\xff\xd8\xff\xe0fake-jpeg").decode()
    assert f'data:image/jpeg;base64,{encoded}' in html
    assert 'src="frames/' not in html
    assert "<style>" in html and "var(--line)" in html and "var(--muted)" in html
    assert "13px" in html
    assert title == "财政再平衡"


def test_finalize_without_figures_skips_style(tmp_path):
    html = TEMPLATE.split("<figure")[0] + "</body></html>"
    work = _work(tmp_path, html=html)
    final = tmp_path / "report" / "report.html"
    finalize_report(work / "report.html", final, work)
    assert "<style>" not in final.read_text(encoding="utf-8")


def test_finalize_rejects_external_references(tmp_path):
    html = TEMPLATE.replace('src="frames/f_000010.jpg"', 'src="https://cdn.example.com/x.jpg"')
    work = _work(tmp_path, html=html)
    with pytest.raises(FinalizeError):
        finalize_report(work / "report.html", tmp_path / "out.html", work)


def test_finalize_inserts_missing_placeholder_after_h1(tmp_path):
    html = "<html><head></head><body><h1>标题</h1><p>正文没有占位符</p></body></html>"
    work = _work(tmp_path, html=html)
    final = tmp_path / "report" / "report.html"
    finalize_report(work / "report.html", final, work)
    filled = final.read_text(encoding="utf-8")
    assert "这是简介。" in filled
    assert "{{VIDEO_DESCRIPTION}}" not in filled
    assert filled.index("这是简介。") < filled.index("正文没有占位符")


def test_extract_report_title():
    assert extract_report_title("<html><body><h1>标题 <b>加粗</b></h1></body></html>") == "标题 加粗"
