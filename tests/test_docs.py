import re

from conftest import PLUGIN
from lv import keys

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")


def _docs():
    return [PLUGIN / "README.md", *sorted((PLUGIN / "docs").rglob("*.md"))]


def test_relative_links_resolve():
    broken = []
    for md in _docs():
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            if not (md.parent / target.split("#")[0]).exists():
                broken.append(f"{md.relative_to(PLUGIN)} -> {target}")
    assert broken == []


def test_images_are_small():
    assert [p.name for p in (PLUGIN / "docs" / "images").glob("*") if p.stat().st_size > 400_000] == []


def test_keys_template_matches_code():
    assert (PLUGIN / "docs" / "keys-template.txt").read_text(encoding="utf-8") == keys.TEMPLATE
