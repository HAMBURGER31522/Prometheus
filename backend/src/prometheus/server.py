"""Prometheus backend: application factory, auth middleware and CLI entry."""

import argparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Only this endpoint is reachable without the bearer token (PLAN 8.1).
PUBLIC_ENDPOINTS = {("GET", "/api/health")}


def create_app(token: str) -> FastAPI:
    app = FastAPI(title="Prometheus")

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

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Prometheus backend server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(token=args.token), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
