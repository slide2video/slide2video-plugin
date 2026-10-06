# lesson-videos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `DanielLandi/plugins`, a public Claude Code marketplace whose `lesson-videos` plugin turns a teacher's slide deck into narrated, animated chapter videos on macOS or Windows.

**Architecture:** One Python entry point (`lesson-videos/scripts/lesson-videos.py`) with PEP 723 inline dependencies, run through `uv`, drives a `lv` package: ingest the deck, narrate with ElevenLabs word timestamps, render the existing canvas engine (`engine.js`) frame by frame with Python Playwright, mix audio with ffmpeg. Two skills (`setup`, `make`) tell Claude how to install, guide key creation, and run the proven chapter workflow with approval gates.

**Tech Stack:** Python ≥3.11 via uv · Playwright (Chromium) · ffmpeg/ffprobe (system or `static-ffmpeg`) · numpy/scipy (sound synthesis) · Pillow · python-pptx · PyMuPDF · ElevenLabs REST · Gemini REST (Veo 3.1 Lite, Lyria 3.5) · pytest · GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-06-lesson-videos-design.md` (same repo). Read it before starting.

**Source being ported (read-only, Daniel's machine):** `~/Projects/ihs/marine-biology/study-kit/videos/_source/` (`engine/engine.js`, `engine/build.py`, `engine/render.js`, `clips/make_clips.py`, `GUIDE.md`, `entry1/`), `~/Projects/dotfiles/claude-plugins/collage-studio/studio/sfx.py`, `~/Projects/dotfiles/.claude/skills/generate-video/scripts/providers.py`. **Never copy class material (slide text, deck images, Entry scripts) into the repo.**

## Global Constraints

- Repo `DanielLandi/plugins`, **public**, created from `DanielLandi/repo-template`; **Tier B** (short-lived branch → local gates → merge to `main`; `TIER=B ./bootstrap.sh`).
- Marketplace name `daniellandi`; plugin `lesson-videos`, version `0.1.0`; skills `/lesson-videos:setup` and `/lesson-videos:make`.
- License MIT; bundled fonts keep their OFL licences (`OFL-PatrickHand.txt`, `OFL-Nunito.txt`).
- Every command in a skill has the form `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py" <command>`; no `bin/` directory, no bash-only syntax in skills.
- Keys: environment variable first, then `~/.lesson-videos/keys.env` (`LESSON_VIDEOS_HOME` overrides the folder). Keys are never printed, logged, put in exceptions, or asked for in chat.
- No paid API call before the teacher approves the costed plan.
- All file I/O passes `encoding="utf-8"`; paths via `pathlib`; subprocesses with argument lists, never shell strings.
- ElevenLabs model `eleven_multilingual_v2`, format `mp3_44100_128`, default voice `cgSgspJ2msm6clMCkdW9` (Jessica). Narration cache key is `sha1(f"{voice}|{model}|{json.dumps(VOICE_SETTINGS)}|{say}")[:12]`, unchanged from `build.py`, so old caches stay valid.
- Gemini: Veo `veo-3.1-lite-generate-preview` (verify in Task 9), 8 s, 16:9, 720p, $0.05/s; Lyria `lyria-3.5` via `POST /v1beta/interactions`, $0.08/track. All model IDs and prices live in `lv/config.py`.
- Engine API stays identical to the Unit 1 engine; the only engine edits are the three font lines in Task 6.
- Commits end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT
  ```

## Review Focus

1. **Paths with spaces and accents** (`Unidad 1 – Biología.pptx`, `C:\Users\Ms Smith\Desktop\Unit 1`): ingest, narrate and render must work. Pinned by `test_ingest_path_with_spaces_and_accents` (Task 7) and the `home with space` fixture plus `doctor test/` folder (Tasks 2, 6, 12).
2. **Non-ASCII text on Windows** (smart quotes, accents, emoji in slides and scripts; cp1252 consoles): must round-trip as UTF-8 and print without `UnicodeEncodeError`. Pinned by `test_ingest_unicode_text` (Task 7) and `test_cli_prints_unicode_on_cp1252` (Task 12).
3. **ElevenLabs credits run out mid-chapter**: finished scenes stay cached, the message says what happened and what to do, no traceback. Pinned by `test_quota_error_keeps_finished_scenes` (Task 4).
4. **Images Pillow can't open** (EMF/WMF from PowerPoint, corrupt files): ingest must still finish and mark them "no preview". Pinned by `test_contact_sheet_survives_unreadable_image` (Task 7).
5. **Broken `scenes.js` or a missing asset**: render must stop with the browser error text, not hang or produce a gray video. Pinned by `test_render_reports_page_error` and `test_render_reports_missing_asset` (Task 6).

---

## File map

```
plugins/                                   repo root (~/Projects/plugins)
  .claude-plugin/marketplace.json          Task 1
  AGENTS.md CLAUDE.md SERVICES.md README.md LICENSE pyproject.toml .gitignore   Task 1
  .github/workflows/ci.yml                 Task 14
  docs/superpowers/{specs,plans}/          Task 1 (already written)
  examples/make_sample_deck.py, examples/water-cycle.pptx                        Task 13
  tests/conftest.py                        Task 2 (grown in Tasks 4, 6)
  tests/test_*.py                          one per task
  lesson-videos/
    .claude-plugin/plugin.json             Task 1
    README.md                              Task 13 (teacher-facing)
    engine/engine.js                       Task 6
    fonts/                                 Task 6
    skills/setup/SKILL.md                  Task 13
    skills/make/SKILL.md                   Task 13
    skills/make/references/guide.md        Task 13
    skills/make/references/sample/         Task 13 (script.json, scenes.js)
    scripts/lesson-videos.py               Task 2
    scripts/lv/__init__.py config.py util.py           Task 2
    scripts/lv/keys.py net.py                          Task 3
    scripts/lv/tools.py narrate.py captions.py         Task 4
    scripts/lv/sfx.py                                  Task 5
    scripts/lv/page.py render.py mix.py                Task 6
    scripts/lv/ingest.py                               Task 7
    scripts/lv/estimate.py status.py                   Task 8
    scripts/lv/music.py clips.py                       Task 9
    scripts/lv/doctor.py                               Task 10
    scripts/lv/cli.py                                  Task 2 (stub), grown in Tasks 3–10, finished Task 12
```

Module responsibilities: `config` = constants and paths; `util` = UTF-8 I/O, `run`, `UserError`, `safe_name`; `keys` = key lookup/masking/file/check; `net` = HTTP + retries + `ApiError` + `gemini_error`; `tools` = ffmpeg/ffprobe/Chromium; `narrate` = TTS takes, timing, narration track; `captions` = VTT; `sfx` = synthesized sound library; `page` = chapter page files + output path; `render` = browser server, stills, frame capture, final assembly; `mix` = audio mix; `ingest` = deck → slides.md/media/contact sheets; `estimate`/`status` = costs and resume state; `music`/`clips` = Gemini assets; `doctor` = install + test render; `cli` = argparse dispatch and error printing.

---

### Task 1: Create the repo, marketplace and plugin skeleton

**Files:**
- Create (GitHub): `DanielLandi/plugins` from template
- Create: `.claude-plugin/marketplace.json`, `lesson-videos/.claude-plugin/plugin.json`, `pyproject.toml`, `LICENSE`, `.gitignore`
- Modify (from template): `AGENTS.md`, `CLAUDE.md`, `SERVICES.md`, `README.md`

**Interfaces:**
- Produces: repo at `~/Projects/plugins` tracking `origin/main`; branch `feat/lesson-videos` for all later tasks.

- [ ] **Step 1: Create the public repo from the template (no clone yet; the local folder already holds the spec and this plan)**

```bash
gh repo create DanielLandi/plugins --template DanielLandi/repo-template --public \
  --description "Claude Code plugins by Daniel Landi. lesson-videos: turn a slide deck into narrated study videos."
sleep 5   # template copy is asynchronous
gh api repos/DanielLandi/plugins/contents --jq '.[].name'
```
Expected: lists `.github AGENTS.md CLAUDE.md README.md SERVICES.md bootstrap.sh docs`. If empty, wait 5 s and re-run the last line.

- [ ] **Step 2: Bring the template history into the existing local folder**

```bash
SCR=/private/tmp/claude-501/-Users-daniellandi-Projects-ihs-marine-biology/3c471b48-d4e5-4eb7-a95d-2335d30977bf/scratchpad
git clone https://github.com/DanielLandi/plugins.git "$SCR/plugins-clone"
rsync -a "$SCR/plugins-clone/" ~/Projects/plugins/
cd ~/Projects/plugins && git status --short && git log --oneline -1
```
Expected: `?? docs/superpowers/` untracked; one template commit.

- [ ] **Step 3: Repo settings (Tier B, no branch protection)**

```bash
cd ~/Projects/plugins && TIER=B ./bootstrap.sh
```
Expected: `Tier B: repo settings applied, branch protection skipped.`

- [ ] **Step 4: Create the branch and write the skeleton files**

```bash
cd ~/Projects/plugins && git switch -c feat/lesson-videos
mkdir -p .claude-plugin lesson-videos/.claude-plugin
```

`.claude-plugin/marketplace.json`:
```json
{
  "name": "daniellandi",
  "owner": { "name": "Daniel Landi" },
  "metadata": {
    "description": "Claude Code plugins by Daniel Landi."
  },
  "plugins": [
    {
      "name": "lesson-videos",
      "source": "./lesson-videos",
      "description": "Turn a slide deck into narrated, animated study videos, one per chapter. Guides setup of the tools and the ElevenLabs/Gemini keys.",
      "version": "0.1.0",
      "category": "education"
    }
  ]
}
```

`lesson-videos/.claude-plugin/plugin.json`:
```json
{
  "name": "lesson-videos",
  "version": "0.1.0",
  "description": "Turn a slide deck into narrated, animated study videos, one per chapter, with captions, test tips and an end-of-video quiz.",
  "author": { "name": "Daniel Landi" },
  "homepage": "https://github.com/DanielLandi/plugins/tree/main/lesson-videos",
  "license": "MIT",
  "keywords": ["education", "video", "slides", "narration", "teacher"]
}
```

`pyproject.toml` (development and tests only; the plugin itself runs from the PEP 723 block in Task 2, and `tests/test_packaging.py` keeps the two dependency lists identical):
```toml
[project]
name = "daniellandi-plugins-dev"
version = "0"
requires-python = ">=3.11"
dependencies = [
  "numpy>=1.26",
  "pillow>=10.0",
  "playwright>=1.45",
  "pymupdf>=1.24",
  "python-pptx>=1.0",
  "scipy>=1.11",
  "static-ffmpeg>=3.0",
]

[dependency-groups]
dev = ["pytest>=8"]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["lesson-videos/scripts"]
testpaths = ["tests"]
```

`.gitignore`:
```
__pycache__/
.pytest_cache/
.venv/
*.pyc
.DS_Store
# never commit keys or class material
*.env
lesson-videos/**/build/
```

`LICENSE`: the standard MIT text with `Copyright (c) 2026 Daniel Landi`.

`CLAUDE.md`:
```markdown
@AGENTS.md
```

`AGENTS.md` (replace the template body):
````markdown
# plugins

Public Claude Code marketplace `daniellandi`. Today it holds one plugin,
`lesson-videos`: teachers install it to turn a slide deck into narrated,
animated study videos. Users install with
`/plugin marketplace add DanielLandi/plugins` then
`/plugin install lesson-videos@daniellandi`.

## Contribution flow

This is a **Tier B repo** (solo dev tool): work on a short-lived branch off
`main`, run the local test gates below, merge back to `main` directly (no PR
needed), and push. PRs are optional and only opened when asked.

Teachers only receive a change when `lesson-videos/.claude-plugin/plugin.json`
`version` (and the matching entry in `.claude-plugin/marketplace.json` and
`lesson-videos/scripts/lv/__init__.py`) is bumped. Bump it for every
teacher-visible change; `tests/test_packaging.py` checks the three agree.

## Rules

- **Public repo.** Never commit class material (slides, worksheets, student
  work, teacher photos), student data, or API keys. Examples are generated
  (`examples/make_sample_deck.py`).
- **Windows and macOS.** Skills call only
  `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py" <command>`; no
  bash-only syntax in skills. Python passes `encoding="utf-8"` on every file
  read/write and uses argument lists for subprocesses.
- **Engine API is frozen** (`lesson-videos/engine/engine.js`): skills,
  `guide.md` and existing chapters depend on it. Add helpers, never rename.
- **Model IDs and prices** live only in `lesson-videos/scripts/lv/config.py`.

## Work tracking

GitHub Issues is the single source of truth for pending work. Capture
follow-ups with the `inbox` skill. For sandboxed sessions pass
`-R DanielLandi/plugins` to `gh`.

## Build & test

```bash
# setup (once): uv installs Python and deps on first run
uv run lesson-videos/scripts/lesson-videos.py doctor --no-keys
uv run python -m playwright install chromium   # same browser for the test env
# test (THE gate before merging):
uv run pytest -q
# run a command the way the skills do:
uv run lesson-videos/scripts/lesson-videos.py --help
```

## External services

See [`SERVICES.md`](./SERVICES.md) — update it in the same commit whenever a
service dependency is added, removed, or re-keyed.

## Frozen directories

Anything under `docs/archive/` or any file with an `⚠️ ARCHIVED` banner is
historical reference only — never a source of truth for current behavior.
````

`SERVICES.md` (replace the template body):
```markdown
# External services

| Service | Used by | Key | Who pays |
|---|---|---|---|
| ElevenLabs text-to-speech (`api.elevenlabs.io`) | `lv/narrate.py`, `lv/keys.py` | `ELEVENLABS_API_KEY`, supplied by each user in `~/.lesson-videos/keys.env` | the user |
| Gemini API: Veo 3.1 Lite, Lyria 3.5 (`generativelanguage.googleapis.com`) | `lv/clips.py`, `lv/music.py`, `lv/keys.py` | `GEMINI_API_KEY`, optional, same file | the user |
| GitHub Actions | `.github/workflows/ci.yml` | none | free (public repo) |
| Downloads at first run: astral.sh (uv), PyPI, Playwright browser CDN, github.com (static-ffmpeg binaries) | `skills/setup`, `lv/tools.py` | none | free |

The repo itself holds no keys.
```

`README.md` (repo root):
````markdown
# Daniel Landi's Claude Code plugins

| Plugin | What it does |
|---|---|
| [`lesson-videos`](./lesson-videos) | Turns a slide deck into narrated, animated study videos, one per chapter. Start with its [README](./lesson-videos/README.md). |

Install in Claude Code:

```
/plugin marketplace add DanielLandi/plugins
/plugin install lesson-videos@daniellandi
```
````

- [ ] **Step 5: Commit and push**

```bash
cd ~/Projects/plugins
git add -A
git commit -m "chore: marketplace + lesson-videos skeleton, spec and plan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
git push -u origin feat/lesson-videos
```

---

### Task 2: Entry point, config, util, CLI stub, test harness

**Files:**
- Create: `lesson-videos/scripts/lesson-videos.py`, `lesson-videos/scripts/lv/__init__.py`, `lv/config.py`, `lv/util.py`, `lv/cli.py`
- Test: `tests/conftest.py`, `tests/test_packaging.py`

**Interfaces:**
- Produces: `lv.__version__ = "0.1.0"`; `config.home() -> Path`, `config.PLUGIN_ROOT`, `config.ENTRY`, `config.ENGINE_JS`, `config.FONTS_DIR`, `config.FONT_FILES`, model/price constants; `util.UserError`, `util.read_text/write_text/read_json/write_json/run/safe_name`; `cli.main(argv=None) -> int`.

- [ ] **Step 1: Write the failing packaging tests**

`tests/conftest.py`:
```python
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "lesson-videos"


@pytest.fixture(autouse=True)
def lv_home(tmp_path, monkeypatch):
    """Every test gets its own ~/.lesson-videos (with a space in the path) and no real keys."""
    home = tmp_path / "home with space"
    monkeypatch.setenv("LESSON_VIDEOS_HOME", str(home))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return home
```

`tests/test_packaging.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/plugins && uv run pytest tests/test_packaging.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'lv'`).

- [ ] **Step 3: Write the entry point and base modules**

`lesson-videos/scripts/lesson-videos.py`:
```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=1.26",
#   "pillow>=10.0",
#   "playwright>=1.45",
#   "pymupdf>=1.24",
#   "python-pptx>=1.0",
#   "scipy>=1.11",
#   "static-ffmpeg>=3.0",
# ]
# ///
"""lesson-videos: turn a slide deck into narrated study videos. Run with --help."""
import sys

from lv.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

`lesson-videos/scripts/lv/__init__.py`:
```python
"""lesson-videos pipeline."""
__version__ = "0.1.0"
```

`lesson-videos/scripts/lv/config.py`:
```python
"""Paths, model IDs and prices. Preview model names change: update them here only."""
from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ENTRY = PLUGIN_ROOT / "scripts" / "lesson-videos.py"
ENGINE_JS = PLUGIN_ROOT / "engine" / "engine.js"
FONTS_DIR = PLUGIN_ROOT / "fonts"
FONT_FILES = ("PatrickHand-Regular.ttf", "Nunito.ttf")


def home() -> Path:
    """Per-user folder for keys, sound effects and caches."""
    return Path(os.environ.get("LESSON_VIDEOS_HOME") or Path.home() / ".lesson-videos")


ELEVEN_ROOT = "https://api.elevenlabs.io/v1"
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_FORMAT = "mp3_44100_128"            # 192 kbps needs a paid plan
VOICE_SETTINGS = {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}
DEFAULT_VOICE = "cgSgspJ2msm6clMCkdW9"     # Jessica: playful, bright, warm (premade voice)
NARRATION_WORKERS = 2                      # the ElevenLabs free plan allows 2 concurrent requests

GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta"
VEO_MODEL = "veo-3.1-lite-generate-preview"
VEO_SECONDS = 8
VEO_PRICE_PER_SECOND = 0.05                # USD at 720p
LYRIA_MODEL = "lyria-3.5"
LYRIA_PRICE = 0.08                         # USD per track

CHARS_PER_MINUTE = 900                     # narration characters per video minute (~150 wpm)
FPS = 30
W, H = 1920, 1080
USER_AGENT = "lesson-videos/0.1 (+https://github.com/DanielLandi/plugins)"
```

`lesson-videos/scripts/lv/util.py`:
```python
"""UTF-8 file helpers, subprocess with argument lists, and the plain-language error type."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class UserError(RuntimeError):
    """A failure with a plain-language message; the CLI prints it without a traceback."""


def read_text(p) -> str:
    return Path(p).read_text(encoding="utf-8")


def write_text(p, s: str) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")
    return p


def read_json(p):
    return json.loads(read_text(p))


def write_json(p, obj) -> Path:
    return write_text(p, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def run(*args, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args], check=True, **kw)


def safe_name(name: str) -> str:
    """A file name that is valid on Windows and macOS ("Entry 5/6" -> "Entry 5-6")."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).strip().rstrip(".") or "video"
