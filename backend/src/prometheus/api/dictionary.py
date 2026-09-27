"""Hover lookup endpoints for English subtitles (PLAN 15.4.9): the offline dictionary is a
local component downloaded on first use; fake mode installs a small sample instead."""

import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus.dictionary import ecdict

router = APIRouter()
_lock = threading.Lock()


def _state(request: Request) -> dict:
    with _lock:
        if not hasattr(request.app.state, "dictionary"):
            request.app.state.dictionary = {"thread": None, "error": None, "done": 0, "total": None}
        return request.app.state.dictionary


@router.get("/api/dictionary")
async def status(request: Request):
    state = _state(request)
    with _lock:
        if state["thread"] is not None and state["thread"].is_alive():
            progress = state["done"] / state["total"] if state["total"] else None
            return {"state": "installing", "detail": "正在下载离线词典…", "progress": progress}
        if ecdict.installed(request.app.state.data_dir):
            return {"state": "ready", "detail": "离线词典已就绪", "progress": 1.0}
        if state["error"]:
            return {"state": "failed", "detail": state["error"], "progress": None}
    return {"state": "idle", "detail": f"离线词典 ECDICT，首次使用需下载（约 {ecdict.DOWNLOAD_MB}MB）", "progress": None}


@router.post("/api/dictionary/install")
async def install(request: Request):
    state = _state(request)
    data_dir = request.app.state.data_dir
    if request.app.state.fake:
        from prometheus.fake.pipeline import DICTIONARY_SAMPLE

        source = str(DICTIONARY_SAMPLE)
    else:
        source = ecdict.SOURCE
    from prometheus.settings import store

    proxy = (store.load(data_dir).get("network") or {}).get("proxy", "")

    def report(done, total):
        state["done"], state["total"] = done, total

    def worker():
        try:
            ecdict.install(data_dir, source=source, proxy=proxy, progress=report)
        except ecdict.DictionaryInstallError as exc:
            with _lock:
                state["error"] = str(exc)[:300]

    with _lock:
        if state["thread"] is not None and state["thread"].is_alive():
            return {"started": False, "detail": "已在下载中"}
        state.update(thread=threading.Thread(target=worker, daemon=True), error=None, done=0, total=None)
        state["thread"].start()
    return {"started": True}


@router.get("/api/dictionary/lookup")
async def lookup(request: Request, word: str):
    try:
        entry = ecdict.lookup(request.app.state.data_dir, word)
    except ecdict.NotInstalled:
        return JSONResponse({"code": "DICTIONARY_NOT_INSTALLED"}, status_code=409)
    if entry is None:
        return JSONResponse({"code": "WORD_NOT_FOUND"}, status_code=404)
    return entry
