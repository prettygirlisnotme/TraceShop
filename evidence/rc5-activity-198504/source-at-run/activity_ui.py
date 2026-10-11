#!/usr/bin/env python3
"""UI check for the TraceShop "办理记录" (activity-log) candidate.

Runs on the same official unmodified RC5 shell + real Store install + loopback
bridge as the onboarding harness (this directory carries a copy of the shared
native_shop_driver/Store driver). A job-owned deterministic localhost fixture
supplies scripted tool calls; there is NO real model and zero paid requests.

This check drives only real UI/bridge actions. It never injects app functions or
fabricates a tool receipt: the fixture sends real shopping.* calls through the
Shell, and the app-side activity records are read back from the rendered Label.

What it verifies (this round only):
  - a manual UI research is NOT recorded as a tool activity;
  - after one scripted app task (status -> proposal.read fails -> research ->
    proposal.create -> proposal.read pending -> final), the "办理记录" page shows
    each real tool return, the failing proposal.read reads as "未确认成功"
    (never as success), no draft.save is present, and no draft file exists;
  - starting a second task clears the in-memory records.

RC5 native first-use consent: the consent control is NOT an ordinary Button and
is absent from /snap, so this script never hard-clicks a coordinate. It writes a
ready marker + one diagnostic PNG, then waits on a restricted control queue
(activity-control.jsonl -> activity-replies.jsonl) for the controller to send a
real click and then {op: resume}. Coordinates are supplied by the controller at
run time, never hard-coded here. (RC1 hard coordinates were deliberately NOT
reused.)
"""
import json
import os
import re
import time
from pathlib import Path

from native_shop_driver import Bridge, Driver

RUN = Path(os.environ["RC1_RUN"])
PORT = int(os.environ["RC1_PORT"])
APP_DATA = os.environ["RC1_APP_DATA"]
APP_ID = "traceshop.shopping"

NEED = os.environ.get("RC1_ACTIVITY_NEED", "办公用无线鼠标")
BUDGET = os.environ.get("RC1_ACTIVITY_BUDGET", "23")
HARD = os.environ.get("RC1_ACTIVITY_HARD", "wireless,silent")

CONSENT_XY = os.environ.get("RC1_ACTIVITY_CONSENT_XY", "")
CONSENT_TIMEOUT = float(os.environ.get("RC1_ACTIVITY_CONSENT_TIMEOUT", "180"))

CONTROL = RUN / "activity-control.jsonl"
REPLIES = RUN / "activity-replies.jsonl"
READY = RUN / "activity-ready.json"
FIXTURE_LOG = RUN / "fixture.jsonl"

UI_TEXT_FIELDS = [
    "catalog_source_label", "need_input", "budget_input", "keywords_input",
    "research_status", "stage_info", "proposal_status", "proposal_summary",
    "proposal_state", "agent_task_status", "draft_status",
    "reply_detail_marker", "reply_detail_records", "reply_detail_info",
]

bridge = Bridge(PORT)
driver = Driver(bridge, str(RUN), str(RUN / "unused-frames"), APP_DATA, APP_ID)

result = {
    "kind": "traceshop-activity-ui",
    "real_model": False,
    "fixture": True,
    "model_requests": 0,
    "video_recorded": False,
    "app_id": APP_ID,
    "scope": ("Official unmodified RC5, real Store install, deterministic localhost "
              "fixture (NO REAL MODEL). Verifies app-side activity records from real "
              "tool returns and that a new task clears them; no save, no destructive "
              "host approval, no video."),
    "checks": {},
    "errors": [],
    "window_size": [driver.window_w, driver.window_h],
}


def check(name, value):
    result["checks"][name] = bool(value)
    if not value:
        result["errors"].append("check failed: " + name)


def click(name):
    if not driver.click(name, wait=0.4):
        raise RuntimeError("cannot click " + name)


def fill(name, value):
    driver.clear_and_type(name, value, None)


def text(name):
    return bridge.text(name) or ""


def click_tab(wid):
    # The panel shows exactly one reading area at a time, so the records text
    # only exists in the snap tree while the records tab is selected (and the
    # original text only while the reply tab is selected).
    if not driver.click(wid, wait=0.35):
        raise RuntimeError("cannot click " + wid)
    time.sleep(0.3)


def select_records_tab():
    click_tab("activity_tab_records_btn")


def select_reply_tab():
    click_tab("activity_tab_reply_btn")


def read_records():
    select_records_tab()
    return text("reply_detail_records")


