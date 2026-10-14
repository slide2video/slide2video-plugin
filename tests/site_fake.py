"""A stand-in for slide2video.com's device API, for the worker and pairing tests."""
from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class FakeSite:
    def __init__(self):
        self.turns, self.files, self.uploads, self.finished, self.heartbeats = [], {}, {}, [], []
        self.pair_polls_pending, self.pair_expired, self.contract = 1, False, 1
        self.token = "s2v_test-token-0123456789"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _handler(self):
        site = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None):
                body = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else b"")
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def _route(self, method):
                u = urllib.parse.urlparse(self.path)
                if self.headers.get("X-LV-Contract") != str(site.contract):
                    return self._send(426, {"error": "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos"})
                if u.path == "/api/device/pair/start":
                    return self._send(200, {"user_code": "KQ7-4M2", "device_code": "dc_1", "expires_in": 600,
                                            "verify_url": f"{site.url}/devices"})
                if u.path == "/api/device/pair/poll":
                    if site.pair_expired:
                        return self._send(410, {"error": "expired"})
                    if site.pair_polls_pending > 0:
                        site.pair_polls_pending -= 1
                        return self._send(428, {"error": "pending"})
                    return self._send(200, {"token": site.token, "teacher_email": "teacher@example.org"})
                if self.headers.get("Authorization") != f"Bearer {site.token}":
                    return self._send(401, {"error": "unauthorized"})
                if u.path == "/api/device/status":
                    return self._send(200, {"teacher_email": "teacher@example.org", "device_name": "Test Mac", "contract": 1})
                if u.path == "/api/device/next":
                    return self._send(200, site.turns.pop(0)) if site.turns else self._send(204)
                parts = u.path.strip("/").split("/")
                if parts[:3] == ["api", "device", "files"]:
                    data = site.files.get(parts[3])
                    return self._send(200, raw=data) if data is not None else self._send(404, {"error": "no file"})
                if parts[:3] == ["api", "device", "turns"] and len(parts) == 5:
                    tid, action = parts[3], parts[4]
                    if action == "heartbeat":
                        site.heartbeats.append((tid, json.loads(self._body())["progress"]))
                        return self._send(204)
                    if action == "files" and method == "PUT":
                        path = urllib.parse.parse_qs(u.query)["path"][0]
                        site.uploads[path] = (self.headers.get("Content-Type"), self._body())
                        return self._send(201, {"id": "fil_up"})
                    if action == "finish":
                        site.finished.append((tid, json.loads(self._body())))
                        return self._send(204)
                return self._send(404, {"error": "not found"})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PUT(self):
                self._route("PUT")

        return H

    def close(self):
        self.server.shutdown()


class DictStore:
    def __init__(self):
        self.tokens = {}

    def get(self, site):
        return self.tokens.get(site)

    def set(self, site, token):
        self.tokens[site] = token

    def delete(self, site):
        self.tokens.pop(site, None)


@pytest.fixture
def fake_site(monkeypatch):
    from lv import site as lvsite
    s = FakeSite()
    monkeypatch.setenv("LV_SITE_URL", s.url)
    monkeypatch.setattr(lvsite, "store", DictStore())
    yield s
    s.close()


@pytest.fixture
def paired(fake_site):
    from lv import site as lvsite
    lvsite.store.set(fake_site.url, fake_site.token)
    return fake_site
