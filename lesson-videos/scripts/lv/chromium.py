"""Which Chromium the renderer launches (LV_CHROMIUM, a saved path, or Playwright's own), and getting one."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config
from .util import UserError, read_text, write_text

# The page runs Claude-written scenes.js, so the browser gets no network beyond this Mac's loopback (the local page
# server): host names don't resolve, everything else goes to a dead proxy, and WebRTC may not send UDP around it.
NO_NETWORK_ARGS = ["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
                   "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                   "--webrtc-ip-handling-policy=disable_non_proxied_udp"]
NO_NETWORK_PROXY = {"server": "http://127.0.0.1:9", "bypass": "127.0.0.1,localhost"}
LAUNCH_ARGS = ["--use-gl=angle", "--enable-gpu-rasterization", "--ignore-gpu-blocklist", *NO_NETWORK_ARGS]
NPM_PACKAGE = "@sparticuz/chromium"   # ships the browser inside the npm package; used where downloads are blocked


def saved_file() -> Path:
    return config.home() / "chromium.txt"


def path() -> str | None:
    """The Chromium to launch, or None for Playwright's own browser. Paths that no longer exist are ignored."""
    env = os.environ.get("LV_CHROMIUM", "").strip()
    if env and Path(env).is_file():
        return env
    f = saved_file()
    if f.exists():
        saved = read_text(f).strip()
        if saved and Path(saved).is_file():
            return saved
    return None


def launch(p):
    """Start headless Chromium from a sync_playwright() handle, with no network beyond the loopback."""
    exe = path()
    return p.chromium.launch(args=LAUNCH_ARGS, proxy=NO_NETWORK_PROXY, **({"executable_path": exe} if exe else {}))


def can_launch() -> str:
    """'' if the browser starts, else the first line of the error."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            launch(p).close()
        return ""
    except Exception as e:  # noqa: BLE001
        return (str(e).splitlines() or [type(e).__name__])[0]


def install_playwright(run=subprocess.run) -> None:
    r = run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True,
            encoding="utf-8", errors="replace")
    if r.returncode:
        raise UserError("Could not download the Chromium renderer (about 150 MB). Check the internet connection "
                        "(school networks may block it), then run `doctor` again.\n" + (r.stderr or "")[-800:])


def install_npm(run=subprocess.run) -> Path:
    """Install NPM_PACKAGE under ~/.lesson-videos and copy its browser to a fixed place. Linux only."""
    prefix = config.home() / "chromium-npm"
    prefix.mkdir(parents=True, exist_ok=True)
    r = run(["npm", "install", "--prefix", str(prefix), "--no-audit", "--no-fund", NPM_PACKAGE],
            capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise UserError(f"Could not install {NPM_PACKAGE} from npm.\n" + (r.stderr or "")[-800:])
    # 153+ is an ES module, so require() returns {default: ...}; older builds export executablePath directly.
    js = f"const m = require({json.dumps(NPM_PACKAGE)}); (m.default ?? m).executablePath().then(p => console.log(p))"
    r = run(["node", "-e", js], cwd=str(prefix), capture_output=True, encoding="utf-8", errors="replace")
    lines = (r.stdout or "").strip().splitlines()
    if r.returncode or not lines or not Path(lines[-1]).is_file():
        raise UserError(f"{NPM_PACKAGE} installed but didn't unpack its browser.\n" + (r.stderr or "")[-800:])
    dest = config.home() / "chromium" / "chrome"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lines[-1], dest)
    dest.chmod(0o755)
    return dest


def ensure(probe=can_launch, playwright_install=None, npm_install=None) -> str:
    """Make a working Chromium available and say which. Tries the existing one before downloading anything."""
    err = probe()
    if not err:
        return f"ready ({path() or 'Playwright browser'})"
    chosen = path()
    if chosen and chosen == os.environ.get("LV_CHROMIUM", "").strip():
        raise UserError(f"The browser in LV_CHROMIUM ({chosen}) won't start: {err}. Fix or unset LV_CHROMIUM.")
    if chosen:  # a saved browser that stopped working: forget it and get a fresh one
        saved_file().unlink(missing_ok=True)
    errors = []
    try:
        (playwright_install or install_playwright)()
        err = probe()
        if not err:
            return "ready (downloaded)"
        errors.append(f"the downloaded Chromium won't start: {err}")
    except UserError as e:
        errors.append(str(e))
    if sys.platform.startswith("linux") and shutil.which("npm") and shutil.which("node"):
        try:
            exe = (npm_install or install_npm)()
            write_text(saved_file(), str(exe))
            err = probe()
            if not err:
                return f"ready (from npm {NPM_PACKAGE})"
            saved_file().unlink(missing_ok=True)
            errors.append(f"the npm Chromium won't start: {err}")
        except UserError as e:
            errors.append(str(e))
    raise UserError("\n".join(errors))
