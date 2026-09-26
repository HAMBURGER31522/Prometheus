"""Model capability parsing from `pi --offline --list-models` (PLAN 8.7)."""

from prometheus.llm.capability import model_supports_images, parse_capabilities

LIST_OUTPUT = """provider  model                         context  max-out  thinking  images
deepseek  deepseek-flash                1M       384K     yes       yes
deepseek  deepseek-v4-flash             1M       384K     yes       no
zhipu     glm-5.3-flash                 128K     65.5K    yes       no
"""


def test_parse_capabilities():
    caps = parse_capabilities(LIST_OUTPUT)
    assert caps["deepseek-flash"] is True
    assert caps["deepseek-v4-flash"] is False
    assert caps["glm-5.3-flash"] is False


def test_model_supports_images():
    assert model_supports_images(LIST_OUTPUT, "deepseek-flash") is True
    assert model_supports_images(LIST_OUTPUT, "deepseek-v4-flash") is False
    assert model_supports_images(LIST_OUTPUT, "unknown-model") is False


def test_no_models_available_means_no_images():
    assert model_supports_images("No models available", "deepseek-flash") is False


def test_capability_query_uses_the_data_dir_config_and_the_key(tmp_path, monkeypatch):
    import subprocess

    from prometheus import paths
    from prometheus.llm import capability

    seen = {}

    def fake_run(command, **kwargs):
        seen["command"], seen["env"] = command, kwargs.get("env") or {}
        return subprocess.CompletedProcess(command, 0, LIST_OUTPUT.encode(), b"")

    monkeypatch.setattr(capability.subprocess, "run", fake_run, raising=False)
    llm = {"provider": "deepseek", "model": "deepseek-flash", "api_key": "sk-key"}
    assert capability.query_supports_images("node.exe", "cli.js", tmp_path, llm) is True
    assert seen["command"][:4] == ["node.exe", "cli.js", "--offline", "--list-models"]
    assert seen["env"]["PI_CODING_AGENT_DIR"] == str(paths.pi_config_dir(tmp_path))
    assert seen["env"]["PI_API_KEY"] == "sk-key"
    assert seen["env"]["DEEPSEEK_API_KEY"] == "sk-key"
