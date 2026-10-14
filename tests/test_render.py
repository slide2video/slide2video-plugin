import contextlib
from contextlib import contextmanager

import pytest

from conftest import HELLO_JS
from lv import narrate, page, render, sfx, tools
from lv.util import UserError, read_text


def test_output_path_layout(make_chapter):
    ch = make_chapter([{"id": "a", "min": 1}], out="Entry 5/6: Keys.mp4")
    assert page.output_dir(ch) == ch.parent.parent
    assert page.output_path(ch, {"out": "Entry 5/6: Keys.mp4"}).name == "Entry 5-6- Keys.mp4"


def test_stills_and_render(make_chapter, fake_speak, browser_ok):
    sfx.build()
    ch = make_chapter([{"id": "hello", "say": "Hello there, students.", "min": 2}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    sheet = render.stills(ch, [0.5, 1.5])
    assert sheet.exists() and len(list((ch / "build/stills").glob("t*.jpg"))) == 2
    out = render.render(ch, workers=2)
    assert out == ch.parent.parent / "Chapter 1 - Test.mp4"
    assert abs(tools.duration(out) - narrate.read_timing(ch)["duration"]) < 0.2
    assert {"video", "audio"} <= tools.streams(out)
    assert read_text(out.with_suffix(".vtt")).startswith("WEBVTT")
    assert (ch / "build" / "final.jpg").exists()  # frames from the finished MP4, for the last visual check


def test_render_reports_page_error(make_chapter, fake_speak, browser_ok):
    ch = make_chapter([{"id": "hello", "min": 1}], "throw new Error('boom in scenes');\n")
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.stills(ch, [0.5])
    assert "boom in scenes" in str(e.value)


def test_render_reports_missing_asset(make_chapter, fake_speak, browser_ok):
    js = "Engine.assets({ pic: 'assets/nope.jpg' });\n" + HELLO_JS
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.render(ch, workers=1)
    assert "assets/nope.jpg" in str(e.value)


def test_render_needs_narration_first(make_chapter):
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    with pytest.raises(UserError) as e:
        render.render(ch)
    assert "narrate" in str(e.value)


def test_wander_spreads_particles(make_chapter, fake_speak, browser_ok):
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    page.ensure_page(ch)
    with render.page_for(ch) as (pg, logs):
        xs = pg.evaluate("[...Array(20)].map((_, i) => Engine.wander(i, 0, {x: 0, y: 0, w: 1000, h: 1000}, 3)[0])")
    assert max(xs) - min(xs) > 600, xs


@pytest.mark.parametrize("js,needle", [
    ("scene('hello', (g, t, s) => { Engine.clip(g, 'assets/clip_nope', 192, t, 0, 0, 640, 360); });\n", "assets/clip_nope/"),
    ("scene('hello', (g, t, s) => { Engine.img(g, 'nokey', 0, 0, 640, 360); });\n", '"nokey"'),
    ("scene('other', (g, t, s) => {});\n", 'no scene() for "hello"'),
])
def test_render_reports_silent_gray(make_chapter, fake_speak, browser_ok, js, needle):
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.stills(ch, [0.5])
    assert needle in str(e.value)


def test_render_builds_sound_effects_when_missing(make_chapter, fake_speak, browser_ok, capsys, lv_home):
    assert not (lv_home / "sfx").exists()
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    render.render(ch, workers=1)
    assert "unknown sound effects skipped" not in capsys.readouterr().out


def test_page_cannot_reach_the_network(make_chapter, fake_speak, browser_ok):
    js = ("fetch('https://example.com/x?leak=1').catch(() => {});\n"
          "new Image().src = 'https://example.com/beacon.png';\n"
          "try { new WebSocket('wss://example.com/ws'); } catch (e) {}\n" + HELLO_JS)
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    page.ensure_page(ch)
    with render.page_for(ch) as (pg, logs):
        got = pg.evaluate("fetch('http://203.0.113.9/y').then(() => 'reached', () => 'blocked')")
        pg.wait_for_timeout(300)
        blocked = [l for l in logs if l.startswith("blocked:")]
        assert got == "blocked"
        for url in ("https://example.com/x?leak=1", "https://example.com/beacon.png", "http://203.0.113.9/y"):
            assert any(url in l for l in blocked), (url, blocked)
        assert pg.evaluate("window.__ready") is True  # the page's own files still load


def _lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # picks the outgoing interface; sends nothing
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return None if ip.startswith("127.") else ip


@contextmanager
def _counting_server(host="127.0.0.1"):
    """A server that records every request path (WebSocket handshakes included) and answers a small page."""
    import http.server
    import threading
    hits = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            body = b"<html><body>ok</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer((host, 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv.server_address[1], hits
    finally:
        srv.shutdown()
        srv.server_close()


PROBE = """async ([fetches, sockets]) => {
    const out = {};
    for (const u of fetches) { try { await fetch(u); out[u] = 'reached'; } catch (e) { out[u] = 'failed'; } }
    for (const u of sockets) { try { new WebSocket(u); } catch (e) {} }
    await new Promise(r => setTimeout(r, 1500));
    return out; }"""


def test_browser_itself_reaches_only_the_local_page_server(browser_ok):
    """The browser layer alone (no Playwright routes): the page server's port works; another service on this Mac's
    loopback, this Mac's own network address, an IP literal and a host name are all unreachable, by fetch or
    WebSocket. The servers count hits, so this needs no internet."""
    from playwright.sync_api import sync_playwright
    from lv import chromium
    lan_ip = _lan_ip()
    with _counting_server() as (port, page_hits), _counting_server() as (other, other_hits), \
            (_counting_server(lan_ip) if lan_ip else contextlib.nullcontext((None, []))) as (lan_port, lan_hits):
        with sync_playwright() as p:
            browser = chromium.launch(p, local_port=port)
            try:
                pg = browser.new_page()
                pg.goto(f"http://127.0.0.1:{port}/page")
                fetches = [f"http://127.0.0.1:{other}/f", f"http://localhost:{other}/f", "http://93.184.216.34/",
                           "http://example.com/"] + ([f"http://{lan_ip}:{lan_port}/f"] if lan_ip else [])
                sockets = [f"ws://127.0.0.1:{other}/ws", f"ws://localhost:{other}/ws", "ws://example.com/"] + \
                          ([f"ws://{lan_ip}:{lan_port}/ws"] if lan_ip else [])
                got = pg.evaluate(PROBE, [fetches, sockets])
                assert set(got.values()) == {"failed"}, got
            finally:
                browser.close()
        assert page_hits == ["/page"] and other_hits == [] and lan_hits == []


def test_rendering_page_cannot_reach_other_local_services(make_chapter, fake_speak, browser_ok):
    with _counting_server() as (other, other_hits):
        js = (f"new WebSocket('ws://127.0.0.1:{other}/ws'); new WebSocket('ws://localhost:{other}/ws');\n"
              f"fetch('http://127.0.0.1:{other}/f').catch(() => {{}});\n"
              f"new WebSocket('ws://example.com/');\n" + HELLO_JS)
        ch = make_chapter([{"id": "hello", "min": 1}], js)
        narrate.narrate(ch, speak_fn=fake_speak)
        page.ensure_page(ch)
        with render.page_for(ch) as (pg, logs):
            pg.wait_for_timeout(1500)
            blocked = [l for l in logs if l.startswith("blocked:")]
        assert other_hits == []
        for url in (f"ws://127.0.0.1:{other}/ws", f"ws://localhost:{other}/ws", f"http://127.0.0.1:{other}/f",
                    "ws://example.com/"):
            assert any(url in l for l in blocked), (url, blocked)
