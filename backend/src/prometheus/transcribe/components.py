"""Local-ASR component install: CUDA libs into the data dir (PLAN 8.5)."""

import subprocess
import sys
from pathlib import Path


def build_pip_cmd(data_dir, *, proxy: str = "") -> list:
    raise NotImplementedError


def install_components(data_dir, *, proxy: str = "") -> None:
    raise NotImplementedError
