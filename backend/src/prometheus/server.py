"""Prometheus backend: application factory, auth middleware and CLI entry."""

import argparse
import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus import paths
from prometheus.api import app as app_api
from prometheus.api import asr_components as asr_components_api
from prometheus.api import categories as categories_api
from prometheus.api import content as content_api
from prometheus.api import items as items_api
from prometheus.api import settings as settings_api
from prometheus.fake.pipeline import build_impls as build_fake_impls
from prometheus.library import db
from prometheus.settings import pi_models
from prometheus.tasks.queue import TaskQueue
from prometheus.tasks.stages import build_real_impls

# Only this endpoint is reachable without the bearer token (PLAN 8.1).
PUBLIC_ENDPOINTS = {("GET", "/api/health")}

# Content-class GETs for the iframe additionally accept ?token= (PLAN 8.1).
CONTENT_PATH_RE = re.compile(r"^/api/items/[^/]+/(report|mindmap|subtitle)$")

CORS_ORIGINS = ["http://tauri.localhost", "http://localhost:1420"]


class AppState:
    def __init__(self, fake: bool | None):
        self.data_dir: Path | None = None
        self.config_dir: Path | None = None
        self.queue: TaskQueue | None = None
        self.fake = bool(os.getenv("PROMETHEUS_FAKE") == "1") if fake is None else fake

    def initialize(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        paths.init_data_dir(self.data_dir)
        db.init_db(self.data_dir)
        pi_models.ensure_models_json(self.data_dir)
        # Startup recovery (PLAN 7.1): a running row means the process died.
        db.mark_running_as_interrupted(self.data_dir)
        if self.queue is None:
            impls = build_fake_impls(self.data_dir) if self.fake else build_real_impls(self.data_dir)
            self.queue = TaskQueue(self.data_dir, impls)
            self.queue.start()

    def shutdown(self) -> None:
        if self.queue is not None:
            self.queue.stop()
            self.queue = None


def create_app(
    token: str,
    data_dir: str | Path | None = None,
    fake: bool | None = None,
    config_dir: str | Path | None = None,
):
    app = FastAPI(title="Prometheus")
    state = AppState(fake)
    if data_dir is not None:
        state.data_dir = Path(data_dir)
    state.config_dir = Path(config_dir) if config_dir else None
    app.state = state
    app.state.token = token

    @app.middleware("http")
    async def auth_and_gating(request: Request, call_next):
        path = request.scope["path"]
        method = request.method
        if (method, path) in PUBLIC_ENDPOINTS:
            return await call_next(request)
        authorized = request.headers.get("Authorization", "") == f"Bearer {token}"
        if not authorized and method == "GET" and CONTENT_PATH_RE.match(path):
            authorized = request.query_params.get("token") == token
        if not authorized:
            return JSONResponse({"code": "UNAUTHORIZED"}, status_code=401)
        if state.data_dir is None and path != "/api/app/data-dir":
            return JSONResponse({"code": "DATA_DIR_NOT_SET"}, status_code=409)
        return await call_next(request)

    # Registered last so CORS wraps the auth middleware: the browser's OPTIONS
    # preflight must be answered here, not rejected by the 401 gate.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.on_event("startup")
    async def startup() -> None:
        if state.data_dir is not None:
            state.initialize(state.data_dir)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        state.shutdown()

    app.include_router(app_api.router)
    app.include_router(items_api.router)
    app.include_router(categories_api.router)
    app.include_router(content_api.router)
    app.include_router(settings_api.router)
    app.include_router(asr_components_api.router)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Prometheus backend server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", required=True)
    parser.add_argument("--config-dir", default=None)
    parser.add_argument("--runtime-dir", default=None)
    args = parser.parse_args()

    # Test mode (PLAN 8.1): skip first-run data-dir selection; fake pipeline for E2E.
    data_dir = os.getenv("PROMETHEUS_TEST_DATA_DIR")
    fake = os.getenv("PROMETHEUS_FAKE") == "1" or None

    # Installed runs persist the chosen data dir in <config-dir>/app.json.
    config_dir = args.config_dir
    if config_dir and not data_dir:
        app_json = Path(config_dir) / "app.json"
        if app_json.is_file():
            data_dir = json.loads(app_json.read_text(encoding="utf-8")).get("data_dir")

    import uvicorn

    uvicorn.run(
        create_app(token=args.token, data_dir=data_dir, fake=fake, config_dir=config_dir),
        host=args.host, port=args.port, log_level="info",
    )


if __name__ == "__main__":
    main()
