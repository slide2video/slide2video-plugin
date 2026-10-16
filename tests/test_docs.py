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


def test_docs_never_suggest_reading_the_clipboard_in_chat():
    """A Claude without the skill loaded might `pbpaste` the key into the transcript; route teachers to the skill."""
    for name in ("elevenlabs.md", "google.md"):
        text = (PLUGIN / "docs" / "keys" / name).read_text(encoding="utf-8")
        assert "from the clipboard\"" not in text and "/slide2video:setup" in text


def test_cowork_guide_mentions_network_egress_toggle():
    assert "Allow network egress" in (PLUGIN / "docs" / "install" / "cowork.md").read_text(encoding="utf-8")


def test_key_skills_send_cowork_users_to_the_keys_file():
    for name in ("elevenlabs-get-api-key", "google-get-api-key"):
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "Cowork" in text and "keys-file.md" in text


def test_cowork_troubleshooting_quotes_the_real_blocked_message(monkeypatch):
    from lv import net
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    said = net.blocked_hint("speech.platform.bing.com")
    guide = (PLUGIN / "docs" / "install" / "cowork.md").read_text(encoding="utf-8")
    quoted = guide.split("## Troubleshooting", 1)[1].split('"')[1].split("…")[0].strip()
    assert quoted and said.startswith(quoted)
