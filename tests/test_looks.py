"""Looks (Engine.theme): each lesson's backgrounds and colours follow its subject; unthemed chapters look as before."""
import re

import pytest

from conftest import PLUGIN

ENGINE = PLUGIN / "engine/engine.js"
LOOK_NAMES = ["classroom", "math", "history", "literature", "life", "space", "ocean"]


def _in_page(script, arg=None):
    """Run `script` (a JS function of one argument) in a blank Chromium page with the engine loaded."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page()
            pg.set_content('<canvas id="c" width="1920" height="1080"></canvas>')
            pg.add_script_tag(content=ENGINE.read_text(encoding="utf-8"))
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


def test_unthemed_chapters_keep_the_original_look(browser_ok):
    got = _in_page("""() => ({ C: Engine.C, look: Engine.theme({}) })""")
    C = got["C"]
    assert [C["head"], C["main"], C["accent"], C["glow"], C["soft"], C["note"]] == \
        [C["navy"], C["teal"], C["coral"], C["aqua"], C["foam"], C["sea"]]
    assert got["look"] == {"title": "ocean", "dark": "deep", "light": "paper", "tint": None}


def test_engine_and_guides_name_the_same_looks(browser_ok):
    assert sorted(_in_page("() => Object.keys(Engine.LOOKS)")) == sorted(LOOK_NAMES)
    school = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    table = school.split("## Look", 1)[1].split("\n## ", 1)[0]
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    for name in LOOK_NAMES:
        assert f"| `{name}` |" in table, name
        assert f"`{name}`" in guide, name


def test_a_look_sets_backgrounds_and_colours(browser_ok):
    got = _in_page("""() => {
        const look = Engine.theme('history', { accent: '#123456' });
        return { look, C: Engine.C };
    }""")
    assert got["look"]["title"] == "sepia" and got["look"]["dark"] == "sepia" and got["look"]["light"] == "parchment"
    assert got["C"]["accent"] == "#123456" and got["C"]["head"] == "#4A2C17"
    assert got["C"]["coral"] == "#FF6B57"   # fixed colours never change


@pytest.mark.parametrize("call", ["Engine.theme('pirate')", "Engine.theme('math', { dark: 'nowhere' })"])
def test_an_unknown_look_or_background_is_an_error(browser_ok, call):
    msg = _in_page(f"() => {{ try {{ {call}; return null; }} catch (e) {{ return e.message; }} }}")
    assert msg and "Engine.theme: unknown" in msg


def test_every_look_reads_well(browser_ok):
    """Text colours on white (headings, kickers, accents) and white text on each look's dark background."""
    looks = _in_page("() => Engine.LOOKS")
    dark = _in_page("""(names) => names.map(n => {
        Engine.theme(n);
        const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080; const g = cv.getContext('2d');
        Engine.bg(g, 'dark', 0);
        const d = g.getImageData(120, 240, 1250, 420).data; let r = 0, gg = 0, b = 0, n4 = d.length / 4;
        for (let i = 0; i < d.length; i += 4) { r += d[i]; gg += d[i + 1]; b += d[i + 2]; }
        const hx = v => Math.round(v / n4).toString(16).padStart(2, '0');
        return '#' + hx(r) + hx(gg) + hx(b);
    })""", LOOK_NAMES)
    for (name, look), bgc in zip(((n, looks[n]) for n in LOOK_NAMES), dark):
        for role in ("head", "main", "accent"):
            # ocean is the original palette, kept exactly so existing chapters render unchanged (teal and coral ~2.9)
            assert _contrast(look[role], "#FFFFFF") >= (2.75 if name == "ocean" else 3.0), (name, role, look[role])
        assert _contrast("#FFFFFF", bgc) >= 7.0, (name, "white on dark", bgc)
        assert _contrast(look["glow"], bgc) >= 4.5, (name, "glow on dark", look["glow"], bgc)


def test_the_reference_chapter_sets_its_look_first():
    scenes = (PLUGIN / "skills/make/references/sample/scenes.js").read_text(encoding="utf-8")
    assert re.search(r"^Engine\.theme\('\w+'\);$", scenes, re.M)
    assert scenes.index("Engine.theme(") < scenes.index("scene(")


def test_underwater_backgrounds_are_only_for_water_lessons():
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "only for lessons about water or the sea" in guide
    school = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    assert "no look is the default for everything" in school and "not by one example in it" in school
