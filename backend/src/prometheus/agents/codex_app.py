"""Codex CLI's own view of models and login (PLAN 15.4.13).

「获取模型列表」 and the thinking levels per model come from its app-server (``model/list``: each model
with the reasoning efforts it takes; after an official login the ChatGPT account's own list). The
login state is what ``codex login status`` says, and 「登录 ChatGPT 账户」 starts ``codex login``,
which opens OpenAI's sign-in page; the credentials stay in the app's own CODEX_HOME, apart from the
user's own Codex. The app never reads them.
"""

import json
import os
import subprocess
import threading
from pathlib import Path

from prometheus.agents import commands

OURS = ("off", "low", "medium", "high", "xhigh", "max")  # the app's six levels; Codex calls off 「none」
WAIT_S = 60
_logins: dict = {}


class CodexAppError(RuntimeError):
    pass


def _env(config_root) -> dict:
    (Path(config_root) / "codex").mkdir(parents=True, exist_ok=True)
    return commands.codex_env(os.environ, config_root=config_root, api_key=None)


def _model(entry: dict) -> dict:
    supported = {option.get("reasoningEffort") for option in entry.get("supportedReasoningEfforts") or []}
    levels = [level for level in OURS if level in supported or (level == "off" and "none" in supported)]
    return {"id": entry["id"], "levels": levels, "images": "image" in (entry.get("inputModalities") or [])}


def models(tools_root, config_root) -> list:
    """[{id, levels, images}] for the models Codex offers, hidden ones left out."""
    server = subprocess.Popen([str(commands.executable(tools_root, "codex")), "app-server"], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_env(config_root))
    watchdog = threading.Timer(WAIT_S, server.kill)  # a server that stops answering ends the call
    watchdog.start()

    def send(message: dict) -> None:
        server.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        server.stdin.flush()

    def answer(request_id: int) -> dict:
        while line := server.stdout.readline():
            message = json.loads(line)
            if message.get("id") == request_id:
                if "error" in message:
                    raise CodexAppError(f"Codex 没有给出模型列表：{message['error']}")
                return message.get("result") or {}
        raise CodexAppError("Codex 没有给出模型列表（没有回应）")

    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "prometheus", "version": "1"}}})
        answer(1)
        send({"method": "initialized"})
        found, cursor, request_id = [], None, 2
        while True:
            send({"id": request_id, "method": "model/list", "params": {"cursor": cursor} if cursor else {}})
            page = answer(request_id)
            found += [_model(entry) for entry in page.get("data") or [] if not entry.get("hidden")]
            cursor = page.get("nextCursor")
            if not cursor:
                return found
            request_id += 1
    finally:
        watchdog.cancel()
        server.kill()
        server.wait()


def logged_in(tools_root, config_root) -> bool:
    done = subprocess.run([str(commands.executable(tools_root, "codex")), "login", "status"], capture_output=True,
                          env=_env(config_root), timeout=30, check=False)
    return done.returncode == 0


def start_login(tools_root, config_root) -> None:
    """Start ``codex login`` (it opens the browser) unless one for this CODEX_HOME is still waiting."""
    key = str(Path(config_root))
    running = _logins.get(key)
    if running is not None and running.poll() is None:
        return
    _logins[key] = subprocess.Popen([str(commands.executable(tools_root, "codex")), "login"], env=_env(config_root),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