```

`lesson-videos/scripts/lv/cli.py` (stub; later tasks add subcommands):
```python
"""Command line: `uv run lesson-videos.py <command>`."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .util import UserError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lesson-videos", description="Turn a slide deck into narrated study videos.")
    p.add_argument("--version", action="version", version=f"lesson-videos {__version__}")
    p.add_subparsers(dest="cmd", required=True, metavar="command")
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    args = build_parser().parse_args(argv)
    try:
        return dispatch(args)
    except UserError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def dispatch(args) -> int:
    raise UserError(f"unknown command {args.cmd}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_packaging.py -q`
Expected: 4 passed. (First run downloads the dependencies.)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: entry point, config, util, CLI stub and packaging tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 3: Keys and HTTP

**Files:**
- Create: `lv/keys.py`, `lv/net.py`
- Modify: `lv/cli.py` (add `keys` command)
- Test: `tests/test_keys.py`, `tests/test_net.py`

**Interfaces:**
- Consumes: `config.home`, `config.ELEVEN_ROOT`, `config.GEMINI_ROOT`, `util.UserError`, `util.read_text/write_text`.
- Produces: `keys.VARS`, `keys.TEMPLATE`, `keys.MissingKey(UserError)`, `keys.keys_file() -> Path`, `keys.parse(text) -> dict`, `keys.get(var, required=True) -> str`, `keys.mask(v) -> str`, `keys.redact(text) -> str`, `keys.ensure_file() -> Path`, `keys.editor_command(path, platform=sys.platform) -> list[str]`, `keys.open_in_editor(path, runner=subprocess.Popen) -> list[str]`, `keys.check(request=None) -> list[tuple[str, bool, str]]`; `net.ApiError(status, detail, url)` with `.status/.detail/.host`, `net.request(url, data=None, headers=None, method=None, timeout=120, retries=2, raw=False, sleep=time.sleep)`, `net._open(req, timeout)` (test seam), `net.gemini_error(e, what) -> UserError`.

- [ ] **Step 1: Write the failing tests**

`tests/test_keys.py`:
```python
import os
import sys

import pytest

from lv import keys, net

EL = "sk_0123456789abcdef0123456789abcdef"
GM = "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"


def test_parse_handles_comments_quotes_export_bom_crlf():
    text = "\ufeff# comment\r\nexport ELEVENLABS_API_KEY=\"abc123456789\"\r\nGEMINI_API_KEY='zz'\r\n\r\nNOEQUALS\r\n"
    assert keys.parse(text) == {"ELEVENLABS_API_KEY": "abc123456789", "GEMINI_API_KEY": "zz"}


def test_env_wins_over_file(monkeypatch):
    keys.ensure_file().write_text("ELEVENLABS_API_KEY=fromfile12345\n", encoding="utf-8")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fromenv123456")
    assert keys.get("ELEVENLABS_API_KEY") == "fromenv123456"


def test_file_used_and_placeholder_ignored(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "your-key-here")
    keys.ensure_file().write_text("ELEVENLABS_API_KEY=fromfile12345\n", encoding="utf-8")
    assert keys.get("ELEVENLABS_API_KEY") == "fromfile12345"


def test_missing_key_message_names_the_fix():
    with pytest.raises(keys.MissingKey) as e:
        keys.get("ELEVENLABS_API_KEY")
    assert "`keys`" in str(e.value) and "keys check" in str(e.value)
    assert keys.get("GEMINI_API_KEY", required=False) == ""


def test_mask_and_redact(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    assert keys.mask(EL) == "set, ends in …cdef"
    assert EL not in keys.redact(f"bad key {EL} and {GM}")
    assert GM not in keys.redact(f"bad key {GM}")


def test_ensure_file_creates_template_once(lv_home):
    f = keys.ensure_file()
    assert f == lv_home / "keys.env"
    assert "ELEVENLABS_API_KEY=" in f.read_text(encoding="utf-8")
    f.write_text("ELEVENLABS_API_KEY=kept\n", encoding="utf-8")
    keys.ensure_file()
    assert f.read_text(encoding="utf-8") == "ELEVENLABS_API_KEY=kept\n"
    if os.name == "posix":
        assert oct(f.stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("platform,first", [("darwin", "open"), ("win32", "notepad.exe"), ("linux", "xdg-open")])
def test_editor_command(tmp_path, platform, first):
    cmd = keys.editor_command(tmp_path / "keys.env", platform)
    assert cmd[0] == first and cmd[-1].endswith("keys.env")


def test_check_reports_credits_without_leaking(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    def fake(url, headers=None, timeout=None, **kw):
        assert headers["xi-api-key"] == EL
        return {"character_limit": 30000, "character_count": 1234, "tier": "starter"}
    rows = keys.check(request=fake)
    text = repr(rows)
    assert EL not in text
    assert rows[0][1] is True and "28,766 characters left" in rows[0][2]
    assert rows[1] == ("Gemini", True, "not set (optional): no music, no AI clips")


def test_check_rejected_key_without_leaking(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    monkeypatch.setenv("GEMINI_API_KEY", GM)
    def fake(url, headers=None, timeout=None, **kw):
        raise net.ApiError(401, f'{{"detail": "invalid_api_key {EL}"}}', url)
    rows = keys.check(request=fake)
    assert [r[1] for r in rows] == [False, False]
    assert EL not in repr(rows) and GM not in repr(rows)
    assert "rejected" in rows[0][2]


def test_check_missing_permission(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", EL)
    def fake(url, headers=None, timeout=None, **kw):
        raise net.ApiError(401, '{"detail": {"status": "missing_permissions", "message": "user_read"}}', url)
    rows = keys.check(request=fake)
    assert "User" in rows[0][2] and "read" in rows[0][2]
```

`tests/test_net.py`:
```python
import io
import urllib.error

import pytest

from lv import net


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://x.test/a", code, "err", {}, io.BytesIO(body))


def test_retries_503_then_succeeds(monkeypatch):
    calls = []
    def fake_open(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise http_error(503)
        return Resp(b'{"ok": true}')
    monkeypatch.setattr(net, "_open", fake_open)
    assert net.request("https://x.test/a", sleep=lambda s: None) == {"ok": True}
    assert len(calls) == 2


def test_no_retry_on_400(monkeypatch):
    calls = []
    def fake_open(req, timeout):
        calls.append(1)
        raise http_error(400, b'{"error": {"message": "bad"}}')
    monkeypatch.setattr(net, "_open", fake_open)
    with pytest.raises(net.ApiError) as e:
        net.request("https://x.test/a", sleep=lambda s: None)
    assert e.value.status == 400 and len(calls) == 1 and e.value.host == "x.test"


def test_api_error_redacts_key_shapes():
    e = net.ApiError(401, "key AIzaSyD-abcdefghijklmnopqrstuvwxyz12345 bad", "https://g.test")
    assert "AIza" not in str(e)


def test_gemini_error_billing():
    msg = str(net.gemini_error(net.ApiError(429, "RESOURCE_EXHAUSTED quota", "https://g.test"), "music"))
    assert "billing" in msg and "without music" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_keys.py tests/test_net.py -q`
Expected: FAIL (`ImportError: cannot import name 'keys'`).

- [ ] **Step 3: Implement `keys.py` and `net.py`**

`lv/keys.py`:
```python
"""API keys: environment first, then ~/.lesson-videos/keys.env. Values are never printed."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from . import config
from .util import UserError, read_text, write_text

VARS = {
    "ELEVENLABS_API_KEY": "ElevenLabs (narration, required)",
    "GEMINI_API_KEY": "Gemini (music and AI clips, optional)",
}
TEMPLATE = """# lesson-videos API keys
# Paste each key right after the = sign (no spaces, no quotes), then save and close.
# Keep this file private. To replace a key, paste the new one over the old one.

# ElevenLabs (required, narration): https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_API_KEY=

# Gemini (optional, music and AI video clips): https://aistudio.google.com/api-keys
GEMINI_API_KEY=
"""
_PLACEHOLDER = re.compile(r"^(|x+|changeme|your[-_ ].*|<.*>|\.\.\.)$", re.I)
_SHAPES = re.compile(r"(AIza[0-9A-Za-z_\-]{10,}|sk_[A-Za-z0-9]{16,}|xi-[A-Za-z0-9]{8,})")


class MissingKey(UserError):
    pass


def keys_file() -> Path:
    return config.home() / "keys.env"


