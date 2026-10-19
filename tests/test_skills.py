import json
import re

from conftest import PLUGIN, REPO
from lv import narrate, render, sfx
from lv.cli import build_parser

SKILLS = ["setup", "make", "serve", "elevenlabs-get-api-key", "google-get-api-key"]


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
        assert "${CLAUDE_SKILL_DIR}/../../scripts/slide2video.py" in text


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


def test_skills_avoid_shell_specific_syntax():
    for s in SKILLS:
        _, text = frontmatter(s)
        assert 'start ""' not in text and "`open URL`" not in text
        assert "$HOME\\.local\\bin\\uv.exe --version" not in text
        assert "uv run --with pillow" not in text and "python -c" not in text
    _, setup = frontmatter("setup")
    assert "LV open" in setup


def test_references_need_no_substitution():
    for f in (PLUGIN / "skills/make/references").rglob("*.md"):
        assert "${CLAUDE_PLUGIN_ROOT}" not in f.read_text(encoding="utf-8"), f
    _, make = frontmatter("make")
    assert "exact **LV** command" in make and "LV asset" in make


def test_skills_mention_bash_timeout():
    for s in ("setup", "make"):  # the skills that run long downloads and renders
        _, text = frontmatter(s)
        assert "timeout" in text


def test_docs_say_videos_work_without_any_keys():
    _, setup = frontmatter("setup")
    _, make = frontmatter("make")
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert "required" not in setup.split("## 3.")[1].split("\n")[0]  # the voice step is a choice, not a requirement
    assert "free Microsoft voice" in setup and "free Microsoft voice" in make and "free Microsoft voice" in readme
    assert '"narrator"' in guide and '"narrator"' in make
    assert "unofficial" in setup and "unofficial" in readme


def test_make_skill_explains_both_layouts():
    _, text = frontmatter("make")
    assert "LV where" in text and "next to the deck" in text and "_source" not in text


def test_make_skill_has_a_site_mode():
    _, text = frontmatter("make")
    site = text.split("## Site mode", 1)[1]
    for needed in ("site/turn.json", "site/card.json", "site/progress.txt", "site/lv.txt", "LV card",
                   '"questions"', '"plan"', '"review"', '"done"', "Never ask", "stop",
                   "`answer`", "`approve`", "`change`", "`continue`", "`feedback`",
                   "LV style", "`check.id`", "`check.remove`", "`check.keep`", "`check.file`", "`check.keep_decision`",
                   "interview.md", "review.md", "Decision: remove", '"problem"', "school"):
        assert needed in site, needed


def test_school_lives_only_in_its_style():
    """The make skill takes every School-specific word from `LV style`, so it can't drift from styles/school."""
    _, text = frontmatter("make")
    for school_only in ("What grade are the students?", "They're not students", "not students", "student-info.md",
                        "calm, light instrumental study music", "3-question quiz"):
        assert school_only not in text, school_only
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "a student at the grade level" not in guide and "Never use images of students" not in guide


def test_make_skill_picks_and_remembers_the_style():
    _, text = frontmatter("make")
    assert "LV styles" in text and 'LV style' in text and "WORK/style.txt" in text
    assert "is `school`" in text            # a WORK from before styles, and every site-mode lesson
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "style's guide" in guide


def test_helpers_get_both_guides():
    _, text = frontmatter("make")
    section = text.split("## 7. Remaining chapters", 1)[1].split("## 8.", 1)[0]
    assert "guide.md" in section and "style's guide" in section


def test_setup_offers_to_connect_this_mac():
    _, text = frontmatter("setup")
    assert "LV pair" in text and "slide2video.com" in text


