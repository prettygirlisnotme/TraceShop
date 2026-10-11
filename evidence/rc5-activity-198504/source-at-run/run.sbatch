#!/usr/bin/env bash
#SBATCH --job-name=gosim-activity
#SBATCH --partition=cluster02
#SBATCH --account=msc
#SBATCH --qos=msc
#SBATCH -c 4
#SBATCH --time=00:06:00
#SBATCH --output=/projects/user007ssd/projects/gosim-agentic-app-2026/runs/activity-%j.log
# Focused check for native/traceshop-activity: official unmodified RC5 shell, real
# Store install, a job-owned deterministic localhost fixture (NO REAL MODEL), and
# the app-side "办理记录" activity log read back from the real UI. Zero paid model
# requests, no video, no download. Reuses the approved private test keys unchanged;
# not production signing.
#
# Reuses native/traceshop-onboarding/check/run.sbatch for the RC5 cache, container,
# old Hub CLI and the three private test keys; only SCRIPTS/RUN/SCRATCH/CAND_BUNDLE/
# port/job/time are specific to this directory. The reused shared helper scripts are:
#   check/native_shop_driver.py               (copy of the shared UI/Store driver)
#   check/traceshop_tools_rehearsal_driver.py (Store driver + fixture launch)
#   check/activity_fixture.py                 (deterministic protocol fixture)
#   check/activity_ui.py                      (UI check; consent via control queue)
set -uo pipefail
ulimit -c 0

ROOT=/projects/user007ssd/projects/gosim-agentic-app-2026
JOB=${SLURM_JOB_ID:-manual}
RUN="$ROOT/native/traceshop-activity/check/run-$JOB"
SCRATCH="$ROOT/scratch/activity-20261011/$JOB"
CHOME="$ROOT/container-home"
SQSH="$ROOT/containers/rust-1.98.1-bookworm.sqsh"
LIBS_ROOT="$ROOT/container-libs/root"
RT_ROOT="$ROOT/container-libs/runtime-root"
CACHE="$ROOT/cache/appimages"
HUB="$ROOT/cache/cargo-target-hub-655114c/release/hub"
SCRIPTS="$ROOT/native/traceshop-activity/check"
APPIMG=octosense_0.1.0-rc.5_amd64.deb
APPSHA=e0a836aea8e56864f7f5d30233624a9fca3fd6a75db99c1cf26243e8376f2caa
APP_SIZE=302047982
CAND_BUNDLE="${RC1_CAND_BUNDLE:-$ROOT/native/traceshop-activity/bundle}"
PORT=18349
RC1_NATIVE_SHOWCASE=1
RC1_SHOWCASE_SCRIPT="$SCRIPTS/activity_ui.py"
# Keep exactly the diagnostic PNGs written by activity_ui.py; suppress store grabs.
RC1_STORE_GRABS=0
# 6 fixture requests for task 1 + 1 no-tool final for task 2.
TRACESHOP_FIXTURE_MAX_REQUESTS="${TRACESHOP_FIXTURE_MAX_REQUESTS:-7}"
# Optional runtime consent coordinate/timeout for the controller (never hard-coded).
RC1_ACTIVITY_CONSENT_XY="${RC1_ACTIVITY_CONSENT_XY:-}"
RC1_ACTIVITY_CONSENT_TIMEOUT="${RC1_ACTIVITY_CONSENT_TIMEOUT:-180}"

export ROOT JOB RUN SCRATCH CHOME SQSH LIBS_ROOT RT_ROOT CACHE HUB SCRIPTS
export APPIMG APPSHA CAND_BUNDLE PORT RC1_NATIVE_SHOWCASE RC1_SHOWCASE_SCRIPT RC1_STORE_GRABS
export TRACESHOP_FIXTURE_MAX_REQUESTS RC1_ACTIVITY_CONSENT_XY RC1_ACTIVITY_CONSENT_TIMEOUT
export TMPDIR="$SCRATCH/tmp" XDG_CACHE_HOME="$ROOT/cache/xdg" \
       ENROOT_CACHE_PATH="$ROOT/cache/enroot" ENROOT_TEMP_PATH="$SCRATCH/enroot"

mkdir -p "$RUN" "$SCRATCH" "$SCRATCH/tmp" "$CACHE" "$CHOME" "$ROOT/runs" "$SCRATCH/enroot"

