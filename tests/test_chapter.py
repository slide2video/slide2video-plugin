"""`chapter`: one chapter's slides and part of the brief, so a chapter build reads only what it uses."""
import pytest

from conftest import REPO
from lv import chapter, cli, ingest
from lv.util import UserError, read_text, write_text

PLAN = """# Plan: The Water Cycle

Approved on 2026-11-15.
Look: ocean

## Chapter 1 — Evaporation and condensation
Slides: 1-3
File: `Chapter 1 - Evaporation.mp4`
Outline: hook, evaporation, condensation (the cloud picture on slide 5), quiz, recap.

### Notes
Keep the tone light.

## Chapter 2 — Precipitation
**Slides:** 4–6
Outline: precipitation, review questions left open (slide 6).
"""

BRIEF = """# Content brief: The Water Cycle

Audience: grade 6.

## Chapter 1: Evaporation and condensation
- Evaporation: liquid to gas (slide 2).

## Chapter 2: Precipitation
- Rain, snow, sleet, hail (slide 4).

## The teacher's questions (left open)
- Slide 6: Name the three main steps.

## Possible issues in the slides
None found.
"""


@pytest.fixture
def lesson(tmp_path):
    work = tmp_path / "Water cycle" / "slide2video" / "_work"
    ingest.ingest(REPO / "examples" / "water-cycle.pptx", work)
    write_text(work / "plan.md", PLAN)
    write_text(work / "brief.md", BRIEF)
    return work


def test_plan_slides_reads_each_chapters_line():
    assert chapter.plan_slides(PLAN, 1) == [1, 2, 3]
    assert chapter.plan_slides(PLAN, 2) == [4, 5, 6]
    assert chapter.plan_slides(PLAN, 3) is None
    assert chapter.plan_slides("## Chapter 1: Intro\nSlides: 2, 4-6 (5 is a video)\n", 1) == [2, 4, 5, 6]
    assert chapter.plan_slides("## Chapter 1\n- Slides: 3 to 5\n", 1) == [3, 4, 5]
    assert chapter.plan_slides("## Chapter 1\nImages: from slides 5-10.\n", 1) is None   # not a Slides: line


def test_mentioned_slides():
    assert chapter.mentioned("the cloud on slide 5; slides 7–9 and slides 11, 12 and 14") == [5, 7, 8, 9, 11, 12, 14]
    assert chapter.mentioned("about 1-5000 slides") == [] and chapter.mentioned("slides 1-5000") == []


def test_extract_keeps_the_chapter_and_what_it_refers_to(lesson):
    out, sheets = chapter.extract(lesson, 1)
    md = read_text(out)
    assert out == lesson / "deck" / "chapter-1.md"
    for n in (1, 2, 3, 5):          # its slides, and slide 5, which its plan mentions
        assert f"## Slide {n}:" in md, n
    for n in (4, 6):
        assert f"## Slide {n}:" not in md, n
    slides = read_text(lesson / "deck" / "slides.md")
    one = slides.split("## Slide 2:", 1)[1].split("## Slide 3:", 1)[0]
    assert one.strip() in md          # a slide comes over word for word: text, notes, images
    assert "Slides: 1-3" in md and "slide 5, which" in md and "`slides.md`" in md
    assert "# The water-cycle.pptx" not in md and md.startswith("# water-cycle.pptx")
    assert "look at contact-*.jpg" not in md
    assert "Audience: grade 6." in md and "Evaporation: liquid to gas" in md      # the brief's shared and own parts
    assert "The teacher's questions (left open)" in md and "Possible issues in the slides" in md
    assert "Rain, snow, sleet, hail" not in md                                   # another chapter's part
    assert all(s.parent == lesson / "deck" and s.name.startswith("chapter-1-contact-") for s in sheets)


def test_extract_keeps_the_decks_other_sections(lesson):
    deck = lesson / "deck" / "slides.md"
    write_text(deck, read_text(deck) + "## Images on the title master\n\nImages: logo.png\n")
    md = read_text(chapter.extract(lesson, 2)[0])
    assert "## Images on the title master" in md and "Images: logo.png" in md


def test_extract_needs_the_slides_line(lesson):
    write_text(lesson / "plan.md", PLAN.replace("Slides: 1-3\n", ""))
    with pytest.raises(UserError) as e:
        chapter.extract(lesson, 1)
    assert "Slides: 4-14" in str(e.value)
    write_text(lesson / "plan.md", PLAN.replace("Slides: 1-3", "Slides: 1-9"))
    with pytest.raises(UserError) as e:
        chapter.extract(lesson, 1)
    assert "7, 8, 9" in str(e.value)


def test_extract_replaces_its_old_sheets(lesson):
    old = lesson / "deck" / "chapter-1-contact-07.jpg"
    old.write_bytes(b"old")
    chapter.extract(lesson, 1)
    assert not old.exists()


def test_extract_of_a_pdf_deck_shows_its_pages(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    for title in ("One", "Two", "Three"):
        doc.new_page().insert_text((72, 72), title)
    deck = tmp_path / "deck.pdf"
    doc.save(str(deck))
    work = tmp_path / "slide2video" / "_work"
    ingest.ingest(deck, work)
    write_text(work / "plan.md", "## Chapter 1\nSlides: 2-3\n")
    md_file, sheets = chapter.extract(work, 1)
    assert "## Slide 1:" not in read_text(md_file) and "## Slide 3: Three" in read_text(md_file)
    assert [s.name for s in sheets] == ["chapter-1-contact-01.jpg"]


def test_estimate_refuses_a_plan_without_slides_lines(lesson, capsys):
    assert cli.main(["estimate", str(lesson), "--chapters", "2", "--json"]) == 0
    write_text(lesson / "plan.md", PLAN.replace("**Slides:** 4–6\n", ""))
    assert cli.main(["estimate", str(lesson), "--chapters", "2", "--json"]) == 1
    assert "chapter 2" in capsys.readouterr().err
    write_text(lesson / "plan.md", PLAN.replace("4–6", "4-7"))
    assert cli.main(["estimate", str(lesson), "--chapters", "2"]) == 1
    assert "slides 1 to 6" in capsys.readouterr().err


def test_estimate_without_a_plan_or_chapters_checks_nothing(tmp_path):
    assert cli.main(["estimate", str(tmp_path / "work"), "--chapters", "2"]) == 0
    assert cli.main(["estimate", str(tmp_path / "work")]) == 0


def test_cli_prints_the_file_and_pictures(lesson, capsys):
    assert cli.main(["chapter", str(lesson), "1"]) == 0
    out = capsys.readouterr().out
    assert "chapter-1.md" in out and "pictures: " in out


def test_ingest_names_its_contact_sheets(tmp_path, capsys):
    ingest.ingest(REPO / "examples" / "water-cycle.pptx", tmp_path / "work")
    assert "contact sheets: contact-01.jpg" in capsys.readouterr().out
