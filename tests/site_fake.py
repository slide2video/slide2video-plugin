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
        self.heartbeat_bodies = []
        self.pair_polls_pending, self.pair_expired, self.contract = 1, False, 2
        self.fail_uploads = False
        self.latest, self.plugin_headers, self.refuse = None, [], None
        self.stop_next, self.next_queries, self.fail_next = False, [], 0
        self.finish_statuses = []   # statuses to answer finish with, one per call, before accepting
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
                if site.latest and code != 426:
                    self.send_header("X-LV-Latest", site.latest)
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def _route(self, method):
                u = urllib.parse.urlparse(self.path)
                site.plugin_headers.append(self.headers.get("X-LV-Plugin"))
                if site.refuse:
                    return self._send(426, {"error": site.refuse})
                if self.headers.get("X-LV-Contract") != str(site.contract):
                    return self._send(426, {"error": "Update the slide2video plugin on this computer: run /plugin update slide2video"})
                if u.path == "/api/device/pair/start":
                    return self._send(200, {"user_code": "ABC-123", "device_code": "dc_1", "expires_in": 600,
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
                    return self._send(200, {"teacher_email": "teacher@example.org", "device_name": "Test Mac", "contract": 2})
                if u.path == "/api/device/next":
                    site.next_queries.append(u.query)
                    if u.query == "start=1":       # like the real site: a fresh watcher clears a stale stop
                        site.stop_next = False
                    if site.fail_next > 0:
                        site.fail_next -= 1
                        return self._send(503, {"error": "busy"})
                    if site.stop_next:
                        site.stop_next = False
                        return self._send(200, {"stop": True})
                    return self._send(200, site.turns.pop(0)) if site.turns else self._send(204)
                parts = u.path.strip("/").split("/")
                if parts[:3] == ["api", "device", "files"]:
                    data = site.files.get(parts[3])
                    return self._send(200, raw=data) if data is not None else self._send(404, {"error": "no file"})
                if parts[:3] == ["api", "device", "turns"] and len(parts) == 5:
                    tid, action = parts[3], parts[4]
                    if action == "heartbeat":
                        body = json.loads(self._body())
                        site.heartbeats.append((tid, body["progress"]))
                        site.heartbeat_bodies.append(body)
                        return self._send(204)
                    if action == "files" and method == "PUT":
                        if site.fail_uploads:
                            return self._send(500, {"error": "boom"})
                        path = urllib.parse.parse_qs(u.query)["path"][0]
                        site.uploads[path] = (self.headers.get("Content-Type"), self._body())
                        return self._send(201, {"id": "fil_up"})
                    if action == "finish":
                        if site.finish_statuses:
                            self._body()
                            return self._send(site.finish_statuses.pop(0), {"error": "card refused: bad field"})
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
