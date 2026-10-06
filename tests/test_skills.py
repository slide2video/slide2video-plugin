import re

from conftest import PLUGIN, REPO
from lv import narrate, render, sfx
from lv.cli import build_parser

SKILLS = ["setup", "make"]


def frontmatter(name):
    text = (PLUGIN / f"skills/{name}/SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(l.split(": ", 1) for l in m.group(1).splitlines()), text


def test_skill_frontmatter():
    for s in SKILLS:
        fm, _ = frontmatter(s)
        assert fm["name"] == s and len(fm["description"]) > 40


def test_skills_use_only_real_commands():
    choices = set(build_parser()._subparsers._group_actions[0].choices)
    for s in SKILLS:
        _, text = frontmatter(s)
        used = set(re.findall(r"\bLV ([a-z_][\w-]*)", text))
        assert used and used <= choices, used - choices
        assert "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py" in text


def test_guide_sfx_names_exist():
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"`((?:pop|sparkle|whoosh|thump|zip|pluck|tape|pencil|crayon|waves|shutter)\d)`", guide))
    assert listed and listed <= set(sfx.NAMES)
    assert "k_question" not in guide


def test_sample_chapter_renders(tmp_path, fake_speak, browser_ok, capsys):
    import shutil
    ch = tmp_path / "_work" / "ch1"
    shutil.copytree(PLUGIN / "skills/make/references/sample", ch)
    sfx.build()
    T = narrate.narrate(ch, speak_fn=fake_speak)
    times = [s["start"] + s["dur"] * 0.8 for s in T["scenes"]]
    sheet = render.stills(ch, times)
    assert sheet.exists()
    assert "cue miss" not in capsys.readouterr().out


def test_sample_deck_exists():
    assert (REPO / "examples/water-cycle.pptx").exists()
