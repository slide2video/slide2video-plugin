"""slide2video.com: this Mac's connection (pairing, its token in the Keychain, device API calls). The token is
never printed."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time

from . import config, contract, net
from .util import UserError, read_json, write_json

NOT_PAIRED = ("This Mac isn't connected to slide2video.com (or it was removed there). Run /lesson-videos:setup "
              "and choose to connect this Mac.")
UPDATE = "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos"


def site_url() -> str:
    return (os.environ.get("LV_SITE_URL") or config.SITE_URL).rstrip("/")


class KeychainStore:
    """macOS Keychain, service 'slide2video', account = the site address."""
    service = "slide2video"

    def get(self, site: str) -> str | None:
        r = subprocess.run(["security", "find-generic-password", "-s", self.service, "-a", site, "-w"],
                           capture_output=True, encoding="utf-8")
        return (r.stdout.strip() or None) if r.returncode == 0 else None

    def set(self, site: str, token: str) -> None:
        # The token goes in on stdin (security -i), never in argv, so ps and error messages cannot show it.
        line = f"add-generic-password -U -s {self.service} -a {site} -w {token}\n"
        r = subprocess.run(["security", "-i"], input=line, capture_output=True, encoding="utf-8")
        if r.returncode != 0 or "error" in (r.stderr or "").lower():
            raise UserError("Couldn't save the connection in the macOS Keychain. Unlock the Keychain (or allow access "
                            "when macOS asks) and run the pairing again.") from None

    def delete(self, site: str) -> None:
        subprocess.run(["security", "delete-generic-password", "-s", self.service, "-a", site], capture_output=True)


class FileStore:
    """Fallback where there is no Keychain: ~/.lesson-videos/site-token.json, readable only by this user."""

    def _file(self):
        return config.home() / "site-token.json"

    def _read(self) -> dict:
        f = self._file()
        return read_json(f) if f.exists() else {}

    def get(self, site: str) -> str | None:
        return self._read().get(site)

    def set(self, site: str, token: str) -> None:
        d = self._read()
        d[site] = token
        write_json(self._file(), d)
        if os.name == "posix":
            os.chmod(self._file(), 0o600)

    def delete(self, site: str) -> None:
        d = self._read()
        if d.pop(site, None) is not None:
            write_json(self._file(), d)


store = KeychainStore() if sys.platform == "darwin" and shutil.which("security") else FileStore()


def _error_message(detail: str) -> str:
    try:
        return str(json.loads(detail).get("error") or "")
    except (ValueError, AttributeError):
        return ""


def call(path: str, data=None, method=None, raw=False, headers=None, auth=True, timeout=120):
    h = {"X-LV-Contract": str(contract.VERSION), **(headers or {})}
    if auth:
        token = store.get(site_url())
        if not token:
            raise UserError(NOT_PAIRED)
        h["Authorization"] = f"Bearer {token}"
    try:
        return net.request(site_url() + path, data=data, headers=h, method=method, raw=raw, timeout=timeout)
    except net.ApiError as e:
        if e.status == 426:
            raise UserError(_error_message(e.detail) or UPDATE) from None
        if e.status == 401 and auth:
            raise UserError(NOT_PAIRED) from None
        raise


def pair(name=None, sleep=None, out=print, clock=time.monotonic) -> str:
    """Show a code to type on the website, wait for it, keep the token. Returns the teacher's email."""
    sleep = sleep or time.sleep
    name = (name or platform.node().removesuffix(".local") or "Mac")[:60]
    start = call("/api/device/pair/start", {"name": name}, auth=False)
    out(f"On any computer, sign in at {start['verify_url']}, choose Add a Mac, and type this code: "
        f"{start['user_code']}")
    out(f"The code works for {start['expires_in'] // 60} minutes. Waiting…")
    deadline = clock() + start["expires_in"]
    while clock() < deadline:
        sleep(5)
        try:
            got = call("/api/device/pair/poll", {"device_code": start["device_code"]}, auth=False)
        except net.ApiError as e:
            if e.status == 428:
                continue
            if e.status == 410:
                break
            raise
        store.set(site_url(), got["token"])
        return got["teacher_email"]
    raise UserError("The code expired before it was entered. Run the pairing again for a new code.")


def status() -> dict:
    return call("/api/device/status")
