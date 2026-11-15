"""One chapter's part of the deck and of the brief, so a chapter build reads only what it uses.

`plan.md` names each chapter's slides on a `Slides:` line under the chapter's heading (`## Chapter 2 — Osmosis`, then
`Slides: 4-14` or `Slides: 2, 4-9, 12`). `LV chapter WORK N` writes, next to `slides.md`, `chapter-N.md`: those slides
as `slides.md` has them (text, charts, speaker notes, images), the slides the chapter's part of the plan or the brief
mentions, every part of `slides.md` that isn't a slide, and the brief without the other chapters' sections; and
`chapter-N-contact-*.jpg`, the pictures of those slides. The whole deck stays in `slides.md` for planning."""
from __future__ import annotations

import re
from pathlib import Path

from . import paths
from .ingest import contact_sheets
from .util import UserError, read_json, read_text, write_text

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_CHAPTER = re.compile(r"^chapter\s+(\d+)\b", re.I)
_SLIDES_LINE = re.compile(r"^[\s>*_-]*slides[*_]*\s*:[*_]*\s*(.*)$", re.I)
_SLIDE = re.compile(r"^slide\s+(\d+)\b", re.I)
_COUNT = re.compile(r"^\d+ slides\. ")    # slides.md's "51 slides. Images are in media/; …" line
_DASH = r"\s*(?:-|–|—|to)\s*"
_RANGE = re.compile(rf"(\d+)(?:{_DASH}(\d+))?")
_MENTION = re.compile(rf"\bslides?\s+(\d+(?:{_DASH}\d+)?(?:\s*(?:,|and|&)\s*\d+(?:{_DASH}\d+)?)*)", re.I)
MAX_RANGE = 2000   # a chapter's slide range never spans more than this (a typo such as 4-1400 would)


def sections(text: str) -> list[tuple[str | None, int, list[str]]]:
    """A markdown text cut at its headings: (heading text or None for the part before the first, its level, lines).
    A section's lines run to the next heading of any level."""
    out: list[tuple[str | None, int, list[str]]] = [(None, 0, [])]
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            out.append((m.group(2).strip(), len(m.group(1)), [line]))
        else:
            out[-1][2].append(line)
    return out


def _blocks(text: str) -> list[tuple[int | None, bool, str]]:
    """The text as blocks: (chapter number or None, whether it is a chapter's own heading, text). A chapter's block
    runs from its heading to the next heading of the same or a higher level; everything else is a block of its own."""
    blocks: list[tuple[int | None, bool, str]] = []
    current, level = None, 0
    for head, lvl, lines in sections(text):
        m = _CHAPTER.match(head or "")
        if m:
            current, level = int(m.group(1)), lvl
            blocks.append((current, True, "\n".join(lines)))
        elif head is not None and current is not None and lvl > level:
            blocks.append((current, False, "\n".join(lines)))
        else:
            current = None
            blocks.append((None, False, "\n".join(lines)))
    return blocks


def chapter_text(text: str, n: int) -> str | None:
    """Chapter n's part of a plan or brief (its heading and everything under it), or None when it has none."""
    parts = [t for ch, _, t in _blocks(text) if ch == n]
    return "\n".join(parts) if parts else None


def without_other_chapters(text: str, n: int) -> str:
    """The text with every other chapter's part left out."""
    return "\n".join(t for ch, _, t in _blocks(text) if ch in (None, n)).strip() + "\n"


def numbers(spec: str) -> list[int]:
    """Slide numbers from `4-14, 17` (also `4–14`, `4 to 14`); text after a `(` is a comment."""
    out: set[int] = set()
    for a, b in _RANGE.findall(spec.split("(", 1)[0]):
        lo, hi = int(a), int(b or a)
        if lo > hi:
            lo, hi = hi, lo
        if hi - lo > MAX_RANGE:
            raise UserError(f"`Slides: {spec.strip()}` spans more slides than any deck has.")
        out.update(range(lo, hi + 1))
    return sorted(out)


def plan_slides(plan: str, n: int) -> list[int] | None:
    """The slides plan.md gives chapter n (its `Slides:` line), or None when it names none."""
    part = chapter_text(plan, n)
    if part is None:
        return None
    for line in part.splitlines():
        m = _SLIDES_LINE.match(line)
        if m and numbers(m.group(1)):
            return numbers(m.group(1))
    return None


def mentioned(text: str) -> list[int]:
    """Slide numbers a text mentions as `slide 7`, `slides 7-9` or `slides 4, 6 and 8`."""
    out: set[int] = set()
    for m in _MENTION.finditer(text or ""):
        try:
            out.update(numbers(m.group(1)))
        except UserError:   # "slides 1-5000" in passing: not a slide list
            pass
    return sorted(out)


