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
    assert sorted(toml["dependencies"]) == sorted(project["dependencies"])
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
