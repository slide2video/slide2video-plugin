"""The opening scene's intro(): every mood draws, its text fits between the logo and the captions and reads on any
brand colour, the logo / name / photo paths work (and a missing logo doesn't fail the render), `at` cues are kept,
options are checked strictly, and drawing is a pure function of time."""
import json
import re

import pytest

from conftest import PLUGIN

MOODS = ["polished", "cinematic", "calm", "energetic", "playful", "themed"]
LONG = {"kicker": "Quarterly review for the whole northern region and all of its partners",
        "title": "Everything you need to know about the *new process* for reviews, goals, check-ins and promotions, "
                 "step by step, from the first of January",
        "sub": "For every manager and every employee in every team, office and region, from the first day of next "
               "month onward, with no exceptions at all",
        "by": "Presented by the people operations team with the help of the regional leads and the works council"}
SHORT = {"kicker": "Science review", "title": "The *Water Cycle*", "sub": "where every raindrop has been", "by": "Ms. Rivera"}
CJK = {"kicker": "季度回顾", "title": "光合作用：植物如何利用阳光把水和二氧化碳变成糖和氧气的完整过程",
       "sub": "Pneumonoultramicroscopicsilicovolcanoconiosis explained", "by": "主讲：王老师"}
THAI = {"title": "การสังเคราะห์ด้วยแสงของพืชและการเปลี่ยนน้ำกับคาร์บอนไดออกไซด์ให้เป็นน้ำตาล"}
TEXTS = {"long": LONG, "short": SHORT, "cjk": CJK, "thai": THAI}
BRANDS = [("#F5D547", "#FFF3B0"), ("#FFFFFF", "#FFE600"), ("#0B0B0B", "#1B2A4A"), ("#808080", "#7F7F7F"),
          ("#B06226", "#F3C98B"), ("#2A1E4E", "#8E55E0")]

SETUP = r"""
window.TIMING = {duration: 30, chapter: '', scenes: [{id: 'x', start: 0, dur: 30, lead: 0, words: []}]};
"""
# Page helpers: assets made on a canvas (a dark logo, a white logo, a bright photo), and one draw of intro() that
# records every fillText (text, colour, bounding box, opacity) and every drawImage, plus the same frame drawn with
# no text, to read the background under each piece of text.
HELPERS = r"""
scene('x', () => {});
function makeImg(draw, w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); return c.toDataURL('image/png'); }
Engine.assets({
  dark: makeImg((g, w, h) => { g.fillStyle = '#0E3A5C'; g.beginPath(); g.arc(60, 60, 50, 0, 7); g.fill(); g.font = 'bold 60px sans-serif'; g.fillText('Acme', 130, 85); }, 300, 120),
  light: makeImg((g, w, h) => { g.fillStyle = '#FFFFFF'; g.beginPath(); g.arc(60, 60, 50, 0, 7); g.fill(); g.font = 'bold 60px sans-serif'; g.fillText('Acme', 130, 85); }, 300, 120),
  photo: makeImg((g, w, h) => { const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#FFFFFF'); gr.addColorStop(1, '#BFE8FF'); g.fillStyle = gr; g.fillRect(0, 0, w, h); }, 640, 360),
});
const lumOf = (r, g, b) => [r, g, b].reduce((s, v, i) => { v /= 255; return s + [0.2126, 0.7152, 0.0722][i] * (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); }, 0);
function parseColour(s) { const c = document.createElement('canvas').getContext('2d'); c.fillStyle = s; const v = c.fillStyle;
  if (typeof v !== 'string') return [0, 0, 0, 0];   // a gradient left over from the background (only emoji meet it)
  if (v[0] === '#') return [1, 3, 5].map(i => parseInt(v.slice(i, i + 2), 16)).concat(1);
  const m = v.match(/[\d.]+/g).map(Number); return [m[0], m[1], m[2], m[3] ?? 1]; }
window.drawIntro = (opts, t) => {
  const make = () => { const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080; return cv; };
  const cv = make(), g = cv.getContext('2d'), texts = [], images = [];
  const fill = g.fillText.bind(g), draw = g.drawImage.bind(g);
  g.fillText = (s, x, y) => { const m = g.measureText(s), T = g.getTransform();
    const pts = [[x, y - m.actualBoundingBoxAscent], [x + m.width, y - m.actualBoundingBoxAscent], [x, y + m.actualBoundingBoxDescent], [x + m.width, y + m.actualBoundingBoxDescent]].map(([px, py]) => T.transformPoint(new DOMPoint(px, py)));
    texts.push({ s, colour: parseColour(g.fillStyle), alpha: g.globalAlpha, x0: Math.min(...pts.map(p => p.x)), x1: Math.max(...pts.map(p => p.x)), y0: Math.min(...pts.map(p => p.y)), y1: Math.max(...pts.map(p => p.y)) });
    fill(s, x, y); };
  g.drawImage = (im, ...a) => { for (const [k, v] of Object.entries(Engine.imgs)) if (v === im) images.push(k); draw(im, ...a); };
  Engine.intro(g, t, { dur: 12, end: 10, start: 0 }, opts);
  const bgc = make(), b = bgc.getContext('2d'); b.fillText = () => {}; Engine.intro(b, t, { dur: 12, end: 10, start: 0 }, opts);
  const d = b.getImageData(0, 0, 1920, 1080).data;
  for (const tx of texts) {   // the background's average colour under this piece of text
    let r = 0, gg = 0, bb = 0, n = 0;
    const X0 = Math.max(0, Math.floor(tx.x0)), X1 = Math.min(1919, Math.ceil(tx.x1)), Y0 = Math.max(0, Math.floor(tx.y0)), Y1 = Math.min(1079, Math.ceil(tx.y1));
    for (let y = Y0; y <= Y1; y += 2) for (let x = X0; x <= X1; x += 2) { const i = (y * 1920 + x) * 4; r += d[i]; gg += d[i + 1]; bb += d[i + 2]; n++; }
    if (n) { const L1 = lumOf(...tx.colour.slice(0, 3)), L2 = lumOf(r / n, gg / n, bb / n); tx.contrast = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05); }
  }
  const px = (x, y) => { const i = (y * 1920 + x) * 4; return [d[i], d[i + 1], d[i + 2]]; };
  return { texts, images, logoBg: px(132, 160), url: cv.toDataURL('image/png') };
};
"""