def parse(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _from_file(var: str) -> str:
    f = keys_file()
    return parse(read_text(f)).get(var, "").strip() if f.exists() else ""


def get(var: str, required: bool = True) -> str:
    for v in (os.environ.get(var, "").strip(), _from_file(var)):
        if v and not _PLACEHOLDER.match(v):
            return v
    if required:
        raise MissingKey(f"{VARS.get(var, var)}: no key yet. Run the `keys` command, paste the key "
                         "into the file that opens, save it, then run `keys check`.")
    return ""


def mask(v: str) -> str:
    return f"set, ends in …{v[-4:]}" if len(v) >= 8 else "set"


def redact(text) -> str:
    text = str(text)
    for var in VARS:
        v = get(var, required=False)
        if len(v) >= 8:
            text = text.replace(v, "[redacted]")
    return _SHAPES.sub("[redacted]", text)


def ensure_file() -> Path:
    f = keys_file()
    if not f.exists():
        write_text(f, TEMPLATE)
    if os.name == "posix":
        os.chmod(f, 0o600)
    return f


def editor_command(path: Path, platform: str = sys.platform) -> list[str]:
    if platform == "darwin":
        return ["open", "-e", str(path)]
    if platform.startswith("win"):
        return ["notepad.exe", str(path)]
    return ["xdg-open", str(path)]


def open_in_editor(path: Path, runner=subprocess.Popen) -> list[str]:
    cmd = editor_command(path)
    runner(cmd)
    return cmd


def check(request=None) -> list[tuple[str, bool, str]]:
    """[(service, ok, message)]. Messages never contain key values."""
    from . import net
    request = request or net.request
    rows = []
    el = get("ELEVENLABS_API_KEY", required=False)
    if not el:
        rows.append(("ElevenLabs", False, "missing (required): run `keys` and paste it"))
    else:
        try:
            sub = request(f"{config.ELEVEN_ROOT}/user/subscription", headers={"xi-api-key": el}, timeout=30)
            left = int(sub.get("character_limit", 0)) - int(sub.get("character_count", 0))
            rows.append(("ElevenLabs", True, f"{mask(el)}; {left:,} characters left this month ({sub.get('tier', '?')} plan)"))
        except net.ApiError as e:
            d = e.detail.lower()
            if "permission" in d:
                hint = "the key works but can't read your account: edit the key at elevenlabs.io and allow User → Read"
            elif e.status == 401:
                hint = "the key was rejected: create a new one and paste it again"
            else:
                hint = str(e)
            rows.append(("ElevenLabs", False, f"{mask(el)}; {hint}"))
    gm = get("GEMINI_API_KEY", required=False)
    if not gm:
        rows.append(("Gemini", True, "not set (optional): no music, no AI clips"))
    else:
        try:
            request(f"{config.GEMINI_ROOT}/models?pageSize=1", headers={"x-goog-api-key": gm}, timeout=30)
            rows.append(("Gemini", True, f"{mask(gm)}; key works. Billing is checked the first time music or a clip is made."))
        except net.ApiError as e:
            hint = "the key was rejected: create a new one and paste it again" if e.status in (400, 401, 403) else str(e)
            rows.append(("Gemini", False, f"{mask(gm)}; {hint}"))
    return rows
```

`lv/net.py`:
```python
"""HTTP with retries on network errors, 429 and 5xx. Errors never carry secrets."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, keys
from .util import UserError


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str = "", url: str = ""):
        self.status = status
        self.detail = keys.redact(detail)
        self.host = urllib.parse.urlparse(url).netloc or "service"
        super().__init__(f"{self.host} failed ({status}): {self.detail[:300]}")


def _open(req, timeout):
    """The single network seam; tests replace it."""
    return urllib.request.urlopen(req, timeout=timeout)


def request(url, data=None, headers=None, method=None, timeout=120, retries=2, raw=False, sleep=time.sleep):
    h = {"User-Agent": config.USER_AGENT, **(headers or {})}
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=body, headers=h, method=method or ("POST" if body is not None else "GET"))
        try:
            with _open(req, timeout) as r:
                payload = r.read()
            return payload if raw else (json.loads(payload) if payload else {})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                sleep(2 * 3 ** attempt)
                attempt += 1
                continue
            raise ApiError(e.code, detail, url) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                sleep(2 + 3 * attempt)
                attempt += 1
                continue
            raise ApiError(0, str(getattr(e, "reason", e)), url) from None


def gemini_error(e: ApiError, what: str) -> UserError:
    d = e.detail.lower()
    if e.status in (403, 429) or "billing" in d or "quota" in d:
        return UserError(f"Gemini refused the {what} ({e.status}): billing isn't enabled on the key's project, "
                         f"or its spend cap was reached. The videos can still be made without {what}.")
    if e.status in (400, 401) and "api key" in d:
        return UserError("The Gemini key was rejected: run `keys check`.")
    if e.status == 404:
        return UserError(f"Gemini doesn't know that model ({e.detail[:120]}). The model name in lv/config.py needs updating.")
    return UserError(f"Gemini failed making the {what}: {e}")
```

- [ ] **Step 4: Add the `keys` command to `cli.py`**

In `build_parser`, keep a handle on the subparsers and register `keys`:
```python
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")
    k = sub.add_parser("keys", help="open the keys file; `keys check` tests the keys")
    k.add_argument("action", nargs="?", choices=["open", "check"], default="open")
    return p
```
(replace the existing `p.add_subparsers(...)` line and `return p`.)

Replace `dispatch`:
```python
def dispatch(args) -> int:
    from . import keys
    if args.cmd == "keys":
        if args.action == "check":
            rows = keys.check()
            for name, good, msg in rows:
                print(f"{'✓' if good else '✗'} {name}: {msg}")
            return 0 if all(good for _, good, _ in rows) else 1
        f = keys.ensure_file()
        keys.open_in_editor(f)
        print(f"Opened {f}. Paste the keys after the = signs, save, close the editor, then run `keys check`.")
        return 0
    raise UserError(f"unknown command {args.cmd}")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_keys.py tests/test_net.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: key file, masked key checks and HTTP with retries

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 4: ffmpeg tools, narration and captions

**Files:**
- Create: `lv/tools.py`, `lv/narrate.py`, `lv/captions.py`
- Modify: `tests/conftest.py` (add `fake_speak`, `make_chapter` fixtures)
- Test: `tests/test_narrate.py`, `tests/test_captions.py`

**Interfaces:**
- Consumes: `config.*`, `keys.get`, `net.request/ApiError`, `util.*`.
- Produces: `tools.ffmpeg() -> str`, `tools.ffprobe() -> str`, `tools.duration(path) -> float`, `tools.streams(path) -> set[str]`, `tools.has_x264() -> bool`, `tools.install_chromium() -> None`; `narrate.cache_key(voice, say) -> str`, `narrate.words_from(al) -> list[dict]`, `narrate.build_timing(spec, takes) -> dict`, `narrate.speak(text, voice, out) -> None`, `narrate.narrate(ch, speak_fn=speak, workers=config.NARRATION_WORKERS) -> dict`, `narrate.read_timing(ch) -> dict`, `narrate.narration_track(ch, T) -> Path`; `captions.segments(T)`, `captions.stamp(t)`, `captions.vtt(T) -> str`.
- Timing dict shape (used by render, mix, captions, engine): `{"chapter", "title", "duration", "scenes": [{"id", "start", "dur", "lead", "speech", "words": [{"w", "s", "e"}], "audio"}]}`; word times are relative to the scene start and already include `lead`.

- [ ] **Step 1: Add shared fixtures to `tests/conftest.py`**

Append:
```python
import subprocess


def _silence(path, seconds):
    from lv import tools
    subprocess.run([tools.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", f"{seconds:.3f}", "-b:a", "128k", str(path)], check=True)


@pytest.fixture
def fake_speak():
    """Stand-in for ElevenLabs: silence 0.06 s per character, evenly spaced alignment."""
    calls = []

    def speak(text, voice, out):
        from lv.util import write_json
        calls.append(text)
        n = len(text)
        write_json(out.with_suffix(".json"), {"chars": list(text), "starts": [i * 0.06 for i in range(n)],
                                              "ends": [(i + 1) * 0.06 for i in range(n)]})
        _silence(out, n * 0.06)
    speak.calls = calls
    return speak


@pytest.fixture
def make_chapter(tmp_path):
    """Write a chapter folder (script.json + optional scenes.js) under a path with spaces."""
    def make(scenes, scenes_js=None, name="ch1", **top):
        from lv.util import write_json, write_text
        ch = tmp_path / "Unit 1 – Biología" / "lesson-videos" / "_work" / name
        write_json(ch / "script.json", {"chapter": "TEST", "title": "Test chapter", "out": "Chapter 1 - Test.mp4", **top, "scenes": scenes})
        if scenes_js is not None:
            write_text(ch / "scenes.js", scenes_js)
        return ch
    return make
```

- [ ] **Step 2: Write the failing tests**

`tests/test_narrate.py`:
```python
import json

import pytest

from lv import narrate, net, tools
from lv.util import UserError, read_text


def test_cache_key_matches_original_build_py():
    # value computed with the Unit 1 build.py formula; old caches must stay valid
    assert narrate.cache_key("cgSgspJ2msm6clMCkdW9", "Hello there.") == "1dd3ed56061b"


def test_words_from_groups_characters():
    al = {"chars": list("Hi you"), "starts": [0, .1, .2, .3, .4, .5], "ends": [.1, .2, .3, .4, .5, .6]}
    assert narrate.words_from(al) == [{"w": "Hi", "s": 0, "e": 0.2}, {"w": "you", "s": 0.3, "e": 0.6}]


def test_build_timing_math():
    spec = {"chapter": "C", "title": "T", "scenes": [
        {"id": "a", "say": "x"}, {"id": "b", "say": "y", "lead": 1.0, "tail": 0.5, "hold": 2},
        {"id": "c", "min": 3}]}
    takes = {"a": (2.0, [{"w": "x", "s": 0.1, "e": 0.4}], "build/voice/a.mp3"), "b": (1.0, [], "build/voice/b.mp3")}
    T = narrate.build_timing(spec, takes)
    assert [s["start"] for s in T["scenes"]] == [0, 3.2, 7.7]
    assert [s["dur"] for s in T["scenes"]] == [3.2, 4.5, 3]
    assert T["scenes"][0]["words"] == [{"w": "x", "s": 0.6, "e": 0.9}]
    assert T["duration"] == 10.7 and T["scenes"][2]["audio"] is None


def test_narrate_writes_timing_and_track_and_caches(make_chapter, fake_speak):
    ch = make_chapter([{"id": "one", "say": "Hola, ¿qué tal?"}, {"id": "two", "say": "Water follows salt."}])
    T = narrate.narrate(ch, speak_fn=fake_speak)
    assert len(fake_speak.calls) == 2
    assert read_text(ch / "build/timing.js").startswith("window.TIMING = ")
    assert narrate.read_timing(ch)["duration"] == T["duration"]
    assert abs(tools.duration(ch / "build/narration.mp3") - T["duration"]) < 0.15
    narrate.narrate(ch, speak_fn=fake_speak)
    assert len(fake_speak.calls) == 2  # cached: no new takes


def test_no_speech_makes_silence(make_chapter, fake_speak):
    ch = make_chapter([{"id": "only", "min": 2}])
    T = narrate.narrate(ch, speak_fn=fake_speak)
    assert fake_speak.calls == [] and T["duration"] == 2
    assert abs(tools.duration(ch / "build/narration.mp3") - 2) < 0.15


def test_quota_error_keeps_finished_scenes(make_chapter, fake_speak):
    ch = make_chapter([{"id": f"s{i}", "say": f"Scene number {i}."} for i in range(4)])
    def flaky(text, voice, out):
        if text.endswith("3."):
            raise net.ApiError(401, '{"detail": {"status": "quota_exceeded"}}', "https://api.elevenlabs.io/v1/x")
        fake_speak(text, voice, out)
    with pytest.raises(UserError) as e:
        narrate.narrate(ch, speak_fn=flaky, workers=1)
    msg = str(e.value)
    assert "credits" in msg and "keys check" in msg and "saved" in msg
    assert len(list((ch / "build/voice").glob("*.mp3"))) == 3
```

`tests/test_captions.py`:
```python
from lv import captions

T = {"scenes": [
    {"start": 10.0, "words": [{"w": "One.", "s": 0.5, "e": 0.9}, {"w": "Two", "s": 1.0, "e": 1.2}, {"w": "three!", "s": 1.3, "e": 1.6}]},
    {"start": 20.0, "words": [{"w": f"w{i}", "s": i * 0.1, "e": i * 0.1 + 0.05} for i in range(20)]},
]}


def test_segments_split_on_sentences_and_16_words():
    seg = captions.segments(T)
    assert seg[0] == (10.5, 10.9, "One.") and seg[1] == (11.0, 11.6, "Two three!")
    assert len(seg[2][2].split()) == 16 and len(seg[3][2].split()) == 4


def test_stamp_and_vtt():
    assert captions.stamp(3725.5) == "01:02:05.500"
    v = captions.vtt(T)
    assert v.startswith("WEBVTT\n\n1\n00:00:10.500 --> 00:00:11.250\nOne.\n")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_narrate.py tests/test_captions.py -q`
Expected: FAIL (`ImportError`).

- [ ] **Step 4: Implement `tools.py`, `narrate.py`, `captions.py`**

`lv/tools.py`:
```python
"""ffmpeg/ffprobe (system first, else the static-ffmpeg download) and the Playwright browser."""
from __future__ import annotations

import functools
import shutil
import subprocess
import sys

from .util import UserError


@functools.cache
def _pair() -> tuple[str, str]:
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ff and fp:
        return ff, fp
    try:
        from static_ffmpeg import run
        ff, fp = run.get_or_fetch_platform_executables_else_raise()
        return str(ff), str(fp)
    except Exception as e:  # noqa: BLE001  network blocked, unsupported platform
        raise UserError(f"Could not get ffmpeg ({e}). Install it (macOS: `brew install ffmpeg`; Windows: "
                        "`winget install Gyan.FFmpeg`) or allow downloads from github.com, then retry.") from None


def ffmpeg() -> str:
    return _pair()[0]


def ffprobe() -> str:
    return _pair()[1]


def _probe(*args) -> str:
    return subprocess.run([ffprobe(), "-v", "error", *map(str, args)], capture_output=True, check=True,
                          encoding="utf-8", errors="replace").stdout


def duration(path) -> float:
    return float(_probe("-show_entries", "format=duration", "-of", "csv=p=0", path).strip())


def streams(path) -> set[str]:
    return {l.strip().strip(",") for l in _probe("-show_entries", "stream=codec_type", "-of", "csv=p=0", path).splitlines() if l.strip()}


def has_x264() -> bool:
    out = subprocess.run([ffmpeg(), "-hide_banner", "-encoders"], capture_output=True, encoding="utf-8", errors="replace").stdout
    return "libx264" in out


def install_chromium() -> None:
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        raise UserError("Could not download the Chromium renderer (about 150 MB). Check the internet connection "
                        "(school networks may block it), then run `doctor` again.\n" + r.stderr[-800:])
```

`lv/narrate.py`:
```python
"""Narration: one ElevenLabs take per scene (cached by text), word timings, the narration track."""
from __future__ import annotations

import base64
import concurrent.futures as cf
import hashlib
import json
from pathlib import Path

from . import config, keys, net, tools
from .util import UserError, read_json, read_text, run, write_json, write_text


def cache_key(voice: str, say: str) -> str:
    raw = f"{voice}|{config.ELEVEN_MODEL}|{json.dumps(config.VOICE_SETTINGS)}|{say}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def words_from(al: dict) -> list[dict]:
    words, cur, s, e = [], "", None, None
    for ch, cs, ce in zip(al["chars"], al["starts"], al["ends"]):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "s": round(s, 3), "e": round(e, 3)})
            cur, s = "", None
            continue
        if s is None:
            s = cs
        cur += ch
        e = ce
    if cur:
        words.append({"w": cur, "s": round(s, 3), "e": round(e, 3)})
    return words


def speak(text: str, voice: str, out: Path) -> None:
    body = {"text": text, "model_id": config.ELEVEN_MODEL, "voice_settings": config.VOICE_SETTINGS}
    url = f"{config.ELEVEN_ROOT}/text-to-speech/{voice}/with-timestamps?output_format={config.ELEVEN_FORMAT}"
    d = net.request(url, data=body, headers={"xi-api-key": keys.get("ELEVENLABS_API_KEY")}, timeout=180)
    a = d.get("alignment") or {}
    write_json(out.with_suffix(".json"), {"chars": a.get("characters", []), "starts": a.get("character_start_times_seconds", []),
                                          "ends": a.get("character_end_times_seconds", [])})
    out.write_bytes(base64.b64decode(d["audio_base64"]))  # the mp3 is the cache marker, so it is written last


def build_timing(spec: dict, takes: dict) -> dict:
    """Pure: scenes + {id: (speech_seconds, words, audio_relpath)} -> timing dict."""
    t, out = 0.0, []
    for sc in spec["scenes"]:
        lead, tail, hold = sc.get("lead", 0.5), sc.get("tail", 0.7), sc.get("hold", 0)
        speech, words, audio = takes.get(sc["id"], (0.0, [], None))
        words = [{**w, "s": round(w["s"] + lead, 3), "e": round(w["e"] + lead, 3)} for w in words]
        dur = max(sc.get("min", 0), lead + speech + tail + hold)
        out.append({"id": sc["id"], "start": round(t, 3), "dur": round(dur, 3), "lead": lead,
                    "speech": round(speech, 3), "words": words, "audio": audio})
        t += dur
    return {"chapter": spec.get("chapter", ""), "title": spec.get("title", ""), "duration": round(t, 3), "scenes": out}


def narration_error(e: net.ApiError, done: int, total: int) -> str:
    msg = (f"Narration stopped after {done} of {total} new scenes ({e.host} said {e.status}). "
           "Finished scenes are saved and won't be paid for again.")
    d = e.detail.lower()
    if "quota" in d or e.status == 402:
        msg += (" Your ElevenLabs credits for this month are used up: run `keys check` to see what's left, "
                "or upgrade the plan, then run `narrate` again.")
    elif e.status == 401:
        msg += " The ElevenLabs key was rejected or can't use Text to Speech: run `keys check`."
    elif e.status == 429:
        msg += " ElevenLabs is limiting requests: wait a minute and run `narrate` again."
    else:
        msg += f" Details: {e.detail[:200]}"
    return msg


def narrate(ch: Path, speak_fn=speak, workers: int = config.NARRATION_WORKERS) -> dict:
    spec = read_json(ch / "script.json")
    voice = spec.get("voice", config.DEFAULT_VOICE)
    vd = ch / "build" / "voice"
    vd.mkdir(parents=True, exist_ok=True)
    files, jobs = {}, []
    for sc in spec["scenes"]:
        say = sc.get("say", "").strip()
        if not say:
            continue
        f = vd / f"{sc['id']}-{cache_key(voice, say)}.mp3"
        files[sc["id"]] = f
        if not f.exists():
            jobs.append((say, f))
    if jobs and speak_fn is speak:
        keys.get("ELEVENLABS_API_KEY")  # fail early with the friendly message
    done = 0
    try:
        with cf.ThreadPoolExecutor(workers) as ex:
            for fu in cf.as_completed([ex.submit(speak_fn, say, voice, f) for say, f in jobs]):
                fu.result()
                done += 1
                print(f"  voiced {done}/{len(jobs)}", flush=True)
    except net.ApiError as e:
        raise UserError(narration_error(e, done, len(jobs))) from None
    takes = {sid: (tools.duration(f), words_from(read_json(f.with_suffix(".json"))), f.relative_to(ch).as_posix())
             for sid, f in files.items()}
    T = build_timing(spec, takes)
    write_text(ch / "build" / "timing.js", "window.TIMING = " + json.dumps(T) + ";\n")
    narration_track(ch, T)
    return T


def read_timing(ch: Path) -> dict:
    f = ch / "build" / "timing.js"
    if not f.exists():
        raise UserError(f"{ch.name}: no narration yet. Run `narrate` first.")
    return json.loads(read_text(f).split("=", 1)[1].strip().rstrip(";"))


def narration_track(ch: Path, T: dict) -> Path:
    out = ch / "build" / "narration.mp3"
    total = T["duration"]
    voiced = [s for s in T["scenes"] if s["audio"]]
    if not voiced:
        run(tools.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", total, "-b:a", "192k", out)
        return out
    ins, flt = [], []
    for i, s in enumerate(voiced):
        ins += ["-i", str(ch / s["audio"])]
        ms = int((s["start"] + s["lead"]) * 1000)
        flt.append(f"[{i}:a]adelay={ms}|{ms},aformat=channel_layouts=stereo[a{i}]")
    flt.append("".join(f"[a{i}]" for i in range(len(voiced))) + f"amix=inputs={len(voiced)}:normalize=0,apad=whole_dur={total}[out]")
    run(tools.ffmpeg(), "-v", "error", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[out]", "-t", total,
        "-ar", 44100, "-b:a", "192k", out)
    return out
```

`lv/captions.py`:
```python
"""WebVTT captions from narration word timings, split the same way as the on-screen captions."""
from __future__ import annotations

import re

SENTENCE_END = re.compile(r"[.!?][\"”']?$")


def segments(T: dict) -> list[tuple[float, float, str]]:
    out = []
    for sc in T["scenes"]:
        cur = []
        for w in sc.get("words") or []:
            cur.append(w)
            if SENTENCE_END.search(w["w"]) or len(cur) >= 16:
                out.append((round(sc["start"] + cur[0]["s"], 3), round(sc["start"] + cur[-1]["e"], 3), " ".join(x["w"] for x in cur)))
                cur = []
        if cur:
            out.append((round(sc["start"] + cur[0]["s"], 3), round(sc["start"] + cur[-1]["e"], 3), " ".join(x["w"] for x in cur)))
    return out


def stamp(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def vtt(T: dict) -> str:
    lines = ["WEBVTT", ""]
    for i, (s, e, text) in enumerate(segments(T), 1):
        lines += [str(i), f"{stamp(s)} --> {stamp(e + 0.35)}", text, ""]
    return "\n".join(lines)
```

- [ ] **Step 5: Verify the static-ffmpeg API name**

Run: `uv run python -c "from static_ffmpeg import run; print(run.get_or_fetch_platform_executables_else_raise())"`
Expected: a tuple of two paths. If the function name differs, read `uv run python -c "import static_ffmpeg.run as r; print(dir(r))"` and update `tools._pair`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_narrate.py tests/test_captions.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: ffmpeg lookup, cached ElevenLabs narration with word timing, VTT captions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 5: Sound-effect library

**Files:**
- Create: `lv/sfx.py` (port of `collage-studio/studio/sfx.py` `synth()`, without the Kenney downloads)
- Test: `tests/test_sfx.py`

**Interfaces:**
- Consumes: `config.home`.
- Produces: `sfx.NAMES: tuple[str, ...]`, `sfx.sfx_dir() -> Path`, `sfx.build(force=False) -> Path`.

- [ ] **Step 1: Write the failing test**

`tests/test_sfx.py`:
```python
import wave

from lv import sfx


def test_build_makes_every_name_once(lv_home):
    d = sfx.build()
    assert d == lv_home / "sfx"
    for name in sfx.NAMES:
        with wave.open(str(d / f"{name}.wav")) as w:
            assert (w.getnchannels(), w.getframerate()) == (2, 48000) and w.getnframes() > 1000
    stamp = (d / "pop0.wav").stat().st_mtime_ns
    sfx.build()
    assert (d / "pop0.wav").stat().st_mtime_ns == stamp
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_sfx.py -q` → FAIL (`ImportError`).

- [ ] **Step 3: Implement `lv/sfx.py`**

```python
"""Synthesized sound effects (pops, sparkles, whooshes, plucks...), built once into ~/.lesson-videos/sfx."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy import signal

from . import config

SR = 48000
NAMES = tuple([f"pencil{i}" for i in range(3)] + [f"crayon{i}" for i in range(2)] + [f"tape{i}" for i in range(3)]
              + [f"whoosh{i}" for i in range(3)] + [f"sparkle{i}" for i in range(3)] + [f"pop{i}" for i in range(4)]
              + [f"pluck{i}" for i in range(4)] + ["waves0"] + [f"zip{i}" for i in range(3)] + ["shutter0"]
              + [f"thump{i}" for i in range(2)])


def sfx_dir() -> Path:
    return config.home() / "sfx"


def _save(name, x, stereo=None):
    if stereo is None:
        stereo = np.stack([x, x], 1)
    stereo = stereo / (np.abs(stereo).max() + 1e-9) * 0.89
    d = (stereo * 32767).astype(np.int16)
    sfx_dir().mkdir(parents=True, exist_ok=True)
    with wave.open(str(sfx_dir() / f"{name}.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(d.tobytes())


def _t(d): return np.arange(int(d * SR)) / SR
def _bp(x, lo, hi, o=2): return signal.sosfilt(signal.butter(o, [lo, hi], "band", fs=SR, output="sos"), x)
def _lp(x, f, o=2): return signal.sosfilt(signal.butter(o, f, "low", fs=SR, output="sos"), x)
def _hp(x, f, o=2): return signal.sosfilt(signal.butter(o, f, "high", fs=SR, output="sos"), x)


def _synth():
    rng = np.random.default_rng(11)

    def pink(n):
        w = rng.standard_normal(n); f = np.fft.rfft(w); k = np.arange(len(f)); k[0] = 1
        return np.fft.irfft(f / np.sqrt(k), n)

    def ir(d=0.9, decay=3.5):
        n = int(d * SR); e = np.exp(-decay * np.arange(n) / n * 5)
        L = _lp(rng.standard_normal(n) * e, 7000); R = _lp(rng.standard_normal(n) * e, 7000)
        return L / np.abs(L).sum() * 30, R / np.abs(R).sum() * 30
    IRL, IRR = ir()

    def verb(x, wet=0.25):
        L = signal.fftconvolve(x, IRL)[:len(x) + len(IRL) - 1]; R = signal.fftconvolve(x, IRR)[:len(L)]
        dry = np.pad(x, (0, len(L) - len(x)))
        return np.stack([dry + wet * L, dry + wet * R], 1)

    def pencil(d, seed):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d)
        base = _bp(pink(n), 1800, 7000) * 0.6 + _bp(r.standard_normal(n), 3000, 9000) * 0.25
        rate = r.uniform(6, 9); env = np.abs(np.sin(np.pi * rate * tt + r.uniform(0, 3))) ** 0.7
        env *= 0.7 + 0.3 * np.sin(2 * np.pi * 1.3 * tt)
        grains = np.zeros(n); idx = r.integers(0, n, int(d * 900)); grains[idx] = r.uniform(-1, 1, len(idx)); grains = _hp(grains, 2500) * 0.5
        fade = np.minimum(1, np.minimum(tt / 0.04, (d - tt) / 0.08))
        return (base + grains) * env * fade
    for i, d in enumerate([0.7, 1.3, 2.0]): _save(f"pencil{i}", pencil(d, 100 + i))

    def crayon(d, seed):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d)
        base = _bp(pink(n), 700, 4500) * 0.8
        env = np.abs(np.sin(np.pi * r.uniform(3.5, 5) * tt)) ** 0.5
        return base * env * np.minimum(1, np.minimum(tt / 0.03, (d - tt) / 0.1))
    for i, d in enumerate([0.8, 1.4]): _save(f"crayon{i}", crayon(d, 200 + i))

    def tape(seed):
        r = np.random.default_rng(seed); d = 0.55; n = int(d * SR); tt = _t(d)
        rip_d = r.uniform(0.22, 0.32); m = tt < rip_d
        dens = np.where(m, 3000 + 9000 * (tt / rip_d), 0)
        imp = (r.random(n) < dens / SR) * r.uniform(-1, 1, n)
        crack = _bp(imp, 900, 9000) * 1.2 + _bp(r.standard_normal(n), 2000, 8000) * 0.15 * m
        env = np.where(m, np.minimum(1, tt / 0.02), np.exp(-(tt - rip_d) * 60))
        thump_t = tt - (rip_d + 0.06)
        thump = np.where(thump_t > 0, np.sin(2 * np.pi * 140 * thump_t) * np.exp(-thump_t * 45), 0) * 0.5
        press = np.where(thump_t > 0, _bp(r.standard_normal(n), 300, 2500) * np.exp(-np.maximum(thump_t, 0) * 30), 0) * 0.3
        return crack * env + thump + press
    for i in range(3): _save(f"tape{i}", tape(300 + i))

    def whoosh(d, seed, lo=350, hi=2600):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d); x = r.standard_normal(n)
        out = np.zeros(n); blk = 480; zi = None
        for s in range(0, n, blk):
            p = s / n; fc = lo + (hi - lo) * np.sin(np.pi * p) ** 1.5
            sos = signal.butter(2, [fc * 0.6, fc * 1.5], "band", fs=SR, output="sos")
            if zi is None: zi = np.zeros((sos.shape[0], 2))
            out[s:s + blk], zi = signal.sosfilt(sos, x[s:s + blk], zi=zi)
        y = out * np.sin(np.pi * tt / d) ** 2
        pan = tt / d
        return y, np.stack([y * np.cos(pan * np.pi / 2) * 1.2, y * np.sin(pan * np.pi / 2) * 1.2], 1)
    for i, d in enumerate([0.6, 0.9, 1.3]):
        m, s = whoosh(d, 400 + i); _save(f"whoosh{i}", m, s)

    def bell(f, d, amp=1.0):
        tt = _t(d)
        return amp * (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 5) + 0.35 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 11)
                      + 0.15 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 18)) * np.minimum(1, tt / 0.002)

    def sparkle(notes, gap, seed, d=2.2):
        r = np.random.default_rng(seed); n = int(d * SR); x = np.zeros(n)
        for k, f in enumerate(notes):
            s = int((k * gap + r.uniform(0, 0.015)) * SR); b = bell(f, 1.2, 0.6 + 0.4 * r.random())
            x[s:s + len(b)] += b[:n - s]
        return verb(x, 0.35)[:n + int(0.5 * SR)]
    P = [1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0, 2349.3, 2637.0, 3136.0]
    _save("sparkle0", None, sparkle([P[i] for i in [2, 4, 5, 7, 8]], 0.07, 500))
    _save("sparkle1", None, sparkle([P[i] for i in [8, 6, 5, 3, 2, 0]], 0.06, 501))
    _save("sparkle2", None, sparkle([P[i] for i in [0, 3, 5, 8]], 0.11, 502))

    def pop(f0, seed):
        r = np.random.default_rng(seed); d = 0.18; tt = _t(d)
        f = f0 * (0.45 + 0.55 * np.exp(-tt * 40)); ph = 2 * np.pi * np.cumsum(f) / SR
        return (np.sin(ph) * np.exp(-tt * 28) * np.minimum(1, tt / 0.003)
                + _bp(r.standard_normal(len(tt)), 1500, 6000) * np.exp(-tt * 120) * 0.2)
    for i, f in enumerate([700, 900, 1100, 1300]): _save(f"pop{i}", None, verb(pop(f, 600 + i), 0.12))

    def pluck(f, d=0.9, seed=0):
        r = np.random.default_rng(seed); n = int(d * SR); N = int(SR / f); buf = r.uniform(-1, 1, N); out = np.zeros(n)
        for i in range(n):
            out[i] = buf[i % N]; buf[i % N] = 0.996 * 0.5 * (buf[i % N] + buf[(i + 1) % N])
        return out
    for i, f in enumerate([523.3, 659.3, 784.0, 1046.5]): _save(f"pluck{i}", None, verb(pluck(f, 0.8, 700 + i), 0.2))

    def waves(d):
        n = int(d * SR); tt = _t(d); b = np.cumsum(rng.standard_normal(n)); b = _hp(b, 40); b = _lp(b, 1800)
        sw = 0.55 + 0.45 * np.sin(2 * np.pi * tt / 2.6 - 1.2) ** 2
        fiz = _bp(rng.standard_normal(n), 2500, 9000) * (np.sin(2 * np.pi * tt / 2.6 - 0.6).clip(0) ** 3) * 0.3
        fade = np.minimum(1, np.minimum(tt / 0.6, (d - tt) / 0.8))
        L = (b / np.abs(b).max() * sw + fiz) * fade; R = np.roll(L, 900)
        return np.stack([L, R], 1)
    _save("waves0", None, waves(4.0))

    def zipper(seed, d=0.35):
        r = np.random.default_rng(seed); n = int(d * SR); tt = _t(d); x = r.standard_normal(n)
        out = np.zeros(n); blk = 240; zi = None
        for s in range(0, n, blk):
            fc = 1200 + 4000 * (s / n); sos = signal.butter(2, [fc * 0.7, fc * 1.3], "band", fs=SR, output="sos")
            if zi is None: zi = np.zeros((sos.shape[0], 2))
            out[s:s + blk], zi = signal.sosfilt(sos, x[s:s + blk], zi=zi)
        return out * np.sin(np.pi * tt / d) ** 1.5
    for i in range(3): _save(f"zip{i}", zipper(800 + i, [0.3, 0.45, 0.6][i]))

    def shutter():
        d = 0.7; n = int(d * SR); tt = _t(d); x = np.zeros(n)
        for s0, a in [(0.0, 1.0), (0.075, 0.7)]:
            s = int(s0 * SR); m = int(0.012 * SR)
            x[s:s + m] += _hp(rng.standard_normal(m), 1500) * np.exp(-np.arange(m) / SR * 400) * a
        wt = tt - 0.16; saw = signal.sawtooth(2 * np.pi * (700 + 150 * np.sin(2 * np.pi * 18 * tt)) * tt) * 0.12
        whirr = np.where((wt > 0) & (wt < 0.4), _lp(saw + 0.2 * _bp(rng.standard_normal(n), 800, 3000), 3000)
                         * np.sin(np.pi * np.clip(wt / 0.4, 0, 1)), 0)
        return x + whirr * 0.8
    _save("shutter0", shutter())

    def thump(seed):
        r = np.random.default_rng(seed); d = 0.3; tt = _t(d)
        return np.sin(2 * np.pi * 95 * tt) * np.exp(-tt * 30) * 0.8 + _bp(r.standard_normal(len(tt)), 400, 3500) * np.exp(-tt * 45) * 0.6
    for i in range(2): _save(f"thump{i}", thump(900 + i))


