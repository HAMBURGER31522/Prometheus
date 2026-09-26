"""Shared fixtures for the backend test suite."""

import time

import pytest
from fastapi.testclient import TestClient
from prometheus.server import create_app

TOKEN = "test-token"
BV_URL = "https://www.bilibili.com/video/BV1xJYT6EEYc/"


@pytest.fixture
def client_factory():
    created = []

    def factory(data_dir=None, fake=False):
        app = create_app(token=TOKEN, data_dir=data_dir, fake=fake)
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


def wait_for_status(client, item_id, status, timeout=5.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/items/{item_id}")
        last = response.json()
        if last.get("status") == status:
            return last
        time.sleep(0.05)
    raise AssertionError(f"item {item_id} never reached {status!r}, last={last!r}")
