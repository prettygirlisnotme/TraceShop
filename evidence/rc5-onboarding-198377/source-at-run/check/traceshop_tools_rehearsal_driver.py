#!/usr/bin/env python3
"""Drive the official OctoSense desktop RC1 shell through Makepad's remote
bridge on a private Xvfb display (CPU-only Slurm job).

Scope: prove the unmodified official RC5 shell starts and opens a real,
bundled script-app bundle (a packed system app) in the Card runner. No model,
no network service, no bundle modification. The bridge is loopback only and the
shell is quit before the job ends.

Reads paths from the environment (set by traceshop_tools_rc1.sbatch). Writes a
single JSON result to $RC1_RUN/rehearsal-driver.json and frames to $RC1_GRABS.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"missing required env {name}")
    return value


RUN = env("RC1_RUN", required=True)
GRABS = env("RC1_GRABS", f"{RUN}/grabs")
BIN = env("RC1_BIN", required=True)
PORT = int(env("RC1_PORT", "18241"))
LOG = env("RC1_LOG", f"{RUN}/rc1-shell.log")
HOME_DIR = env("RC1_SHELL_HOME", f"{RUN}/shell-home")
APP_DATA = env("RC1_APP_DATA", f"{RUN}/shell-apps")
CORE_DIR = env("RC1_CORE_DIR", f"{RUN}/shell-octos")

os.makedirs(GRABS, exist_ok=True)
os.makedirs(HOME_DIR, exist_ok=True)
os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(CORE_DIR, exist_ok=True)

result = {
    "binary": BIN,
    "port": PORT,
    "bridge_up": False,
    "desktop_up": False,
    "opened_bundle": None,
    "script_tools_dispatch_verified": False,
    "host_confirmation_verified": False,
    "card_running_marker": None,
    "snaps": {},
    "frames": {},
    "errors": [],
    "log_tail": None,
}


def http(route, timeout=8, **params):
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"http://127.0.0.1:{PORT}/{route}{query}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return json.load(response)
        except Exception as error:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(0.3)
    raise RuntimeError("unreachable")


def get_text(route, **params):
    try:
        return json.dumps(http(route, **params))
    except Exception:  # noqa: BLE001
        return ""


def snap(query):
    try:
        data = http("snap", q=query)
    except Exception:  # noqa: BLE001
        return []
    return [(item.get("i"), item.get("ty"), item.get("t")) for item in data.get("s", [])]


def grab(name):
    # Presentation-check disables the harness's store-stage grabs so the run
    # writes exactly one proposal-page diagnostic PNG. Default keeps them.
    if os.environ.get("RC1_STORE_GRABS", "1") == "0":
        return None
    for _ in range(8):
        try:
            data = http("g", scale=0.5)
            png = data.get("png")
            if png:
                dst = os.path.join(GRABS, f"{name}.png")
                with open(png, "rb") as src, open(dst, "wb") as out:
                    out.write(src.read())
                result["frames"][name] = {"path": dst, "bytes": os.path.getsize(dst)}
                return dst
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    return None


def key(code, cmd=0):
    try:
        http("k", k="press", c=code, wait=1, **({"cmd": 1} if cmd else {}))
    except Exception:  # noqa: BLE001
        pass


def type_keys(text):
    for ch in text:
        if ch == " ":
            key("Space")
        elif ch == "-":
            key("Minus")
        elif ch.isalpha():
            key("Key" + ch.upper())
        elif ch.isdigit():
            key("Key" + ch)
        else:
            continue


def log_text():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def wait_log(needle, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if needle in log_text():
            return True
        time.sleep(0.5)
    return False


def wait_bridge(timeout=120):
    deadline = time.monotonic() + timeout
    pattern = re.compile(r"listening on 127\.0\.0\.1:(\d+)")
    while time.monotonic() < deadline:
        match = pattern.search(log_text())
        if match:
            result["bridge_port_seen"] = int(match.group(1))
            return True
        time.sleep(0.5)
    return False


print(f"[driver] launching {BIN} display={os.environ.get('DISPLAY')} port={PORT}", flush=True)
shell_env = dict(os.environ)
shell_env.update({
    "OCTOSENSE_HOME": HOME_DIR,
    "OCTOS_APP_CORE_DIR": CORE_DIR,
    "OCTOSENSE_APP_DATA": APP_DATA,
    "OCTOSENSE_MAIL_VAULT": "file",
    "OCTOSENSE_LLM_VAULT": "file",
    "MAKEPAD_HIDE_WINDOWS": "1",
    "MAKEPAD_REMOTE": str(PORT),
})
shell_env.pop("MAKEPAD_HOME", None)
shell_env.pop("MAKEPAD_WM_ROOT", None)
shell_env.pop("MAKEPAD_WM_THEME", None)

log_fh = open(LOG, "wb")
proc = subprocess.Popen([BIN], env=shell_env, stdout=log_fh, stderr=subprocess.STDOUT,
                        cwd=RUN, start_new_session=True)


def stop():
    try:
        http("quit", timeout=3)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(2)
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:  # noqa: BLE001
            pass


try:
    result["bridge_up"] = wait_bridge()
    if result["bridge_up"]:
        # Desktop is up once the main window is queryable.
        for _ in range(120):
            if snap("main_window"):
                result["desktop_up"] = True
                break
            time.sleep(0.5)
        grab("01-desktop")

        # Card runtime registers app_tools.dispatch lazily in CardApp.register.
        # Open a shipped script app before App Hub snapshots host capabilities.
        key("Space", cmd=1)
        time.sleep(0.8)
        type_keys("photos")
        time.sleep(0.8)
        key("Return")
        result["card_runtime_warmed"] = wait_log("card: os.photos running under", timeout=30)
        if not result["card_runtime_warmed"]:
            raise RuntimeError("shipped Card runtime did not initialize")
        key("Space", cmd=1)
        time.sleep(0.8)
        type_keys("app hub")
        time.sleep(0.8)
        key("Return")
        time.sleep(1)
        key("Escape")
        # The native host-consent overlay is not part of App Hub's /snap.
        # Measured on run-196517/grabs/03-after.png (700x450 at scale=.5):
        # "Don't allow" centre (262.5,309) => native (525,618).
        # Deny only App Hub's optional agent start; installation does not need it.
        result["apphub_agent_denial"]=http("click",x=525,y=618,wait=1)
        time.sleep(0.5)
        def rows():
            return http("snap").get("s", [])
        def record_step(name):
            data=rows()
            # Card Splash carries the full app source; omit it from diagnostic snapshots.
            clean=[{k:v for k,v in w.items() if k in ("i","ty","t","r","w")} for w in data if "Splash" not in w.get("ty","")]
            result["snaps"][name]=clean
            with open(f"{RUN}/snap-{name}.json","w",encoding="utf-8") as f:
                json.dump(clean,f,ensure_ascii=False,indent=2)
            return data
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            rr=rows()
            if any("TraceShop" in (w.get("t") or "") for w in rr if "Splash" not in w.get("ty","")):break
            time.sleep(0.5)
        record_step("apphub")
        result["action_labels"]=[w.get("t") for w in rows() if w.get("i")=="action"]
        install_pending=False
        for step in range(12):
            if "card: traceshop.shopping running under" in log_text():break
            rr=rows()
            install_pending=install_pending or any((w.get("t") or "").startswith("Install TraceShop") for w in rr)
            confirming=install_pending
            wanted=("INSTALL",) if confirming else ("GET","OPEN")
            targets=[w for w in rr if (w.get("t") or "").strip().upper() in wanted and "Splash" not in w.get("ty","")]
            if confirming and not targets:
                # The six-tool permission summary puts the official Install
                # control below the current viewport. Scroll the real store.
                result.setdefault("actions",[]).append({"scroll_confirmation":True})
                http("m",k="scroll",x=600,y=500,dy=420,wait=1)
                time.sleep(0.4)
                record_step("scroll-"+str(step))
                continue
            if not targets:break
            w=targets[0]
            result.setdefault("actions",[]).append({"id":w.get("i"),"text":w.get("t")})
            rect=w.get("r")
            if not rect: raise RuntimeError("store action has no measured rectangle")
            x,y,width,height=rect
            result["actions"][-1]["reply"]=http("click",x=int(x+width/2),y=int(y+height/2),wait=1)
            time.sleep(1)
            if (w.get("t") or "").strip().upper()=="INSTALL":
                install_pending=False
                http("m",k="scroll",x=600,y=500,dy=-1800,wait=1)
                time.sleep(0.4)
            record_step("install-"+str(step))
        opened=wait_log("card: traceshop.shopping running under",timeout=35)
        result["card_running_marker"]="card: traceshop.shopping running under" if opened else None
        if opened:
            result["opened_bundle"]="traceshop.shopping"
            record_step("traceshop-open")
            grab("02-traceshop")
        else:
            record_step("not-open")
        grab("03-after")

        # Optional manual-UI native showcase, only when the parent job opts in.
        # Runs against the SAME already-opened shell/bridge; it launches no
        # shell and sends no model/agent request. Failure is recorded as an
        # error and fails this run; default (unset) behavior is unchanged.
        if opened and os.environ.get("RC1_NATIVE_SHOWCASE") == "1":
            # Reused verbatim from the selection-record check harness; the only
            # change is an env override so presentation-check can point at its
            # own UI script without editing the shared Store driver.
            showcase_driver = os.environ.get("RC1_SHOWCASE_SCRIPT") or os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "decision_ui.py")
            result["native_showcase"] = {"enabled": True, "driver": showcase_driver}
            try:
                showcase_proc = subprocess.run(
                    [sys.executable or "python3", showcase_driver],
                    env=dict(os.environ), capture_output=True, timeout=260)
                result["native_showcase"].update({
                    "returncode": showcase_proc.returncode,
                    "stdout": showcase_proc.stdout.decode("utf-8", "replace")[-2000:],
                    "stderr": showcase_proc.stderr.decode("utf-8", "replace")[-4000:],
                })
                if showcase_proc.returncode != 0:
                    result["errors"].append(
                        "native showcase driver rc=%d" % showcase_proc.returncode)
            except Exception as error:  # noqa: BLE001
                result["native_showcase"]["error"] = repr(error)
                result["errors"].append("native showcase: " + repr(error))
except Exception as error:  # noqa: BLE001
    result["errors"].append(repr(error))
finally:
    stop()
    log_fh.close()

tail = [line[:400] for line in log_text().splitlines()[-60:]]
result["log_tail"] = tail
result["shell_exit_code"] = proc.returncode
with open(f"{RUN}/rehearsal-driver.json", "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
print(json.dumps({k: result[k] for k in
                  ("bridge_up", "desktop_up", "opened_bundle", "card_running_marker", "errors")},
                 ensure_ascii=False))
_exit = 0 if result["opened_bundle"] == "traceshop.shopping" else 3
_showcase = result.get("native_showcase") or {}
if _showcase.get("enabled") and _showcase.get("returncode") != 0:
    _exit = 4
sys.exit(_exit)
