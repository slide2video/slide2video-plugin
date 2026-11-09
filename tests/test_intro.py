"""The opening scene's intro(): every look draws, stays clear of the captions, and is a pure function of time."""
import re

from conftest import PLUGIN

LOOKS = ["polished", "cinematic", "calm", "energetic", "playful"]
LONG = {"kicker": "Members' handbook", "title": "Everything you need to know about the *new process*, step by step",
        "sub": "For every team, from the first day of next month onward", "by": "Presented by the operations team",
        "name": "Example Co", "emojis": ["☀️", "🌊"]}


def _engine():
    return (PLUGIN / "engine/engine.js").read_text(encoding="utf-8")


def _draw(pg, look, t, extra=None):
    """Draw intro() at local time t; returns the text it drew (with bottom y) and a pixel fingerprint."""
    return pg.evaluate("""([look, t, o]) => {
        const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080;
        const g = cv.getContext('2d'), out = [], fill = g.fillText.bind(g);
        g.fillText = (s, x, y) => { const m = g.measureText(s); const p = g.getTransform().transformPoint(new DOMPoint(x, y + m.actualBoundingBoxDescent));
                                    out.push({ s, y: p.y, right: g.getTransform().transformPoint(new DOMPoint(x + m.width, y)).x }); fill(s, x, y); };
        Engine.intro(g, t, { dur: 12, end: 10, start: 0 }, { look, ...o });
        return { out, url: cv.toDataURL('image/png') };
    }""", [look, t, {**LONG, **(extra or {})}])


def _page(p):
    b = p.chromium.launch()
    pg = b.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.set_content('<canvas id="c" width="1920" height="1080"></canvas>')
    pg.add_script_tag(content="window.TIMING = {duration: 12, chapter: '', scenes: [{id: 'x', start: 0, dur: 12, lead: 0, words: []}]};")
    pg.add_script_tag(content=_engine() + "\nscene('x', () => {});")
    return b, pg, errors


def test_every_look_draws_its_text_clear_of_the_captions(browser_ok):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, pg, errors = _page(p)
        for look in LOOKS:
            for t in (0, 0.4, 1.5, 10):
                _draw(pg, look, t)
            drawn = _draw(pg, look, 10)["out"]
            words = " ".join(d["s"] for d in drawn)
            for needed in ("Everything", "process", "operations", "Example"):
                if look == "playful" and needed in ("operations",):
                    continue   # the playful look has no by line: emojis sit there
                assert needed in words, (look, needed, words)
            assert all(d["y"] <= 900 for d in drawn), (look, [d for d in drawn if d["y"] > 900])
            assert all(d["right"] <= 1820 for d in drawn), (look, [d for d in drawn if d["right"] > 1820])
        b.close()
    assert errors == []


def test_intro_is_a_pure_function_of_time(browser_ok):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, pg, _ = _page(p)
        for look in LOOKS:
            a = _draw(pg, look, 2.25)["url"]
            _draw(pg, look, 7)
            assert _draw(pg, look, 2.25)["url"] == a, look
        b.close()


def test_unknown_look_falls_back(browser_ok):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, pg, errors = _page(p)
        assert _draw(pg, "nope", 5)["url"] == _draw(pg, "polished", 5)["url"]
        b.close()
    assert errors == []


def test_guide_documents_intro_and_its_looks():
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "intro(g, t, s, {look, title, kicker, sub, by, logo, name, photo, main, accent, emojis, at})" in guide
    assert "never rebuild the title slide" in guide
    engine = _engine()
    looks = re.search(r"const INTRO_LOOKS = \{(.*?)\};", engine, re.S).group(1)
    assert re.findall(r"(\w+): \{ main", looks) == LOOKS
    for look in LOOKS:
        assert f"`'{look}'`" in guide, look
    assert "titleCard, intro, quizQ" in guide and "titleCard, intro, quizQ" in engine
