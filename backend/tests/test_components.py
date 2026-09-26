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