def build(force: bool = False) -> Path:
    if force or not all((sfx_dir() / f"{n}.wav").exists() for n in NAMES):
        _synth()
    return sfx_dir()
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_sfx.py -q` → PASS.

- [ ] **Step 5: Listen to two of them** (sanity, Mac only): `afplay "$(uv run python -c 'from lv import sfx; print(sfx.build())')/pop0.wav"` with `LESSON_VIDEOS_HOME` unset is fine; they must sound like the Unit 1 videos' pops/sparkles.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: synthesized sound-effect library

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 6: Engine, fonts, page, renderer and audio mix

**Files:**
- Create: `lesson-videos/engine/engine.js` (copy + 3 edits), `lesson-videos/fonts/{PatrickHand-Regular.ttf,OFL-PatrickHand.txt,Nunito.ttf,OFL-Nunito.txt}`, `lv/page.py`, `lv/render.py`, `lv/mix.py`
- Modify: `lv/cli.py` (`narrate`, `stills`, `render`, `_part`)
- Test: `tests/test_render.py`, `tests/test_mix.py`, `tests/conftest.py` (browser fixture)

**Interfaces:**
- Consumes: `narrate.read_timing`, `captions.vtt`, `tools.*`, `sfx.sfx_dir`, `config.*`, `util.*`.
- Produces: `page.INDEX`, `page.ensure_page(ch)`, `page.output_dir(ch) -> Path`, `page.output_path(ch, spec, out_dir=None) -> Path`; `render.serve(root)` (context manager → port), `render.page_for(ch)` (context manager → `(page, logs)`), `render.fail_on_errors(logs)`, `render.grab(pg, t, q) -> bytes`, `render.events(ch) -> list[dict]`, `render.stills(ch, times, cols=3) -> Path`, `render.video_part(ch, out, fps, f0, f1)`, `render.default_workers() -> int`, `render.render(ch, workers=None, fps=30, out_dir=None) -> Path`; `mix.mix_audio(ch, T, spec) -> Path`.

- [ ] **Step 1: Copy the engine and make the three font edits**

```bash
SRC=~/Projects/ihs/marine-biology/study-kit/videos/_source
mkdir -p lesson-videos/engine lesson-videos/fonts
cp "$SRC/engine/engine.js" lesson-videos/engine/engine.js
cp ~/Projects/dotfiles/claude-plugins/collage-studio/runtime/fonts/PatrickHand-Regular.ttf \
   ~/Projects/dotfiles/claude-plugins/collage-studio/runtime/fonts/OFL-PatrickHand.txt lesson-videos/fonts/
curl -fsSL -o lesson-videos/fonts/Nunito.ttf "https://github.com/google/fonts/raw/main/ofl/nunito/Nunito%5Bwght%5D.ttf"
curl -fsSL -o lesson-videos/fonts/OFL-Nunito.txt "https://github.com/google/fonts/raw/main/ofl/nunito/OFL.txt"
file lesson-videos/fonts/Nunito.ttf
```
Expected: `TrueType Font data`.

Edit `lesson-videos/engine/engine.js`:
1. `const FONT = '"Avenir Next", "Helvetica Neue", Arial, sans-serif';` → `const FONT = '"Avenir Next", "Nunito", "Helvetica Neue", Arial, sans-serif';`
2. `"Apple Color Emoji", "Noto Color Emoji", sans-serif` → `"Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif`
3. `` document.fonts.load(`700 40px "Patrick Hand"`).catch(() => {}) `` → `` Promise.all([`700 40px "Patrick Hand"`, `600 40px "Nunito"`, `800 40px "Nunito"`].map(f => document.fonts.load(f))).catch(() => {}) ``
4. First comment line: `// Study-video engine` stays; change `timing.js (window.TIMING, from narrate.py)` if present to `timing.js (window.TIMING, from lv/narrate.py)`.

Run: `grep -n -E 'Nunito|Segoe' lesson-videos/engine/engine.js` → three matching lines.

- [ ] **Step 2: Add the browser fixture to `tests/conftest.py`**

Append:
```python
@pytest.fixture(scope="session")
def browser_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Chromium not installed for this environment ({e}); run `uv run python -m playwright install chromium`")
    return True


HELLO_JS = "scene('hello', (g, t, s) => Engine.titleCard(g, t, s, { kicker: 'Test', title: 'Héllo *world*', emojis: ['🌊'] }), { bug: false, sfx: [[0.3, 'pop0', -12]] });\n"
```

- [ ] **Step 3: Write the failing tests**

`tests/test_render.py`:
```python
import pytest

from conftest import HELLO_JS
from lv import narrate, page, render, sfx, tools
from lv.util import UserError, read_text


def test_output_path_layout(make_chapter):
    ch = make_chapter([{"id": "a", "min": 1}], out="Entry 5/6: Keys.mp4")
    assert page.output_dir(ch) == ch.parent.parent
    assert page.output_path(ch, {"out": "Entry 5/6: Keys.mp4"}).name == "Entry 5-6- Keys.mp4"


def test_stills_and_render(make_chapter, fake_speak, browser_ok):
    sfx.build()
    ch = make_chapter([{"id": "hello", "say": "Hello there, students.", "min": 2}], HELLO_JS)
    narrate.narrate(ch, speak_fn=fake_speak)
    sheet = render.stills(ch, [0.5, 1.5])
    assert sheet.exists() and len(list((ch / "build/stills").glob("t*.jpg"))) == 2
    out = render.render(ch, workers=2)
    assert out == ch.parent.parent / "Chapter 1 - Test.mp4"
    assert abs(tools.duration(out) - narrate.read_timing(ch)["duration"]) < 0.2
    assert {"video", "audio"} <= tools.streams(out)
    assert read_text(out.with_suffix(".vtt")).startswith("WEBVTT")


def test_render_reports_page_error(make_chapter, fake_speak, browser_ok):
    ch = make_chapter([{"id": "hello", "min": 1}], "throw new Error('boom in scenes');\n")
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.stills(ch, [0.5])
    assert "boom in scenes" in str(e.value)


def test_render_reports_missing_asset(make_chapter, fake_speak, browser_ok):
    js = "Engine.assets({ pic: 'assets/nope.jpg' });\n" + HELLO_JS
    ch = make_chapter([{"id": "hello", "min": 1}], js)
    narrate.narrate(ch, speak_fn=fake_speak)
    with pytest.raises(UserError) as e:
        render.render(ch, workers=1)
    assert "assets/nope.jpg" in str(e.value)


def test_render_needs_narration_first(make_chapter):
    ch = make_chapter([{"id": "hello", "min": 1}], HELLO_JS)
    with pytest.raises(UserError) as e:
        render.render(ch)
    assert "narrate" in str(e.value)
```

`tests/test_mix.py`:
```python
from lv import mix, narrate, sfx, tools
from lv.util import write_json


def test_mix_groups_sfx_and_skips_unknown(make_chapter, fake_speak, capsys):
    sfx.build()
    ch = make_chapter([{"id": "a", "min": 3}])
    T = narrate.narrate(ch, speak_fn=fake_speak)
    write_json(ch / "build/sfx.json", [{"t": 0.5, "name": "pop0", "gain": -12}, {"t": 1.0, "name": "pop0"},
                                       {"t": 1.5, "name": "sparkle1"}, {"t": 2.0, "name": "k_question_001"}])
    out = mix.mix_audio(ch, T, {"music": "../music/missing.mp3"})
    assert abs(tools.duration(out) - 3) < 0.2
    said = capsys.readouterr().out
    assert "k_question_001" in said and "missing.mp3" in said
```

- [ ] **Step 4: Run to verify they fail**

Run: `uv run pytest tests/test_render.py tests/test_mix.py -q` → FAIL (`ImportError`).

- [ ] **Step 5: Implement `page.py`, `mix.py`, `render.py`**

`lv/page.py`:
```python
"""Chapter page files (index.html, engine copy, fonts) and where the finished video goes."""
from __future__ import annotations

import shutil
from pathlib import Path

from . import config
from .util import safe_name, write_text

INDEX = """<!doctype html><html><head><meta charset="utf-8"><title>lesson video</title>
<style>@font-face{font-family:"Patrick Hand";src:url(fonts/PatrickHand-Regular.ttf)}
@font-face{font-family:"Nunito";src:url(fonts/Nunito.ttf);font-weight:200 1000}
html,body{margin:0;background:#000}canvas{width:100vw;max-width:1920px;display:block;margin:auto}</style>
</head><body><canvas id="c" width="1920" height="1080"></canvas>
<script src="build/timing.js"></script><script src="build/engine.js"></script><script src="scenes.js"></script></body></html>
"""


def ensure_page(ch: Path) -> None:
    (ch / "build").mkdir(parents=True, exist_ok=True)
    (ch / "fonts").mkdir(exist_ok=True)
    for f in config.FONT_FILES:
        if not (ch / "fonts" / f).exists():
            shutil.copy(config.FONTS_DIR / f, ch / "fonts" / f)
    shutil.copy(config.ENGINE_JS, ch / "build" / "engine.js")
    write_text(ch / "index.html", INDEX)


def output_dir(ch: Path) -> Path:
    """<deck>/lesson-videos/ for chapters in _work/, else the chapter's own out/ folder."""
    return ch.parent.parent if ch.parent.name == "_work" else ch / "out"


def output_path(ch: Path, spec: dict, out_dir: Path | None = None) -> Path:
    name = spec.get("out") or f"{spec.get('title') or ch.name}.mp4"
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    return (out_dir or output_dir(ch)) / safe_name(name)
```

`lv/mix.py`:
```python
"""Final audio: narration + ducked music bed + sound effects, loudness-normalized."""
from __future__ import annotations

from pathlib import Path

from . import sfx, tools
from .util import read_json, run


def mix_audio(ch: Path, T: dict, spec: dict) -> Path:
    b = ch / "build"
    total = T["duration"]
    events = read_json(b / "sfx.json") if (b / "sfx.json").exists() else []
    ins = ["-i", str(b / "narration.mp3")]
    flt = ["[0:a]aformat=channel_layouts=stereo,asplit=2[nar][key]"]
    mixes = ["[nar]"]
    idx = 1
    music = spec.get("music")
    mp = (ch / music).resolve() if music else None
    if mp and not mp.exists():
        print(f"note: music file {music} not found; mixing without music")
        mp = None
    if mp:
        ins += ["-stream_loop", "-1", "-i", str(mp)]
        flt.append(f"[{idx}:a]aformat=channel_layouts=stereo,volume={spec.get('music_db', -24)}dB,atrim=0:{total},"
                   f"afade=t=in:d=2,afade=t=out:st={max(0, total - 3)}:d=3[bed]")
        flt.append("[bed][key]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=400[duck]")
        mixes.append("[duck]")
        idx += 1
    else:
        flt[0] = "[0:a]aformat=channel_layouts=stereo[nar]"
    groups: dict[str, list[dict]] = {}
    for e in events:
        groups.setdefault(e["name"], []).append(e)
    missing = []
    for name, es in groups.items():
        f = sfx.sfx_dir() / f"{name}.wav"
        if not f.exists():
            missing.append(name)
            continue
        ins += ["-i", str(f)]
        labels = [f"s{idx}x{k}" for k in range(len(es))]
        flt.append(f"[{idx}:a]aformat=channel_layouts=stereo:sample_rates=44100,asplit={len(es)}" + "".join(f"[{l}i]" for l in labels))
        for l, e in zip(labels, es):
            ms = max(0, int(e["t"] * 1000))
            flt.append(f"[{l}i]volume={e.get('gain', -8)}dB,adelay={ms}|{ms}[{l}]")
            mixes.append(f"[{l}]")
        idx += 1
    if missing:
        print("note: unknown sound effects skipped: " + ", ".join(sorted(missing)))
    flt.append("".join(mixes) + f"amix=inputs={len(mixes)}:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    out = b / "mix.m4a"
    run(tools.ffmpeg(), "-v", "error", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[out]", "-t", total,
        "-ar", 44100, "-c:a", "aac", "-b:a", "192k", out)
    return out
```

`lv/render.py`:
```python
"""Serve a chapter folder, seek the page frame by frame in headless Chromium, pipe JPEGs into ffmpeg."""
from __future__ import annotations

import base64
import functools
import http.server
import math
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from . import captions, config, mix, tools
from .narrate import read_timing
from .page import ensure_page, output_path
from .util import UserError, read_json, run, write_json, write_text

GRAB = """async ([t, q]) => {
  window.__render(t);
  if (Engine.pending) { await Engine.waitLoads(); window.__render(t); }
  return document.getElementById('c').toDataURL('image/jpeg', q).split(',')[1];
}"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".html": "text/html", ".ttf": "font/ttf", ".jpg": "image/jpeg",
                      ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".mp3": "audio/mpeg",
                      ".json": "application/json", ".svg": "image/svg+xml"}

    def log_message(self, *args):
        pass


@contextmanager
def serve(root: Path):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


@contextmanager
def page_for(ch: Path):
    from playwright.sync_api import sync_playwright
    logs: list[str] = []
    with serve(ch) as port, sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--use-gl=angle", "--enable-gpu-rasterization", "--ignore-gpu-blocklist"])
        except Exception as e:  # noqa: BLE001
            raise UserError(f"The Chromium renderer is missing or won't start ({str(e).splitlines()[0]}). Run `doctor`.") from None
        try:
            pg = browser.new_page(viewport={"width": config.W, "height": config.H}, device_scale_factor=1)
            pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            pg.on("pageerror", lambda e: logs.append(f"PAGEERROR: {e}"))
            pg.goto(f"http://127.0.0.1:{port}/index.html?export=1")
            try:
                pg.wait_for_function("window.__ready === true", timeout=90_000)
            except Exception:  # noqa: BLE001
                raise UserError("The chapter page never finished loading:\n" + "\n".join(logs[:20])) from None
            yield pg, logs
        finally:
            browser.close()


def fail_on_errors(logs: list[str]) -> None:
    bad = [l for l in logs if l.startswith("PAGEERROR") or "asset failed" in l]
    if bad:
        raise UserError("The chapter page has errors; fix scenes.js or the asset paths:\n" + "\n".join(bad[:20]))


def grab(pg, t: float, q: float) -> bytes:
    try:
        return base64.b64decode(pg.evaluate(GRAB, [t, q]))
    except Exception as e:  # noqa: BLE001
        raise UserError(f"Drawing the frame at {t:.2f}s failed: {str(e).splitlines()[0]}") from None


def events(ch: Path) -> list[dict]:
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        return pg.evaluate("window.__sfx()")


def stills(ch: Path, times: list[float], cols: int = 3) -> Path:
    from PIL import Image, ImageDraw
    read_timing(ch)
    ensure_page(ch)
    out = ch / "build" / "stills"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        files = []
        for t in times:
            f = out / f"t{t:07.2f}.jpg"
            f.write_bytes(grab(pg, t, 0.9))
            files.append(f)
        fail_on_errors(logs)
        warnings = [l for l in logs if l.startswith("warning")]
    tw, th = 640, 360
    sheet = Image.new("RGB", (cols * tw, math.ceil(len(files) / cols) * th), "white")
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        with Image.open(f) as im:
            sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        d.text(((i % cols) * tw + 8, (i // cols) * th + 8), f.stem, fill="yellow")
    p = ch / "build" / "stills.jpg"
    sheet.save(p, quality=85)
    for w in warnings[:20]:
        print(w)
    return p


def video_part(ch: Path, out: Path, fps: int, f0: int, f1: int) -> None:
    with page_for(ch) as (pg, logs):
        fail_on_errors(logs)
        ff = subprocess.Popen([tools.ffmpeg(), "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
                               "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                               "-r", str(fps), str(out)], stdin=subprocess.PIPE)
        try:
            for i in range(f0, f1):
                ff.stdin.write(grab(pg, i / fps, 0.94))
                if (i - f0) % 600 == 0:
                    print(f"  [{out.name}] frame {i - f0}/{f1 - f0}", file=sys.stderr, flush=True)
        finally:
            ff.stdin.close()
            code = ff.wait()
        fail_on_errors(logs)
    if code:
        raise UserError(f"ffmpeg failed while encoding {out.name} (exit {code}).")


def default_workers() -> int:
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def render(ch: Path, workers: int | None = None, fps: int = config.FPS, out_dir: Path | None = None) -> Path:
    spec = read_json(ch / "script.json")
    T = read_timing(ch)
    ensure_page(ch)
    b = ch / "build"
    write_json(b / "sfx.json", events(ch))
    n = round(T["duration"] * fps)
    workers = workers or default_workers()
    seg = math.ceil(n / workers)
    parts, procs = [], []
    for w in range(workers):
        f0, f1 = w * seg, min(n, (w + 1) * seg)
        if f0 >= f1:
            continue
        p = b / f"part{w}.mp4"
        parts.append(p)
        procs.append(subprocess.Popen([sys.executable, str(config.ENTRY), "_part", str(ch), str(p), str(fps), str(f0), str(f1)]))
    codes = [p.wait() for p in procs]
    if any(codes):
        raise UserError(f"Rendering failed in {sum(1 for c in codes if c)} of {len(codes)} worker(s); see the messages above.")
    lst = write_text(b / "parts.txt", "".join(f"file '{p.name}'\n" for p in parts))
    run(tools.ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", b / "video.mp4")
    audio = mix.mix_audio(ch, T, spec)
    out = output_path(ch, spec, out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(tools.ffmpeg(), "-v", "error", "-y", "-i", b / "video.mp4", "-i", audio, "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v", "-map", "1:a", "-shortest", "-movflags", "+faststart", out)
    write_text(out.with_suffix(".vtt"), captions.vtt(T))
    for p in parts:
        p.unlink(missing_ok=True)
    print(f"wrote {out} ({tools.duration(out):.1f}s)")
    return out
```

Note: `test_render_reports_missing_asset` relies on `page_for` failing before workers start. `render()` calls `events(ch)` first, which runs `fail_on_errors`; the error text includes `asset failed: assets/nope.jpg`.

- [ ] **Step 6: Wire `narrate`, `stills`, `render`, `_part` into `cli.py`**

In `build_parser`, after the `keys` parser:
```python
    n = sub.add_parser("narrate", help="record narration for a chapter (cached; only changed scenes cost credits)")
    n.add_argument("chapter", type=Path)
    s = sub.add_parser("stills", help="contact sheet of frames at the given seconds")
    s.add_argument("chapter", type=Path)
    s.add_argument("times", type=float, nargs="+")
    r = sub.add_parser("render", help="render the finished MP4 and captions")
    r.add_argument("chapter", type=Path)
    r.add_argument("--workers", type=int)
    r.add_argument("--fps", type=int, default=30)
    r.add_argument("--out", type=Path)
    pt = sub.add_parser("_part")
    for a in ("chapter", "out"):
        pt.add_argument(a, type=Path)
    for a in ("fps", "f0", "f1"):
        pt.add_argument(a, type=int)
```
Add `from pathlib import Path` to the imports. In `dispatch`, before the final `raise`:
```python
    from . import narrate, render
    if args.cmd == "narrate":
        T = narrate.narrate(args.chapter.resolve())
        print(f"narration {T['duration']:.1f}s, {len(T['scenes'])} scenes")
        for s in T["scenes"]:
            print(f"  {s['id']:<16} start {s['start']:7.2f}  dur {s['dur']:6.2f}")
        return 0
    if args.cmd == "stills":
        print(render.stills(args.chapter.resolve(), args.times))
        return 0
    if args.cmd == "render":
        render.render(args.chapter.resolve(), args.workers, args.fps, args.out.resolve() if args.out else None)
        return 0
    if args.cmd == "_part":
        render.video_part(args.chapter, args.out, args.fps, args.f0, args.f1)
        return 0
```

