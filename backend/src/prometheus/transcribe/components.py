"""Local-ASR component install: CUDA libs into the data dir (PLAN 8.5)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

CUDA_PACKAGES = (
    "nvidia-cublas-cu12==12.9.2.10",
    "nvidia-cudnn-cu12==9.26.0.51",
)


class ComponentInstallError(RuntimeError):
    code = "ENVIRONMENT_FAILURE"


def build_pip_cmd(data_dir, *, proxy: str = "") -> list:
    target = str(Path(data_dir) / "runtime" / "cuda")
    command = [
        sys.executable, "-m", "pip", "install", "--no-deps",
        "--target", target, *CUDA_PACKAGES,
    ]
    if proxy.strip():
        command += ["--proxy", proxy.strip()]
    return command


def _has_pip() -> bool:
    probe = subprocess.run(
        [sys.executable, "-m", "pip", "--version"], capture_output=True, check=False,
    )
    return probe.returncode == 0


def install_components(data_dir, *, proxy: str = "") -> None:
    target = Path(data_dir) / "runtime" / "cuda"
    target.mkdir(parents=True, exist_ok=True)
    env = None
    if _has_pip():
        # Packaged builds: the bundled interpreter ships pip (PLAN 8.5).
        command = build_pip_cmd(data_dir, proxy=proxy)
    else:
        # uv-managed dev venvs have no pip; uv takes over, proxy via env vars.
        uv = shutil.which("uv")
        if uv is None:
            raise ComponentInstallError(
                "当前 Python 没有 pip，也找不到 uv，无法安装本地转写组件。"
            )
        command = [
            uv, "pip", "install", "--no-deps", "--target", str(target), *CUDA_PACKAGES,
        ]
        env = dict(os.environ)
        if proxy.strip():
            env["HTTPS_PROXY"] = proxy.strip()
            env["HTTP_PROXY"] = proxy.strip()
    result = subprocess.run(
        command, capture_output=True, check=False, env=env,
    )
    if result.returncode != 0:
        raise ComponentInstallError(
            "CUDA 运行库安装失败：" + result.stderr.decode("utf-8", "replace")[-500:]
        )