def _engine():
    return (PLUGIN / "engine/engine.js").read_text(encoding="utf-8")


def _page(b, theme=None):
    pg = b.new_page()
    log = {"errors": [], "console": []}
    pg.on("pageerror", lambda e: log["errors"].append(str(e)))
    pg.on("console", lambda m: log["console"].append(f"{m.type}: {m.text}"))
    pg.set_content('<canvas id="c" width="1920" height="1080"></canvas>')
    pg.add_script_tag(content=SETUP)
    pg.add_script_tag(content=_engine())
    if theme:
        pg.add_script_tag(content=f"Engine.theme({json.dumps(theme[0])}, {json.dumps(theme[1])});")
    pg.add_script_tag(content=HELPERS)
    pg.wait_for_function("['dark', 'light', 'photo'].every(k => Engine.imgs[k].complete && Engine.imgs[k].naturalWidth > 0)")
    pg.log = log
    return pg


@pytest.fixture(scope="module")
def page(browser_ok):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = _page(b)
        yield pg
        b.close()


def draw(pg, opts, t):
    return pg.evaluate("([o, t]) => drawIntro(o, t)", [opts, t])


def opts_for(mood, text, **more):
    o = {"mood": mood, **text, **more}
    if mood == "cinematic":
        o.setdefault("photo", "photo")
    if mood == "playful":
        o.setdefault("emojis", ["☀️", "🌊"])
    return o


@pytest.mark.parametrize("mood", MOODS)
def test_text_fits_between_the_logo_and_the_captions(page, mood):
    for name, text in TEXTS.items():
        for logo in ({"logo": "dark"}, {"name": "Example Company International"}):
            for t in (0.3, 1.5, 4, 20):
                r = draw(page, opts_for(mood, text, **logo), t)
                for d in r["texts"]:
                    assert d["y1"] <= 900 and d["y0"] >= 0, (mood, name, t, d)        # clear of the captions
                    assert d["x0"] >= 110 and d["x1"] <= 1820, (mood, name, t, d)    # inside the frame's margins
            words = "".join(d["s"] for d in draw(page, opts_for(mood, text, **logo), 20)["texts"])
            assert re.sub(r"[*_\s]", "", text["title"])[:2] in words, (mood, name, words)
            for k in ("sub", "by"):
                if k in text and name != "long":   # the long text may be cut short, but short lines are all there
                    assert re.sub(r"\s", "", text[k])[:3] in words, (mood, name, k, words)
    assert page.log["errors"] == []


@pytest.mark.parametrize("mood", MOODS)
def test_every_line_is_drawn_including_by(page, mood):
    words = " ".join(d["s"] for d in draw(page, opts_for(mood, SHORT, name="Acme Co"), 20)["texts"])
    for needed in ("SCIENCE", "Water", "raindrop", "Rivera", "Acme"):
        assert needed in words, (mood, needed, words)


@pytest.mark.parametrize("mood", MOODS)
def test_text_reads_on_any_brand_colour(page, mood):
    for main, accent in BRANDS:
        for logo in ({"logo": "dark"}, {"logo": "light"}, {"name": "Acme Co"}):
            r = draw(page, opts_for(mood, SHORT, main=main, accent=accent, **logo), 20)
            for d in r["texts"]:
                if d["alpha"] > 0.99 and d["s"].strip() and "contrast" in d and d["s"] not in ("☀️", "🌊"):   # emoji have their own colours
                    assert d["contrast"] >= 4.3, (mood, main, accent, logo, d["s"], d["contrast"])


