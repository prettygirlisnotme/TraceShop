#!/usr/bin/env python3
"""Drive the real native card-host instance of native/traceshop-app and record
continuous real window frames, using only the standard library and the official
makepad remote bridge (GET /snap, /click, /t, /k, /m, /g, /quit).

Development/verification tool, not part of the app. Runs inside the Slurm
container with DISPLAY pointing at a private Xvfb. No network, no keys.

The window frames are the app's own rendered frames (GET /g?raw=1), captured
continuously; they are encoded to a video afterwards. No mock UI and no
screenshot stitching: these are real successive window frames.
"""
import argparse
import json
import os
import threading
import time
import urllib.parse
import urllib.request

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def log(msg):
    print("[driver] " + msg, flush=True)


class Bridge:
    def __init__(self, port, host="127.0.0.1", timeout=25.0):
        self.base = "http://%s:%d" % (host, port)
        self.timeout = timeout

    def get(self, path, timeout=None):
        url = self.base + path
        last = None
        for _ in range(4):
            try:
                with urllib.request.urlopen(url, timeout=timeout or self.timeout) as r:
                    return r.read()
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(0.25)
        raise RuntimeError("GET %s failed: %r" % (path, last))

    def get_json(self, path, timeout=None):
        try:
            return json.loads(self.get(path, timeout))
        except ValueError:
            return None

    def snap_raw(self):
        data = self.get("/snap")
        return data

    def snap(self):
        data = self.get_json("/snap")
        if not isinstance(data, dict):
            return []
        return data.get("s") or []

    def find(self, wid):
        for w in self.snap():
            if w.get("i") == wid:
                return w
        return None

    def text(self, wid):
        w = self.find(wid)
        return (w or {}).get("t")

    def ids(self):
        return {w.get("i") for w in self.snap() if w.get("i")}

    def ready(self):
        widgets = self.snap()
        content = [w for w in widgets if w.get("ty") not in ("Splash", "Window")]
        return bool(content) and any((w.get("t") or "").strip() for w in content)


class Recorder(threading.Thread):
    """Capture GET /g?raw=1 frames continuously until stopped."""

    def __init__(self, bridge, outdir, fps=4.0):
        super().__init__(daemon=True)
        self.bridge = bridge
        self.outdir = outdir
        self.period = 1.0 / fps
        self._stop = threading.Event()
        self._pause = threading.Event()
        self.frames = []
        self.times = []
        self.errors = 0
        self.t0 = None

    def pause(self):
        self._pause.set()

    def resume(self):
        self._pause.clear()

    def stop(self):
        self._stop.set()

    def duration(self):
        if self.t0 is None or not self.times:
            return 0.0
        return self.times[-1] - self.t0

    def run(self):
        os.makedirs(self.outdir, exist_ok=True)
        i = 0
        while not self._stop.is_set():
            start = time.time()
            if not self._pause.is_set():
                try:
                    data = self.bridge.get("/g?raw=1", timeout=15)
                    if data.startswith(PNG_MAGIC):
                        path = os.path.join(self.outdir, "f%05d.png" % i)
                        with open(path, "wb") as fh:
                            fh.write(data)
                        self.frames.append(path)
                        if self.t0 is None:
                            self.t0 = start
                        self.times.append(start)
                        i += 1
                    else:
                        self.errors += 1
                except Exception:  # noqa: BLE001
                    self.errors += 1
            elapsed = time.time() - start
            self._stop.wait(max(0.0, self.period - elapsed))