def check_plan(work: Path, chapters: int) -> None:
    """Refuses (UserError) a plan.md that doesn't name every chapter's slides on a `Slides:` line, or names a slide the
    deck doesn't have. No plan.md yet: nothing to check."""
    les = paths.lesson(work)
    plan_file = les.code / "plan.md"
    if not plan_file.is_file():
        return
    plan = read_text(plan_file)
    missing = [n for n in range(1, chapters + 1) if not plan_slides(plan, n)]
    if missing:
        raise UserError(f"plan.md doesn't name the slides of chapter{'s' if len(missing) > 1 else ''} "
                        f"{', '.join(map(str, missing))}. Under each chapter's heading (`## Chapter N — <Title>`) add "
                        "a line with the deck's slides it covers, like `Slides: 4-14` or `Slides: 2, 4-9, 12`, then "
                        "run estimate again.")
    deck = les.work / "deck" / "deck.json"
    count = read_json(deck).get("slides") if deck.is_file() else None
    if count:
        bad = sorted({s for n in range(1, chapters + 1) for s in plan_slides(plan, n) if s < 1 or s > count})
        if bad:
            raise UserError(f"plan.md names slide{'s' if len(bad) > 1 else ''} {', '.join(map(str, bad))}, but the "
                            f"deck has slides 1 to {count}. Fix the `Slides:` lines, then run estimate again.")


def _deck_parts(slides_md: str) -> tuple[list[str], dict[int, str], list[str]]:
    """slides.md as (the part before the first slide, {slide number: its section}, the other sections)."""
    head: list[str] = []
    slides: dict[int, str] = {}
    other: list[str] = []
    for title, _, lines in sections(slides_md):
        m = _SLIDE.match(title or "")
        text = "\n".join(lines).rstrip()
        if m:
            slides[int(m.group(1))] = text
        elif not slides:          # the deck's name and its summary line, before the first slide
            text = "\n".join(l for l in text.splitlines() if not _COUNT.match(l)).strip()   # the note says it
            if text:
                head.append(text)
        else:
            other.append(text)
    return head, slides, other


def _images(section: str) -> list[str]:
    return [name.strip() for line in section.splitlines() if line.startswith("Images: ")
            for name in line[len("Images: "):].split(",") if name.strip()]


def _span(nums: list[int]) -> str:
    """4, 5, 6, 9 -> 4-6, 9"""
    out, start = [], None
    for i, s in enumerate(nums):
        if start is None:
            start = s
        if i + 1 == len(nums) or nums[i + 1] != s + 1:
            out.append(f"{start}-{s}" if s != start else f"{s}")
            start = None
    return ", ".join(out)


def extract(work: Path, n: int) -> tuple[Path, list[Path]]:
    """Write chapter n's part of the deck and brief next to slides.md; return the file and its picture sheets."""
    les = paths.lesson(work)
    deck_dir = les.work / "deck"
    slides_file, plan_file = deck_dir / "slides.md", les.code / "plan.md"
    if not slides_file.is_file():
        raise UserError(f"No {slides_file} yet: run `ingest` first.")
    if not plan_file.is_file():
        raise UserError(f"No {plan_file} yet: write the plan first.")
    plan = read_text(plan_file)
    own = plan_slides(plan, n)
    if not own:
        raise UserError(f"plan.md doesn't name chapter {n}'s slides. Under its heading (`## Chapter {n} — <Title>`) add "
                        "a line with the deck's slides it covers, like `Slides: 4-14` (brief.md's chapter section says "
                        "which), then run `chapter` again.")
    brief_file = les.code / "brief.md"
    brief = read_text(brief_file) if brief_file.is_file() else ""
    head, deck, other = _deck_parts(read_text(slides_file))
    extra = sorted(set(mentioned(chapter_text(plan, n) or "") + mentioned(chapter_text(brief, n) or "")) - set(own))
    keep = [s for s in sorted(set(own) | set(extra)) if s in deck]
    unknown = sorted(set(own) - set(deck))
    if unknown:
        raise UserError(f"plan.md gives chapter {n} slide{'s' if len(unknown) > 1 else ''} "
                        f"{', '.join(map(str, unknown))}, which the deck doesn't have (its slides are 1 to {max(deck, default=0)}).")
    extra = [s for s in extra if s in deck]
    name = f"chapter-{n}"
    # the pictures of its slides, of the deck's other parts (a slide master's logo), and for a PDF the pages themselves
    pictures = [deck_dir / "media" / f for part in [*(deck[s] for s in keep), *other] for f in _images(part)]
    pictures += [deck_dir / "pages" / f"p{s:03d}.png" for s in keep]
    for old in deck_dir.glob(f"{name}-contact-*.jpg"):
        old.unlink()
    sheets = contact_sheets([p for p in dict.fromkeys(pictures) if p.is_file()], deck_dir, prefix=f"{name}-contact")
    lines = [*head, "",
             f"**Chapter {n} only:** the slides `plan.md` gives it (Slides: {_span(own)})"
             + (f", and slide{'s' if len(extra) > 1 else ''} {_span(extra)}, which its part of the plan or brief mentions"
                if extra else "")
             + f". The whole deck ({len(deck)} slides) is `slides.md`, next to this file: open a slide there only when "
             "this chapter needs one that isn't here."
             + (f" This chapter's pictures: {', '.join(s.name for s in sheets)}." if sheets else
                " These slides have no pictures."),
             ""]
    lines += [deck[s] + "\n" for s in keep]
    lines += [t + "\n" for t in other]
    if brief:
        lines += ["---", "", f"# brief.md, without the other chapters (chapter {n}'s section and every shared one)", "",
                  without_other_chapters(brief, n)]
    out = write_text(deck_dir / f"{name}.md", "\n".join(lines).rstrip() + "\n")
    return out, sheets
