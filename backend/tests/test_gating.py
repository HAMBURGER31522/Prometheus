"""Auth, data-dir gating and CORS (PLAN 8.1)."""

from conftest import TOKEN


def test_health_is_public(client_factory):
    response = client_factory().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_token_gets_401(client_factory):
    response = client_factory(data_dir=None).get("/api/settings")
    assert response.status_code == 401


def test_wrong_token_gets_401(client_factory):
    response = client_factory(data_dir=None).get(
        "/api/settings", headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_query_token_only_works_for_content_gets(client_factory, tmp_path):
    import time

    client = client_factory(data_dir=tmp_path / "data", fake=True)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    created = client.post("/api/items", headers=headers, json={
        "url": "https://www.bilibili.com/video/BV1xJYT6EEYc/", "figures": False,
    })
    item_id = created.json()["id"]
    deadline = time.time() + 15
    while time.time() < deadline:
        if client.get(f"/api/items/{item_id}", headers=headers).json().get("status") == "done":
            break
        time.sleep(0.05)
    report_url = f"/api/items/{item_id}/report"
    assert client.get(report_url).status_code == 401
    assert client.get(f"{report_url}?token={TOKEN}").status_code == 200
    assert client.get(f"/api/items?token={TOKEN}").status_code == 401
    assert client.get(f"/api/settings?token={TOKEN}").status_code == 401
    assert client.get(report_url, headers=headers).status_code == 200


def test_data_dir_gating(client_factory, tmp_path):
    client = client_factory(data_dir=None)
    gated = client.get("/api/settings", headers={"Authorization": f"Bearer {TOKEN}"})
    assert gated.status_code == 409
    assert gated.json() == {"code": "DATA_DIR_NOT_SET"}
    assert client.get("/api/health").status_code == 200

    read = client.get("/api/app/data-dir", headers={"Authorization": f"Bearer {TOKEN}"})
    assert read.status_code == 200
    assert read.json() == {"data_dir": None}

    target = tmp_path / "fresh-data"
    set_response = client.put(
        "/api/app/data-dir",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"data_dir": str(target)},
    )
    assert set_response.status_code == 200
    assert set_response.json() == {"data_dir": str(target)}
    # No restart needed: the same client can now use the gated API.
    assert client.get(
        "/api/settings", headers={"Authorization": f"Bearer {TOKEN}"}
    ).status_code == 200
    assert (target / "prometheus.db").is_file()


def test_cors_allows_only_listed_origins(client):
    allowed = client.get(
        "/api/health", headers={"Origin": "http://tauri.localhost"}
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://tauri.localhost"
    dev = client.get("/api/health", headers={"Origin": "http://localhost:1420"})
    assert dev.headers.get("access-control-allow-origin") == "http://localhost:1420"
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers
