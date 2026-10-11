#!/usr/bin/env python3
"""NO REAL MODEL. Deterministic protocol fixture for the TraceShop "办理记录"
(activity-log) candidate (isolated experiment, not published, not evidence of
model ability).

This is a scripted OpenAI-compatible endpoint used to exercise the unmodified
OctoSense Shell's real script-tool dispatch so the new application-side activity
log can be observed end to end. It is NOT a real LLM and makes no autonomous
decisions: it walks one fixed request sequence

    status.read -> proposal.read (fails: no proposal)
                -> catalog.research -> proposal.create
                -> proposal.read (pending) -> final text

and binds every identifier/version it sends to the ACTUAL structured result the
Shell returned in the previous turn. It never invents an item, price or version;
it never calls shopping.draft.save (so no destructive host approval is
requested) and never claims success when a required binding field is absent.
After the first task's final text, the next fresh conversation (the second app
task) gets a plain final text with NO tool call, so the check can verify that a
new task clears the in-memory activity records.

Standard library only: ThreadingHTTPServer on 127.0.0.1 with a random port.
The first line of stdout is the chosen port (official fixture convention), then
it serves until the scripted session finishes or fails, at which point the
server shuts down and the process exits.

Endpoints (same shape as the official tests/fixtures/mock_llm.py):
  GET  /v1/models               -> {"object": "list", "data": [...]}
  POST /v1/chat/completions     -> OpenAI chat completion, stream and non-stream

Environment:
  TRACESHOP_FIXTURE_LOG           path for the fixture log (JSON lines). Fallback
                                  env name FIXTURE_LOG. If neither is set, no log
                                  file is written and a warning goes to stderr.
  TRACESHOP_FIXTURE_MAX_REQUESTS  hard request cap, default 7.

The log records only: request sequence, tool name, selected arguments, failure
reason and the actual returned result. It never records HTTP headers or keys.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NO_REAL_MODEL = "NO REAL MODEL"
MODEL_ID = "no-real-model-fixture"

# Full declared tool set (native/traceshop-activity/bundle/tools.json). Used only
# to recognise the actual offered spelling; this fixture calls a strict subset.
CANONICAL = [
    "shopping.status.read",
    "shopping.catalog.research",
    "shopping.proposal.create",
    "shopping.proposal.read",
    "shopping.draft.save",
    "shopping.draft.read",
]

FIRST_FINAL = (
    "NO REAL MODEL fixture: 本次办理已按脚本流程结束"
    "（状态读取 -> 读取提案失败 -> 研究 -> 创建提案 -> 读取提案待确认）；"
    "未保存草稿、未下单。此文本是确定性协议流量，不是模型推理。"
)
SECOND_FINAL = (
    "NO REAL MODEL fixture: 第二个任务返回纯文字、未调用任何工具；"
    "用于验证新任务会清空办理记录。"
)

MAX_REQUESTS = int(os.environ.get("TRACESHOP_FIXTURE_MAX_REQUESTS", "7") or "7")
LOG_PATH = os.environ.get("TRACESHOP_FIXTURE_LOG") or os.environ.get("FIXTURE_LOG")

_state = {
    "requests": 0,
    "logged_results": set(),
    "completed": False,
    "finished": False,
    "failed": False,
}


def log(event):
    if not LOG_PATH:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        sys.stderr.write(f"{NO_REAL_MODEL} fixture: cannot write log: {exc}\n")


def next_seq():
    _state["requests"] += 1
    return _state["requests"]


def scan_messages(messages):
    """Rebuild the tool calls the Shell has already made and their results."""
    calls = {}
    results = {}
    order = []
    for message in messages:
        role = message.get("role")
        if role == "assistant":
            for call in message.get("tool_calls") or []:
                call_id = call.get("id")
                function = call.get("function") or {}
                try:
                    args = json.loads(function.get("arguments") or "{}")
                except (TypeError, ValueError):
                    args = {}
                calls[call_id] = {"name": function.get("name"), "args": args}
        elif role == "tool":
            call_id = message.get("tool_call_id")
            results[call_id] = parse_content(message.get("content"))
            if call_id not in order:
                order.append(call_id)
    return calls, results, order


def parse_content(content):
    if content is None:
        return None
    if isinstance(content, (dict, list)):
        return content
    if isinstance(content, str):
        text = content.strip()
        try:
            return json.loads(text)
        except ValueError:
            start = text.find("{")
            end = text.rfind("}")
            if 0 <= start < end:
                try:
                    return json.loads(text[start : end + 1])
                except ValueError:
                    pass
        return {"_unparsed": text}
    return {"_unparsed": repr(content)}


def offered_names(body):
    names = []
    for tool in body.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function") or {}
        name = function.get("name")
        if name:
            names.append(name)
    return names


def match_offered(offered, canonical):
    """Match only the actual offered spelling of this complete tool name."""
    normalized = canonical.replace(".", "").replace("_", "")
    matches = [name for name in offered if
               name.replace(".", "").replace("_", "") == normalized]
    return matches[0] if len(matches) == 1 else None


def canonical_of(name):
    """Map an offered tool name back to its canonical name, or None."""
    if not name:
        return None
    for canonical in CANONICAL:
        if match_offered([name], canonical):
            return canonical
    return None


def tool_call(call_id, name, args):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


CHECKS = {}


def verify(name, value):
    CHECKS[name] = bool(value)
    path = os.path.join(os.environ["RC1_RUN"], "fixture-checks.json")
    with open(path, "w") as handle:
        json.dump({"checks": CHECKS, "passed": bool(CHECKS) and all(CHECKS.values())},
                  handle, indent=2)
    if not value:
        raise RuntimeError("failed: " + name)


def res(completed, index):
    return completed[index][3]


def emit(offered, step, name, args):
    actual = match_offered(offered, name)
    if not actual:
        return ("fail", "tool missing: " + name)
    call_id = "activity_call_%d" % (step + 1)
    log({"event": "tool_call", "canonical": name, "tool": actual,
         "call_id": call_id, "args": args})
    return ("tool", actual, args, call_id)


def decide(offered, messages):
    calls, results, order = scan_messages(messages)
    completed = []
    for call_id in order:
        info = calls.get(call_id)
        if not info:
            continue
        canonical = canonical_of(info.get("name"))
        if canonical is None:
            continue
        completed.append((canonical, call_id, info, results.get(call_id)))
        if call_id not in _state["logged_results"]:
            _state["logged_results"].add(call_id)
            log({"event": "tool_result", "canonical": canonical,
                 "call_id": call_id, "result": results.get(call_id)})
    step = len(completed)
    last_role = messages[-1].get("role") if messages else None

    # Second app task: after the first task completed, any fresh user turn (or an
    # already-finished conversation) gets a final text with no tool call.
    if _state["completed"] and (last_role == "user" or step >= 5):
        return ("final", SECOND_FINAL)

    try:
        if step == 0:
            return emit(offered, step, "shopping.status.read", {})
        initial = res(completed, 0)
        binding = initial.get("agent_task_binding") if isinstance(initial, dict) else None
        if not isinstance(binding, dict):
            return ("fail", "status result has no agent_task_binding")
        tid = binding.get("task_id")
        request = binding.get("request") if isinstance(binding.get("request"), dict) else {}
        ui_need = request.get("need")
        ui_budget = request.get("budget_usd")
        ui_hard = list(request.get("hard_keywords") or [])
        if step == 1:
            verify("manual_research_visible_in_real_status", initial.get("has_research") is True)
            verify("status_binding_is_active", binding.get("active") is True)
            verify("status_binding_has_task_id", bool(tid))
            verify("status_binding_captured_ui_request",
                   bool(ui_need) and isinstance(ui_budget, (int, float)) and ui_budget > 0
                   and len(ui_hard) > 0)
            # A real failing read: there is no proposal yet.
            return emit(offered, step, "shopping.proposal.read", {})
        if step == 2:
            row = res(completed, 1)
            verify("proposal_read_without_proposal_fails",
                   isinstance(row, dict) and row.get("is_ok") is False
                   and row.get("error_code") == "no_proposal")
            return emit(offered, step, "shopping.catalog.research",
                        {"need": ui_need, "budget_usd": ui_budget,
                         "hard_keywords": ui_hard, "task_id": tid})
        if step == 3:
            row = res(completed, 2)
            verify("research_is_ok", isinstance(row, dict) and row.get("is_ok") is True)
            candidates = (row or {}).get("candidates") or []
            verify("research_has_candidate", len(candidates) >= 1)
            verify("research_has_versions",
                   row.get("research_revision") is not None
                   and row.get("merchant_version") is not None)
            return emit(offered, step, "shopping.proposal.create",
                        {"item_id": candidates[0]["item_id"],
                         "research_revision": row["research_revision"],
                         "merchant_version": row["merchant_version"],
                         "task_id": tid})
        if step == 4:
            row = res(completed, 3)
            verify("proposal_create_is_ok",
                   isinstance(row, dict) and row.get("is_ok") is True)
            verify("proposal_create_is_pending", row.get("status") == "pending")
            return emit(offered, step, "shopping.proposal.read", {})
        if step == 5:
            row = res(completed, 4)
            verify("proposal_read_is_ok",
                   isinstance(row, dict) and row.get("is_ok") is True)
            verify("proposal_read_is_pending", row.get("status") == "pending")
            _state["completed"] = True
            return ("final", FIRST_FINAL)
        return ("fail", "unexpected step: " + str(step))
    except Exception as error:  # noqa: BLE001
        return ("fail", repr(error))


def failure_text(reason):
    return (
        "NO REAL MODEL fixture: scripted session FAILED and stopped: "
        f"{reason}. No success is claimed."
    )


def schedule_shutdown(delay=0.5):
    if _state["finished"]:
        return
    _state["finished"] = True
    threading.Timer(delay, server.shutdown).start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.endswith("/models"):
            self._json({"object": "list",
                        "data": [{"id": MODEL_ID, "object": "model"}]})
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_error(400)
            return

        seq = next_seq()
        stream = bool(body.get("stream"))
        if seq > MAX_REQUESTS:
            reason = f"request cap {MAX_REQUESTS} exceeded"
            log({"seq": seq, "event": "stop", "reason": reason})
            _state["failed"] = True
            self._respond_text(stream, failure_text(reason))
            schedule_shutdown()
            return

        offered = offered_names(body)
        outcome = decide(offered, body.get("messages") or [])

        if outcome[0] == "fail":
            reason = outcome[1]
            log({"seq": seq, "event": "stop", "reason": reason})
            _state["failed"] = True
            self._respond_text(stream, failure_text(reason))
            schedule_shutdown()
            return

        if outcome[0] == "tool":
            _, name, args, call_id = outcome
            self._respond_tool(stream, call_id, name, args)
            return

        _, text = outcome
        log({"seq": seq, "event": "final", "text": text})
        self._respond_text(stream, text)
        # Keep the job-owned provider alive for the fresh second app task.
        if text == SECOND_FINAL:
            schedule_shutdown()

    def _respond_tool(self, stream, call_id, name, args):
        arguments = json.dumps(args)
        if not stream:
            self._json({
                "id": "chatcmpl-fixture",
                "object": "chat.completion",
                "model": MODEL_ID,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call(call_id, name, args)],
                    },
                    "finish_reason": "tool_calls",
                }],
                "usage": self._usage(),
            })
            return
        self._sse_start()
        first = {
            "id": "chatcmpl-fixture", "object": "chat.completion.chunk",
            "model": MODEL_ID,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "tool_calls": [{
                    "index": 0, "id": call_id, "type": "function",
                    "function": {"name": name, "arguments": ""},
                }]},
                "finish_reason": None,
            }],
        }
        second = {
            "id": "chatcmpl-fixture", "object": "chat.completion.chunk",
            "model": MODEL_ID,
            "choices": [{
                "index": 0,
                "delta": {"tool_calls": [{
                    "index": 0, "function": {"arguments": arguments},
                }]},
                "finish_reason": None,
            }],
        }
        final = {
            "id": "chatcmpl-fixture", "object": "chat.completion.chunk",
            "model": MODEL_ID,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": self._usage(),
        }
        self._sse_send(first)
        self._sse_send(second)
        self._sse_send(final)
        self._sse_end()

    def _respond_text(self, stream, text):
        if not stream:
            self._json({
                "id": "chatcmpl-fixture",
                "object": "chat.completion",
                "model": MODEL_ID,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }],
                "usage": self._usage(),
            })
            return
        self._sse_start()
        half = len(text) // 2
        for chunk in (text[:half], text[half:]):
            self._sse_send({
                "id": "chatcmpl-fixture", "object": "chat.completion.chunk",
                "model": MODEL_ID,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": chunk},
                    "finish_reason": None,
                }],
            })
        self._sse_send({
            "id": "chatcmpl-fixture", "object": "chat.completion.chunk",
            "model": MODEL_ID,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": self._usage(),
        })
        self._sse_end()

    def _sse_start(self):
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.end_headers()

    def _sse_send(self, value):
        self.wfile.write(b"data: " + json.dumps(value).encode() + b"\n\n")

    def _sse_end(self):
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _json(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def _usage(self):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
print(server.server_address[1], flush=True)
sys.stderr.write(f"{NO_REAL_MODEL} fixture: deterministic TraceShop activity "
                 f"server on 127.0.0.1:{server.server_address[1]} "
                 f"(log={LOG_PATH or 'disabled'})\n")
try:
    server.serve_forever()
finally:
    state = "FAILED" if _state["failed"] else "COMPLETED"
    sys.stderr.write(f"{NO_REAL_MODEL} fixture: {state} after "
                     f"{_state['requests']} request(s)\n")
    server.server_close()
sys.exit(2 if _state["failed"] else 0)
