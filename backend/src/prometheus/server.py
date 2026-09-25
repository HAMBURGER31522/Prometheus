"""Prometheus backend application factory."""

from fastapi import FastAPI


def create_app(token: str) -> FastAPI:
    return FastAPI()
