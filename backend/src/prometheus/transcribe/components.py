"""Local-ASR component install: CUDA libs into the data dir (PLAN 8.5)."""

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


def install_components(data_dir, *, proxy: str = "") -> None:
    target = Path(data_dir) / "runtime" / "cuda"
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        build_pip_cmd(data_dir, proxy=proxy), capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise ComponentInstallError(
            "CUDA 运行库安装失败：" + result.stderr.decode("utf-8", "replace")[-500:]
        )
