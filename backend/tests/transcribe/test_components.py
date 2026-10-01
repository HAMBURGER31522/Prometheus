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
    monkeypatch.setattr(components, "install_funasr_models", lambda data_dir, *, proxy="": None)
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


def test_cuda_libraries_install_under_the_hidden_internal_folder(tmp_path):
    # R3 moved runtime files into .prometheus; the installer must follow (PLAN 15.4.4).
    from prometheus import paths

    command = build_pip_cmd(tmp_path, proxy="")
    assert command[command.index("--target") + 1] == str(paths.cuda_dir(tmp_path))


def _fake_fetch(calls, fail_on=None):
    def fetch(url, target, *, proxy=""):
        calls.append((url, target))
        if fail_on and fail_on in url:
            target.write_bytes(b"half")
            raise OSError("connection reset")
        target.write_bytes(b"ok")
    return fetch


def test_funasr_models_download_from_modelscope_into_models_funasr(tmp_path):
    # PLAN 15.4.4: ONNX exports from ModelScope under .prometheus/models/funasr (D-39).
    from prometheus import paths
    from prometheus.transcribe import components

    calls = []
    assert components.funasr_models_installed(tmp_path) is False
    components.install_funasr_models(tmp_path, fetch=_fake_fetch(calls))
    assert components.funasr_models_installed(tmp_path) is True
    assert len(calls) == sum(len(files) for _model, files in components.FUNASR_MODELS)
    for url, target in calls:
        assert url.startswith("https://www.modelscope.cn/api/v1/models/iic/")
        assert target.parent.parent == paths.funasr_dir(tmp_path)
        assert target.name.endswith(".part")
    assert paths.funasr_dir(tmp_path) == paths.models_dir(tmp_path) / "funasr"


def test_funasr_files_already_present_are_not_downloaded_again(tmp_path):
    from prometheus.transcribe import components

    first = []
    components.install_funasr_models(tmp_path, fetch=_fake_fetch(first))
    assert first, "the first install must download the model files"
    calls = []
    components.install_funasr_models(tmp_path, fetch=_fake_fetch(calls))
    assert calls == []


def test_an_interrupted_download_does_not_count_as_installed(tmp_path):
    import pytest
    from prometheus.transcribe import components

    with pytest.raises(components.ComponentInstallError):
        components.install_funasr_models(tmp_path, fetch=_fake_fetch([], fail_on="paraformer"))
    assert components.funasr_models_installed(tmp_path) is False


def test_installing_components_fetches_cuda_and_funasr(tmp_path, monkeypatch):
    import subprocess as sp

    from prometheus.transcribe import components

    monkeypatch.setattr(components.subprocess, "run",
                        lambda command, **kwargs: sp.CompletedProcess(command, 0, b"", b""))
    installed = []
    monkeypatch.setattr(components, "install_funasr_models",
                        lambda data_dir, *, proxy="": installed.append((data_dir, proxy)))
    components.install_components(tmp_path, proxy="http://127.0.0.1:7897")
    assert installed == [(tmp_path, "http://127.0.0.1:7897")]
