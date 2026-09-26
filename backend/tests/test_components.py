"""CUDA component install command (PLAN 8.5 components.py)."""

from prometheus.transcribe.components import build_pip_cmd


def test_pip_command_pins_cuda_libraries(tmp_path):
    command = build_pip_cmd(tmp_path, proxy="http://127.0.0.1:7897")
    assert "pip" in command
    assert "--target" in command
    target = command[command.index("--target") + 1]
    assert str(tmp_path) in target or target == str(tmp_path)
    assert "nvidia-cublas-cu12==12.9.2.10" in command
    assert "nvidia-cudnn-cu12==9.26.0.51" in command
    assert "--proxy" in command
    assert command[command.index("--proxy") + 1] == "http://127.0.0.1:7897"


def test_pip_command_without_proxy(tmp_path):
    command = build_pip_cmd(tmp_path, proxy="")
    assert "--proxy" not in command


def test_install_falls_back_to_uv_when_pip_missing(tmp_path, monkeypatch):
    """uv-managed dev venvs ship without pip; uv must take over (proxy via env)."""
    import subprocess as sp

    from prometheus.transcribe import components

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("env")))
        if command[:3] == [sys_executable(), "-m", "pip"]:
            return sp.CompletedProcess(command, 1, b"", b"No module named pip")
        return sp.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(components.subprocess, "run", fake_run)
    monkeypatch.setattr(
        components.shutil, "which", lambda name: "C:/tools/uv/uv.exe" if name == "uv" else None
    )
    monkeypatch.setenv("HTTP_PROXY", "")
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    components.install_components(tmp_path, proxy="http://127.0.0.1:7897")

    assert len(calls) == 2
    uv_command, env = calls[1]
    assert uv_command[:3] == ["C:/tools/uv/uv.exe", "pip", "install"]
    assert any("nvidia-cublas-cu12==12.9.2.10" in part for part in uv_command)
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:7897"


def sys_executable():
    import sys

    return sys.executable
