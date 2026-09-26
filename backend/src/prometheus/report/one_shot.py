"""One-shot text calls for classify/mindmap/test-model (PLAN 8.6).

The prompt always travels via stdin: the mindmap outline exceeds the command
line limit, and cmd-style wrappers would mangle long arguments (D-16).
"""

import os
import subprocess
from pathlib import Path

ONE_SHOT_FLAGS = [
    "--no-tools", "--no-session", "--offline", "--no-extensions", "--no-skills",
    "--no-prompt-templates", "--no-themes", "--no-context-files",
]


class OneShotError(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def run_one_shot(work_dir, *, prompt: str, provider: str, model: str, api_key: str,
                 thinking: str, node_exe: str, pi_cli: str, agent_dir) -> str:
    command = [
        node_exe, pi_cli, "-p", *ONE_SHOT_FLAGS,
        "--provider", provider, "--model", model,
        "--thinking", thinking, "--api-key", api_key,
    ]
    env = {**os.environ, "PI_CODING_AGENT_DIR": str(agent_dir)}
    result = subprocess.run(
        command, input=prompt.encode("utf-8"), capture_output=True,
        cwd=str(Path(work_dir)), env=env,
    )
    if result.returncode != 0:
        raise OneShotError(
            f"一次性文本调用失败（exit {result.returncode}）："
            + result.stderr.decode("utf-8", "replace")[-300:]
        )
    return result.stdout.decode("utf-8").strip()
