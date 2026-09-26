"""Runtime binary resolution (PLAN 15.2-1): installed runs use --runtime-dir only."""

from pathlib import Path

import pytest
from prometheus import runtime

PI_CLI = Path("pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js")


def _bundle(root: Path) -> Path:
    """Lay out node / Pi / ffmpeg the way scripts/package.ps1 does."""
    (root / "node").mkdir(parents=True)
    (root / "node" / "node.exe").write_bytes(b"")
    (root / PI_CLI).parent.mkdir(parents=True)
    (root / PI_CLI).write_text("", encoding="utf-8")
    (root / "ffmpeg").mkdir()
    (root / "ffmpeg" / "ffmpeg.exe").write_bytes(b"")
    (root / "ffmpeg" / "ffprobe.exe").write_bytes(b"")
    return root


def _dev_env(tools: Path, **extra) -> dict:
    """What E:\\tools\\Prometheus-Desktop\\env.ps1 exports during development."""
    return {
        "PROMETHEUS_NODE": str(tools / "node" / "node.exe"),
        "PROMETHEUS_PI": str(tools / "pi" / "node_modules" / ".bin" / "pi.cmd"),
        "PROMETHEUS_FFMPEG": str(tools / "ffmpeg"),
        **extra,
    }


def test_runtime_dir_resolves_the_bundled_binaries(tmp_path):
    root = _bundle(tmp_path / "runtime")
    found = runtime.resolve(root, env={})
    assert found.node == root / "node" / "node.exe"
    assert found.pi_cli == root / PI_CLI
    assert found.ffmpeg == root / "ffmpeg" / "ffmpeg.exe"
    assert found.ffprobe == root / "ffmpeg" / "ffprobe.exe"


def test_development_resolves_from_the_toolchain_env(tmp_path):
    tools = _bundle(tmp_path / "tools")
    found = runtime.resolve(None, env=_dev_env(tools))
    assert found.node == tools / "node" / "node.exe"
    assert found.pi_cli == tools / PI_CLI
    assert found.ffmpeg == tools / "ffmpeg" / "ffmpeg.exe"


def test_forbidding_dev_paths_requires_a_runtime_dir(tmp_path):
    tools = _bundle(tmp_path / "tools")
    with pytest.raises(runtime.RuntimeConfigError):
        runtime.resolve(None, env=_dev_env(tools, PROMETHEUS_FORBID_DEV_PATHS="1"))


def test_forbidding_dev_paths_still_accepts_the_bundle(tmp_path):
    root = _bundle(tmp_path / "runtime")
    tools = _bundle(tmp_path / "tools")
    found = runtime.resolve(root, env=_dev_env(tools, PROMETHEUS_FORBID_DEV_PATHS="1"))
    assert found.node == root / "node" / "node.exe"


def test_a_missing_binary_is_named_in_the_error(tmp_path):
    empty = tmp_path / "runtime"
    empty.mkdir()
    with pytest.raises(runtime.RuntimeConfigError, match="node"):
        runtime.resolve(empty, env={})


def test_backend_source_has_no_developer_machine_paths():
    package = Path(runtime.__file__).parent
    offenders = [
        str(path.relative_to(package)) for path in package.rglob("*.py")
        if "E:/tools" in (text := path.read_text(encoding="utf-8")) or "E:\\tools" in text
    ]
    assert offenders == []