@pytest.mark.parametrize("mood", MOODS)
def test_a_logo_is_always_visible_and_a_light_one_gets_a_dark_panel(page, mood):
    def lum(c):
        return sum(w * ((v / 255) / 12.92 if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4)
                   for w, v in zip((0.2126, 0.7152, 0.0722), c))
    light = draw(page, opts_for(mood, SHORT, logo="light", main="#FFFFFF"), 20)
    assert "light" in light["images"], mood
    assert lum(light["logoBg"]) < 0.3, (mood, light["logoBg"])       # a dark panel behind a white logo
    dark = draw(page, opts_for(mood, SHORT, logo="dark", main="#0B0B0B"), 20)
    assert "dark" in dark["images"], mood
    assert lum(dark["logoBg"]) > 0.3, (mood, dark["logoBg"])         # a light panel (or page) behind a dark logo


def test_a_missing_logo_draws_the_name_and_does_not_fail_the_render(page):
    before = len(page.log["console"])
    for mood in MOODS:
        r = draw(page, opts_for(mood, SHORT, logo="nope", name="Acme Co"), 20)
        assert "Acme" in " ".join(d["s"] for d in r["texts"]), mood
    new = page.log["console"][before:]
    assert any("warning" in m and '"nope"' in m for m in new), new
    assert not any("asset failed" in m or m.startswith("error") for m in new), new   # render.py fails on these
    assert page.log["errors"] == []


def test_a_photo_is_drawn_and_a_missing_one_falls_back(page):
    assert "photo" in draw(page, opts_for("cinematic", SHORT), 5)["images"]
    r = draw(page, opts_for("cinematic", SHORT, photo="missing"), 5)
    assert "missing" not in r["images"] and "Water" in " ".join(d["s"] for d in r["texts"])


@pytest.mark.parametrize("mood", MOODS)
def test_at_cues_are_kept(page, mood):
    o = opts_for(mood, SHORT, logo="dark", at={"logo": 0.4, "kicker": 0.5, "title": 3.0, "sub": 5.0, "by": 6.0})

    def shown(t):
        r = draw(page, o, t)
        words = " ".join(d["s"] for d in r["texts"] if d["alpha"] > 0.01)
        return words, r["images"]
    w, imgs = shown(0.45)
    assert "dark" in imgs, mood                      # the logo at its cue, even where the default comes later
    assert "Water" not in w and "raindrop" not in w, (mood, w)
    w, _ = shown(2.95)
    assert "Water" not in w, (mood, w)
    w, _ = shown(4.9)
    assert "Water" in w and "raindrop" not in w, (mood, w)
    w, _ = shown(5.9)
    assert "raindrop" in w and "Rivera" not in w, (mood, w)
    w, _ = shown(6.5)
    assert "Rivera" in w, (mood, w)


@pytest.mark.parametrize("mood", MOODS)
def test_without_at_the_lines_follow_the_title(page, mood):
    def first(word):
        for i in range(0, 120):
            t = i * 0.05
            if word in " ".join(d["s"] for d in draw(page, opts_for(mood, SHORT), t)["texts"] if d["alpha"] > 0.01):
                return t
        return None
    title, sub = first("Cycle"), first("raindrop")
    assert title is not None and sub is not None and sub > title, (mood, title, sub)
    assert sub <= 4.5, (mood, sub)


BAD = [
    ({"look": "polished", "title": "T"}, "mood"),
    ({"mood": "nope", "title": "T"}, "unknown mood"),
    ({"mood": "toString", "title": "T"}, "unknown mood"),
    ({"title": "T"}, "unknown mood"),
    ({"mood": "calm"}, "title"),
    ({"mood": "calm", "title": ""}, "title"),
    ({"mood": "calm", "title": "T", "kicker": 5}, "kicker"),
    ({"mood": "calm", "title": "T", "main": "red"}, "main"),
    ({"mood": "calm", "title": "T", "main": "#F60"}, "main"),
    ({"mood": "calm", "title": "T", "accent": "rgb(1, 2, 3)"}, "accent"),
    ({"mood": "calm", "title": "T", "colour": "#FFFFFF"}, "unknown option"),
    ({"mood": "calm", "title": "T", "panel": "yes"}, "panel"),
    ({"mood": "calm", "title": "T", "photo": "photo"}, "cinematic"),
    ({"mood": "calm", "title": "T", "emojis": ["☀️"]}, "playful"),
    ({"mood": "playful", "title": "T", "emojis": "☀️"}, "emojis"),
    ({"mood": "calm", "title": "T", "at": {"foo": 1}}, "at.foo"),
    ({"mood": "calm", "title": "T", "at": {"title": -1}}, "at.title"),
    ({"mood": "calm", "title": "T", "at": {"title": "1"}}, "at.title"),
    ({"mood": "calm", "title": "T", "at": [1]}, "at"),
]


