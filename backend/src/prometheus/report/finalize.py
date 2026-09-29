"""Report finalization (PLAN 8.6): description fill, image inlining, style, checks."""

import base64
import re
import shutil
from pathlib import Path

from video_report_agent.report_content import fill_video_description


class FinalizeError(RuntimeError):
    code = "IMPLEMENTATION_FAILURE"

_FIGURE_STYLE = (
    "<style>figure.report-figure{margin:24px 0;border:1px solid var(--line);"
    "border-radius:6px;padding:12px}"
    "figure.report-figure figcaption{color:var(--muted);font-size:13px;"
    "margin-top:8px}</style>"
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_FRAME_SRC_RE = re.compile(r'src="frames/([^"]+)"')
_EXTERNAL_RE = re.compile(
    r"<(?:img|script|link|iframe)\b[^>]*?\b(?:src|href)\s*=\s*['\"](?:https?:)?//",
    re.IGNORECASE,
)


def extract_report_title(html: str) -> str:
    match = _H1_RE.search(html)
    return _TAG_RE.sub("", match.group(1)).strip() if match else ""


# 「补充说明（非视频内容）」(PLAN 15.4.11): set apart from the video's own words, template colours only.
_SUPPLEMENT_STYLE_ID = "prometheus-supplement"
_SUPPLEMENT_STYLE = (
    f'<style id="{_SUPPLEMENT_STYLE_ID}">aside.supplement{{margin:14px 0 18px;padding:12px 16px;'
    "border:1px dashed var(--line);border-radius:8px;background:var(--wash);font-size:15px}"
    "aside.supplement .supplement-label{margin:0 0 6px;font-size:12px;color:var(--muted)}"
    "aside.supplement p{margin:0 0 6px}aside.supplement p:last-child{margin-bottom:0}</style>"
)

# 「编者观点（非视频内容）」(PLAN 15.4.11a): the editor's own view, set apart from supplements too.
_VIEWPOINT_STYLE_ID = "prometheus-viewpoint"
_VIEWPOINT_STYLE = (
    f'<style id="{_VIEWPOINT_STYLE_ID}">aside.viewpoint{{margin:14px 0 18px;padding:12px 16px;'
    "border-left:3px solid var(--accent);border-radius:4px;background:var(--wash);font-size:15px}"
    "aside.viewpoint .viewpoint-label{margin:0 0 6px;font-size:12px;color:var(--accent)}"
    "aside.viewpoint ul{margin:0;padding-left:1.2em}aside.viewpoint li{margin:0 0 6px}"
    "aside.viewpoint .confidence{margin-left:6px;font-size:12px;color:var(--muted)}</style>"
)


def finalize_report(work_report, final_path, work_dir) -> str:
    work_report = Path(work_report)
    final_path = Path(final_path)
    work_dir = Path(work_dir)
    # vendor's fill_video_description reads <work>/download/source.info.json
    # (vendor layout); PLAN 7 keeps the file at the work root, so mirror it.
    download_dir = work_dir / "download"
    if not (download_dir / "source.info.json").is_file() and (work_dir / "source.info.json").is_file():
        download_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(work_dir / "source.info.json", download_dir / "source.info.json")
    html = work_report.read_text(encoding="utf-8")
    has_boundary = (
        "<!-- VIDEO_DESCRIPTION_START -->" in html
        or "<!-- VIDEO_DESCRIPTION_END -->" in html
    )
    if "{{VIDEO_DESCRIPTION}}" not in html and not has_boundary and "</h1>" in html.lower():
        # Agents sometimes drop the template placeholder; re-anchor it after the
        # h1 so the description disclosure can still be placed (PLAN 8.6).  A
        # filled boundary block is already idempotent under fill_video_description.
        html = re.sub(
            r"(</h1>)", r'\1\n    <p>{{VIDEO_DESCRIPTION}}</p>', html,
            count=1, flags=re.IGNORECASE,
        )
        work_report.write_text(html, encoding="utf-8")
    fill_video_description(work_report, work_dir)
    html = work_report.read_text(encoding="utf-8")

    def _inline(match: re.Match) -> str:
        name = match.group(1)
        frame = work_dir / "frames" / name
        if not frame.is_file():
            raise FinalizeError(f"配图文件缺失：frames/{name}")
        encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
        return f'src="data:image/jpeg;base64,{encoded}"'

    html = _FRAME_SRC_RE.sub(_inline, html)
    if '<figure class="report-figure"' in html and "<style>" not in html:
        html = html.replace("</head>", _FIGURE_STYLE + "</head>", 1)
    if '<aside class="supplement"' in html and _SUPPLEMENT_STYLE_ID not in html:
        html = html.replace("</head>", _SUPPLEMENT_STYLE + "</head>", 1)
    if '<aside class="viewpoint"' in html and _VIEWPOINT_STYLE_ID not in html:
        html = html.replace("</head>", _VIEWPOINT_STYLE + "</head>", 1)
    external = _EXTERNAL_RE.search(html)
    if external:
        raise FinalizeError(
            "报告包含外部资源引用，不能交付：" + html[external.start():external.start() + 80]
        )
    title = extract_report_title(html)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(html, encoding="utf-8")
    return title
