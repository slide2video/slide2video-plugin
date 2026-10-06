import io
import urllib.error

import pytest

from lv import net


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://x.test/a", code, "err", {}, io.BytesIO(body))


def test_retries_503_then_succeeds(monkeypatch):
    calls = []
    def fake_open(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise http_error(503)
        return Resp(b'{"ok": true}')
    monkeypatch.setattr(net, "_open", fake_open)
    assert net.request("https://x.test/a", sleep=lambda s: None) == {"ok": True}
    assert len(calls) == 2


def test_no_retry_on_400(monkeypatch):
    calls = []
    def fake_open(req, timeout):
        calls.append(1)
        raise http_error(400, b'{"error": {"message": "bad"}}')
    monkeypatch.setattr(net, "_open", fake_open)
    with pytest.raises(net.ApiError) as e:
        net.request("https://x.test/a", sleep=lambda s: None)
    assert e.value.status == 400 and len(calls) == 1 and e.value.host == "x.test"


def test_api_error_redacts_key_shapes():
    e = net.ApiError(401, "key AIzaSyD-abcdefghijklmnopqrstuvwxyz12345 bad", "https://g.test")
    assert "AIza" not in str(e)


def test_gemini_error_billing():
    msg = str(net.gemini_error(net.ApiError(429, "RESOURCE_EXHAUSTED quota", "https://g.test"), "music"))
    assert "billing" in msg and "without music" in msg