class Driver:
    def __init__(self, bridge, out, frames_dir, app_data, jail_id):
        self.b = bridge
        self.out = out
        self.frames_dir = frames_dir
        self.app_data = app_data
        self.jail = os.path.join(app_data, jail_id)
        self.steps = []
        self.window_w = 412
        self.window_h = 892
        self._scroll_sign = 1

    # ---------------------------------------------------------------- helpers
    def shot(self, name):
        os.makedirs(self.out, exist_ok=True)
        data = self.b.get("/g?raw=1")
        path = os.path.join(self.out, name)
        with open(path, "wb") as fh:
            fh.write(data)
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        log("shot %s (%dx%d, %d bytes)" % (path, w, h, len(data)))
        return path

    def dump_snap(self, name):
        try:
            data = self.b.snap_raw()
            path = os.path.join(self.out, "snap-%s.json" % name)
            with open(path, "wb") as fh:
                fh.write(data)
        except Exception:  # noqa: BLE001
            pass

    def draft_path(self):
        return os.path.join(self.jail, "purchase_draft.json")

    def draft_exists(self):
        return os.path.isfile(self.draft_path())

    def draft_json(self):
        try:
            with open(self.draft_path(), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def record(self, step, **kw):
        entry = {"step": step, "at": round(time.time(), 3)}
        entry.update(kw)
        self.steps.append(entry)
        log("step %s %s" % (step, json.dumps(kw, ensure_ascii=False)[:500]))

    def rect_center(self, wid):
        w = self.b.find(wid)
        if not w or not w.get("r"):
            return None
        x, y, ww, hh = w["r"]
        return (x + ww / 2.0, y + hh / 2.0, w["r"])

    def scroll(self, dy):
        self.b.get("/m?k=scroll&x=%d&y=%d&dy=%d&wait=1"
                   % (self.window_w // 2, int(self.window_h * 0.55), int(dy)))

    def in_view(self, c):
        return bool(c) and 45 <= c[1] <= self.window_h - 55

    def reveal(self, wid, tries=10, step=380):
        """Scroll stepwise until the widget is in the window and present."""
        c = self.rect_center(wid)
        if self.in_view(c):
            return c
        for direction in (self._scroll_sign, -self._scroll_sign):
            for _ in range(tries):
                self.scroll(step * direction)
                time.sleep(0.35)
                c = self.rect_center(wid)
                if self.in_view(c):
                    self._scroll_sign = direction
                    return c
            for _ in range(tries):
                self.scroll(-step * direction)
                time.sleep(0.12)
        return self.rect_center(wid)

    def click(self, wid, wait=0.6):
        c = self.reveal(wid)
        if c is None:
            self.record("click_miss", widget=wid)
            return False
        self.b.get("/click?x=%d&y=%d&wait=1" % (int(c[0]), int(c[1])))
        time.sleep(wait)
        return True

    def key(self, name):
        self.b.get("/k?k=down&c=%s" % name)
        time.sleep(0.12)
        self.b.get("/k?k=up&c=%s" % name)

    def clear_and_type(self, wid, text, recorder):
        if recorder:
            recorder.pause()
        try:
            w = self.b.find(wid)
            current = (w or {}).get("t") or ""
            self.click(wid, wait=0.4)
            for _ in range(len(current) + 3):
                self.key("Backspace")
            q = urllib.parse.quote(text, safe="")
            self.b.get("/t?t=%s&wait=1" % q)
            time.sleep(0.6)
        finally:
            if recorder:
                recorder.resume()
        return self.b.text(wid)

    # ------------------------------------------------------------------ steps
    def run(self):
        rec = Recorder(self.b, self.frames_dir, fps=4.0)
        rec.start()
        try:
            self._run_sequence(rec)
        finally:
            rec.stop()
            time.sleep(0.5)
            self.recorder = rec
        return rec

    def _run_sequence(self, rec):
        deadline = time.time() + 40
        while time.time() < deadline and not self.b.ready():
            time.sleep(0.2)
        self.record("app_ready", ready=bool(self.b.ready()))
        time.sleep(1.0)
        self.shot("00-start.png")
        self.dump_snap("00-start")

        # --- 1. invalid budget shows a reason, no candidates -----------------
        self.clear_and_type("budget_input", "abc", rec)
        self.click("research_btn")
        time.sleep(0.5)
        self.record("invalid_budget", research_status=self.b.text("research_status"),
                    draft_exists=self.draft_exists())
        self.shot("01-invalid-budget.png")

        # --- 1b. no result for budget+keyword shows a reason -----------------
        self.clear_and_type("budget_input", "5", rec)
        self.clear_and_type("need_input", "办公用无线鼠标，安静", rec)
        self.clear_and_type("keywords_input", "wireless", rec)
        self.click("research_btn")
        time.sleep(0.5)
        self.record("no_result", research_status=self.b.text("research_status"),
                    draft_exists=self.draft_exists())
        self.shot("02-no-result.png")

        # --- 2. office preset -> research -> candidates (VicTsing first) -----
        self.click("nav_input")
        self.click("preset_office")
        time.sleep(0.4)
        self.record("preset_office",
                    need=self.b.text("need_input"),
                    budget=self.b.text("budget_input"),
                    keywords=self.b.text("keywords_input"))
        self.click("research_btn")
        time.sleep(0.6)
        self.record("research", stage_info=self.b.text("stage_info"),
                    cand0=self.b.text("cand0_info"),
                    cand1=self.b.text("cand1_info"),
                    cand2=self.b.text("cand2_info"))
        self.shot("03-candidates.png")

        # --- 3. pick candidate 0 -> pending proposal -------------------------
        self.click("cand0_btn")
        time.sleep(0.6)
        self.record("pick_cand0", stage_info=self.b.text("stage_info"),
                    proposal_info=self.b.text("proposal_info"),
                    proposal_status=self.b.text("proposal_status"),
                    draft_exists=self.draft_exists())
        self.shot("04-proposal.png")
        self.dump_snap("04-proposal")

        # --- 4. review button: real "no service" and no draft ----------------
        clicked = self.click("review_btn")
        self.dump_snap("05-after-review-click")
        agent_status = None
        deadline = time.time() + 8
        while time.time() < deadline:
            self.reveal("agent_status", tries=4, step=250)
            agent_status = self.b.text("agent_status")
            if agent_status:
                break
            time.sleep(0.4)
        self.record("review_no_service", review_clicked=clicked,
                    agent_status=agent_status,
                    agent_answer=self.b.text("agent_answer"),
                    draft_exists=self.draft_exists(),
                    proposal_status=self.b.text("proposal_status"))
        self.shot("05-review-noservice.png")

        # --- 5. simulated quote change invalidates the proposal -------------
        self.click("price_btn")
        time.sleep(0.6)
        self.record("price_change", proposal_status=self.b.text("proposal_status"),
                    proposal_info=self.b.text("proposal_info"))
        self.shot("06-pricechange.png")

        # --- 6. confirming the stale proposal is refused, no draft ----------
        self.click("confirm_btn")
        time.sleep(0.6)
        self.record("confirm_stale", proposal_status=self.b.text("proposal_status"),
                    draft_exists=self.draft_exists())

        # --- 7. re-research, pick, confirm -> save + independent readback ----
        self.click("nav_input")
        self.click("research_btn")
        time.sleep(0.6)
        self.record("re_research", stage_info=self.b.text("stage_info"),
                    cand0=self.b.text("cand0_info"))
        self.click("cand0_btn")
        time.sleep(0.6)
        self.record("re_pick", proposal_info=self.b.text("proposal_info"),
                    proposal_status=self.b.text("proposal_status"))
        self.click("confirm_btn")
        time.sleep(0.8)
        self.record("confirm_saved",
                    draft_status=self.b.text("draft_status"),
                    draft_info=self.b.text("draft_info"),
                    draft_exists=self.draft_exists(),
                    draft_json=self.draft_json())
        self.shot("07-saved.png")

        # --- 8. independent readback button ---------------------------------
        self.click("readback_btn")
        time.sleep(0.6)
        self.record("readback", draft_status=self.b.text("draft_status"),
                    draft_info=self.b.text("draft_info"))
        self.shot("08-readback.png")

        # --- 9. nav across the four stages (real clicks) --------------------
        for nav in ("nav_input", "nav_candidates", "nav_proposal", "nav_draft"):
            self.click(nav, wait=0.4)
        self.record("nav_stages", stage_info=self.b.text("stage_info"))
        self.shot("09-nav-draft.png")

        self.record("run1_done", frames=len(rec.frames), draft_exists=self.draft_exists())

    def run_restart(self):
        rec = Recorder(self.b, self.frames_dir, fps=4.0)
        rec.start()
        try:
            deadline = time.time() + 40
            while time.time() < deadline and not self.b.ready():
                time.sleep(0.2)
            time.sleep(2.0)
            self.record("restart_ready", ready=bool(self.b.ready()),
                        draft_status=self.b.text("draft_status"),
                        draft_info=self.b.text("draft_info"),
                        stage_info=self.b.text("stage_info"),
                        draft_exists=self.draft_exists(),
                        draft_json=self.draft_json())
            self.shot("10-restart.png")
            time.sleep(6.0)
            self.record("restart_done", frames=len(rec.frames))
        finally:
            rec.stop()
            time.sleep(0.5)
        return rec


def wait_for_bridge(port, timeout):
    b = Bridge(port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if b.get_json("/s") is not None:
                return b
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    raise RuntimeError("bridge on port %d did not answer within %ss" % (port, timeout))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--frames", required=True)
    p.add_argument("--app-data", required=True)
    p.add_argument("--jail-id", default="traceshop.shopping")
    p.add_argument("--mode", choices=["full", "restart"], default="full")
    p.add_argument("--ready-timeout", type=float, default=60.0)
    args = p.parse_args()

    bridge = wait_for_bridge(args.port, args.ready_timeout)
    info = bridge.get_json("/s")
    if isinstance(info, dict):
        log("bridge /s: " + json.dumps(info)[:400])
    driver = Driver(bridge, args.out, args.frames, args.app_data, args.jail_id)
    if args.mode == "restart":
        rec = driver.run_restart()
    else:
        rec = driver.run()
    report = {
        "mode": args.mode,
        "port": args.port,
        "steps": driver.steps,
        "frames": len(rec.frames),
        "frame_errors": rec.errors,
        "record_seconds": round(rec.duration(), 3),
        "frames_dir": args.frames,
    }
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "driver-report-%s.json" % args.mode), "w",
              encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    log("wrote driver-report-%s.json with %d steps (%d frames, %.1fs)"
        % (args.mode, len(driver.steps), len(rec.frames), rec.duration()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
