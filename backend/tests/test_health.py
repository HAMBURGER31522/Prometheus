"""M0: /api/health needs no auth; every other /api path requires the bearer token."""

from fastapi.testclient import TestClient
from prometheus.server import create_app

TOKEN = "test-token"


def make_client() -> TestClient:
    return TestClient(create_app(token=TOKEN))


def test_health_requires_no_auth():
    response = make_client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_token_gets_401():
    response = make_client().get("/api/settings")
    assert response.status_code == 401


def test_wrong_token_gets_401():
    client = make_client()
    response = client.get("/api/settings", headers={"Authorization": f"Bearer wrong-{TOKEN}"})
    assert response.status_code == 401


def test_correct_token_passes_auth():
    client = make_client()
    response = client.get("/api/settings", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code != 401