- [ ] **Step 7: Install the test-env browser and run the tests**

Run: `uv run python -m playwright install chromium && uv run pytest tests/test_render.py tests/test_mix.py -q`
Expected: all pass (render test takes ~15 s).

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: engine with cross-platform fonts, Playwright renderer, audio mix

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 7: Deck ingest (PPTX and PDF)

**Files:**
- Create: `lv/ingest.py`
- Modify: `lv/cli.py` (`ingest`)
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `util.UserError/write_text`.
- Produces: `ingest.ingest(deck: Path, work: Path) -> Path` (returns `work/"deck"` containing `slides.md`, `media/`, `contact-NN.jpg`, and for PDFs `pages/`), `ingest.contact_sheets(files, out, cols=5, rows=4) -> list[Path]`, `ingest.default_work(deck) -> Path` (= `deck.parent/"lesson-videos"/"_work"`).

- [ ] **Step 1: Write the failing tests**

`tests/test_ingest.py`:
```python
import io

import pytest
from PIL import Image

from lv import ingest
from lv.util import UserError, read_text


def png(color, size=(400, 300)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    b.seek(0)
    return b


def make_pptx(path):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Osmosis – ¿qué es?"
    s1.placeholders[1].text = "Water follows salt 🌊 “always”"
    s1.shapes.add_picture(png("red"), Inches(5), Inches(2))
    s1.notes_slide.notes_text_frame.text = "Ask: which way does water move?"
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Data"
    rows = s2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    rows.cell(0, 0).text, rows.cell(0, 1).text = "Before", "After"
    rows.cell(1, 0).text, rows.cell(1, 1).text = "39 g", "43 g"
    s2.shapes.add_picture(png("red"), Inches(5), Inches(2))      # same image again: deduplicated
    s2.shapes.add_picture(png("blue"), Inches(1), Inches(4))
    prs.save(str(path))


def test_ingest_unicode_text(tmp_path):
    deck = tmp_path / "deck.pptx"
    make_pptx(deck)
    out = ingest.ingest(deck, tmp_path / "work")
    md = read_text(out / "slides.md")
    assert "## Slide 1: Osmosis – ¿qué es?" in md and "🌊 “always”" in md
    assert "Speaker notes: Ask: which way does water move?" in md
    assert "Before | After" in md and "39 g | 43 g" in md
    assert len(list((out / "media").iterdir())) == 2
    assert "Images: s001-1.png" in md and "Images: s001-1.png, s002-2.png" in md
    assert (out / "contact-01.jpg").exists()


def test_ingest_path_with_spaces_and_accents(tmp_path):
    folder = tmp_path / "Unidad 1 – Biología"
    folder.mkdir()
    deck = folder / "Clase 1 – Ósmosis.pptx"
    make_pptx(deck)
    out = ingest.ingest(deck, ingest.default_work(deck))
    assert out == folder / "lesson-videos" / "_work" / "deck" and (out / "slides.md").exists()


def test_ingest_pdf(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Photosynthesis\nProducers make glucose")
    page.insert_image(pymupdf.Rect(72, 120, 272, 270), stream=png("green").getvalue())
    deck = tmp_path / "deck.pdf"
    doc.save(str(deck))
    out = ingest.ingest(deck, tmp_path / "work")
    md = read_text(out / "slides.md")
    assert "## Slide 1: Photosynthesis" in md and "Producers make glucose" in md
    assert (out / "pages" / "p001.png").exists() and len(list((out / "media").iterdir())) == 1


@pytest.mark.parametrize("ext", [".key", ".ppt", ".odp"])
def test_unsupported_formats_explain_export(tmp_path, ext):
    deck = tmp_path / f"deck{ext}"
    deck.write_bytes(b"x")
    with pytest.raises(UserError) as e:
        ingest.ingest(deck, tmp_path / "work")
    assert "PowerPoint (.pptx)" in str(e.value)


def test_contact_sheet_survives_unreadable_image(tmp_path):
    (tmp_path / "a.emf").write_bytes(b"not an image at all")
    Image.new("RGB", (50, 50), "red").save(tmp_path / "b.png")
    sheets = ingest.contact_sheets(sorted(tmp_path.iterdir()), tmp_path)
    assert len(sheets) == 1 and sheets[0].exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ingest.py -q` → FAIL (`ImportError`).

- [ ] **Step 3: Implement `lv/ingest.py`**

```python
"""Read a .pptx or .pdf deck into slides.md, extracted images and labeled contact sheets for Claude to read."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .util import UserError, write_text

EXPORT_HELP = ("export it as PowerPoint (.pptx) first. Keynote: File → Export To → PowerPoint. "
               "Google Slides: File → Download → Microsoft PowerPoint (.pptx). Old .ppt or .odp: open it and Save As .pptx.")


def default_work(deck: Path) -> Path:
    return Path(deck).resolve().parent / "lesson-videos" / "_work"


def ingest(deck: Path, work: Path) -> Path:
    deck = Path(deck)
    ext = deck.suffix.lower()
    if ext in (".key", ".ppt", ".odp", ".gslides"):
        raise UserError(f"{deck.name}: {EXPORT_HELP}")
    if ext not in (".pptx", ".pdf"):
        raise UserError(f"{deck.name}: only .pptx and .pdf decks are supported; {EXPORT_HELP}")
    if not deck.exists():
        raise UserError(f"Can't find {deck}.")
    out = Path(work) / "deck"
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)
    slides = _pptx(deck, media) if ext == ".pptx" else _pdf(deck, out)
    write_text(out / "slides.md", _markdown(deck.name, slides))
    images = sorted(media.iterdir())
    sheets = contact_sheets(images, out)
    print(f"{len(slides)} slides, {len(images)} unique images, {len(sheets)} contact sheet(s) → {out}")
    return out


def _walk(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for sh in shapes:
        try:
            group = sh.shape_type == MSO_SHAPE_TYPE.GROUP
        except Exception:  # noqa: BLE001  shapes python-pptx can't classify
            group = False
        if group:
            yield from _walk(sh.shapes)
        else:
            yield sh


def _image_blob(sh):
    try:
        im = sh.image
    except (AttributeError, ValueError, KeyError):
        return None
    return im.blob, (im.ext or "bin").lower()


def _pptx(deck: Path, media: Path) -> list[dict]:
    from pptx import Presentation
    prs = Presentation(str(deck))
    seen: dict[str, str] = {}
    slides = []
    for n, slide in enumerate(prs.slides, 1):
        title_shape = slide.shapes.title
        title = title_shape.text_frame.text.strip() if title_shape is not None and title_shape.has_text_frame else ""
        texts, images = [], []
        for sh in _walk(slide.shapes):
            if title_shape is not None and sh == title_shape:
                continue
            if sh.has_text_frame and sh.text_frame.text.strip():
                texts.append(sh.text_frame.text.strip())
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    texts.append(" | ".join(c.text.strip() for c in row.cells))
            blob = _image_blob(sh)
            if blob:
                data, ext = blob
                h = hashlib.sha1(data).hexdigest()
                if h not in seen:
                    seen[h] = f"s{n:03d}-{len(images) + 1}.{ext}"
                    (media / seen[h]).write_bytes(data)
                images.append(seen[h])
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        slides.append({"n": n, "title": title, "text": texts, "notes": notes, "images": images})
    return slides


def _pdf(deck: Path, out: Path) -> list[dict]:
    import pymupdf
    doc = pymupdf.open(str(deck))
    media, pages = out / "media", out / "pages"
    pages.mkdir(exist_ok=True)
    seen: dict[str, str] = {}
    slides = []
    for n, page in enumerate(doc, 1):
        lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
        page.get_pixmap(dpi=96).save(str(pages / f"p{n:03d}.png"))
        images = []
        for k, info in enumerate(page.get_images(full=True), 1):
            try:
                im = doc.extract_image(info[0])
            except Exception:  # noqa: BLE001
                continue
            if not im or im.get("width", 0) < 64 or im.get("height", 0) < 64:
                continue
            h = hashlib.sha1(im["image"]).hexdigest()
            if h not in seen:
                seen[h] = f"p{n:03d}-{k}.{im['ext']}"
                (media / seen[h]).write_bytes(im["image"])
            images.append(seen[h])
        slides.append({"n": n, "title": lines[0] if lines else "", "text": lines[1:], "notes": "", "images": images})
    return slides


def _markdown(name: str, slides: list[dict]) -> str:
    out = [f"# {name}", "", f"{len(slides)} slides. Images are in media/; look at contact-*.jpg to see them.", ""]
    for s in slides:
        out += [f"## Slide {s['n']}: {s['title'] or '(no title)'}", ""]
        out += s["text"]
        if s["notes"]:
            out += ["", f"Speaker notes: {s['notes']}"]
        if s["images"]:
            out += ["", "Images: " + ", ".join(s["images"])]
        out.append("")
    return "\n".join(out)


def contact_sheets(files: list[Path], out: Path, cols: int = 5, rows: int = 4) -> list[Path]:
    from PIL import Image, ImageDraw, ImageOps
    tiles = []
    for f in files:
        try:
            with Image.open(f) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                w, h = im.size
                im.thumbnail((300, 225))
                tiles.append((f.name, f"{w}x{h}", im.copy()))
        except Exception:  # noqa: BLE001  EMF/WMF, corrupt files
            tiles.append((f.name, "no preview", None))
    per, sheets = cols * rows, []
    for s in range(math.ceil(len(tiles) / per)):
        sheet = Image.new("RGB", (cols * 320, rows * 270), "white")
        d = ImageDraw.Draw(sheet)
        for i, (name, size, im) in enumerate(tiles[s * per:(s + 1) * per]):
            x, y = (i % cols) * 320 + 10, (i // cols) * 270 + 8
            if im is not None:
                sheet.paste(im, (x + (300 - im.width) // 2, y + (225 - im.height) // 2))
            else:
                d.rectangle([x, y, x + 300, y + 225], outline="gray")
            d.text((x, y + 230), f"{name}  {size}", fill="black")
        p = out / f"contact-{s + 1:02d}.jpg"
        sheet.save(p, quality=85)
        sheets.append(p)
    return sheets
```

- [ ] **Step 4: Add the `ingest` command to `cli.py`**

Parser:
```python
    i = sub.add_parser("ingest", help="read a .pptx/.pdf deck into lesson-videos/_work/deck/")
    i.add_argument("deck", type=Path)
    i.add_argument("--work", type=Path)
```
Dispatch:
```python
    from . import ingest
    if args.cmd == "ingest":
        ingest.ingest(args.deck, args.work or ingest.default_work(args.deck))
        return 0
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_ingest.py -q` → all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: deck ingest for PPTX and PDF with contact sheets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 8: Cost estimate and resume status

**Files:**
- Create: `lv/estimate.py`, `lv/status.py`
- Modify: `lv/cli.py` (`estimate`, `status`)
- Test: `tests/test_estimate_status.py`

**Interfaces:**
- Consumes: `config.*`, `page.output_path`, `util.read_json`.
- Produces: `estimate.chars_in_scripts(work) -> int`, `estimate.plan_chars(chapters, minutes) -> int`, `estimate.gemini_usd(clips, music) -> float`, `estimate.report(chars, clips, music) -> str`; `status.chapters(work) -> list[Path]`, `status.stage(ch) -> str`, `status.report(work) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_estimate_status.py`:
```python
import os
import time

from lv import estimate, status
from lv.util import write_json, write_text


def test_plan_estimate():
    assert estimate.plan_chars(5, 5) == 22500
    assert estimate.gemini_usd(2, True) == 0.88
    r = estimate.report(22500, 2, True)
    assert "22,500" in r and "$0.88" in r and "20%" in r


def test_chars_in_scripts(tmp_path):
    write_json(tmp_path / "ch1/script.json", {"scenes": [{"id": "a", "say": "Hello."}, {"id": "b"}]})
    write_json(tmp_path / "ch2/script.json", {"scenes": [{"id": "a", "say": "Hi"}]})
    assert estimate.chars_in_scripts(tmp_path) == 8


def test_status_stages(tmp_path):
    work = tmp_path / "lesson-videos" / "_work"
    ch = work / "ch2"
    write_json(ch / "script.json", {"out": "Chapter 2 - X.mp4", "scenes": []})
    assert status.stage(ch) == "script written: run narrate"
    time.sleep(0.01)
    write_text(ch / "build/timing.js", "window.TIMING = {};")
    assert status.stage(ch) == "narrated: write scenes.js"
    write_text(ch / "scenes.js", "")
    assert status.stage(ch) == "scenes written: check stills, then render"
    time.sleep(0.01)
    write_text(tmp_path / "lesson-videos/Chapter 2 - X.mp4", "x")
    assert status.stage(ch) == "done: Chapter 2 - X.mp4"
    write_json(work / "ch10/script.json", {"scenes": []})
    assert [c.name for c in status.chapters(work)] == ["ch2", "ch10"]
    assert "ch10" in status.report(work)
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_estimate_status.py -q` → FAIL.

- [ ] **Step 3: Implement**

`lv/estimate.py`:
```python
"""Cost estimates shown at the plan gate, before anything is paid for."""
from __future__ import annotations

from pathlib import Path

from . import config
from .util import read_json


def chars_in_scripts(work: Path) -> int:
    return sum(len(sc.get("say", "").strip()) for f in Path(work).glob("*/script.json") for sc in read_json(f).get("scenes", []))


def plan_chars(chapters: int, minutes: float) -> int:
    return int(chapters * minutes * config.CHARS_PER_MINUTE)


def gemini_usd(clips: int, music: bool) -> float:
    return round(clips * config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND + (config.LYRIA_PRICE if music else 0), 2)


def report(chars: int, clips: int, music: bool) -> str:
    clip_usd = config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND
    lines = [
        f"Narration: about {chars:,} ElevenLabs characters (Free plan: 10,000 a month; Starter: 30,000 a month). "
        "Allow about 20% extra for re-recorded scenes.",
        f"Gemini: about ${gemini_usd(clips, music):.2f} ({clips} AI clip(s) at ${clip_usd:.2f} each"
        + (f", plus music ${config.LYRIA_PRICE:.2f})." if music else ", no music)."),
    ]
    return "\n".join(lines)
```

`lv/status.py`:
```python
"""Where each chapter stands, from the files on disk, so a run can resume in a later session."""
from __future__ import annotations

import re
from pathlib import Path

from .page import output_path
from .util import read_json


def chapters(work: Path) -> list[Path]:
    found = [f.parent for f in Path(work).glob("*/script.json")]
    return sorted(found, key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)])


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def stage(ch: Path) -> str:
    script, timing, scenes = ch / "script.json", ch / "build" / "timing.js", ch / "scenes.js"
    if not script.exists():
        return "empty"
    if _mtime(timing) < _mtime(script):
        return "script written: run narrate"
    if not scenes.exists():
        return "narrated: write scenes.js"
    out = output_path(ch, read_json(script))
    if _mtime(out) < max(_mtime(scenes), _mtime(timing)):
        return "scenes written: check stills, then render"
    return f"done: {out.name}"


def report(work: Path) -> str:
    rows = [f"{ch.name:<8} {stage(ch)}" for ch in chapters(work)]
    return "\n".join(rows) if rows else "No chapters yet."
```

- [ ] **Step 4: CLI wiring**

Parser:
```python
    e = sub.add_parser("estimate", help="estimated ElevenLabs characters and Gemini dollars")
    e.add_argument("work", type=Path)
    e.add_argument("--chapters", type=int, help="plan stage: number of chapters (else count the written scripts)")
    e.add_argument("--minutes", type=float, default=5)
    e.add_argument("--clips", type=int, default=0)
    e.add_argument("--music", action="store_true")
    st = sub.add_parser("status", help="which chapters are done and what each needs next")
    st.add_argument("work", type=Path)
```
Dispatch:
```python
    from . import estimate, status
    if args.cmd == "estimate":
        chars = estimate.plan_chars(args.chapters, args.minutes) if args.chapters else estimate.chars_in_scripts(args.work)
        print(estimate.report(chars, args.clips, args.music))
        return 0
    if args.cmd == "status":
        print(status.report(args.work.resolve()))
        return 0
```

- [ ] **Step 5: Run tests** — `uv run pytest tests/test_estimate_status.py -q` → pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: cost estimate and resumable chapter status

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 9: Music (Lyria) and clips (Veo)

**Files:**
- Create: `lv/music.py`, `lv/clips.py`
- Modify: `lv/cli.py` (`music`, `clip`, `frames`), possibly `lv/config.py` (`VEO_MODEL`)
- Test: `tests/test_music_clips.py`

**Interfaces:**
- Consumes: `keys.get`, `net.request/ApiError/gemini_error`, `tools.ffmpeg`, `config.*`, `util.*`.
- Produces: `music.make_bed(work, prompt, request=None) -> Path` (`work/music/bed.mp3`); `clips.prep(image, frac=0.5) -> bytes` (1280×720 PNG), `clips.result_uri(op) -> str`, `clips.veo(image_png, prompt, request=None, sleep=time.sleep, max_polls=60) -> bytes`, `clips.make_clip(image, prompt, name, work, frac=0.5, request=None, sleep=time.sleep) -> Path` (`work/clips/<name>.mp4` + `<name>-strip.jpg`), `clips.frames(mp4, dest, max_frames=None) -> int`.

- [ ] **Step 1: Confirm the Veo Lite model ID with Daniel's key (never printed)**

```bash
GEMINI_API_KEY="$(grep '^GEMINI_API_KEY=' ~/Projects/dotfiles/secrets/gemini/.env | cut -d= -f2- | tr -d '\"')" \
uv run python -c "
import os, json, urllib.request
r = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000', headers={'x-goog-api-key': os.environ['GEMINI_API_KEY']})
names = [m['name'] for m in json.load(urllib.request.urlopen(r))['models']]
print([n for n in names if 'veo' in n or 'lyria' in n])"
```
Expected: the list includes a Veo 3.1 Lite name. If it is not `models/veo-3.1-lite-generate-preview`, set `VEO_MODEL` in `lv/config.py` to the listed name (without `models/`). If no Lite model is listed, use `veo-3.1-fast-generate-preview` and set `VEO_PRICE_PER_SECOND = 0.10`.

- [ ] **Step 2: Write the failing tests**