def widget_probe(name):
    w = bridge.find(name)
    if not w:
        return {"present": False}
    return {"present": True, "rect": w.get("r"), "text_len": len(w.get("t") or "")}


def scroll_at(x, y, dy):
    x = max(10, min(int(x), driver.window_w - 10))
    y = max(10, min(int(y), driver.window_h - 10))
    bridge.get("/m?k=scroll&x=%d&y=%d&dy=%d&wait=1" % (x, y, int(dy)))


def outer_scroll_point():
    # A point on the reply panel that is NOT inside the nested 170px records or
    # 240px original-text scrollers, so the scroll moves the OUTER page view.
    # The marker label sits above both nested scrollers; Driver.scroll's default
    # center point can land inside a nested scroller instead.
    for wid in ("reply_detail_marker", "reply_detail_refresh_btn",
                "reply_detail_back_btn"):
        c = driver.rect_center(wid)
        if c and driver.in_view(c):
            return int(c[0]), int(c[1])
    return driver.window_w // 2, 150


def ensure_visible(wid, max_tries=4, step=260):
    # Scroll the outer page view until wid is measured and inside the window.
    # Both directions are tried because the initial failure mode is "not in the
    # snap tree yet" (a widget below the outer viewport is unmeasured).
    for direction in (step, -step):
        for _ in range(max_tries):
            c = driver.rect_center(wid)
            if c and driver.in_view(c):
                return True
            px, py = outer_scroll_point()
            scroll_at(px, py, direction)
            time.sleep(0.35)
    c = driver.rect_center(wid)
    return bool(c) and driver.in_view(c)


def reveal_reply_text():
    present_before = bridge.find("reply_detail_info") is not None
    text_before = text("reply_detail_info")
    revealed = ensure_visible("reply_detail_info")
    return {"present_before": present_before, "text_before": text_before,
            "revealed": revealed,
            "present_after": bridge.find("reply_detail_info") is not None,
            "text_after": text("reply_detail_info")}


