"""Where the bundled node / Pi / ffmpeg binaries live (PLAN 15.2-1).

Installed runs get ``--runtime-dir`` from the Tauri shell (layout produced by
scripts/package.ps1). Development falls back to the variables exported by
E:\\tools\\Prometheus-Desktop\\env.ps1. With PROMETHEUS_FORBID_DEV_PATHS=1 only the
runtime dir is acceptable, which is how acceptance proves an install is
self-contained.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

PI_CLI = Path("pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js")


class RuntimeConfigError(RuntimeError):
    code = "ENVIRONMENT_FAILURE"


@dataclass(frozen=True)
class Runtime:
    node: Path | None
    pi_cli: Path | None
    ffmpeg: Path | None
    ffprobe: Path | None


def _from_bundle(root: Path) -> Runtime:
    return Runtime(
        node=root / "node" / "node.exe",
        pi_cli=root / PI_CLI,
        ffmpeg=root / "ffmpeg" / "ffmpeg.exe",
        ffprobe=root / "ffmpeg" / "ffprobe.exe",
    )


def _from_toolchain(env) -> Runtime:
    node = env.get("PROMETHEUS_NODE")
    pi_cli = env.get("PROMETHEUS_PI_CLI")
    if not pi_cli and env.get("PROMETHEUS_PI"):
        # <tools>\pi\node_modules\.bin\pi.cmd -> <tools>\pi\node_modules\...\cli.js
        pi_cli = Path(env["PROMETHEUS_PI"]).parents[3] / PI_CLI
    ffmpeg_dir = env.get("PROMETHEUS_FFMPEG")
    return Runtime(
        node=Path(node) if node else None,
        pi_cli=Path(pi_cli) if pi_cli else None,
        ffmpeg=Path(ffmpeg_dir) / "ffmpeg.exe" if ffmpeg_dir else None,
        ffprobe=Path(ffmpeg_dir) / "ffprobe.exe" if ffmpeg_dir else None,
    )


def resolve(runtime_dir, env=None) -> Runtime:
    env = os.environ if env is None else env
    if runtime_dir:
        found = _from_bundle(Path(runtime_dir))
    elif env.get("PROMETHEUS_FORBID_DEV_PATHS") == "1":
        raise RuntimeConfigError(
            "要求只使用安装包自带的运行时（PROMETHEUS_FORBID_DEV_PATHS=1），但没有提供 --runtime-dir。"
        )
    else:
        found = _from_toolchain(env)
    missing = [
        name for name in ("node", "pi_cli", "ffmpeg", "ffprobe")
        if getattr(found, name) is None or not getattr(found, name).is_file()
    ]
    if missing:
        raise RuntimeConfigError(f"找不到运行时组件：{', '.join(missing)}。请重新安装 Prometheus。")
    return found


def activate(found: Runtime, runtime_dir=None, env=None) -> None:
    """Put the bundled ffmpeg and node first on PATH for vendor code and yt-dlp."""
    env = os.environ if env is None else env
    front = [str(found.ffmpeg.parent), str(found.node.parent)]
    env["PATH"] = os.pathsep.join([*front, env.get("PATH", "")])
    if env.get("PROMETHEUS_FORBID_DEV_PATHS") == "1" and runtime_dir:
        root = Path(runtime_dir).resolve()
        for tool in ("ffmpeg", "ffprobe", "node"):
            located = shutil.which(tool, path=env["PATH"])
            if located is None or root not in Path(located).resolve().parents:
                raise RuntimeConfigError(f"{tool} 解析到了安装目录以外的位置：{located}")
