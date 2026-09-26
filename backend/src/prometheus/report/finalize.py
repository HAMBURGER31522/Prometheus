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
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_FRAME_SRC_RE = re.compile(r'src="frames/([^"]+)"')
_EXTERNAL_RE = re.compile(
    r"<(?:img|script|link|iframe)\b[^>]*?\b(?:src|href)\s*=\s*['\"](?:https?:)?//",
    re.IGNORECASE,
)


def extract_report_title(html: str) -> str:
    match = _H1_RE.search(html)
    return _TAG_RE.sub("", match.group(1)).strip() if match else ""


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
    external = _EXTERNAL_RE.search(html)
    if external:
        raise FinalizeError(
            "报告包含外部资源引用，不能交付：" + html[external.start():external.start() + 80]
        )
    title = extract_report_title(html)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(html, encoding="utf-8")
    return title
