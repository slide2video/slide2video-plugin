"""Looks (Engine.theme): each lesson's backgrounds and colours follow its subject; unthemed chapters look as before."""
import json
import re
import subprocess

import pytest

from conftest import PLUGIN, REPO

ENGINE = PLUGIN / "engine/engine.js"
# engine.js exactly as released in 2.5.3 (before looks): unthemed chapters must draw the same pixels as with it
ENGINE_2_5_3 = REPO / "tests/fixtures/engine-2.5.3.js"
LOOK_NAMES = ["classroom", "math", "history", "literature", "life", "space", "ocean"]
OCEAN = {"title": "ocean", "dark": "deep", "light": "paper", "head": "#0B2545", "main": "#1FA7A0", "accent": "#FF6B57",
         "glow": "#7FE0D6", "soft": "#E8F7F5", "note": "#134E6F"}


def _in_page(script, arg=None, engine=ENGINE, before=""):
    """Run `script` (a JS function of one argument) in a blank Chromium page with an engine loaded."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page()
            pg.set_content('<canvas id="c" width="1920" height="1080"></canvas>')
            if before:
                pg.add_script_tag(content=before)
            pg.add_script_tag(content=engine.read_text(encoding="utf-8"))
            return pg.evaluate(script, arg)
        finally:
            b.close()


def _lum(hexcolor):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------- unthemed chapters render exactly as in 2.5.3 ----------

def _words(text, start):
    return [{"w": w, "s": start + i * 0.3, "e": start + i * 0.3 + 0.25} for i, w in enumerate(text.split())]


# Every ready-made scene and widget, every original background, and names 2.5.3 didn't know (drawn as the ocean)
UNTHEMED_SCENES = r"""
const { C, P, bg, heading, bullets, tip, label, badge, table, arrow, check, cross, ring, card, text, emoji, titleCard, quizQ, quizA, recap } = Engine;
scene('title', (g, t, s) => titleCard(g, t, s, { kicker: 'Science review', title: 'The *Water Cycle*', sub: 'where raindrops go', emojis: ['☀️', '🌧️'] }), { bug: false, sfx: [[1, 'pop0', -12]] });
scene('widgets', (g, t, s) => {
  bg(g, 'paper', t); heading(g, 'Step 1: *Evaporation*', t, { kicker: 'Liquid → gas' });
  bullets(g, ['First *accent* point', 'Second _bold_ point'], 120, 240, t, [0.2, 0.5]);
  label(g, 'a label', 1300, 400, 1500, 300, P(t, 0.3)); badge(g, 'BADGE', 1300, 520, {});
  table(g, [['Step', 'Change'], ['one', '*liquid*'], ['two', 'gas']], 120, 520, [300, 300], { k: 1 });
  arrow(g, 900, 600, 1200, 700, { prog: 0.8, bend: 40 }); check(g, 1400, 650, 80, 1); cross(g, 1550, 650, 80, 1); ring(g, 1700, 650, 60, 0.6);
  tip(g, 'Evaporation = *liquid → gas*', t, 0.4);
});
scene('quiz', (g, t, s) => quizQ(g, t, s, { n: 1, q: 'Which *step*?', choices: ['Evaporation', 'Condensation'], emoji: '☀️' }), { dark: true });
scene('answer', (g, t, s) => quizA(g, t, s, { answer: 'Evaporation', why: 'The sun turned the *liquid* into vapor.' }), { dark: true });
scene('recap', (g, t, s) => recap(g, t, s, ['*One:* first', '*Two:* second'], [0.2, 0.5], { title: 'Recap', next: 'Next: clouds', nextAt: 0.5 }));
scene('sand', (g, t) => bg(g, 'sand', t));
scene('lab', (g, t) => bg(g, 'lab', t));
scene('ocean', (g, t) => bg(g, 'ocean', t));
scene('deep', (g, t) => bg(g, 'deep', t), { dark: true });
scene('dark', (g, t) => bg(g, 'dark', t));
scene('light', (g, t) => bg(g, 'light', t));
scene('title-word', (g, t) => bg(g, 'title', t));
scene('night', (g, t) => bg(g, 'night', t));
scene('grid', (g, t) => bg(g, 'grid', t));
scene('nonsense', (g, t) => bg(g, 'nonsense', t));
scene('paper-title', (g, t, s) => titleCard(g, t, s, { title: 'On *paper*', bg: 'paper' }));
"""
SCENE_IDS = ["title", "widgets", "quiz", "answer", "recap", "sand", "lab", "ocean", "deep", "dark", "light",
             "title-word", "night", "grid", "nonsense", "paper-title", "missing"]


def _timing():
    scenes, start = [], 0.0
    for sid in SCENE_IDS:
        say = f"Now the {sid} scene shows its words."
        scenes.append({"id": sid, "start": start, "dur": 4.0, "lead": 0.3, "speech": 2.4, "words": _words(say, 0.3)})
        start += 4.0
    return {"duration": start, "chapter": "CHAPTER 1 · TEST", "title": "Test", "scenes": scenes}


FRAME_HASHES = """(times) => times.map(t => {
    window.__render(t);
    const d = document.getElementById('c').getContext('2d').getImageData(0, 0, 1920, 1080).data;
    let h1 = 0x811c9dc5, h2 = 7;
    for (let i = 0; i < d.length; i++) { h1 = Math.imul(h1 ^ d[i], 16777619); h2 = (Math.imul(h2, 31) + d[i]) | 0; }
    return (h1 >>> 0).toString(16) + ':' + (h2 >>> 0).toString(16);
})"""


def test_the_fixture_is_the_released_engine():
    """tests/fixtures/engine-2.5.3.js must stay byte for byte the 2.5.3 engine (checked when the tag is here)."""
    out = subprocess.run(["git", "show", "v2.5.3:slide2video/engine/engine.js"], cwd=REPO, capture_output=True)
    if out.returncode:
        pytest.skip("tag v2.5.3 isn't in this checkout")
    assert out.stdout == ENGINE_2_5_3.read_bytes()


def test_unthemed_chapters_draw_the_same_pixels_as_2_5_3(browser_ok):
    T = _timing()
    # three moments per scene: the crossfade in, mid-reveal, and settled (captions and chrome on every frame)
    times = [s["start"] + k for s in T["scenes"] for k in (0.2, 1.1, 3.4)]
    stub = f"window.TIMING = {json.dumps(T)}; window.scene = () => {{}};"
    # scenes.js runs after the engine; load it as a second script through `before` of a wrapper engine file
    hashes = {}
    for name, engine in (("2.5.3", ENGINE_2_5_3), ("now", ENGINE)):
        script = "(times) => { " + UNTHEMED_SCENES.replace("\\", "\\\\") + " return (" + FRAME_HASHES + ")(times); }"
        hashes[name] = _in_page(script, times, engine=engine, before=stub)
    assert len(hashes["now"]) == len(times)
    assert len(set(hashes["now"])) > len(SCENE_IDS)   # the frames really differ from one another
    diff = [f"{t:.1f}s" for t, a, b in zip(times, hashes["2.5.3"], hashes["now"]) if a != b]
    assert not diff, f"unthemed frames differ from 2.5.3 at {diff}"


def test_unthemed_new_background_names_warn_and_draw_the_ocean(browser_ok):
    got = _in_page("""() => { const warns = []; const w = console.warn; console.warn = m => warns.push(m);
        const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080; const g = cv.getContext('2d');
        Engine.bg(g, 'grid', 0); Engine.bg(g, 'grid', 1); console.warn = w; return warns; }""")
    assert len(got) == 1 and "needs Engine.theme" in got[0] and "'ocean'" in got[0]


# ---------- the looks ----------

def test_engine_and_guides_name_the_same_looks(browser_ok):
    assert sorted(_in_page("() => Object.keys(Engine.LOOKS)")) == sorted(LOOK_NAMES)
    school = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    table = school.split("## Look", 1)[1].split("\n## ", 1)[0]
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    for name in LOOK_NAMES:
        assert f"| `{name}` |" in table, name
        assert f"`{name}`" in guide, name


def test_the_ocean_look_is_the_original_palette(browser_ok):
    assert _in_page("() => Engine.LOOKS.ocean") == OCEAN
    C = _in_page("() => Engine.C")   # unthemed roles
    assert {k: C[k] for k in ("head", "main", "accent", "glow", "soft", "note")} == \
        {k: OCEAN[k] for k in ("head", "main", "accent", "glow", "soft", "note")}


def test_a_look_sets_backgrounds_and_colours(browser_ok):
    got = _in_page("() => ({ look: Engine.theme('history', { accent: '#123456' }), C: Engine.C })")
    assert got["look"] == {"look": "history", "title": "sepia", "dark": "sepia", "light": "parchment", "tint": None}
    assert got["C"]["accent"] == "#123456" and got["C"]["head"] == "#4A2C17"
    assert got["C"]["coral"] == "#FF6B57"   # fixed colours never change


def test_each_call_replaces_the_previous_look(browser_ok):
    got = _in_page("""() => { Engine.theme('math', { tint: ['#101010', '#202020'], accent: '#123456' });
        return { look: Engine.theme('history'), C: Engine.C }; }""")
    assert got["look"]["tint"] is None and got["C"]["accent"] == "#B23A48"


@pytest.mark.parametrize("call, says", [
    ("Engine.theme('pirate')", 'unknown look "pirate"'),
    ("Engine.theme('constructor')", 'unknown look "constructor"'),
    ("Engine.theme(null)", 'unknown look "null"'),
    ("Engine.theme()", 'unknown look "undefined"'),
    ("Engine.theme({ main: '#123456' })", 'unknown look "undefined"'),
    ("Engine.theme('math', { dark: 'nowhere' })", '"nowhere" can\'t be the dark background'),
    ("Engine.theme('math', { title: 'paper' })", '"paper" can\'t be the title background'),
    ("Engine.theme('math', { light: 'cosmos' })", '"cosmos" can\'t be the light background'),
    ("Engine.theme('math', { tint: ['#000000'] })", "tint must be"),
    ("Engine.theme('math', { accent: 'red' })", "accent must be a colour"),
    ("Engine.theme('math', { colour: '#000000' })", 'unknown option "colour"'),
    ("Engine.theme('math', null)", "second argument"),
])
def test_a_wrong_look_is_an_error_and_changes_nothing(browser_ok, call, says):
    got = _in_page(f"""() => {{ Engine.theme('life'); let msg = null;
        try {{ {call}; }} catch (e) {{ msg = e.message; }}
        return {{ msg, head: Engine.C.head, look: Engine.theme('life') }}; }}""")
    assert got["msg"] and got["msg"].startswith("Engine.theme: ") and says in got["msg"], got["msg"]
    assert got["head"] == "#1E3D2B"   # the earlier look is still whole


def test_an_unknown_background_in_a_themed_chapter_is_an_error(browser_ok):
    msg = _in_page("""() => { Engine.theme('math'); const g = document.createElement('canvas').getContext('2d');
        try { Engine.bg(g, 'nonsense', 0); return null; } catch (e) { return e.message; } }""")
    assert msg and 'unknown background "nonsense"' in msg


def test_tint_recolours_every_dark_background(browser_ok):
    got = _in_page("""() => ['math', 'ocean'].map(n => {
        const px = () => { const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080; const g = cv.getContext('2d');
          Engine.bg(g, 'dark', 0); return Array.from(g.getImageData(4, 1070, 1, 1).data.slice(0, 3)); };
        Engine.theme(n); const plain = px(); Engine.theme(n, { tint: ['#400000', '#400000'] }); return [plain, px()]; })""")
    for plain, tinted in got:
        assert plain != tinted and tinted[0] > tinted[2], (plain, tinted)


def test_every_look_reads_well(browser_ok):
    """Each colour on the background it's drawn on, sampled from the look's own backgrounds."""
    res = _in_page("""(names) => names.map(n => {
        Engine.theme(n);
        const avg = slot => { const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080; const g = cv.getContext('2d');
          Engine.bg(g, slot, 0); const d = g.getImageData(120, 40, 1680, 860).data; let r = 0, gg = 0, b = 0; const m = d.length / 4;
          for (let i = 0; i < d.length; i += 4) { r += d[i]; gg += d[i + 1]; b += d[i + 2]; }
          const hx = v => Math.round(v / m).toString(16).padStart(2, '0'); return '#' + hx(r) + hx(gg) + hx(b); };
        return { C: { ...Engine.C }, light: avg('light'), dark: avg('dark'), title: avg('title') };
    })""", LOOK_NAMES)
    for name, r in zip(LOOK_NAMES, res):
        C = r["C"]
        if name == "ocean":   # the original palette, kept exactly (teal and coral are ~2.7:1 on paper); pinned above
            continue
        assert _contrast(C["head"], r["light"]) >= 7.0, (name, "head")
        for role in ("main", "accent", "note"):   # kickers, bullets, *accent* words, the recap's next line: large text
            assert _contrast(C[role], r["light"]) >= 3.5, (name, role, C[role], r["light"])
        for slot in ("dark", "title"):
            assert _contrast("#FFFFFF", r[slot]) >= 7.0, (name, slot, "white")
            assert _contrast(C["soft"], r[slot]) >= 7.0, (name, slot, "soft")
            assert _contrast(C["glow"], r[slot]) >= 4.5, (name, slot, "glow")


# ---------- the guides ----------

def test_the_reference_chapter_sets_its_look_first():
    scenes = (PLUGIN / "skills/make/references/sample/scenes.js").read_text(encoding="utf-8")
    assert re.search(r"^Engine\.theme\('\w+'\);$", scenes, re.M)
    assert scenes.index("Engine.theme(") < scenes.index("scene(")


def test_underwater_backgrounds_are_only_for_water_lessons():
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "only for lessons about water or the sea" in guide
    school = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    assert "no look is the default for everything" in school and "not by one example in it" in school


def test_the_look_lives_in_the_plan_and_follows_changes():
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "when `plan.md`'s `Look:` line names a look, first `Engine.theme('<look>')`" in guide
    assert "with no `Look:` line, or `Look: none`, don't call it" in guide
    school = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    look = school.split("## Look", 1)[1].split("\n## ", 1)[0]
    assert "change the `Look:` line in `plan.md` first" in look
    assert "A lesson resumed without a `Look:` line" in look and "`Look: none" in look
    make = (PLUGIN / "skills/make/SKILL.md").read_text(encoding="utf-8")
    resume = make.split("## 0. Resume?", 1)[1].split("\n## ", 1)[0]
    assert "no `Look:` line" in resume
