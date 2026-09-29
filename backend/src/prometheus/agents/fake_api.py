"""A local stand-in for a model endpoint (PLAN 15.4.13), for the update window's self-check and the
isolation tests: the Anthropic Messages API (Claude Code, and Pi on the Anthropic protocol) and the
OpenAI Responses API (Codex CLI), streaming as the real ones do. It never goes online.

It answers 「可用」. Lines in the prompt make it act first, one tool call per turn, with whatever tool
the Agent offers (Pi's ``write`` / ``powershell``, Claude Code's ``Edit`` / ``PowerShell``, Codex's
``exec_command``): ``DELETE:<path>`` and ``OUTSIDE:<path>`` try to delete that file and to write one
there (the file protection must stop both), then ``WRITE:<path>`` writes 「ok」 there. Every request
it saw is kept in memory, bodies and the key it came with, for the checks.
"""

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANSWER = "可用"


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _marked(body, marker: str) -> list:
    found = {}
    for text in _strings(body):
        for match in re.finditer(rf"{marker}:([^\r\n\"]+)", text):
            found[match.group(1).strip()] = True
    return list(found)


def _plan(body) -> list:
    """The steps the prompt asks for: ("shell", command) then ("write", path)."""
    # .NET calls rather than Remove-Item: Codex refuses commands that look destructive by their wording,
    # a guess, not a protection; these it runs, so only the file protection can stop them.
    tries = ([f"[System.IO.File]::Delete('{path}')" for path in _marked(body, "DELETE")]
             + [f"[System.IO.File]::WriteAllText('{path}', 'bad')" for path in _marked(body, "OUTSIDE")])
    steps = [("shell", "; ".join(tries))] if tries else []
    return steps + [("write", path) for path in _marked(body, "WRITE")[:1]]


def _anthropic_call(body: dict, step):
    """(tool name, input) for a step with the tools offered; None when none fits."""
    names = {tool.get("name") for tool in body.get("tools") or []}
    shell = next((name for name in ("powershell", "PowerShell") if name in names), None)
    kind, value = step
    if kind == "write" and "write" in names:
        return "write", {"path": value, "content": "ok"}
    if kind == "write" and "Edit" in names:
        return "Edit", {"file_path": value, "old_string": "", "new_string": "ok"}
    command = value if kind == "shell" else f"Set-Content -LiteralPath '{value}' -Value 'ok'"
    return (shell, {"command": command, "description": "run"}) if shell else None


def _anthropic_turn(body: dict) -> int:
    return sum(1 for message in body.get("messages") or [] if isinstance(message.get("content"), list)
               for block in message["content"] if isinstance(block, dict) and block.get("type") == "tool_result")


def _anthropic_events(model: str, tool=None, turn: int = 0) -> list:
    start = {"type": "message_start", "message": {
        "id": "msg_fake", "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None,
        "usage": {"input_tokens": 10, "output_tokens": 1}}}
    if tool:
        name, arguments = tool
        blocks = [
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "tool_use", "id": f"toolu_fake_{turn}", "name": name, "input": {}}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "input_json_delta", "partial_json": json.dumps(arguments, ensure_ascii=False)}},
            {"type": "content_block_stop", "index": 0},
        ]
        stop = "tool_use"
    else:
        blocks = [
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": ANSWER}},
            {"type": "content_block_stop", "index": 0},
        ]
        stop = "end_turn"
    return [start, *blocks, {"type": "message_delta", "delta": {"stop_reason": stop}, "usage": {"output_tokens": 3}},
            {"type": "message_stop"}]


def _responses_turn(body: dict) -> int:
    return sum(1 for item in body.get("input") or [] if isinstance(item, dict) and item.get("type") == "function_call_output")


def _responses_command(step) -> str:
    kind, value = step
    return value if kind == "shell" else f"Set-Content -LiteralPath '{value}' -Value 'ok'"


def _responses_events(model: str, command=None, turn: int = 0) -> list:
    if command:
        item = {"id": f"fc_fake_{turn}", "type": "function_call", "status": "completed", "call_id": f"call_fake_{turn}",
                "name": "exec_command", "arguments": json.dumps({"cmd": command})}
        added = {**item, "status": "in_progress", "arguments": ""}
    else:
        item = {"id": "msg_fake", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": ANSWER, "annotations": []}]}
        added = {**item, "status": "in_progress", "content": []}
    response = {"id": "resp_fake", "object": "response", "created_at": int(time.time()), "model": model,
                "status": "completed", "output": [item],
                "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13,
                          "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}
    events = [{"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
              {"type": "response.output_item.added", "output_index": 0, "item": added}]
    if not command:
        events.append({"type": "response.output_text.delta", "item_id": "msg_fake", "output_index": 0,
                       "content_index": 0, "delta": ANSWER})
    return [*events, {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": response}]


class FakeModelApi:
    """``with FakeModelApi() as api:`` serves on ``api.url`` until the block ends."""

    def __init__(self):
        self.requests: list = []
        self.keys: list = []
        self.url = ""
        self._server = None

    def __enter__(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def _send(self, status: int, payload=None, events=None):
                self.send_response(status)
                if events is None:
                    data = json.dumps(payload or {}).encode("utf-8")
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for event in events:
                    self.wfile.write(f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                                     .encode())
                self.wfile.flush()

            def _body(self) -> bytes:
                """The whole request body, sized or chunked (larger bodies come chunked)."""
                if "chunked" not in (self.headers.get("Transfer-Encoding") or "").lower():
                    return self.rfile.read(int(self.headers.get("Content-Length") or 0))
                chunks = []
                while size := int(self.rfile.readline().split(b";")[0].strip() or b"0", 16):
                    chunks.append(self.rfile.read(size))
                    self.rfile.readline()
                self.rfile.readline()
                return b"".join(chunks)

            def do_HEAD(self):
                self._send(200)

            def do_GET(self):
                self._send(200, {"object": "list", "data": []})

            def do_POST(self):
                try:
                    body = json.loads(self._body() or b"{}")
                except ValueError:
                    body = {}
                path = self.path.split("?")[0]
                key = self.headers.get("x-api-key") or (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                api.requests.append({"path": path, "body": body})
                api.keys.append(key)
                model = body.get("model", "fake") if isinstance(body, dict) else "fake"
                plan = _plan(body)
                if path.endswith("/messages/count_tokens"):
                    self._send(200, {"input_tokens": 10})
                elif path.endswith("/messages"):
                    turn = _anthropic_turn(body)
                    tool = _anthropic_call(body, plan[turn]) if turn < len(plan) else None
                    self._send(200, events=_anthropic_events(model, tool, turn))
                elif path.endswith("/responses"):
                    turn = _responses_turn(body)
                    shell = "exec_command" in {tool.get("name") for tool in body.get("tools") or []}
                    command = _responses_command(plan[turn]) if shell and turn < len(plan) else None
                    self._send(200, events=_responses_events(model, command, turn))
                else:
                    self._send(404, {"error": {"message": f"no fake for {path}"}})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        return False