XVFB_PID=0
cleanup() {
  rc=$?
  [ "$XVFB_PID" -gt 0 ] && kill -TERM "$XVFB_PID" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

echo "job=$JOB node=$(hostname) date=$(date -u +%FT%TZ) cpus=$(nproc)"

# No network here. The official RC5 DEB (302047982 bytes) must already exist in the
# shared cache; verify the fixed size and hash and exit clearly if it is missing or wrong.
# This script never downloads the package or the SHA256SUMS file.
if [ ! -f "$CACHE/$APPIMG" ]; then
  echo "RC5_CACHE_MISSING: expected $CACHE/$APPIMG ($APP_SIZE bytes); not downloading." | tee "$RUN/cache-status.txt"
  exit 17
fi
[ "$(stat -c %s "$CACHE/$APPIMG")" = "$APP_SIZE" ] || { echo "RC5_CACHE_SIZE_MISMATCH: $CACHE/$APPIMG; not downloading." | tee "$RUN/cache-status.txt"; exit 17; }
[ "$(sha256sum "$CACHE/$APPIMG" | cut -d' ' -f1)" = "$APPSHA" ] || { echo "RC5_CACHE_SHA_MISMATCH: $CACHE/$APPIMG; not downloading." | tee "$RUN/cache-status.txt"; exit 17; }
printf 'package=%s\nsha256=%s\nbytes=%s\nunmodified_official=true\nsource=existing_cache_no_download\n' "$APPIMG" "$APPSHA" "$(stat -c %s "$CACHE/$APPIMG")" > "$RUN/appimage-metadata.txt"
# ---- inner step inside the rust container ----------------------------------
cat > "$RUN/rc1_inner.sh" <<'INNER'
#!/usr/bin/env bash
set -uo pipefail
RUN="${GOSIM_RUN:?}"; CACHE="${GOSIM_CACHE:?}"; APPIMG="${GOSIM_APPIMG:?}"
PORT="${GOSIM_PORT:?}"; CAND="${GOSIM_CAND:?}"; HUB="${GOSIM_HUB:?}"
RT_ROOT="${GOSIM_RT:?}"; LIBS_ROOT="${GOSIM_LIBS:?}"; SCRIPTS="${GOSIM_SCRIPTS:?}"
SCRATCH="${GOSIM_SCRATCH:?}"
LOG="$RUN/rc1-inner-$SLURM_JOB_ID.log"
: > "$LOG"
log(){ echo "$@" | tee -a "$LOG"; }
GRABS="$RUN/grabs"; mkdir -p "$GRABS"
WORK=/tmp/rc1-work; rm -rf "$WORK"; mkdir -p "$WORK"

# runtime libs (reused from native_shop_run.sbatch)
export PATH="$RT_ROOT/usr/bin:$LIBS_ROOT/usr/bin:/usr/local/bin:/usr/bin:/bin"
LD="$RT_ROOT/usr/lib/x86_64-linux-gnu:$LIBS_ROOT/usr/lib/x86_64-linux-gnu:$LIBS_ROOT/usr/lib/x86_64-linux-gnu/pulseaudio:$LIBS_ROOT/usr/lib:$LIBS_ROOT/lib/x86_64-linux-gnu:$LIBS_ROOT/usr/lib/x86_64-linux-gnu/dri"
export LD_LIBRARY_PATH="$LD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LIBGL_DRIVERS_PATH="$LIBS_ROOT/usr/lib/x86_64-linux-gnu/dri"
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
export EGL_PLATFORM=x11

# Unpack the official .deb without apt/install/root or changing any ELF/receipt.
mkdir -p "$WORK/squashfs-root"
dpkg-deb -x "$CACHE/$APPIMG" "$WORK/squashfs-root" > "$RUN/package-extract.log" 2>&1 || exit 21
# find the shell binary
BIN=""
for cand in "$WORK/squashfs-root/usr/bin/octosense" "$WORK/squashfs-root/AppRun"; do
  [ -x "$cand" ] && { BIN="$cand"; break; }
done
log "=== squashfs-root listing ==="
find "$WORK/squashfs-root" -maxdepth 3 \( -name 'octosense' -o -name 'AppRun' -o -name 'octos-kernel' -o -type d -name 'octosense' \) 2>/dev/null | tee -a "$LOG"
log "shell_binary=$BIN"
[ -n "$BIN" ] || { log "RC1_BINARY_NOT_FOUND"; exit 22; }
MAKEPAD_PACKAGE_DIR="$WORK/squashfs-root/usr/lib/octosense"
[ -d "$MAKEPAD_PACKAGE_DIR" ] || MAKEPAD_PACKAGE_DIR=""
log "makeapd_package_dir=$MAKEPAD_PACKAGE_DIR"
octos_kernel_dir="$(dirname "$BIN")"

# Approved private legacy rehearsal; exactly these three protected keys.
umask 077
KEYS="$ROOT/private/script-tools-rehearsal-20261009/keys"
M="$SCRATCH/mirror"; B="$SCRATCH/signed-bundle"
[ -d "$KEYS" ] || exit 32
mkdir -p "$M" "$B"
python3 - "$CAND" <<'PY'
from pathlib import Path
import hashlib,json,sys
p=Path(sys.argv[1]);expect=json.loads((p.parent/'expected-sha256.json').read_text())
for name,sha in expect.items():
 if hashlib.sha256((p/name).read_bytes()).hexdigest()!=sha:raise SystemExit("candidate hash mismatch: "+name)
PY
[ "$?" = 0 ] || exit 29
mkdir -p "$RUN/source-at-run/bundle"
cp "$CAND/main.splash" "$CAND/tools.json" "$CAND/AGENT.md" "$RUN/source-at-run/bundle/"
cp "$CAND/../expected-sha256.json" "$RUN/source-at-run/expected-sha256.json"
mkdir -p "$RUN/source-at-run/check"
cp "$SCRIPTS/activity_fixture.py" "$SCRIPTS/activity_ui.py" "$SCRIPTS/native_shop_driver.py" \
   "$SCRIPTS/traceshop_tools_rehearsal_driver.py" "$SCRIPTS/run.sbatch" "$RUN/source-at-run/check/"
printf 'hub_cli_source=655114c4943cd2490daaefa2173e7b5aaa20669f\nstructural_check_only=true\nrc5_runtime_store_admission_is_separate=true\nno_real_model_fixture=true\n' > "$RUN/checker-source.txt"
cp -a "$CAND/." "$B/"
sha256sum "$CAND/main.splash" "$CAND/tools.json" > "$RUN/candidate-sha.txt"
python3 - "$B/listing.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads(p.read_text())
d['platforms']=['linux']
d['publisher']['name']='TraceShop private rehearsal (test only)'
d['release_notes']='Private Linux test copy; no public release or compatibility claim.'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
PY
"$HUB" stamp "$B" > "$RUN/stamp.txt" 2>&1 || exit 30
"$HUB" check "$B" --allow-unsigned > "$RUN/unsigned-check.txt" 2>&1 || exit 31
for name in anchor working publisher; do
 [ -f "$KEYS/$name.key" ] || { echo "Existing approved test key missing; do not regenerate"; exit 32; }
done
printf "key_count=3\nprivate_test_only=true\n" > "$RUN/key-generation-status.txt"
ANCHOR=$("$HUB" pubkey "$KEYS/anchor.key")
PUB=$("$HUB" pubkey "$KEYS/publisher.key")
CERT=$("$HUB" certify --anchor "$KEYS/anchor.key" --working "$KEYS/working.key")
"$HUB" sign-manifest "$B" --key "$KEYS/publisher.key" --key-id traceshop-private-test > "$RUN/sign.txt" 2>&1 || exit 33
"$HUB" publish "$B" --catalog "$M/catalog.json" --key "$KEYS/working.key" --anchor-cert "$CERT" \
 --publisher traceshop-private-test --publisher-key "traceshop-private-test=$PUB" \
 --out "$M" --anchor "$ANCHOR" > "$RUN/publish.txt" 2>&1 || exit 34
"$HUB" verify "$M/catalog.json" --anchor "$ANCHOR" > "$RUN/verify.txt" 2>&1 || exit 35
export OCTOSENSE_HUB_CATALOG=legacy OCTOSENSE_HUB="$M" OCTOSENSE_HUB_ANCHOR="$ANCHOR"
printf 'approved_test_only=true\nkey_count=3\nglobal_trust_modified=false\nmirror=%s\n' "$M" > "$RUN/signing-scope.txt"

# private Xvfb
DN=99
while [ -e "/tmp/.X11-unix/X$DN" ] && [ "$DN" -gt 90 ]; do DN=$((DN-1)); done
export DISPLAY=":$DN"; unset WAYLAND_DISPLAY || true
export XKB_CONFIG_ROOT="$RT_ROOT/usr/share/X11/xkb" XKB_BIN_DIRECTORY="$RT_ROOT/usr/bin"
mkdir -p /tmp/.X11-unix 2>/dev/null || true; chmod 1777 /tmp/.X11-unix 2>/dev/null || true
[ -x /usr/bin/xkbcomp ] || { [ -x "$RT_ROOT/usr/bin/xkbcomp" ] && cp -f "$RT_ROOT/usr/bin/xkbcomp" /usr/bin/xkbcomp 2>/dev/null; }
[ -e "$RT_ROOT/usr/lib/x86_64-linux-gnu/libxkbfile.so.1" ] && cp -fL "$RT_ROOT/usr/lib/x86_64-linux-gnu/libxkbfile.so.1" /usr/lib/x86_64-linux-gnu/ 2>/dev/null
MESA_JSON="$LIBS_ROOT/usr/share/glvnd/egl_vendor.d/50_mesa.json"
if [ -f "$MESA_JSON" ]; then
  export __EGL_VENDOR_LIBRARY_FILENAMES="$MESA_JSON"
  mkdir -p /usr/share/glvnd/egl_vendor.d 2>/dev/null || true
  cp -fL "$MESA_JSON" /usr/share/glvnd/egl_vendor.d/ 2>/dev/null || true
fi
Xvfb ":$DN" -screen 0 1600x1000x24 -ac -nolisten tcp +extension GLX +extension DRI2 +extension DRI3 \
  +render -noreset -xkbdir "$RT_ROOT/usr/share/X11/xkb" > "$RUN/xvfb-rc1-$SLURM_JOB_ID.log" 2>&1 &
XVFB_PID=$!
for i in $(seq 1 40); do [ -e "/tmp/.X11-unix/X$DN" ] && break; kill -0 "$XVFB_PID" 2>/dev/null || break; sleep 0.5; done
echo "xvfb_pid=$XVFB_PID display=$DISPLAY" > "$RUN/xvfb-rc1.status"
log "xvfb_pid=$XVFB_PID display=$DISPLAY"

PROFILE="$SCRATCH/profile"; rm -rf "$PROFILE"; mkdir -p "$PROFILE/home" "$PROFILE/cache" "$PROFILE/config" "$PROFILE/data"
export XDG_CACHE_HOME="$PROFILE/cache" XDG_CONFIG_HOME="$PROFILE/config" \
       XDG_DATA_HOME="$PROFILE/data" XDG_RUNTIME_DIR="/tmp/traceshop-$SLURM_JOB_ID-run"
mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"

# ---- drive the shell through the loopback bridge ---------------------------
# The driver opens the real Store app, then runs activity_ui.py on the same
# bridge. A job-owned loopback fixture supplies the scripted tool calls.
export RC1_RUN="$RUN" RC1_GRABS="$GRABS" RC1_BIN="$BIN" RC1_PORT="$PORT" \
       RC1_LOG="$RUN/rc1-shell.log" RC1_SHELL_HOME="$PROFILE/octosense-home" \
       RC1_APP_DATA="$PROFILE/apps" RC1_CORE_DIR="$PROFILE/octos" \
       MAKEPAD_PACKAGE_DIR
log "=== run driver (activity showcase enabled) ==="
python3 "$SCRIPTS/traceshop_tools_rehearsal_driver.py" >> "$LOG" 2>&1
DRIVER_RC=$?
log "driver_rc=$DRIVER_RC"
sed -n '1,40p' "$RUN/rehearsal-driver.json" 2>/dev/null | tee -a "$LOG"
stat -c '%a %n' "$KEYS" "$KEYS/"*.key > "$RUN/key-permissions.txt"

kill -TERM "$XVFB_PID" 2>/dev/null
for i in $(seq 1 20); do kill -0 "$XVFB_PID" 2>/dev/null || break; sleep 0.5; done
kill -KILL "$XVFB_PID" 2>/dev/null || true
exit "$DRIVER_RC"
INNER
chmod 0750 "$RUN/rc1_inner.sh"

echo "=== srun container (inner) ==="
timeout 340 srun \
  --container-image="$SQSH" \
  --container-mounts="$ROOT:$ROOT,$CHOME:$HOME" \
  --container-workdir="$RUN" \
  --export=ALL,GOSIM_RUN="$RUN",GOSIM_CACHE="$CACHE",GOSIM_APPIMG="$APPIMG",GOSIM_PORT="$PORT",GOSIM_CAND="$CAND_BUNDLE",GOSIM_HUB="$HUB",GOSIM_RT="$RT_ROOT",GOSIM_LIBS="$LIBS_ROOT",GOSIM_SCRIPTS="$SCRIPTS",GOSIM_SCRATCH="$SCRATCH",RC1_NATIVE_SHOWCASE="$RC1_NATIVE_SHOWCASE",RC1_SHOWCASE_SCRIPT="$RC1_SHOWCASE_SCRIPT",RC1_STORE_GRABS="$RC1_STORE_GRABS",TRACESHOP_FIXTURE_MAX_REQUESTS="$TRACESHOP_FIXTURE_MAX_REQUESTS",RC1_ACTIVITY_CONSENT_XY="$RC1_ACTIVITY_CONSENT_XY",RC1_ACTIVITY_CONSENT_TIMEOUT="$RC1_ACTIVITY_CONSENT_TIMEOUT",ENROOT_CACHE_PATH="$ENROOT_CACHE_PATH",ENROOT_TEMP_PATH="$ENROOT_TEMP_PATH" \
  bash "$RUN/rc1_inner.sh"
SRUN_RC=$?
echo "srun_rc=$SRUN_RC"


exit "$SRUN_RC"
