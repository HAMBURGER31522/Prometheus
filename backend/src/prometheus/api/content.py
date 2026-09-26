"""Content endpoints served from item folders (PLAN 8.2).

These are the content-class GETs that also accept ?token= for the iframe.
"""

import json

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus import paths
from prometheus.subtitle import format as subtitle_format

router = APIRouter()


def _read_or_none(path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


# Served-time injection (PLAN 9.3): the iframe hands external links to the shell
# instead of loading them in-app. The file on disk is never modified.
_OPEN_EXTERNAL_SCRIPT = """
<script>
document.addEventListener("click", function (event) {
  var anchor = event.target.closest && event.target.closest('a[href^="http"]');
  if (!anchor) return;
  event.preventDefault();
  parent.postMessage({ type: "open-external", href: anchor.href }, "*");
}, true);
</script>
</body>"""


@router.get("/api/items/{item_id}/report")
async def report(request: Request, item_id: str):
    text = _read_or_none(paths.report_file(request.app.state.data_dir, item_id))
    if text is None:
        return JSONResponse({"code": "REPORT_NOT_READY"}, status_code=404)
    if "</body>" in text:
        text = text.replace("</body>", _OPEN_EXTERNAL_SCRIPT, 1)
    else:
        text = text + _OPEN_EXTERNAL_SCRIPT
    return Response(text, media_type="text/html")


@router.get("/api/items/{item_id}/mindmap")
async def mindmap(request: Request, item_id: str):
    text = _read_or_none(paths.mindmap_file(request.app.state.data_dir, item_id))
    if text is None:
        return JSONResponse({"code": "MINDMAP_NOT_READY"}, status_code=404)
    return Response(text, media_type="text/markdown")


@router.get("/api/items/{item_id}/subtitle")
async def subtitle(request: Request, item_id: str, format: str = "json"):
    file = paths.segments_file(request.app.state.data_dir, item_id)
    if not file.is_file():
        return JSONResponse({"code": "SUBTITLE_NOT_READY"}, status_code=404)
    segments = json.loads(file.read_text(encoding="utf-8"))
    if format == "json":
        return segments
    if format == "srt":
        return Response(subtitle_format.to_srt(segments), media_type="text/plain")
    if format == "txt":
        return Response(subtitle_format.to_txt(segments), media_type="text/plain")
    return JSONResponse({"code": "UNSUPPORTED_FORMAT"}, status_code=422)
