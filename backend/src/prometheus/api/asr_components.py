"""Local-ASR component install endpoints (PLAN 8.2/8.5)."""

import threading

from fastapi import APIRouter, Request
from prometheus.transcribe import components

router = APIRouter()

_state = {"thread": None, "detail": "尚未安装", "error": None}
_lock = threading.Lock()


def _progress() -> dict:
    with _lock:
        if _state["thread"] is not None and _state["thread"].is_alive():
            return {"state": "installing", "detail": "正在下载并安装 CUDA 运行库…"}
        if _state["error"]:
            return {"state": "failed", "detail": _state["error"]}
        if _state["thread"] is not None:
            return {"state": "ready", "detail": "本地转写组件已就绪"}
        return {"state": "idle", "detail": _state["detail"]}


@router.post("/api/asr-components/install")
async def install(request: Request):
    with _lock:
        if _state["thread"] is not None and _state["thread"].is_alive():
            return {"started": False, "detail": "已在安装中"}
        from prometheus.settings import store

        settings = store.load(request.app.state.data_dir)
        proxy = (settings.get("network") or {}).get("proxy", "")
        data_dir = request.app.state.data_dir

        def worker():
            try:
                components.install_components(data_dir, proxy=proxy)
            except Exception as exc:  # noqa: BLE001 - surfaced via /status
                with _lock:
                    _state["error"] = str(exc)[:300]

        thread = threading.Thread(target=worker, daemon=True)
        _state["thread"] = thread
        _state["error"] = None
        thread.start()
    return {"started": True}


@router.get("/api/asr-components")
async def status():
    return _progress()
