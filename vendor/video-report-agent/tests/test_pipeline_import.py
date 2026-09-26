"""V3: pipeline and paraformer must import without playwright (appendix A V3)."""

import subprocess
import sys


def _imports_without_playwright(module: str) -> subprocess.CompletedProcess:
    code = f"import sys; sys.modules['playwright'] = None; import {module}"
    return subprocess.run([sys.executable, "-c", code], capture_output=True)


def test_pipeline_imports_without_playwright():
    result = _imports_without_playwright("video_report_agent.pipeline")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def test_paraformer_imports_without_playwright():
    result = _imports_without_playwright("video_report_agent.paraformer")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
