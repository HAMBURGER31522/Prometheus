"""Shared fixtures for the backend test suite."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from prometheus.runtime import Runtime
from prometheus.server import create_app

TOKEN = "test-token"
BV_URL = "https://www.bilibili.com/video/BV1xJYT6EEYc/"
# Paths only; unit tests never execute them (CI has no toolchain).
DUMMY_RUNTIME = Runtime(Path("node.exe"), Path("cli.js"), Path("ffmpeg.exe"), Path("ffprobe.exe"))


@pytest.fixture
def client_factory():
    created = []

    def factory(data_dir=None, fake=False):
        app = create_app(token=TOKEN, data_dir=data_dir, fake=fake, runtime=DUMMY_RUNTIME)
        client = TestClient(app)
        client.__enter__()
        created.append(client)
        return client

    yield factory
    for client in created:
        client.__exit__(None, None, None)


@pytest.fixture
def client(client_factory, tmp_path):
    authorized = client_factory(data_dir=tmp_path / "data", fake=True)
    authorized.headers["Authorization"] = f"Bearer {TOKEN}"
    return authorized


def wait_for_status(client, item_id, status, timeout=15.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/items/{item_id}")
        last = response.json()
        if last.get("status") == status:
            return last
        time.sleep(0.05)
    raise AssertionError(f"item {item_id} never reached {status!r}, last={last!r}")


def pytest_collection_modifyitems(config, items):
    """-m agents runs the real private CLIs (PLAN 15.4.13); every other selection leaves them out."""
    if "agents" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="runs the app's own Codex CLI and Claude Code: use -m agents")
    for item in items:
        if "agents" in item.keywords:
            item.add_marker(skip)