def _setup_section(title):
    _, text = frontmatter("setup")
    m = re.search(rf"^## \d+\. {re.escape(title)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"setup has no numbered step '{title}'"
    return m.group(1)


def test_setup_points_to_serve_after_pairing():
    connect = _setup_section("Connect this computer to slide2video.com")
    assert "/slide2video:serve" in connect
    assert "worker --once" not in connect and "Terminal" not in connect


def test_serve_runs_the_watching_worker_in_the_background():
    fm, text = frontmatter("serve")
    assert "LV worker --watch" in text and "run_in_background" in text
    assert "LV worker --status" in text.split("LV worker --watch", 1)[0]  # checks the connection first
    low = text.lower()
    assert "keep this claude code window open" in low
    assert "disconnect" in low and "stop" in low
    assert "/root/.claude/plugins/synced/" in text


def test_serve_quotes_the_workers_own_words():
    _, text = frontmatter("serve")
    worker_src = (PLUGIN / "scripts/lv/worker.py").read_text(encoding="utf-8")
    for line in ("Making videos for", "already making videos", "Disconnected from the website", "Working on"):
        assert f'"{line}' in text, line          # the skill quotes it…
        assert line in worker_src, line          # …and the worker prints it


def test_serve_stop_explains_a_step_in_progress_starts_over():
    _, text = frontmatter("serve")
    stop = text.split("**\"Stop\"**", 1)[1].split("\n- ", 1)[0]
    low = stop.lower()
    assert "stop the background bash task" in low
    assert "working on" in low and "starts over" in low and "disconnect" in low


def test_serve_explains_autostart_is_intentionally_not_built():
    _, text = frontmatter("serve")
    section = text.split("## Start automatically", 1)[1]
    low = section.lower()
    assert "on purpose" in low or "intentionally" in low
    assert "launchagent" in low and "task scheduler" in low
    assert "never set it up unasked" in low or "only if the teacher asks" in low


def test_setup_asks_about_slide2video_and_pairs_in_the_background():
    connect = _setup_section("Connect this computer to slide2video.com")
    assert "ask the teacher" in connect and "invited" in connect and "?" in connect  # not "only if they bring it up"
    assert "LV worker --status" in connect.split("ask the teacher", 1)[0]  # skip the question when already connected
    assert "LV pair" in connect and "run_in_background" in connect     # pair waits for the code to be typed
    done = _setup_section("Done")
    assert "slide2video.com" in done


def test_site_mode_plans_only_after_the_interview():
    _, text = frontmatter("make")
    site = text.split("## Site mode", 1)[1]
    row = next(l for l in site.splitlines() if l.startswith("| `answer`"))
    assert "for every case" not in row
    assert "Otherwise (`interview.md` exists or was just written in this turn), step 4" in row
    assert "then leave the flagged slides out everywhere" not in row
    assert "if the decision is `remove`, leave the flagged slides out everywhere" in row
    start = next(l for l in site.splitlines() if l.startswith("| `start`"))
    assert "don't write `brief.md` yet" in start


def test_site_mode_sends_the_new_card_details():
    text = (PLUGIN / "skills" / "make" / "SKILL.md").read_text(encoding="utf-8")
    site = text.split("## Site mode (slide2video.com)", 1)[1]
    assert '--json' in site and '"items"' in site          # cost items from estimate --json
    assert '"recommended": true' in site                   # Claude's suggested option
    assert "issue-1" in site                               # possible-issue question ids
    assert "[3/12]" in site                                # counted progress lines


def test_impossible_instructions_are_asked_about_first():
    _, text = frontmatter("make")
    read = text.split("## 1. Read the deck", 1)[1].split("## 2.", 1)[0]
    assert "before anything else" in read and "recommend none" in read
    site = text.split("## Site mode", 1)[1]
    start = next(l for l in site.splitlines() if l.startswith("| `start`"))
    assert start.index("instructions.md") < start.index("the style's check")   # notes first, students second
    assert "instructions-1" in start and "no option is `recommended`" in start
    answer = next(l for l in site.splitlines() if l.startswith("| `answer`"))
    assert answer.index("instructions-") < answer.index("check.id")
    assert "the rest of the `start` row" in answer
    assert "`instructions.md`" in site.split("**Files between turns**", 1)[1]


def test_site_mode_writes_plain_notes_for_the_website():
    _, text = frontmatter("make")
    site = text.split("## Site mode", 1)[1]
    notes = next(l for l in site.splitlines() if l.startswith("- **Notes:**"))
    assert "site/notes.txt" in notes and "never a name of a person" in notes.lower()


STEPS = "/plugin update slide2video`, then close and reopen Claude Code"


def test_serve_update_says_to_reopen_claude_code():
    _, text = frontmatter("serve")
    assert STEPS in text
    assert "hasn't caught up" in text and "nothing to do on this computer" in text.lower()
    assert "A newer slide2video" in text


def test_install_guide_update_row_says_to_reopen_claude_code():
    guide = (PLUGIN / "docs/install/slide2video.md").read_text(encoding="utf-8")
    assert STEPS in guide and "hasn't caught up" in guide


def test_setup_and_serve_know_only_slide2video_com():
    for name in ("setup", "serve"):
        _, text = frontmatter(name)
        assert "pro.slide2video.com" not in text and "--site" not in text


def test_make_skill_card_examples_match_the_schema():
    import json
    from lv import contract
    _, text = frontmatter("make")
    cards = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]
    cards = [c for c in cards if isinstance(c, dict) and "kind" in c]
    assert cards
    for card in cards:
        assert contract.problems("card", card) == [], card
    assert '"contract": 1' not in text


def test_quiz_question_badge_is_configurable():
    engine = (PLUGIN / "engine/engine.js").read_text(encoding="utf-8")
    assert "o.badge || `QUIZ · QUESTION ${o.n}`" in engine
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "quizQ(g, t, s, {n, q, choices, emoji, badge})" in guide


def test_deck_questions_stay_open():
    _, text = frontmatter("make")
    for needed in ("The teacher's questions stay the teacher's.", "never answered, hinted at, pointed to",
                   "Speaker notes don't count", "If the slides themselves answer a question, that's content",
                   "are not put in the video unless the teacher asks",
                   '**"The teacher\'s questions (left open)"**', "None found.",
                   "which deck questions it shows open", "notes the style's guide lists for the wrap-up"):
        assert needed in text, needed
    site = text.split("## Site mode", 1)[1]
    assert "deck questions left open" in site


def test_reference_chapter_shows_a_deck_question_open():
    sample = PLUGIN / "skills/make/references/sample"
    ids = [s["id"] for s in json.loads((sample / "script.json").read_text(encoding="utf-8"))["scenes"]]
    assert ids.index("tq") < ids.index("q1") and "ta" not in ids
    scenes = (sample / "scenes.js").read_text(encoding="utf-8")
    assert "badge: \"YOUR TEACHER'S QUESTION\"" in scenes and 'badge: "EXTRA QUESTION"' in scenes
