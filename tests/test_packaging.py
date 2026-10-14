import json
import re
import tomllib

import lv
from conftest import PLUGIN, REPO


def test_versions_agree():
    plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == "lesson-videos")
    assert plugin["version"] == entry["version"] == lv.__version__
    assert entry["source"] == "./lesson-videos"
    assert market["name"] == "daniellandi"


def test_inline_deps_match_pyproject():
    script = (PLUGIN / "scripts/lesson-videos.py").read_text(encoding="utf-8")
    block = re.search(r"# /// script\n(.*?)# ///", script, re.S).group(1)
    toml = tomllib.loads("\n".join(l[2:] if l.startswith("# ") else "" for l in block.splitlines()))
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert set(toml["dependencies"]) <= set(project["dependencies"])
    assert toml["requires-python"] == project["requires-python"]


def test_no_private_paths_in_plugin():
    leaks = []
    for f in PLUGIN.rglob("*"):
        if f.is_file() and f.suffix in {".py", ".md", ".js", ".json"}:
            text = f.read_text(encoding="utf-8")
            if re.search(r"/Users/|/private/tmp|dotfiles|marine-biology|daniellandi@|collage-studio", text):
                leaks.append(str(f.relative_to(REPO)))
    assert leaks == []


def test_cli_help_runs(capsys):
    from lv import cli
    try:
        cli.main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    assert "lesson-videos" in capsys.readouterr().out


def test_skills_use_skill_dir_not_plugin_root():
    offenders = [str(f.relative_to(REPO)) for f in (PLUGIN / "skills").rglob("*.md")
                 if "CLAUDE_PLUGIN_ROOT" in f.read_text(encoding="utf-8")]
    assert offenders == []
    for name in ("make", "setup"):
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert 'uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"' in text


def test_key_skills_present_and_safe():
    import yaml
    for name, service in (("elevenlabs-get-api-key", "elevenlabs"), ("google-get-api-key", "gemini")):
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---")[1])
        assert front["name"] == name and len(front["description"]) <= 1024
        assert f"keys paste {service}" in text
        assert "no screenshots" in text.lower() and "password" in text.lower()
    setup = (PLUGIN / "skills/setup/SKILL.md").read_text(encoding="utf-8")
    assert "elevenlabs-get-api-key" in setup and "google-get-api-key" in setup


def test_edge_tts_floor_has_the_v2_token_fix():
    """Microsoft's Read Aloud server requires the Sec-MS-GEC v2 token since 2026-10; edge-tts added it in 7.3.0."""
    script = (PLUGIN / "scripts/lesson-videos.py").read_text(encoding="utf-8")
    floor = re.search(r'"edge-tts>=([\d.]+)"', script).group(1)
    assert tuple(map(int, floor.split("."))) >= (7, 3, 1)