@pytest.mark.parametrize("bad,needle", BAD)
def test_options_are_checked_strictly(page, bad, needle):
    msg = page.evaluate("""(o) => { try { Engine.intro(document.createElement('canvas').getContext('2d'), 1, { dur: 5 }, o); return null; }
                                    catch (e) { return String(e.message); } }""", bad)
    assert msg and msg.startswith("Engine.intro:") and needle in msg, (bad, msg)


def test_an_undefined_at_value_is_rejected(page):
    msg = page.evaluate("""() => { try { Engine.intro(document.createElement('canvas').getContext('2d'), 1, { dur: 5 }, { mood: 'calm', title: 'T', at: { title: undefined } }); return null; }
                                    catch (e) { return String(e.message); } }""")
    assert msg and "at.title" in msg, msg


def test_intro_is_a_pure_function_of_time(page):
    for mood in MOODS:
        o = opts_for(mood, SHORT, logo="dark")
        a = draw(page, o, 2.25)["url"]
        draw(page, o, 7)
        assert draw(page, o, 2.25)["url"] == a, mood


def test_guide_documents_intro_and_its_moods():
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "intro(g, t, s, {mood, title, kicker, sub, by, logo, name, photo, main, accent, panel, emojis, at})" in guide
    assert "never rebuild the title slide" in guide and "never open with `titleCard`" in guide
    engine = _engine()
    moods = re.search(r"const MOODS = \{(.*?)\n  \};", engine, re.S).group(1)
    assert re.findall(r"(\w+): \{ main", moods) == MOODS
    for mood in MOODS:
        assert f"`'{mood}'`" in guide, mood
    assert "titleCard, intro, quizQ" in guide and "titleCard, intro, quizQ" in engine


def test_school_and_the_sample_open_with_intro():
    school = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    assert "drawn with `intro`: `mood: 'playful'`" in school and "`mood: 'themed'`" in school and "never with `titleCard`" in school
    sample = (PLUGIN / "skills/make/references/sample/scenes.js").read_text(encoding="utf-8")
    hook = next(l for l in sample.splitlines() if l.startswith("scene('hook'"))
    assert "intro(g, t, s, { mood: 'playful'" in hook and "titleCard" not in hook
    script = json.loads((PLUGIN / "skills/make/references/sample/script.json").read_text(encoding="utf-8"))
    say = next(s["say"] for s in script["scenes"] if s["id"] == "hook").lower()
    for cue in re.findall(r"s\.cue\('(\w+)'\)", hook):
        assert cue in say, cue


LOOKS = ["classroom", "math", "history", "literature", "life", "space", "ocean"]
PIXEL = """([o, t, kind, x, y]) => { const a = document.createElement('canvas'); a.width = 1920; a.height = 1080; const g = a.getContext('2d');
  Engine.intro(g, t, { dur: 12, start: 0 }, o); const b = document.createElement('canvas'); b.width = 1920; b.height = 1080; const h = b.getContext('2d');
  Engine.bg(h, kind, t); return [[...g.getImageData(x, y, 1, 1).data], [...h.getImageData(x, y, 1, 1).data]]; }"""


def test_with_a_theme_playful_and_themed_follow_the_look(page):
    """Finding 6: with Engine.theme, playful paints the look's light background (and its colours) and themed its
    title background; every text still reads on all seven looks, including with the deck's own colours."""
    for look in LOOKS:
        for over in ({}, {"main": "#7A1F5C", "accent": "#C2410C"}):
            pg = _page(page.context.browser, (look, over))
            for mood, kind in (("playful", "light"), ("themed", "title")):
                got, want = pg.evaluate(PIXEL, [opts_for(mood, SHORT, logo="dark"), 20, kind, 960, 1010])
                assert max(abs(x - y) for x, y in zip(got[:3], want[:3])) <= 2, (look, over, mood, got, want)
                for d in draw(pg, opts_for(mood, SHORT, logo="dark"), 20)["texts"]:
                    if d["alpha"] > 0.99 and d["s"].strip() and "contrast" in d and d["s"] not in ("☀️", "🌊"):
                        assert d["contrast"] >= 4.3, (look, over, mood, d["s"], d["contrast"])
            assert pg.log["errors"] == [], (look, pg.log["errors"])
            pg.close()


def test_without_a_theme_playful_keeps_its_paper(page):
    got, want = page.evaluate(PIXEL, [opts_for("playful", SHORT), 20, "paper", 960, 1010])
    assert got[:3] == want[:3], (got, want)
