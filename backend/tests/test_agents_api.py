"""The three Agents' versions, 「检查」「更新」「安装」「全部更新」 and the Codex login (PLAN 15.4.13).
The fake backend simulates them; the real one reports what is installed."""

AUTH = {"Authorization": "Bearer test-token"}


def _answer(response):
    assert response.status_code == 200, response.status_code
    return {row["id"]: row for row in response.json()["agents"]}


def _rows(client):
    return _answer(client.get("/api/agents", headers=AUTH))


def test_three_agents_with_their_installed_versions(client):
    rows = _rows(client)
    assert list(rows) == ["pi", "codex", "claude"]
    assert [row["name"] for row in rows.values()] == ["Pi", "Codex CLI", "Claude Code"]
    assert rows["pi"]["installed"] and rows["pi"]["version"]
    assert rows["claude"]["installed"] is False and rows["claude"]["version"] is None
    assert all(row["latest"] is None for row in rows.values())


def test_check_finds_the_latest_versions_and_update_all_brings_everything_there(client):
    checked = _answer(client.post("/api/agents/check", headers=AUTH))
    assert all(row["latest"] for row in checked.values())
    assert checked["codex"]["version"] != checked["codex"]["latest"]
    updated = _answer(client.post("/api/agents/update-all", headers=AUTH))
    assert all(row["installed"] and row["version"] == row["latest"] for row in updated.values())


def test_installing_one_agent_leaves_the_others_alone(client):
    before = _rows(client)
    installed = _answer(client.post("/api/agents/claude/install", headers=AUTH))
    assert installed["claude"]["installed"] and installed["claude"]["version"]
    assert installed["codex"]["version"] == before["codex"]["version"]
    assert client.post("/api/agents/gemini/install", headers=AUTH).status_code == 404


def test_the_codex_login_shows_its_state_and_signs_in(client):
    status = client.get("/api/agents/codex/login", headers=AUTH)
    assert status.status_code == 200 and status.json()["logged_in"] is False
    assert client.post("/api/agents/codex/login", headers=AUTH).json()["logged_in"] is True
    assert client.get("/api/agents/codex/login", headers=AUTH).json()["logged_in"] is True


def test_the_real_backend_reports_codex_and_claude_code_as_not_installed_until_their_copies_exist(client_factory, tmp_path):
    real = client_factory(data_dir=tmp_path / "data", fake=False)
    rows = _answer(real.get("/api/agents", headers=AUTH))
    assert rows["codex"]["installed"] is False and rows["claude"]["installed"] is False
    assert rows["pi"]["installed"] is True
