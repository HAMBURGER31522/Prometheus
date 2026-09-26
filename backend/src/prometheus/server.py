"""Prometheus backend: application factory, auth middleware and CLI entry."""

import argparse
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from prometheus.api import app as app_api
from prometheus.api import categories as categories_api
from prometheus.api import content as content_api
from prometheus.api import items as items_api
from prometheus.api import settings as settings_api

# Only this endpoint is reachable without the bearer token (PLAN 8.1).
PUBLIC_ENDPOINTS = {("GET", "/api/health")}

CORS_ORIGINS = ["http://tauri.localhost", "http://localhost:1420"]


def create_app(token: str, data_dir: str | Path | None = None, fake: bool | None = None):
    app = FastAPI(title="Prometheus")
    app.state.token = token
    app.state.data_dir = Path(data_dir) if data_dir is not None else None
    app.state.fake = bool(fake)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        if (request.method, request.scope["path"]) in PUBLIC_ENDPOINTS:
            return await call_next(request)
        authorization = request.headers.get("Authorization", "")
        if authorization != f"Bearer {token}":
            return JSONResponse({"code": "UNAUTHORIZED"}, status_code=401)
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(app_api.router)
    app.include_router(items_api.router)
    app.include_router(categories_api.router)
    app.include_router(content_api.router)
    app.include_router(settings_api.router)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Prometheus backend server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", required=True)
    parser.add_argument("--config-dir", default=None)
    parser.add_argument("--runtime-dir", default=None)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(token=args.token), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
