import http.client

from PIL import Image

from conftest import HELLO_JS
from lv import config, narrate, page, paths, render, sfx, tools
from lv.util import write_json, write_text


def get(port, url):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", url)
    r = c.getresponse()
    return r.status, r.read()


def test_routes_teacher_mode_match_the_chapter_folder(make_chapter):
    ch = make_chapter([{"id": "a", "min": 1}])
    r = dict(page.routes(paths.chapter(ch)))
    assert r["/assets/"] == ch / "assets" and r["/build/"] == ch / "build" and r["/"] == ch
    assert r["/index.html"] == ch / "index.html" and r["/fonts/"] == config.FONTS_DIR


def test_server_maps_prefixes(tmp_path):
    write_text(tmp_path / "code/scenes.js", "code")
    write_text(tmp_path / "src/assets/a.txt", "asset")
    write_text(tmp_path / "cache/timing.js", "timing")
    routes = [("/index.html", tmp_path / "cache/index.html"), ("/assets/", tmp_path / "src/assets"),
              ("/build/", tmp_path / "cache"), ("/fonts/", config.FONTS_DIR), ("/", tmp_path / "code")]
    with render.serve(routes) as port:
        assert get(port, "/scenes.js") == (200, b"code")
        assert get(port, "/assets/a.txt") == (200, b"asset")
        assert get(port, "/build/timing.js") == (200, b"timing")
        assert get(port, "/fonts/Nunito.ttf")[0] == 200
        assert get(port, "/index.html")[0] == 404


def test_server_refuses_paths_outside_roots(tmp_path):
    write_text(tmp_path / "secret.txt", "no")
    write_text(tmp_path / "src/assets/a.txt", "asset")
    with render.serve([("/assets/", tmp_path / "src/assets"), ("/", tmp_path / "src")]) as port:
        assert get(port, "/assets/a.txt") == (200, b"asset")
        for url in ("/assets/../../secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/../secret.txt"):
            assert get(port, url)[0] == 404, url


def test_project_chapter_renders_end_to_end(lv_project, fake_speak, browser_ok):
    sfx.build()
    ch = lv_project.lessons_dir / "biology" / "unit-2" / "ch1"
    write_json(ch / "script.json", {"chapter": "TEST", "title": "Test", "out": "Chapter 1 - Test.mp4",
                                    "scenes": [{"id": "hello", "say": "Hello there, students.", "min": 2}]})
    write_text(ch / "scenes.js", "Engine.assets({ pic: 'assets/pic.png' });\n" + HELLO_JS)
    p = paths.chapter(ch)
    p.assets.mkdir(parents=True)
    Image.new("RGB", (64, 64), "teal").save(p.assets / "pic.png")
    narrate.narrate(ch, speak_fn=fake_speak)
    render.stills(ch, [0.5])
    assert (p.build / "stills.jpg").exists()
    out = render.render(ch, workers=1)
    assert out == p.out / "Chapter 1 - Test.mp4"
    assert abs(tools.duration(out) - narrate.read_timing(ch)["duration"]) < 0.2
    assert out.with_suffix(".vtt").exists() and (p.build / "final.jpg").exists()
    assert sorted(f.name for f in ch.iterdir()) == ["scenes.js", "script.json"]  # the repo stays text-only
    import shutil
    from lv import status
    shutil.rmtree(p.build)                                                       # the cache is free to wipe
    assert status.stage(ch) == "done: Chapter 1 - Test.mp4"
