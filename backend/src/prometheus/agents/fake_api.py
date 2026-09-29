"""A local stand-in for a model endpoint (PLAN 15.4.13), for the update window's self-check and the
isolation tests: the Anthropic Messages API (Claude Code, and Pi on the Anthropic protocol) and the
OpenAI Responses API (Codex CLI), streaming as the real ones do. It never goes online.

It answers 「可用」. When the prompt carries ``WRITE:<absolute path>`` and the request offers a tool
that can write a file (Pi's ``write``, Claude Code's ``Edit`` or ``PowerShell``, Codex's
``exec_command``), it first calls that tool to write 「ok」 there, then answers. Every request it saw
is kept in memory, bodies and the key it came with, for the checks.
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


def _target(body) -> str | None:
    """The path a request asks to be written, from any text in it."""
    for text in _strings(body):
        if match := re.search(r"WRITE:([^\r\n\"]+)", text):
            return match.group(1).strip()
    return None


def _anthropic_write(body: dict, path: str):
    """(tool name, input) for the first tool offered that can write `path`; None when none can."""
    names = {tool.get("name") for tool in body.get("tools") or []}
    if "write" in names:
        return "write", {"path": path, "content": "ok"}
    if "Edit" in names:
        return "Edit", {"file_path": path, "old_string": "", "new_string": "ok"}
    for name in ("PowerShell", "powershell"):
        if name in names:
            return name, {"command": f"Set-Content -LiteralPath '{path}' -Value 'ok'", "description": "write the file"}
    return None


def _anthropic_done(body: dict) -> bool:
    return any(isinstance(block, dict) and block.get("type") == "tool_result"
               for message in body.get("messages") or [] for block in message.get("content") or []
               if isinstance(message.get("content"), list))


def _anthropic_events(model: str, tool=None) -> list:
    start = {"type": "message_start", "message": {
        "id": "msg_fake", "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None,
        "usage": {"input_tokens": 10, "output_tokens": 1}}}
    if tool:
        name, arguments = tool
        blocks = [
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "tool_use", "id": "toolu_fake", "name": name, "input": {}}},
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


def _responses_done(body: dict) -> bool:
    return any(isinstance(item, dict) and item.get("type") == "function_call_output" for item in body.get("input") or [])


def _responses_events(model: str, path=None) -> list:
    if path:
        item = {"id": "fc_fake", "type": "function_call", "status": "completed", "call_id": "call_fake",
                "name": "exec_command", "arguments": json.dumps({"cmd": f"Set-Content -LiteralPath '{path}' -Value 'ok'"})}
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
    if not path:
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
                target = _target(body)
                if path.endswith("/messages/count_tokens"):
                    self._send(200, {"input_tokens": 10})
                elif path.endswith("/messages"):
                    tool = _anthropic_write(body, target) if target and not _anthropic_done(body) else None
                    self._send(200, events=_anthropic_events(model, tool))
                elif path.endswith("/responses"):
                    names = {tool.get("name") for tool in body.get("tools") or []}
                    write = target if target and "exec_command" in names and not _responses_done(body) else None
                    self._send(200, events=_responses_events(model, write))
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