def reply_diagnostics(tag):
    diag = {
        "tag": tag,
        "at": round(time.time(), 3),
        "window": [driver.window_w, driver.window_h],
        "stage_info": text("stage_info"),
        "agent_task_status": text("agent_task_status"),
        "agent_task_reply": text("agent_task_reply"),
        "agent_task_reply_len": len(text("agent_task_reply") or ""),
        "reply_detail_marker": text("reply_detail_marker"),
        "reply_detail_info": text("reply_detail_info"),
        "reply_detail_info_len": len(text("reply_detail_info") or ""),
        "widgets": {name: widget_probe(name) for name in
                    ("reply_detail_marker", "reply_detail_records",
                     "reply_detail_info", "reply_detail_refresh_btn",
                     "reply_detail_back_btn", "agent_task_reply")},
    }
    result.setdefault("reply_diagnostics", {})[tag] = diag
    (RUN / ("reply-diag-%s.json" % tag)).write_text(
        json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    driver.dump_snap("reply-diag-" + tag)
    return diag


def open_records_page():
    click("reply_detail_top_btn")
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if "办理记录" in text("stage_info"):
            return True
        time.sleep(0.3)
    return False


def open_input_page():
    click("nav_input")


def fixture_finals():
    count = 0
    try:
        lines = FIXTURE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            if json.loads(line).get("event") == "final":
                count += 1
        except ValueError:
            continue
    return count


def last_fixture_final():
    try:
        rows = [json.loads(line) for line in FIXTURE_LOG.read_text().splitlines() if line.strip()]
        return [row["text"] for row in rows if row.get("event") == "final"][-1]
    except (OSError, ValueError, KeyError, IndexError):
        return None


def fixture_log_size():
    try:
        return FIXTURE_LOG.stat().st_size
    except OSError:
        return 0


def wait_fixture_finals(n, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fixture_finals() >= n:
            return True
        time.sleep(0.4)
    return False


def wait_task_idle(timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = text("agent_task_status")
        if "本轮已回复" in status or "未开始" in status:
            return True
        time.sleep(0.3)
    return False


def append_reply(entry):
    with open(REPLIES, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()


def handle_op(item):
    kind = item.get("op")
    if kind == "click_xy":
        x, y = int(item["x"]), int(item["y"])
        return {"ok": True, "x": x, "y": y,
                "reply": bridge.get_json("/click?x=%d&y=%d&wait=1" % (x, y))}
    if kind == "click_id":
        wid = item.get("widget")
        center = driver.rect_center(wid)
        if not center:
            return {"ok": False, "error": "widget not measured: %r" % (wid,)}
        return {"ok": True, "widget": wid,
                "reply": bridge.get_json("/click?x=%d&y=%d&wait=1"
                                         % (int(center[0]), int(center[1])))}
    if kind == "state":
        data = {"ui": {name: text(name) for name in UI_TEXT_FIELDS},
                "window": [driver.window_w, driver.window_h]}
        if item.get("capture"):
            frame = bridge.get_json("/g?scale=0.25")
            if isinstance(frame, dict) and frame.get("png"):
                dst = RUN / "diagnostic-current.png"
                dst.write_bytes(Path(frame["png"]).read_bytes())
                data["diagnostic_image"] = str(dst)
        return {"ok": True, "state": data}
    if kind == "resume":
        return {"ok": True, "resume": True}
    if kind == "finish":
        return {"ok": True, "finished": True}
    return {"ok": False, "error": "unsupported op %r" % (kind,)}


def await_consent():
    # The native RC5 consent control is not in /snap; give the controller one
    # diagnostic PNG and a ready marker, then wait on the restricted queue.
    ready = {
        "kind": "traceshop-activity-consent-ready",
        "app_id": APP_ID,
        "window": [driver.window_w, driver.window_h],
        "diagnostic_scale": 0.25,
        "agent_task_status": text("agent_task_status"),
        "note": ("Review diagnostic-consent.png, then send real click_xy/click_id "
                 "ops on the control file and finish with {\"op\":\"resume\"}. "
                 "No coordinate is hard-coded by this script."),
        "control_file": str(CONTROL),
        "replies_file": str(REPLIES),
        "run_dir": str(RUN),
        "at": round(time.time(), 3),
    }
    frame = bridge.get_json("/g?scale=0.25")
    if isinstance(frame, dict) and frame.get("png"):
        diagnostic = RUN / "diagnostic-consent.png"
        diagnostic.write_bytes(Path(frame["png"]).read_bytes())
        ready["diagnostic_image"] = str(diagnostic)
    READY.write_text(json.dumps(ready, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")

    # Optional runtime coordinate from the controller env; never hard-coded.
    if CONSENT_XY:
        parts = CONSENT_XY.split(",")
        if len(parts) == 2:
            bridge.get_json("/click?x=%d&y=%d&wait=1" % (int(parts[0]), int(parts[1])))
            ready["consent_via"] = "RC1_ACTIVITY_CONSENT_XY"
            return ready

    offset = 0
    deadline = time.monotonic() + CONSENT_TIMEOUT
    while time.monotonic() < deadline:
        try:
            with open(CONTROL, "r", encoding="utf-8") as handle:
                handle.seek(offset)
                chunk = handle.read()
                offset = handle.tell()
        except OSError:
            chunk = ""
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            try:
                outcome = handle_op(item)
            except Exception as error:  # noqa: BLE001
                outcome = {"ok": False, "error": repr(error)}
            append_reply({"id": item.get("id"), "op": item.get("op"),
                          "at": round(time.time(), 3), "result": outcome})
            if item.get("op") == "resume":
                ready["consent_via"] = "controller-control-queue"
                return ready
            if item.get("op") == "finish":
                raise RuntimeError("controller finished before the check completed")
        time.sleep(0.5)
    raise RuntimeError("timed out waiting for controller consent")


def start_task():
    before = fixture_log_size()
    click("agent_start_btn")
    # First-use consent blocks the request; if traffic already arrived, skip.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if fixture_log_size() > before or "办理中" in text("agent_task_status"):
            return "no_consent_needed"
        time.sleep(0.3)
    await_consent()
    # Wait until the app either proceeds to the fixture or stays stuck starting.
    # First consent grants permission but may not resume the failed request
    # (RC1 evidence); the active guard makes a duplicate click a no-op when it
    # did resume, so retrying is safe.
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        if fixture_log_size() > before or "办理中" in text("agent_task_status"):
            return "consent_handled"
        time.sleep(0.3)
    click("agent_start_btn")
    return "consent_handled"


try:
    frame = bridge.get("/g?raw=1")
    driver.window_w = int.from_bytes(frame[16:20], "big")
    driver.window_h = int.from_bytes(frame[20:24], "big")
    result["window_size"] = [driver.window_w, driver.window_h]
    del frame

    # --- Phase 1: a manual research must NOT appear as a tool record ---
    fill("need_input", NEED)
    fill("budget_input", BUDGET)
    fill("keywords_input", HARD)
    click("research_btn")
    time.sleep(0.8)
    check("manual_research_ran", "候选" in text("stage_info") and bool(text("cand0_info")))
    check("records_page_opened_before_task", open_records_page())
    before_records = read_records()
    result["records_before_task"] = before_records
    check("manual_research_not_recorded", "尚无应用工具记录" in before_records)
    reply_diagnostics("before_task")
    open_input_page()

    # --- Phase 2: first scripted app task (real tool dispatch) ---
    result["first_task_consent"] = start_task()
    check("fixture_first_task_final", wait_fixture_finals(1, 150))
    check("task_idle_after_first", wait_task_idle())
    time.sleep(0.8)

    checks_file = RUN / "fixture-checks.json"
    if checks_file.exists():
        fixture_checks = json.loads(checks_file.read_text(encoding="utf-8"))
        result["fixture_checks"] = fixture_checks.get("checks")
        check("fixture_all_tool_assertions_pass",
              fixture_checks.get("passed") is True)
    else:
        check("fixture_all_tool_assertions_pass", False)

    check("records_page_opened_after_task", open_records_page())
    records = read_records()
    result["records_after_task"] = records
    reply_diagnostics("first_records")
    check("records_exactly_five_actual_returns",
          len(re.findall(r"(?m)^\d+\. ", records)) == 5)
    # First switch to the 完整回复 tab: the original text must already be
    # readable with no outer scroll (the layout keeps it in view), and must
    # match the fixture's final text verbatim.
    select_reply_tab()
    first_reply_no_scroll = text("reply_detail_info")
    result["first_reply_text"] = first_reply_no_scroll
    check("first_reply_visible_without_scroll",
          first_reply_no_scroll != "" and first_reply_no_scroll == last_fixture_final())
    check("first_reply_is_exact_fixture_text",
          first_reply_no_scroll == last_fixture_final())
    reply_diagnostics("first_reply")
    result["first_reveal"] = reveal_reply_text()
    reply_diagnostics("first_after_reveal")
    # Refresh consistency: read records on the records tab, then the original
    # text on the reply tab.
    click("reply_detail_refresh_btn")
    records_after_refresh = read_records()
    result["records_after_refresh"] = records_after_refresh
    select_reply_tab()
    reply_after_refresh = text("reply_detail_info")
    check("refresh_preserves_records_and_reply",
          records_after_refresh == records
          and reply_after_refresh == result["first_reply_text"])
    check("records_status_read", "状态读取：" in records)
    check("records_research_ok", "商品研究：已返回候选" in records)
    check("records_proposal_created", "创建提案：已生成待确认提案" in records)
    check("records_proposal_read_failure_not_success", "读取提案：未确认成功" in records)
    check("records_proposal_read_pending",
          "读取提案：已读到提案" in records and "待确认" in records)
    # No draft.save call was scripted; it must not appear and no draft must exist.
    check("records_no_draft_save", "保存草稿" not in records and "已保存" not in records)
    check("no_draft_written", not driver.draft_exists())

    # --- Phase 3: a second task must clear the in-memory records ---
    open_input_page()
    result["second_task_consent"] = start_task()
    time.sleep(0.8)
    check("records_page_opened_before_second_final", open_records_page())
    cleared_early = read_records()
    result["records_after_second_start"] = cleared_early
    check("new_task_clears_records", "尚无应用工具记录" in cleared_early)
    check("fixture_second_task_final", wait_fixture_finals(2, 90))
    check("task_idle_after_second", wait_task_idle())
    time.sleep(0.5)
    open_records_page()
    records2 = read_records()
    result["records_after_second_final"] = records2
    select_reply_tab()
    second_reply_no_scroll = text("reply_detail_info")
    result["second_reply_text"] = second_reply_no_scroll
    check("second_reply_visible_without_scroll",
          second_reply_no_scroll != "" and second_reply_no_scroll == last_fixture_final())
    check("second_reply_is_exact_fixture_text",
          second_reply_no_scroll == last_fixture_final())
    reply_diagnostics("second_reply")
    result["second_reveal"] = reveal_reply_text()
    reply_diagnostics("second_after_reveal")
    check("second_task_no_tools_recorded", "尚无应用工具记录" in records2)
except Exception as error:  # noqa: BLE001
    result["errors"].append(repr(error))
    result["ui_on_error"] = {name: text(name) for name in UI_TEXT_FIELDS}
    try:
        (RUN / "activity-ui-on-error.snap").write_bytes(bridge.snap_raw())
    except Exception:  # noqa: BLE001
        pass

result["passed"] = bool(result["checks"]) and all(result["checks"].values()) and not result["errors"]
(RUN / "activity-result.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                  "errors": result["errors"]}, ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 4)
