import html
import json

import pytest

from video_report_agent.report_content import (
    VIDEO_DESCRIPTION_END,
    VIDEO_DESCRIPTION_PLACEHOLDER,
    VIDEO_DESCRIPTION_START,
    fill_video_description,
)


def make_run(tmp_path, description_marker=True):
    (tmp_path / "download").mkdir()
    if description_marker:
        (tmp_path / "download/source.info.json").write_text(
            json.dumps({"description": description_marker}), encoding="utf-8"
        )
    report = tmp_path / "report.html"
    report.write_text(
        f"<html><body>{VIDEO_DESCRIPTION_PLACEHOLDER}<p>正文</p></body></html>", encoding="utf-8",
    )
    return report


def test_fills_escaped_multiline_description_and_is_idempotent(tmp_path):
    raw = "  第一行 <b>原文</b> &\nhttps://example.com/" + "x" * 300 + "  "
    report = make_run(tmp_path, raw)
    before = report.read_text(encoding="utf-8")

    fill_video_description(report, tmp_path)
    filled = report.read_text(encoding="utf-8")
    fill_video_description(report, tmp_path)

    assert report.read_text(encoding="utf-8") == filled
    assert filled.count(VIDEO_DESCRIPTION_START) == 1
    assert filled.count(VIDEO_DESCRIPTION_END) == 1
    assert f'<div class="video-description-text">{html.escape(raw)}</div>' in filled
    assert "<b>原文</b>" not in filled
    assert before != filled


@pytest.mark.parametrize("metadata", [{}, {"description": "   "}, {"description": 123}])
def test_empty_missing_or_non_string_description_is_omitted(tmp_path, metadata):
    report = make_run(tmp_path, True)
    (tmp_path / "download/source.info.json").write_text(json.dumps(metadata), encoding="utf-8")

    fill_video_description(report, tmp_path)

    assert VIDEO_DESCRIPTION_PLACEHOLDER not in report.read_text(encoding="utf-8")
    assert VIDEO_DESCRIPTION_START not in report.read_text(encoding="utf-8")


def test_bad_json_is_explicit_error(tmp_path):
    report = make_run(tmp_path, True)
    (tmp_path / "download/source.info.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON.*source.info.json"):
        fill_video_description(report, tmp_path)


def test_non_empty_description_requires_one_placeholder_or_boundary(tmp_path):
    report = make_run(tmp_path, "简介")
    report.write_text("<html><body><p>正文</p></body></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="requires one"):
        fill_video_description(report, tmp_path)


def test_duplicate_placeholder_and_malformed_boundary_are_errors(tmp_path):
    report = make_run(tmp_path, True)
    report.write_text(
        f"{VIDEO_DESCRIPTION_PLACEHOLDER}{VIDEO_DESCRIPTION_PLACEHOLDER}", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        fill_video_description(report, tmp_path)

    report.write_text(f"{VIDEO_DESCRIPTION_START}<details>", encoding="utf-8")
    with pytest.raises(ValueError, match="boundaries"):
        fill_video_description(report, tmp_path)


def test_no_description_without_placeholder_leaves_report_untouched(tmp_path):
    report = make_run(tmp_path, True)
    report.write_text("<html><body><p>正文</p></body></html>", encoding="utf-8")
    (tmp_path / "download/source.info.json").write_text("{}", encoding="utf-8")
    original = report.read_text(encoding="utf-8")

    fill_video_description(report, tmp_path)

    assert report.read_text(encoding="utf-8") == original