`tests/test_music_clips.py`:
```python
import base64
import subprocess

import pytest
from PIL import Image

from lv import clips, music, net, tools
from lv.util import UserError

KEY = "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)


def test_make_bed_writes_mp3(tmp_path):
    def fake(url, data=None, headers=None, timeout=None, **kw):
        assert url.endswith("/interactions") and data["model"] == "lyria-3.5"
        return {"steps": [{"content": [{"type": "audio", "data": base64.b64encode(b"ID3fake").decode()}]}]}
    out = music.make_bed(tmp_path, "calm lo-fi study music", request=fake)
    assert out == tmp_path / "music/bed.mp3" and out.read_bytes() == b"ID3fake"


def test_make_bed_billing_error(tmp_path):
    def fake(url, **kw):
        raise net.ApiError(429, "RESOURCE_EXHAUSTED: billing", url)
    with pytest.raises(UserError) as e:
        music.make_bed(tmp_path, "x", request=fake)
    assert "billing" in str(e.value) and KEY not in str(e.value)


def test_prep_crops_to_720p(tmp_path):
    Image.new("RGB", (1000, 1000), "red").save(tmp_path / "a.png")
    import io
    with Image.open(io.BytesIO(clips.prep(tmp_path / "a.png"))) as im:
        assert im.size == (1280, 720)


def test_veo_polls_then_downloads(tmp_path):
    Image.new("RGB", (1600, 900), "blue").save(tmp_path / "a.png")
    calls = []
    def fake(url, data=None, headers=None, timeout=None, raw=False, **kw):
        calls.append(url)
        if url.endswith(":predictLongRunning"):
            assert data["parameters"]["resolution"] == "720p"
            return {"name": "operations/abc"}
        if url.endswith("operations/abc"):
            return {"done": len(calls) > 2, "response": {"generateVideoResponse": {"generatedSamples": [{"video": {"uri": "https://dl.test/v.mp4"}}]}}}
        assert raw
        return b"MP4DATA"
    out = clips.make_clip(tmp_path / "a.png", "kelp swaying", "kelp", tmp_path, request=fake, sleep=lambda s: None, strip=False)
    assert out.read_bytes() == b"MP4DATA" and calls[-1] == "https://dl.test/v.mp4"


def test_veo_safety_filter_message():
    op = {"done": True, "response": {"generateVideoResponse": {"raiMediaFilteredCount": 1, "raiMediaFilteredReasons": ["person"]}}}
    with pytest.raises(UserError) as e:
        clips.result_uri(op)
    assert "safety filter" in str(e.value)


def test_frames(tmp_path):
    mp4 = tmp_path / "c.mp4"
    subprocess.run([tools.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24", "-t", "1",
                    "-pix_fmt", "yuv420p", str(mp4)], check=True)
    assert clips.frames(mp4, tmp_path / "clip_c") == 24
    assert clips.frames(mp4, tmp_path / "clip_c", max_frames=10) == 10
    assert (tmp_path / "clip_c/0001.jpg").exists()
```

- [ ] **Step 3: Run to verify they fail** — `uv run pytest tests/test_music_clips.py -q` → FAIL.

- [ ] **Step 4: Implement**

`lv/music.py`:
```python
"""One Lyria track used as a looped, ducked music bed under the narration."""
from __future__ import annotations

import base64
from pathlib import Path

from . import config, keys, net
from .util import UserError, write_text


def make_bed(work: Path, prompt: str, request=None) -> Path:
    request = request or net.request
    key = keys.get("GEMINI_API_KEY")
    try:
        d = request(f"{config.GEMINI_ROOT}/interactions",
                    data={"model": config.LYRIA_MODEL, "input": prompt, "response_format": {"type": "audio"}},
                    headers={"x-goog-api-key": key}, timeout=300)
    except net.ApiError as e:
        raise net.gemini_error(e, "music") from None
    for step in d.get("steps") or []:
        for block in step.get("content") or []:
            if block.get("type") == "audio" and block.get("data"):
                out = Path(work) / "music" / "bed.mp3"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(base64.b64decode(block["data"]))
                write_text(out.with_suffix(".txt"), prompt)
                return out
    raise UserError(f"Lyria returned no audio (status {d.get('status')!r}); try a simpler prompt.")
```

`lv/clips.py`:
```python
"""Veo image-to-video clips from deck photos, and their JPEG frames for the engine's clip()."""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path

from . import config, keys, net, tools
from .util import UserError, run, write_text


def prep(image: Path, frac: float = 0.5) -> bytes:
    """Crop to 16:9 (frac picks the vertical position, 0 = top) and resize to 1280x720 PNG."""
    from PIL import Image, ImageOps
    with Image.open(image) as src:
        im = ImageOps.exif_transpose(src).convert("RGB")
    w, h = im.size
    th = round(w * 9 / 16)
    if th <= h:
        top = int((h - th) * frac)
        im = im.crop((0, top, w, top + th))
    else:
        tw = round(h * 16 / 9)
        left = (w - tw) // 2
        im = im.crop((left, 0, left + tw, h))
    b = io.BytesIO()
    im.resize((1280, 720), Image.LANCZOS).save(b, "PNG")
    return b.getvalue()


def result_uri(op: dict) -> str:
    if op.get("error"):
        raise UserError(f"Veo failed: {op['error'].get('message', 'no reason given')}")
    resp = (op.get("response") or {}).get("generateVideoResponse") or {}
    samples = resp.get("generatedSamples") or []
    if not samples:
        if resp.get("raiMediaFilteredCount") or resp.get("raiMediaFilteredReasons"):
            reasons = "; ".join(resp.get("raiMediaFilteredReasons") or []) or "no reason given"
            raise UserError(f"Veo's safety filter dropped the clip ({reasons}). Try another photo or prompt (photos of children are often refused).")
        raise UserError("Veo finished without a video and without a reason; try again.")
    uri = (samples[0].get("video") or {}).get("uri")
    if not uri:
        raise UserError("Veo finished without a video link; try again.")
    return uri


def veo(image_png: bytes, prompt: str, request=None, sleep=time.sleep, max_polls: int = 60) -> bytes:
    request = request or net.request
    h = {"x-goog-api-key": keys.get("GEMINI_API_KEY")}
    payload = {"instances": [{"prompt": prompt, "image": {"bytesBase64Encoded": base64.b64encode(image_png).decode("ascii"),
                                                          "mimeType": "image/png"}}],
               "parameters": {"aspectRatio": "16:9", "durationSeconds": config.VEO_SECONDS, "resolution": "720p",
                              "personGeneration": "allow_adult"}}
    try:
        op = request(f"{config.GEMINI_ROOT}/models/{config.VEO_MODEL}:predictLongRunning", data=payload, headers=h, timeout=60)
        name = op.get("name") or ""
        if not name:
            raise UserError("Veo didn't start the job; try again.")
        for _ in range(max_polls):
            sleep(10)
            op = request(f"{config.GEMINI_ROOT}/{name}", headers=h, timeout=60)
            if op.get("done"):
                return request(result_uri(op), headers=h, timeout=300, raw=True)
    except net.ApiError as e:
        raise net.gemini_error(e, "AI clip") from None
    raise UserError(f"Veo was still working after {max_polls * 10 // 60} minutes; try again later.")


def make_clip(image: Path, prompt: str, name: str, work: Path, frac: float = 0.5, request=None, sleep=time.sleep,
              strip: bool = True) -> Path:
    out = Path(work) / "clips" / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(veo(prep(image, frac), prompt, request=request, sleep=sleep))
    write_text(out.with_suffix(".txt"), f"source: {Path(image).name}\nprompt: {prompt}\n")
    if strip:  # one frame per second, side by side, to check the subject doesn't drift
        run(tools.ffmpeg(), "-v", "error", "-y", "-i", out, "-vf", "fps=1,scale=320:-2,tile=8x1", "-frames:v", "1",
            out.with_name(f"{name}-strip.jpg"))
    print(f"clip {out} (~${config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND:.2f})")
    return out


def frames(mp4: Path, dest: Path, max_frames: int | None = None) -> int:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.jpg"):
        old.unlink()
    args = [tools.ffmpeg(), "-v", "error", "-y", "-i", mp4, "-vf", "fps=24,scale=1280:-2", "-q:v", "3"]
    if max_frames:
        args += ["-frames:v", max_frames]
    run(*args, dest / "%04d.jpg")
    return len(list(dest.glob("*.jpg")))
```

- [ ] **Step 5: CLI wiring**

Parser:
```python
    m = sub.add_parser("music", help="one Lyria music bed (~$0.08) into _work/music/bed.mp3")
    m.add_argument("work", type=Path)
    m.add_argument("--prompt", required=True)
    c = sub.add_parser("clip", help="one Veo clip (~$0.40) from a photo into _work/clips/")
    c.add_argument("image", type=Path)
    c.add_argument("--work", type=Path, required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--prompt", required=True)
    c.add_argument("--frac", type=float, default=0.5)
    f = sub.add_parser("frames", help="turn a clip into JPEG frames for clip() in scenes.js")
    f.add_argument("clip", type=Path)
    f.add_argument("dest", type=Path)
    f.add_argument("--max", type=int)
```
Dispatch:
```python
    from . import clips, music
    if args.cmd == "music":
        print(music.make_bed(args.work.resolve(), args.prompt))
        return 0
    if args.cmd == "clip":
        clips.make_clip(args.image, args.prompt, args.name, args.work.resolve(), args.frac)
        return 0
    if args.cmd == "frames":
        print(f"{clips.frames(args.clip, args.dest, args.max)} frames → {args.dest}")
        return 0
```

- [ ] **Step 6: Run tests** — `uv run pytest tests/test_music_clips.py -q` → pass.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: Lyria music bed and Veo Lite clips with frame extraction

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 10: Doctor

**Files:**
- Create: `lv/doctor.py`
- Modify: `lv/cli.py` (`doctor`)
- Test: `tests/test_doctor.py`

**Interfaces:**
- Consumes: `tools.*`, `sfx.build/NAMES`, `keys.check`, `narrate.narrate`, `render.render`, `config.*`.
- Produces: `doctor.TEST_SCENES: str`, `doctor.test_render() -> float`, `doctor.run_doctor(no_keys=False, install=True) -> int`.

- [ ] **Step 1: Write the failing test**

`tests/test_doctor.py`:
```python
from lv import doctor


def test_doctor_without_keys(browser_ok, capsys):
    assert doctor.run_doctor(no_keys=True, install=False) == 0
    out = capsys.readouterr().out
    for item in ("ffmpeg", "Chromium renderer", "Fonts", "Sound effects", "Test video"):
        assert f"✓ {item}" in out


def test_doctor_reports_missing_key(browser_ok, capsys):
    assert doctor.run_doctor(no_keys=False, install=False) == 1
    assert "✗ ElevenLabs key" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_doctor.py -q` → FAIL.

- [ ] **Step 3: Implement `lv/doctor.py`**

```python
"""Install and check everything, then prove it works with a 3-second test video."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from . import config, keys, narrate, render, sfx, tools
from .util import UserError, write_json, write_text

TEST_SCENES = ("scene('hello', (g, t, s) => Engine.titleCard(g, t, s, { kicker: 'lesson-videos', title: 'It *works*!', "
               "sub: 'Test render', emojis: ['🎬', '✅'] }), { bug: false, sfx: [[0.5, 'sparkle0', -12]] });\n")


def test_render() -> float:
    with tempfile.TemporaryDirectory() as d:
        ch = Path(d) / "doctor test" / "ch1"
        write_json(ch / "script.json", {"chapter": "TEST", "title": "Doctor test", "out": "doctor-test.mp4",
                                        "scenes": [{"id": "hello", "min": 3}]})
        write_text(ch / "scenes.js", TEST_SCENES)
        narrate.narrate(ch)
        out = render.render(ch, workers=1, out_dir=Path(d))
        dur, kinds = tools.duration(out), tools.streams(out)
        if abs(dur - 3) > 0.3 or not {"video", "audio"} <= kinds:
            raise UserError(f"the test video came out wrong ({dur:.1f}s, streams {sorted(kinds)})")
        return dur


def run_doctor(no_keys: bool = False, install: bool = True) -> int:
    rows: list[tuple[str, str, str]] = []
    ok = lambda name, msg: rows.append(("✓", name, msg))      # noqa: E731
    bad = lambda name, msg: rows.append(("✗", name, msg))     # noqa: E731
    ok("Python", sys.version.split()[0])
    try:
        ok("ffmpeg", tools.ffmpeg())
        if not tools.has_x264():
            bad("ffmpeg H.264", "this ffmpeg can't write H.264 video; install the full ffmpeg build")
    except UserError as e:
        bad("ffmpeg", str(e))
    try:
        if install:
            tools.install_chromium()
        ok("Chromium renderer", "ready")
    except UserError as e:
        bad("Chromium renderer", str(e))
    missing = [f for f in config.FONT_FILES if not (config.FONTS_DIR / f).exists()]
    (bad if missing else ok)("Fonts", "missing: " + ", ".join(missing) if missing else "bundled")
    try:
        ok("Sound effects", f"{len(sfx.NAMES)} in {sfx.build()}")
    except Exception as e:  # noqa: BLE001
        bad("Sound effects", str(e))
    if not any(r[0] == "✗" for r in rows):
        try:
            ok("Test video", f"{test_render():.1f}s rendered")
        except UserError as e:
            bad("Test video", str(e))
    if not no_keys:
        for name, good, msg in keys.check():
            (ok if good else bad)(f"{name} key", msg)
    for mark, name, msg in rows:
        print(f"{mark} {name}: {msg}")
    return 0 if all(r[0] == "✓" for r in rows) else 1
```

- [ ] **Step 4: CLI wiring**

Parser:
```python
    d = sub.add_parser("doctor", help="install and check everything, then render a 3-second test video")
    d.add_argument("--no-keys", action="store_true", help="skip the API key checks (for CI)")
```
Dispatch:
```python
    from . import doctor
    if args.cmd == "doctor":
        return doctor.run_doctor(args.no_keys)
```

- [ ] **Step 5: Run tests and the real command**

Run: `uv run pytest tests/test_doctor.py -q && uv run lesson-videos/scripts/lesson-videos.py doctor --no-keys`
Expected: tests pass; the command prints six ✓ lines and exits 0.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: doctor command with a 3-second test render

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 11: Parity check against the original Entry 1 (local only, nothing committed)

**Files:** none in the repo. Work in the scratchpad.

**Interfaces:**
- Consumes: the full CLI.

- [ ] **Step 1: Copy Entry 1 and its music into the scratchpad**

```bash
SCR=/private/tmp/claude-501/-Users-daniellandi-Projects-ihs-marine-biology/3c471b48-d4e5-4eb7-a95d-2335d30977bf/scratchpad
SRC=~/Projects/ihs/marine-biology/study-kit/videos/_source
rm -rf "$SCR/parity" && mkdir -p "$SCR/parity"
cp -R "$SRC/entry1" "$SCR/parity/entry1" && cp -R "$SRC/music" "$SCR/parity/music"
rm -f "$SCR/parity/entry1/build/timing.js" "$SCR/parity/entry1/build/narration.mp3"
```

- [ ] **Step 2: Narrate from cache only (no key available proves no API call)**

```bash
cd ~/Projects/plugins
env -u ELEVENLABS_API_KEY LESSON_VIDEOS_HOME="$SCR/parity-home" \
  uv run lesson-videos/scripts/lesson-videos.py narrate "$SCR/parity/entry1"
```
Expected: `narration 307.9s, 17 scenes` and no `voiced` lines. A `MissingKey` error means the cache key formula changed: fix `narrate.cache_key`.

- [ ] **Step 3: Render with the new pipeline**

```bash
LESSON_VIDEOS_HOME="$SCR/parity-home" uv run lesson-videos/scripts/lesson-videos.py doctor --no-keys
LESSON_VIDEOS_HOME="$SCR/parity-home" uv run lesson-videos/scripts/lesson-videos.py render "$SCR/parity/entry1" --out "$SCR/parity/out"
```
Expected: `wrote …/Entry 1 - Land vs Sea and the 7 Characteristics of Life.mp4 (307.9s)`. Notes about `k_question_001` being skipped are expected (Kenney sounds were dropped).

- [ ] **Step 4: Compare frames with the original**

```bash
ORIG="$HOME/Projects/ihs/marine-biology/study-kit/videos/Entry 1 - Land vs Sea and the 7 Characteristics of Life.mp4"
NEW="$SCR/parity/out/Entry 1 - Land vs Sea and the 7 Characteristics of Life.mp4"
for t in 5 40 80 120 160 200 240 280 300; do
  ffmpeg -v error -y -ss $t -i "$ORIG" -frames:v 1 "$SCR/parity/o_$t.png"
  ffmpeg -v error -y -ss $t -i "$NEW" -frames:v 1 "$SCR/parity/n_$t.png"
  ffmpeg -v error -i "$SCR/parity/o_$t.png" -i "$SCR/parity/n_$t.png" -lavfi psnr -f null - 2>&1 | grep -o 'average:[0-9.inf]*' | sed "s/^/t=$t /"
done
```
Expected: every `average:` ≥ 30 (dB) or `inf`. Then Read `o_120.png` and `n_120.png` and confirm they look the same. If a frame is below 30 dB, compare the pair visually and find the cause (font fallback, emoji font, missing asset) before continuing.

- [ ] **Step 5: Record the result** in the final report to Daniel (PSNR per timestamp, duration match). Nothing to commit.

---

### Task 12: CLI polish and end-to-end CLI tests

**Files:**
- Modify: `lv/cli.py` (catch `net.ApiError`, ordering)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything in `cli.dispatch`.
- Produces: final `cli.main`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
import io
import subprocess
import sys

from conftest import PLUGIN
from lv import cli, net


def test_keys_check_without_keys(capsys):
    assert cli.main(["keys", "check"]) == 1
    assert "✗ ElevenLabs: missing (required)" in capsys.readouterr().out


