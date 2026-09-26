"""Where the bundled node / Pi / ffmpeg binaries live (PLAN 15.2-1)."""

from dataclasses import dataclass
from pathlib import Path


class RuntimeConfigError(RuntimeError):
    code = "ENVIRONMENT_FAILURE"


@dataclass(frozen=True)
class Runtime:
    node: Path | None
    pi_cli: Path | None
    ffmpeg: Path | None
    ffprobe: Path | None


def resolve(runtime_dir, env) -> Runtime:
    return Runtime(None, None, None, None)
