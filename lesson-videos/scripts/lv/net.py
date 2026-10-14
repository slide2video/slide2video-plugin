"""HTTP with retries on network errors, 429 and 5xx. Errors never carry secrets."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, keys
from .util import UserError


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str = "", url: str = ""):
        self.status = status
        self.detail = keys.redact(detail)
        self.host = urllib.parse.urlparse(url).netloc or "service"
        super().__init__(f"{self.host} failed ({status}): {self.detail[:300]}")


def behind_proxy() -> bool:
    """True in claude.ai cloud sessions (and other proxied networks)."""
    return bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))


def blocked_hint(host: str) -> str:
    if not behind_proxy():
        return ""
    return (f"blocked by Claude's network setting: in claude.ai open Settings → Capabilities → Additional allowed "
            f"domains, add {host}, then start a new session")


def _open(req, timeout):
    """The single network seam; tests replace it."""
    return urllib.request.urlopen(req, timeout=timeout)


def request(url, data=None, headers=None, method=None, timeout=120, retries=2, raw=False, sleep=time.sleep):
    h = {"User-Agent": config.USER_AGENT, **(headers or {})}
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=body, headers=h, method=method or ("POST" if body is not None else "GET"))
        try:
            with _open(req, timeout) as r:
                payload = r.read()
            return payload if raw else (json.loads(payload) if payload else {})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                sleep(2 * 3 ** attempt)
                attempt += 1
                continue
            raise ApiError(e.code, detail, url) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                sleep(2 + 3 * attempt)
                attempt += 1
                continue
            raise ApiError(0, str(getattr(e, "reason", e)), url) from None


def gemini_error(e: ApiError, what: str) -> UserError:
    d = e.detail.lower()
    if e.status in (403, 429) or "billing" in d or "quota" in d:
        return UserError(f"Gemini refused the {what} ({e.status}): billing isn't enabled on the key's project, "
                         f"or its spend cap was reached. The videos can still be made without {what}.")
    if e.status in (400, 401) and "api key" in d:
        return UserError("The Gemini key was rejected: run `keys check`.")
    if e.status == 404:
        return UserError(f"Gemini doesn't know that model ({e.detail[:120]}). The model name in lv/config.py needs updating.")
    return UserError(f"Gemini failed making the {what}: {e}")