def test_unsupported_deck_no_traceback(tmp_path, capsys):
    deck = tmp_path / "deck.key"
    deck.write_bytes(b"x")
    assert cli.main(["ingest", str(deck)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: deck.key: export it as PowerPoint") and "Traceback" not in err


def test_api_error_is_printed_plainly(monkeypatch, capsys):
    def boom(args):
        raise net.ApiError(500, "server sad", "https://api.elevenlabs.io/v1/x")
    monkeypatch.setattr(cli, "dispatch", boom)
    assert cli.main(["keys"]) == 1
    assert "api.elevenlabs.io failed (500)" in capsys.readouterr().err


def test_cli_prints_unicode_on_cp1252(tmp_path):
    env = {"PYTHONIOENCODING": "cp1252", "LESSON_VIDEOS_HOME": str(tmp_path), "PATH": __import__("os").environ["PATH"],
           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts/lesson-videos.py"), "keys", "check"], capture_output=True, env=env)
    assert r.returncode == 1 and "✗".encode("utf-8") in r.stdout
```

- [ ] **Step 2: Run to verify** — `uv run pytest tests/test_cli.py -q`. Expected: `test_api_error_is_printed_plainly` FAILS (ApiError escapes `main`); the others pass.

- [ ] **Step 3: Catch `ApiError` in `main`**

In `cli.main`, add after the `UserError` handler:
```python
    except Exception as e:  # noqa: BLE001
        from . import net
        if isinstance(e, net.ApiError):
            print(f"error: {e}", file=sys.stderr)
            return 1
        raise
```
(Place it before `except KeyboardInterrupt` is irrelevant: `KeyboardInterrupt` is not an `Exception`.)

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: plain error output for API failures; CLI tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 13: Skills, guide, sample chapter, sample deck and teacher README

**Files:**
- Create: `lesson-videos/skills/setup/SKILL.md`, `lesson-videos/skills/make/SKILL.md`, `lesson-videos/skills/make/references/guide.md`, `lesson-videos/skills/make/references/sample/script.json`, `lesson-videos/skills/make/references/sample/scenes.js`, `examples/make_sample_deck.py`, `examples/water-cycle.pptx` (generated), `lesson-videos/README.md`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: CLI commands from Tasks 2–10, exact names: `doctor [--no-keys]`, `keys [open|check]`, `ingest DECK [--work DIR]`, `narrate CH`, `stills CH T…`, `render CH [--workers N] [--out DIR]`, `music WORK --prompt P`, `clip IMAGE --work WORK --name N --prompt P [--frac F]`, `frames CLIP DEST [--max N]`, `estimate WORK [--chapters N --minutes M --clips K --music]`, `status WORK`.

- [ ] **Step 1: Write the failing tests**

`tests/test_skills.py`:
```python
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
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_skills.py -q` → FAIL (files missing).

- [ ] **Step 3: Write `lesson-videos/skills/setup/SKILL.md`**

````markdown
---
name: setup
description: Use once per computer before making lesson videos, or whenever lesson-videos says a tool or key is missing. Installs uv, the renderer and ffmpeg, then walks the teacher through creating ElevenLabs (required) and Gemini (optional) API keys and checks them without ever showing them in chat.
---

# lesson-videos setup

You are helping a teacher who may never have used a terminal. Explain each step in one or two plain sentences, do the technical work yourself, and ask them only to click in their browser or paste into the file you open.

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py"
```

**Never ask for an API key in chat, never read or print `keys.env`.** If the teacher pastes a key into the chat anyway, tell them it's safest to delete that key on the website and create a new one, then continue.

## 1. uv

Check whether `uv` works: run `uv --version`. If that fails, also try `~/.local/bin/uv --version` (Windows: `$HOME\.local\bin\uv.exe --version`); if that works, use that full path in place of `uv` for the rest of this session.

If uv is missing, tell the teacher you're installing uv, a small free tool that downloads everything else (no administrator password needed), then run:
- macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Then use the full path above (the current window won't see uv on its PATH until Claude Code restarts).

## 2. Doctor

Tell the teacher the first run downloads about 300 MB (Python libraries, a headless Chrome for drawing frames, ffmpeg) and can take a few minutes. Run:

```
LV doctor --no-keys
```

Every line should start with ✓. For each ✗, do what the message says. Common ones:
- **Chromium / downloads blocked**: school networks sometimes block downloads. Suggest a home network, or ask IT to allow astral.sh, pypi.org, files.pythonhosted.org, github.com and Playwright's browser downloads (cdn.playwright.dev).
- **ffmpeg can't write H.264**: macOS `brew install ffmpeg`; Windows `winget install Gyan.FFmpeg`; then run doctor again.

## 3. ElevenLabs key (required: the narrator's voice)

Explain the choice in plain words before they sign up:
- **Free plan**: 10,000 characters a month, about one 5-minute video. Free-plan audio is for non-commercial use only and, if a video is published, its title must include "elevenlabs.io". The free plan must use a personal email address.
- **Starter plan**: $6/month for 30,000 characters (about four videos, enough for most units) and a commercial licence. They can cancel after the unit is done.
- One thing to read themselves: ElevenLabs' use policy (elevenlabs.io/use-policy) restricts use by government entities without authorization. A public school may count; a teacher using it personally is their own call. Don't decide for them.

Then open the keys page in their browser (macOS: `open URL`; Windows: `start "" URL`): `https://elevenlabs.io/app/settings/api-keys`. Guide them:
1. Sign up or log in.
2. Click **Create API Key**. Name it `lesson-videos`.
3. Under permissions, turn on **Text to Speech** (access) and **User** (read). Leave the rest off.
4. Optional but recommended: set a **credit quota** (for example 30,000) so the key can never spend more.
5. Click Create and **Copy** the key. It is shown only once.

## 4. Gemini key (optional: music and AI video clips)

Ask whether they want background music and a few short AI-animated clips made from their photos. If not, skip to step 5; videos still work.

If yes, explain: this needs a Google account with billing turned on (Google has no free tier for these), a minimum $5 prepayment, and costs about $0.40 per clip and $0.08 per music track, roughly $2–3 for a whole unit. Use a **personal** Google account: school accounts often have AI Studio turned off.

Open `https://aistudio.google.com/api-keys` and guide them:
1. Sign in, accept the terms.
2. Click **Create API key** (let it create a project if asked) and **copy** the key.
3. Open `https://aistudio.google.com/billing` (or follow the "Set up billing" link) to link a billing account and add the $5 prepayment.
4. Open `https://aistudio.google.com/spend` and set a **monthly spend cap**, for example $10.

## 5. Paste the keys into the keys file

Run:
```
LV keys
```
It opens a small text file in TextEdit (Mac) or Notepad (Windows). Tell the teacher: paste the ElevenLabs key right after `ELEVENLABS_API_KEY=` and, if they made one, the Gemini key after `GEMINI_API_KEY=`, with no spaces, then **save and close** the file. Wait for them to say they've done it.

## 6. Check

```
LV keys check
```
Read the result to them in plain words. ✓ ElevenLabs shows how many characters are left this month. If ElevenLabs says the key can't read the account, send them back to the key's permissions (User → Read). Gemini billing is only verified the first time music or a clip is made, because testing it costs money.

## 7. Done

Summarize: what's ready, what was skipped, and the cost per video (about 5,000–6,000 ElevenLabs characters; Gemini about $0.40 per clip plus $0.08 for music). Tell them the next step: open Claude Code in the folder that holds their slide deck and run `/lesson-videos:make`.
````

- [ ] **Step 4: Write `lesson-videos/skills/make/SKILL.md`**

````markdown
---
name: make
description: Use when a teacher wants narrated study videos made from their slide deck (.pptx or .pdf). Reads the deck, writes a content brief in the teacher's wording, gets a costed plan approved, builds one reference chapter for feedback, then the rest, and saves MP4s with captions next to the deck. Resumes an unfinished run.
---

# Make lesson videos from a slide deck

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py"
```

If `uv` isn't found, or any command says a tool or key is missing, run the `setup` skill first.

Read `${CLAUDE_PLUGIN_ROOT}/skills/make/references/guide.md` before writing any `script.json` or `scenes.js`. The sample chapter in `${CLAUDE_PLUGIN_ROOT}/skills/make/references/sample/` shows every idiom.

**Folders.** For a deck at `<folder>/<deck>.pptx`, everything goes in `<folder>/lesson-videos/`: finished videos at its top level, working files in `_work/` (`deck/`, `brief.md`, `plan.md`, `music/`, `clips/`, `ch1/`, `ch2/`…). Call `<folder>/lesson-videos/_work` **WORK**.

**Ground rules.**
- The teacher's slides are the only source of facts. Never add facts, numbers or examples that aren't in the deck or in files the teacher points you to.
- Nothing that costs money (narration, music, clips) happens before the teacher approves the plan in step 4.
- Nothing is uploaded or published.
- Keep the teacher informed in plain words; they don't need to see commands.

## 0. Resume?

If `WORK` already exists, run `LV status "WORK"` and read `WORK/plan.md`. Tell the teacher where things stand and continue from the first unfinished chapter (skip the steps already done).

## 1. Read the deck

Find the deck in the current folder (ask if there are several). Keynote, Google Slides or old `.ppt` files must be exported to `.pptx` first; `ingest` explains how. Run:

```
LV ingest "<deck path>"
```

Read `WORK/deck/slides.md` in full and look at every `WORK/deck/contact-*.jpg` (and `deck/pages/` for PDFs). Ask whether there are other files to use (worksheets, labs, review sheets); read them too.

## 2. Short interview (one message, sensible defaults offered)

- Grade level of the students.
- Chapters: propose a split from the deck's sections or titles (for example one video per unit/entry/lesson) and ask them to confirm or adjust.
- Length per video: default 4–6 minutes.
- Voice: default Jessica (warm, upbeat young American). They can pick another premade ElevenLabs voice by name.
- Music and AI clips: only if a Gemini key is set (`LV keys check`).

## 3. Content brief

Write `WORK/brief.md`. Per chapter: the essential question if the deck has one; key terms with definitions **in the teacher's own wording**; examples and lab data from the slides; likely test questions; common mistakes worth a "trap" warning. Finish with a section **"Possible issues in the slides"**: contradictions between slides, typos in key terms, definitions worded two ways. Show the teacher that section and ask how to handle each item (follow the slide, follow the correction, or leave it out).

## 4. Plan and approval gate

Write `WORK/plan.md`: for each chapter, the title, the output file name (`Chapter N - <Title>.mp4`), a scene outline (hook, 6–12 content scenes, 3-question quiz, recap), which deck images it uses, and 0–2 photos per unit worth animating as AI clips (only living things or landscapes that benefit from motion; never diagrams with text, never photos of students). Then run:

```
LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music]
```

Show the teacher the outline in brief and the estimate, and **ask for approval**. Do not continue until they say yes. Note the approval and date at the top of `plan.md`.

## 5. Music and clips (only if approved and a Gemini key is set)

- Music: `LV music "WORK" --prompt "<calm, light instrumental study music, no vocals, steady gentle beat>"`. If it fails with a billing message, tell the teacher in one line and continue without music.
- Each clip: copy the source photo path from `WORK/deck/media/`, then `LV clip "<photo>" --work "WORK" --name <short-name> --prompt "<cinematic, realistic, slow camera move, describe the subject and its natural motion, no text>"`. Look at `WORK/clips/<name>-strip.jpg`: if the subject changes into something else partway, note how many seconds are usable and use `--max <seconds × 24>` below.

## 6. Reference chapter (chapter 1), then stop for feedback

Follow the workflow in `guide.md` for chapter 1 in `WORK/ch1/`:
1. Write `script.json` (narration per scene; `"music": "../music/bed.mp3"` only if music exists).
2. `LV narrate "WORK/ch1"`.
3. Copy the images you use from `WORK/deck/media/` into `WORK/ch1/assets/` (downscale to at most 1600 px wide with Pillow); for clips run `LV frames "WORK/clips/<name>.mp4" "WORK/ch1/assets/clip_<name>" [--max N]`.
4. Write `scenes.js`.
5. `LV stills "WORK/ch1" <one time per scene>` and look at `WORK/ch1/build/stills.jpg`. Fix overlaps, text running off cards, things hidden behind captions, empty-looking scenes, and every `cue miss` warning. Repeat until clean (2–3 rounds is normal).
6. `LV render "WORK/ch1"`.
7. Verify: the printed duration matches the narration length; pull 3–4 frames with `ffmpeg -ss <t> -i "<video>" -frames:v 1 <file>.png` and look at them.

Then **stop**. Tell the teacher where the video is (`<folder>/lesson-videos/Chapter 1 - ….mp4`) and ask about tone, pace, reading level, voice and look. Apply their feedback to chapter 1 (re-narrating only changed scenes is cheap) before moving on, and write the agreed style notes at the top of `plan.md` so later chapters (and later sessions) follow them.

## 7. Remaining chapters

Default: one chapter at a time, same steps as 6.1–6.7, checking in briefly after each. If the teacher asks for speed, you may hand chapters to parallel helper agents; give each the paths to `guide.md`, `brief.md`, `plan.md` (with the style notes), its own `WORK/chN/` folder, and the finished `WORK/ch1/` as the reference. Tell the teacher this uses much more of their Claude plan.

Between chapters, `LV status "WORK"` shows what's left. If the session ends, the next `/lesson-videos:make` resumes from step 0.

## 8. Wrap up

Write `<folder>/lesson-videos/README.md`: a table of the videos with their lengths, one line on what each covers, and these notes:
- Narration is an AI voice (ElevenLabs); music and clips, if any, are AI-generated (Google).
- If the deck contains photos or diagrams from other sources, check their licences before posting the videos publicly; keeping them unlisted or sharing the files directly is safer.
- On the ElevenLabs free plan, a published video's title must include "elevenlabs.io".
- Each `.vtt` file holds the captions (they are also burned into the video).

Tell the teacher the videos are done and where they are.
````

- [ ] **Step 5: Write `lesson-videos/skills/make/references/guide.md`**

Adapt `~/Projects/ihs/marine-biology/study-kit/videos/_source/GUIDE.md`. Full content:

````markdown
# Chapter video guide

How to build one chapter video with the lesson-videos engine. **LV** = `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py"`. A chapter is a folder `WORK/chN/` with `script.json`, `scenes.js` and `assets/`. Copy the idioms in `sample/` (next to this file).

## Workflow
1. Write `script.json`. Top level: `chapter` (small top-right label, e.g. `"CHAPTER 2 · OSMOSIS"`), `title`, `out` (e.g. `"Chapter 2 - Osmosis and the Salty Potato Lab.mp4"`), optional `"music": "../music/bed.mp3"`, optional `"voice"` (ElevenLabs voice ID). `scenes`: one object per scene with `id`, `say` (narration), optional `lead` (s before speech, default 0.5), `tail` (s after, default 0.7), `hold` (extra silent s, used for quiz countdowns), `min` (minimum s).
2. `LV narrate "WORK/chN"`: one ElevenLabs take per scene, cached by text, so re-running only re-voices changed scenes. Prints each scene's start and duration.
3. Write `scenes.js`: `Engine.assets({...})` plus one `scene(id, draw, opts)` per scene id.
4. `LV stills "WORK/chN" t1 t2 ...` (absolute seconds; one per scene, late enough that its reveals have happened) → `build/stills.jpg`. Read it and fix problems; it also prints `cue miss` warnings for cue words that never occur in the narration.
5. `LV render "WORK/chN"` → the MP4 and a `.vtt` next to the deck in `lesson-videos/`.

## Engine API (globals)
`const { W, H, C, E, P, pop, clamp, lerp, text, measure, card, circle, arrow, line, check, cross, img, clip, bg, heading, badge, tip, bullets, label, emoji, titleCard, quizQ, quizA, recap, rr, molecule, wander, membrane, ring, table, rng, noise } = Engine;`
- `scene(id, (g, t, s) => {...}, opts)`: `g` = canvas 2D context (1920×1080), `t` = seconds since the scene started. `s.cue('word', n=0)` = local time the n-th occurrence of a word (prefix match, case- and punctuation-insensitive) is spoken; **sync every reveal to a cue word**. `s.after('word')` = when it ends. `s.end` = narration end, `s.dur` = scene length.
- `opts`: `dark: true` (dark background; adjusts label and captions), `bug: false` (hide the top-right label), `noCaptions: true`, `cut: true` (no crossfade), `sfx: [[cue, name, gainDb]]` where cue is seconds, `'word'` or `['word', n]`. A soft whoosh is added automatically at each scene change; keep sound effects tasteful (−12 to −16 dB).
- Sound effects available: `pop0` `pop1` `pop2` `pop3` (reveals), `sparkle0` `sparkle1` `sparkle2` (correct answers, big moments), `whoosh0` `whoosh1` `whoosh2`, `thump0` `thump1` (heavy landings), `zip0` `zip1` `zip2` (arrows, lines), `pluck0` `pluck1` `pluck2` `pluck3` (quiz questions, playful notes), `tape0` `tape1` `tape2`, `pencil0` `pencil1` `pencil2`, `crayon0` `crayon1`, `waves0`, `shutter0` (photos).
- Timing helpers: `P(t, start, dur=0.6, ease=E.out)` → 0..1; `pop(t, start)` = overshoot pop-in for scale; easings `E.lin/out/in/inOut/back/elastic`.
- `bg(g, 'paper'|'lab'|'sand'|'ocean'|'deep', t)`: ocean and deep are animated.
- `heading(g, 'Title with *accent*', t, {kicker: 'Small caps line'})`: top-left title. Use on every content scene.
- `text(g, str, x, y, {size, weight, color, align, maxW, lh, alpha, accent, shadow, font})` → height. `y` = top of the text block. Markup `*accent color*`, `_bold_`. Wraps at `maxW`. `measure(g, str, opts)` → `{w, h, lines}`.
- `card(g, x, y, w, h, {fill, r, stroke, lw, alpha, shadow})`, `rr(g, x, y, w, h, r)` path, `circle(g, x, y, r, fill, {stroke, alpha})`, `line(...)`, `arrow(g, x1, y1, x2, y2, {color, w, head, prog, bend, dash, alpha})` (`prog` animates drawing, `bend` curves it).
- `check(g, x, y, size, prog)`, `cross(...)`, `badge(g, 'LABEL', x, yCenter, {fill, color, size, scale, alpha})`, `ring(g, x, y, r, k)`.
- `tip(g, 'text', t, atTime, {label: 'TEST TIP', size})`: callout card above the captions. 1–2 per scene for exam tips and traps (`label: 'TRAP!'` or `'WATCH OUT'`).
- `bullets(g, items[], x, y, t, times[], {size, maxW})`, `table(g, rows, x, y, colW[], {rowTimes, t, size, rowH})`, `label(g, 'text', px, py, tx, ty, k)` leader-line label.
- `img(g, key, x, y, w, h, {fit: 'cover'|'contain', r, zoom, panX, panY, alpha, shadow})`: images registered with `Engine.assets({key: 'assets/file.jpg'})`. Slow Ken Burns: `zoom: 1.05 + 0.02 * t`.
- `clip(g, 'assets/clip_name', frameCount, t, x, y, w, h, {fps: 24, loop: false, fit: 'cover', r})`: plays a JPEG frame sequence made by `LV frames` (an 8 s clip = 192 frames).
- `emoji(g, '🐟', x, y, size, {scale, rot, alpha})`: great for icons. Emoji look slightly different on Windows and Mac.
- Science helpers: `molecule(g, x, y, 'water'|'salt'|'sugar'|'o2'|'co2'|color, scale, alpha)`, `wander(i, t, {x, y, w, h}, seed)` → `[x, y]` for particle fields, `membrane(g, x, y1, y2, t)`.
- Standard scenes: `titleCard(g, t, s, {kicker, title, sub, emojis, bg})`, `quizQ(g, t, s, {n, q, choices, emoji})` (countdown ring during `hold`), `quizA(g, t, s, {answer, why})`, `recap(g, t, s, items, times, {title, kicker, gap, next, nextAt})`.
- Layout: margins x 120..1800; headings y 40..170; content y 210..900; **captions are drawn automatically below y ≈ 930**, so keep content above 900. Minimum text size 30 px (prefer 36 or more). One idea per scene; big, bold, colorful; animate things in as they are spoken.
- Palette: `C.navy, C.sea, C.teal, C.aqua, C.foam, C.coral, C.sun, C.leaf, C.purple, C.pink, C.ink, C.grey, C.water`.

## Assets
Copy the deck images you use from `WORK/deck/media/` into `WORK/chN/assets/`, downscaled to at most 1600 px wide (`from PIL import Image`; Pillow is available through `uv run --with pillow python`). Use the contact sheets to pick them. Never use images of students.

## Narration style
- Talk to "you", a student at the grade level from the interview, preparing for a test. Warm, upbeat, a little funny, never cringe or babyish. Short sentences. Contractions.
- Every concept: the class definition (close to the teacher's wording in `brief.md`) → a picture or animation that makes it obvious → a memory hook → **how it shows up on the test** (likely question, common trap, the exact vocabulary word to use).
- Open with a hook (15 s or less). End with a 3-question quiz (`q1`/`a1`… scenes, each `q` with `"hold": 4.5`) and a ~25 s recap that teases the next chapter.
- Text-to-speech friendly: spell symbols as spoken ("C O two" or "carbon dioxide", "ten point three percent", "three hundred milliliters"); no abbreviations like "e.g."; no emoji in `say`. Captions show the `say` text, so keep it clean.
- Target 4–6 minutes per chapter (about 600–850 words). Never invent facts or statistics beyond `brief.md`.
````

- [ ] **Step 6: Write the sample chapter**

`lesson-videos/skills/make/references/sample/script.json`:
```json
{
  "chapter": "SAMPLE · THE WATER CYCLE",
  "title": "The Water Cycle",
  "out": "Sample - The Water Cycle.mp4",
  "scenes": [
    {"id": "hook", "lead": 0.8, "say": "Hey! The water in your glass might have fallen as rain on a dinosaur. Let's find out how water travels around the planet."},
    {"id": "evaporation", "say": "Step one is evaporation. The sun heats water in oceans and lakes, and it turns into an invisible gas called water vapor. Remember: evaporation means liquid to gas."},
    {"id": "condensation", "say": "Step two is condensation. High up, the air is cold, so the vapor cools and turns back into tiny droplets. Millions of droplets together make a cloud. Watch out for this trap: clouds are liquid droplets, not gas."},
    {"id": "precipitation", "say": "Step three is precipitation. When the droplets get heavy, they fall as rain, snow, sleet or hail. Then the water collects in oceans, lakes and the ground, and the cycle starts again."},
    {"id": "q1", "hold": 4.5, "say": "Quiz time! Pause if you need more time. A puddle disappears on a sunny afternoon. Which step is that?"},
    {"id": "a1", "say": "Evaporation! The sun turned the liquid water into water vapor."},
    {"id": "outro", "tail": 1.5, "say": "So, the water cycle in three words: evaporation, condensation, precipitation. Liquid to gas, gas to droplets, droplets fall. You've got this!"}
  ]
}
```

`lesson-videos/skills/make/references/sample/scenes.js`:
```js
// Sample chapter: The Water Cycle. Shows the idioms: cue-synced reveals, heading, tip, quiz, recap.
const { W, H, C, E, P, pop, text, card, arrow, bg, heading, tip, bullets, emoji, titleCard, quizQ, quizA, recap, wander, circle } = Engine;

scene('hook', (g, t, s) => titleCard(g, t, s, { kicker: 'Science review', title: 'The *Water Cycle*', sub: 'where every raindrop has been', emojis: ['☀️', '☁️', '🌧️', '🌊'] }), { bug: false, sfx: [[1.2, 'sparkle0', -12]] });

scene('evaporation', (g, t, s) => {
  bg(g, 'paper');
  heading(g, 'Step 1: *Evaporation*', t, { kicker: 'Liquid → gas' });
  const sun = s.cue('sun'), vap = s.cue('vapor'), rem = s.cue('Remember');
  emoji(g, '☀️', 1560, 300, 200, { scale: pop(t, sun), rot: t * 0.1 });
  g.save(); g.fillStyle = C.water; g.fillRect(120, 600, 1680, 150); g.restore();
  text(g, 'ocean / lake (liquid)', 160, 640, { size: 40, weight: 700, color: '#fff' });
  const k = P(t, vap, 1.2);
  for (let i = 0; i < 26; i++) {
    const [x] = wander(i, t, { x: 180, y: 300, w: 1300, h: 280 }, 3);
    circle(g, x, 600 - ((t * 60 + i * 37) % 300), 10, 'rgba(79,195,247,0.55)', { alpha: k });
  }
  text(g, 'water *vapor* (invisible gas)', 180, 230, { size: 48, weight: 800, color: C.navy, alpha: k, accent: C.teal });
  tip(g, 'Evaporation = *liquid → gas*', t, rem);
}, { sfx: [['sun', 'pop0', -14], ['vapor', 'zip0', -14]] });

scene('condensation', (g, t, s) => {
  bg(g, 'sand');
  heading(g, 'Step 2: *Condensation*', t, { kicker: 'Gas → droplets' });
  const cold = s.cue('cold'), drop = s.cue('droplets'), cloud = s.cue('cloud'), trap = s.cue('trap');
  card(g, 120, 220, 760, 120, { fill: '#fff', alpha: P(t, cold) });
  text(g, 'cold air up high 🥶', 160, 250, { size: 50, weight: 700, color: C.sea, alpha: P(t, cold) });
  for (let i = 0; i < 40; i++) {
    const [x, y] = wander(i, t, { x: 1000, y: 260, w: 700, h: 260 }, 7);
    circle(g, x, y, 7, C.water, { alpha: P(t, drop + i * 0.03, 0.4) });
  }
  emoji(g, '☁️', 1350, 640, 300, { scale: pop(t, cloud) });
  tip(g, 'Clouds are *liquid droplets*, not gas!', t, trap, { label: 'TRAP!' });
}, { sfx: [['cloud', 'pop2', -12], ['trap', 'thump0', -14]] });

scene('precipitation', (g, t, s) => {
  bg(g, 'paper');
  heading(g, 'Step 3: *Precipitation*', t, { kicker: 'Droplets fall' });
  const fall = s.cue('fall'), forms = [['🌧️', 'rain'], ['❄️', 'snow'], ['🌨️', 'sleet'], ['🧊', 'hail']];
  forms.forEach(([e, word], i) => {
    const at = s.cue(word);
    card(g, 140 + i * 420, 260, 360, 300, { fill: '#fff', alpha: P(t, at) });
    emoji(g, e, 320 + i * 420, 370, 130, { scale: pop(t, at) });
    text(g, word, 320 + i * 420, 470, { size: 50, weight: 800, color: C.navy, align: 'center', alpha: P(t, at) });
  });
  const again = s.cue('again');
  arrow(g, 1500, 820, 420, 820, { color: C.teal, w: 10, prog: P(t, again, 1.2), bend: -0.25 });
  text(g, 'and the cycle starts again', 960, 650, { size: 44, weight: 700, color: C.teal, align: 'center', alpha: P(t, again) });
}, { sfx: [['rain', 'pop0', -14], ['snow', 'pop1', -14], ['sleet', 'pop2', -14], ['hail', 'pop3', -14], ['again', 'zip1', -14]] });

scene('q1', (g, t, s) => quizQ(g, t, s, { n: 1, q: 'A puddle *disappears* on a sunny afternoon. Which step?', choices: ['Evaporation', 'Condensation', 'Precipitation'], emoji: '☀️' }), { dark: true, sfx: [[0.1, 'pluck2', -10]] });
scene('a1', (g, t, s) => quizA(g, t, s, { answer: 'Evaporation', why: 'The sun turned the *liquid* into *water vapor*.' }), { dark: true, sfx: [[0.1, 'sparkle1', -12]] });

scene('outro', (g, t, s) => recap(g, t, s, [
  '*Evaporation:* liquid → gas (the sun heats water)',
  '*Condensation:* gas → droplets (cold air, clouds)',
  '*Precipitation:* droplets fall (rain, snow, sleet, hail)',
], [s.cue('evaporation'), s.cue('condensation'), s.cue('precipitation')], { title: 'The water cycle in 30 seconds', kicker: 'Recap' }));
```

- [ ] **Step 7: Write the sample deck generator and generate the deck**

`examples/make_sample_deck.py`:
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-pptx>=1.0", "pillow>=10.0"]
# ///
"""Build examples/water-cycle.pptx: a 6-slide, photo-free sample deck for trying lesson-videos."""
import io
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches

OUT = Path(__file__).resolve().parent / "water-cycle.pptx"


def drawing(kind: str) -> io.BytesIO:
    im = Image.new("RGB", (1200, 800), "#DFF3FB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 620, 1200, 800], fill="#2E86C1")
    if kind in ("sun", "cycle"):
        d.ellipse([920, 60, 1120, 260], fill="#F7C531")
    if kind in ("cloud", "cycle"):
        for x, y, r in [(380, 220, 90), (480, 180, 110), (600, 220, 90)]:
            d.ellipse([x - r, y - r, x + r, y + r], fill="white")
    if kind == "cycle":
        d.line([(900, 560), (700, 300)], fill="#1B4F72", width=12)
        d.line([(480, 330), (480, 600)], fill="#1B4F72", width=12)
    b = io.BytesIO()
    im.save(b, "PNG")
    b.seek(0)
    return b


def main():
    prs = Presentation()
    slides = [
        ("The Water Cycle", "Unit 3 · How water moves around Earth", None, "Essential question: How does water move between the ocean, the air and the land?"),
        ("Evaporation", "The sun heats water in oceans and lakes.\nLiquid water turns into water vapor, an invisible gas.", "sun", "Key word: evaporation = liquid to gas."),
        ("Condensation", "Water vapor cools high in the atmosphere.\nIt turns back into tiny liquid droplets.\nMany droplets together form clouds.", "cloud", "Common mistake: clouds are liquid droplets, not water vapor."),
        ("Precipitation", "Droplets join and get heavy.\nThey fall as rain, snow, sleet or hail.", None, ""),
        ("Collection", "Water collects in oceans, lakes, rivers and underground.\nThen the cycle starts again.", "cycle", ""),
        ("Review", "1. Name the three main steps of the water cycle.\n2. Which step turns liquid into gas?\n3. Are clouds made of gas or liquid?", None, "Answers: evaporation, condensation, precipitation; evaporation; liquid droplets."),
    ]
    for title, body, pic, notes in slides:
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = title
        s.placeholders[1].text = body
        if pic:
            s.shapes.add_picture(drawing(pic), Inches(5.2), Inches(2.2), width=Inches(4.3))
        if notes:
            s.notes_slide.notes_text_frame.text = notes
    prs.save(str(OUT))
    print(OUT)


if __name__ == "__main__":
    main()
```

Run: `uv run examples/make_sample_deck.py` → prints the path; `examples/water-cycle.pptx` exists.

- [ ] **Step 8: Write the teacher README `lesson-videos/README.md`**

````markdown
# lesson-videos

Turn your slide deck into narrated, animated study videos, one per chapter or unit, using Claude Code.

Each video is 4–6 minutes long and includes:
- a friendly AI narrator who explains each idea in your wording
- animated diagrams and your own slide images, revealed in sync with the narration
- captions, "test tip" and "trap" callouts
- a 3-question pause-and-answer quiz and a 30-second recap
- optional background music and a few AI-animated clips made from your photos

Before building anything, Claude also lists places where your slides contradict each other or have typos.

## What you need

- **Claude Code** (the desktop app or the terminal version) and a Claude plan. Download it at https://claude.com/claude-code.
  - **Windows:** install **Git for Windows** first (https://git-scm.com/download/win), then Claude Code.
- **An ElevenLabs account** for the narrator's voice. Free works for about one video a month; Starter ($6/month) covers a whole unit.
- *(Optional)* **A Google account with billing** for music and AI clips: about $2–3 for a whole unit, with a $5 minimum prepayment.
- About 1 GB of free disk space and an internet connection that allows downloads. Some school networks block them; a home network works.

## Install (about 10 minutes, once)

1. Open Claude Code and type:
   ```
   /plugin marketplace add DanielLandi/plugins
   /plugin install lesson-videos@daniellandi
   ```
2. Type `/lesson-videos:setup`. Claude installs the free tools it needs and walks you through creating your API keys step by step. It opens a small file for you to paste the keys into, so they never appear in the chat.

## Make videos

1. Put your deck in a folder. PowerPoint (`.pptx`) and PDF work. For Keynote use File → Export To → PowerPoint; for Google Slides use File → Download → Microsoft PowerPoint.
2. Open Claude Code in that folder and type `/lesson-videos:make`.
3. Claude takes you through these steps:
   - It reads the deck and asks a few questions: grade level, how to split it into chapters, and video length.
   - It shows you a content brief and the possible issues it found in your slides.
   - It proposes a plan with costs. **Nothing that costs money happens until you approve it.**
   - It builds chapter 1 and asks for your feedback, then makes the rest.
4. The videos appear in a new `lesson-videos` folder next to your deck. Each one has a captions file (`.vtt`).

If you stop partway, run `/lesson-videos:make` again later and it picks up where it left off.

## Costs

| Item | Cost |
|---|---|
| Narration | About 5,000–6,000 ElevenLabs characters per 5-minute video. Free plan: 10,000 a month. Starter: $6/month for 30,000. |
| Music (optional) | About $0.08 per track (Google Lyria). |
| AI clips (optional) | About $0.40 per 8-second clip (Google Veo). |
| Claude | Uses your Claude plan. A whole unit is a lot of work, so on a Pro plan expect to spread it over a few sessions. |

## Good to know

- **Privacy.** Your slides are read by Claude (Anthropic). The narration text goes to ElevenLabs, and any photos you choose for AI clips go to Google.
- **ElevenLabs free-plan rules.** Free-plan audio is for non-commercial use, and a published video's title must include "elevenlabs.io".
  - ElevenLabs' use policy also restricts use by government entities without authorization. Read it (elevenlabs.io/use-policy) and decide whether it applies to you.
- **Images from other sources.** If your deck has pictures from elsewhere on the web, check their licences before posting the videos publicly. Unlisted links or sharing the files directly is safer.
- **Where things are kept.** Your keys and sound effects are stored in `~/.lesson-videos` (on Windows, `C:\Users\<you>\.lesson-videos`). Deleting that folder removes them.

## Troubleshooting

| Problem | Fix |
|---|---|
| "uv not found" | Run `/lesson-videos:setup` again; it installs uv. |
| Downloads fail | Try another network, or ask IT to allow astral.sh, pypi.org, files.pythonhosted.org, github.com and cdn.playwright.dev. |
| "credits used up" | Your ElevenLabs month ran out. Finished scenes are saved; upgrade the plan or wait for next month, then run `/lesson-videos:make` again. |
| "Gemini refused … billing" | Billing isn't set up, or the spend cap was reached. Videos still work without music and clips. |
| A video looks wrong | Tell Claude what's wrong ("the text overlaps the photo at 1:20"). It fixes that scene and re-renders. |

Made by Daniel Landi. MIT licence. Fonts: Patrick Hand and Nunito (SIL Open Font Licence).
````

- [ ] **Step 9: Run tests**

Run: `uv run pytest tests/test_skills.py -q`
Expected: all pass. If `test_sample_chapter_renders` reports `cue miss` problems or a page error, fix `scenes.js` (the cue words must appear in the matching `say`).

- [ ] **Step 10: Look at the sample stills**

```bash
SCR=/private/tmp/claude-501/-Users-daniellandi-Projects-ihs-marine-biology/3c471b48-d4e5-4eb7-a95d-2335d30977bf/scratchpad
rm -rf "$SCR/sample/_work" && mkdir -p "$SCR/sample/_work" && cp -R lesson-videos/skills/make/references/sample "$SCR/sample/_work/ch1"
```
Narrate it for real only if Daniel's key is available and the ~700 characters are acceptable (`LESSON_VIDEOS_HOME="$SCR/e2e-home"`, keys file from Task 15 Step 1); otherwise reuse the test's fake narration by running `uv run pytest tests/test_skills.py::test_sample_chapter_renders -q --basetemp="$SCR/sample-pytest"` and Read `$SCR/sample-pytest/*/_work/ch1/build/stills.jpg`. Fix any overlaps or overflow in `scenes.js`.

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat: setup and make skills, chapter guide, sample chapter and deck, teacher README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
```

---

### Task 14: CI on macOS and Windows

**Files:**
- Create: `.github/workflows/ci.yml`
- Delete: `.github/workflows/ci.yml.example` (from the template)
- Modify: `uv.lock` (create with `uv lock`, commit)

- [ ] **Step 1: Write the workflow**

`.github/workflows/ci.yml`:
```yaml
name: ci
on:
  push:
    branches: [main, "feat/**"]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - name: doctor (installs Chromium + ffmpeg, renders a test video)
        run: uv run lesson-videos/scripts/lesson-videos.py doctor --no-keys
      - name: browser for the test environment
        run: uv run python -m playwright install chromium
      - name: tests
        run: uv run pytest -q
```

- [ ] **Step 2: Lock and push**

```bash
rm -f .github/workflows/ci.yml.example
uv lock
git add -A && git commit -m "ci: tests and doctor on macOS and Windows

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT"
git push
```

- [ ] **Step 3: Watch the run**

Run: `gh run watch -R DanielLandi/plugins --exit-status $(gh run list -R DanielLandi/plugins -b feat/lesson-videos -L 1 --json databaseId -q '.[0].databaseId')`
Expected: both jobs green. On a Windows failure, read the log with `gh run view --log-failed`, fix the cause (typical: path quoting, encoding, a POSIX-only call), commit and push again. Do not mark a test as skipped on Windows to get green unless the behavior is genuinely macOS-only (only `chmod 600` is).

---

### Task 15: End-to-end run on this Mac (real keys, ~$0.50 Gemini + 1–2k ElevenLabs characters, approved 2026-10-06)

**Files:** none committed unless fixes are needed. Work in the scratchpad.

- [ ] **Step 1: Fresh home with Daniel's keys copied in (never printed)**

```bash
SCR=/private/tmp/claude-501/-Users-daniellandi-Projects-ihs-marine-biology/3c471b48-d4e5-4eb7-a95d-2335d30977bf/scratchpad
export LESSON_VIDEOS_HOME="$SCR/e2e-home"; rm -rf "$LESSON_VIDEOS_HOME"
LV="uv run $HOME/Projects/plugins/lesson-videos/scripts/lesson-videos.py"
mkdir -p "$LESSON_VIDEOS_HOME"
{ grep '^ELEVENLABS_API_KEY=' ~/Projects/dotfiles/secrets/elevenlabs/.env; grep '^GEMINI_API_KEY=' ~/Projects/dotfiles/secrets/gemini/.env; } > "$LESSON_VIDEOS_HOME/keys.env" && chmod 600 "$LESSON_VIDEOS_HOME/keys.env"
$LV doctor
```
Expected: all ✓ including both keys (ElevenLabs shows characters left).

- [ ] **Step 2: Confirm Jessica is a premade voice (free-tier usable)**

```bash
cd ~/Projects/plugins && uv run python - <<'EOF'
import os, sys
sys.path.insert(0, os.path.expanduser("~/Projects/plugins/lesson-videos/scripts"))
from lv import keys, net, config
v = net.request(f"{config.ELEVEN_ROOT}/voices/{config.DEFAULT_VOICE}", headers={"xi-api-key": keys.get("ELEVENLABS_API_KEY")})
print(v.get("name"), v.get("category"))
EOF
```
Expected: `Jessica premade`. If the category is not `premade`, pick a premade voice from `GET /v1/voices` with a similar description, update `DEFAULT_VOICE` and the `make` skill's interview line, and commit.

- [ ] **Step 3: Follow `/lesson-videos:make` by hand on the sample deck**

```bash
mkdir -p "$SCR/e2e/Unit 3 – Water" && cp ~/Projects/plugins/examples/water-cycle.pptx "$SCR/e2e/Unit 3 – Water/"
```
Then execute `lesson-videos/skills/make/SKILL.md` step by step exactly as written, playing the teacher with these answers: grade 6; one chapter; about 1 minute; Jessica; music yes; one clip (from `s002-1.png`, prompt "gentle sunlight shimmering on calm water, soft rising mist, slow push-in, no text"). Keep the chapter to ~1 minute (hook, 2 content scenes, 1 quiz pair, recap). Record every place where the skill's instructions were unclear, wrong, or missing a step, and fix the skill text.

Expected outputs: `…/Unit 3 – Water/lesson-videos/Chapter 1 - The Water Cycle.mp4` + `.vtt` + `README.md`; `ffprobe` shows video and audio, duration within 0.2 s of the narration; 4 sampled frames look right (Read them).

- [ ] **Step 4: Headless smoke test of the real plugin loading**

```bash
cd "$SCR/e2e/Unit 3 – Water" && claude -p --plugin-dir ~/Projects/plugins/lesson-videos \
  "Run /lesson-videos:make on water-cycle.pptx. Stop at the approval gate and print the plan summary." \
  --allowedTools "Bash Read Write Edit Glob Grep Skill" 2>&1 | tail -40
```
Expected: the skill loads, `ingest` runs, a brief and plan are written to a new `lesson-videos/_work/`, and it stops at the approval gate without any paid call. (Delete that `lesson-videos/` folder afterwards if it collides with Step 3's output; run this in a copy of the folder.)

- [ ] **Step 5: Commit any skill/code fixes from Steps 2–4**

```bash
cd ~/Projects/plugins && uv run pytest -q && git add -A && git commit -m "fix: lessons from the end-to-end run

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT" && git push
```
(Skip if nothing changed.)

---

### Task 16: Merge, publish and install test

- [ ] **Step 1: Whole-branch review** — run the `superpowers:requesting-code-review` skill on `feat/lesson-videos` vs `main`; fix what it confirms; re-run `uv run pytest -q`.

- [ ] **Step 2: Merge to main (Tier B) and push**

```bash
cd ~/Projects/plugins && git switch main && git pull --ff-only && git merge --no-ff feat/lesson-videos -m "feat: lesson-videos 0.1.0

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Mo2NXxE7Yo8VUFp4qrKMYT" && git push && git branch -d feat/lesson-videos && git push origin --delete feat/lesson-videos
```
Then confirm CI is green on `main` (same `gh run watch` command as Task 14, branch `main`).

- [ ] **Step 3: Install test from GitHub in a throwaway Claude Code config**

```bash
SCR=/private/tmp/claude-501/-Users-daniellandi-Projects-ihs-marine-biology/3c471b48-d4e5-4eb7-a95d-2335d30977bf/scratchpad
export CLAUDE_CONFIG_DIR="$SCR/cc-install-test"; rm -rf "$CLAUDE_CONFIG_DIR"
claude plugin marketplace add DanielLandi/plugins
claude plugin install lesson-videos@daniellandi
find "$CLAUDE_CONFIG_DIR/plugins" -path '*lesson-videos*' -name SKILL.md
unset CLAUDE_CONFIG_DIR
```
Expected: two `SKILL.md` paths (setup, make) under a `0.1.0` cache folder.

- [ ] **Step 4: Report to Daniel**: repo URL, install commands for the teacher, parity results (Task 11), E2E video path, CI status, money spent, and the remaining caveats (Windows untested by a human; ElevenLabs government-entity clause).

**Self-review notes for the executor:** the plan's Review Focus items map to `test_ingest_path_with_spaces_and_accents`, `test_ingest_unicode_text`, `test_cli_prints_unicode_on_cp1252`, `test_quota_error_keeps_finished_scenes`, `test_contact_sheet_survives_unreadable_image`, `test_render_reports_page_error`, `test_render_reports_missing_asset`.
