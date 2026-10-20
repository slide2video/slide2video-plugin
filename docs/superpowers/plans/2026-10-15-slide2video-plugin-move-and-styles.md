# slide2video plugin: move, rename and styles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lesson-videos becomes the slide2video plugin (1.1.0) in a new public repo `slide2video/slide2video-plugin`, with a style format whose only style is School (behaving exactly as today); `DanielLandi/plugins` ships a final lesson-videos 1.0.2 that says it moved and then drops lesson-videos; slide2video.com names the new plugin.

**Architecture:** The new repo is cut from `DanielLandi/plugins` with `git filter-repo` (history kept), then renamed in ordinary commits. Styles are folders (`styles/<id>/style.json` + `guide.md`) validated by a JSON Schema and read through two new commands (`LV styles`, `LV style <id>`); the make skill takes everything School-specific from them. Internals the live website depends on (package `lv`, `LV_*`/`LESSON_VIDEOS_*` variables, headers, contract, Keychain entry, the `lesson-videos/` folder inside website lessons) stay.

**Tech Stack:** Python 3.11+ run by `uv` (inline script deps), pytest, `jsonschema`; Claude Code plugin/marketplace manifests; the website is a Cloudflare Worker in TypeScript with vitest (`npm run check && npm test`).

**Spec:** `docs/superpowers/specs/2026-10-15-slide2video-plugin-move-and-styles-design.md`

## Global Constraints

- Plugin name `slide2video`, marketplace name `slide2video`, install: `/plugin marketplace add slide2video/slide2video-plugin` then `/plugin install slide2video@slide2video`; commands `/slide2video:setup`, `/slide2video:make`, `/slide2video:serve`.
- New version **1.1.0** in `slide2video/.claude-plugin/plugin.json`, the marketplace entry and `lv/__init__.py` (they must agree). The old plugin's final version is **1.0.2**.
- Stay unchanged: package `lv`; env vars `LV_*` and `LESSON_VIDEOS_*`; headers `X-LV-Plugin`, `X-LV-Contract`; `site-contract/` content (`{"plugin": "1.0.0"}`) and schemas; the Keychain entry; the `lesson-videos/` folder inside a website lesson folder (worker `_inside`, `_publish`, `timing_for`, `deck.json` paths).
- School behaves exactly as today: question `grade` "What grade are the students?", check id `students`, labels "Remove these slides" / "They're not students", decision words `remove` / `not students`, notes file `student-info.md`, quiz and recap, today's voices including the free Microsoft voice.
- music-video and batatais (their folders, tests, `mv_fixtures.py`, marketplace entries) are never modified.
- Windows and macOS: skills call only the **LV** command; Python passes `encoding="utf-8"` on every file read/write and uses argument lists for subprocesses.
- The engine API (`engine/engine.js`) is frozen.
- Public repos: no class material, student data, keys or private paths (`test_no_private_paths_in_plugin`).
- Outward actions need Daniel's go-ahead at the time: creating the public repo, publishing releases, pushing the old repo's tag/entry change, transferring the website repo, deploying the website.
- Commit trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4
  ```

## Review Focus

1. **A registered project without `results_dir`/`work_dir` lines** keeps finding its videos and extracted decks after the update (old `~/Movies/Lesson Videos/` and old cache folder still used when they exist) — Task 3.
2. **The first-run copy interrupted or run twice at once** (worker and a skill command starting together) never leaves a half-copied `~/.slide2video/` that later runs trust — Task 3 copies to a temporary folder and renames.
3. **A keys file that is a symlink** (Daniel's `keys.env` points into a secrets folder) stays a symlink after the copy, and the token fallback keeps its owner-only permissions — Task 3.
4. **A worker started by 1.0.1 still running** while the new plugin starts: the lock check recognizes both `lesson-videos` and `slide2video` in the process command line, so two workers never run at once — Task 2.
5. **A lesson in progress on the website when the plugin updates** (no `style.txt` in its WORK) continues as School with its existing `student-info.md` — Task 5 (skill rule + test) and Task 3 (`~/Lesson Videos/` kept).

---

## Phase 1 — The new repo (`~/Projects/slide2video-plugin`)

### Task 1: Cut the new repo from history and make its gate pass

**Files (in the new repo):**
- Create by filtering: everything listed in Step 2.
- Modify: `tests/conftest.py`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, `.claude-plugin/marketplace.json`, `.gitignore`, `README.md`, `AGENTS.md`, `SERVICES.md`
- Left out by the filter (never enter the new repo): `bootstrap.sh`, `batatais/`, `music-video/`, `tests/test_mv_*`, `tests/mv_fixtures.py`. `.github/PULL_REQUEST_TEMPLATE.md` comes along unchanged.

**Interfaces:**
- Produces: a repo at `~/Projects/slide2video-plugin` whose `uv run pytest -q` passes, still using the names `lesson-videos/` and `lesson-videos.py` (Task 2 renames).

- [ ] **Step 1: Fresh clone (never filter the working repo)**

```bash
cd ~/Projects && git clone --no-local ~/Projects/plugins slide2video-plugin && cd slide2video-plugin
git remote remove origin
```

- [ ] **Step 2: Filter to the lesson-videos paths**

```bash
uvx git-filter-repo --force \
  --path lesson-videos/ --path examples/ \
  --path tests/conftest.py --path tests/site_fake.py --path tests/proxy-ca.pem \
  $(cd ~/Projects/plugins && git ls-files tests | grep -v -e 'test_mv_' -e 'mv_fixtures' -e conftest -e site_fake -e proxy-ca | sed 's/^/--path /') \
  $(cd ~/Projects/plugins && git ls-files docs/superpowers | grep -e lesson-videos -e slide2video -e plugin-version-check | sed 's/^/--path /') \
  --path docs/archive/.gitkeep \
  --path pyproject.toml --path uv.lock --path LICENSE --path .gitignore --path .github/ \
  --path README.md --path AGENTS.md --path CLAUDE.md --path SERVICES.md --path .claude-plugin/marketplace.json
```

Note: the `$(...)` lists are taken from the working repo at the time you run it, so the file list must include every lesson-videos test and every lesson-videos/slide2video spec and plan, including this plan.

Verify: `git log --oneline -- lesson-videos/scripts/lv/worker.py | tail -1` shows its first commit; `ls` shows no `music-video`, `batatais`, `bootstrap.sh`; `ls tests | grep mv` prints nothing.

- [ ] **Step 3: Trim the shared files**

`tests/conftest.py`: change the plugins line to

```python
pytest_plugins = ["site_fake"]
```

Keep `lv_home`, `lv_project`, `_silence`, `fake_speak`, `make_chapter`, `browser_ok` and everything else that the lesson-videos tests use; delete anything that only `mv_fixtures` or `test_mv_*` used (search: `grep -n "mv\|music" tests/conftest.py`).

`pyproject.toml`:

```toml
[project]
name = "slide2video-plugin-dev"
version = "0"
requires-python = ">=3.11"
dependencies = [
  "edge-tts>=7.3.1",
  "jsonschema>=4.23",
  "numpy>=1.26",
  "pillow>=10.0",
  "playwright>=1.45",
  "pymupdf>=1.24",
  "pyyaml>=6.0",
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

(`mutagen` and the `studio` marker were music-video's; check `grep -rn mutagen lesson-videos tests` prints nothing before dropping it.) Then `uv lock`.

`.claude-plugin/marketplace.json`:

```json
{
  "name": "slide2video",
  "owner": {"name": "Daniel Landi"},
  "metadata": {"description": "slide2video: turn slide decks into narrated videos."},
  "plugins": [
    {
      "name": "lesson-videos",
      "source": "./lesson-videos",
      "description": "Turn a slide deck into narrated, animated study videos, one per chapter. Guides setup of the tools and the ElevenLabs/Gemini keys.",
      "version": "1.0.1",
      "category": "education"
    }
  ]
}
```

`.github/workflows/ci.yml`: drop the ffmpeg step's comment about music-video (keep the step: the doctor installs ffmpeg anyway, so delete the step entirely if `doctor` passes without it on both OSes in CI; otherwise keep it).

`.gitignore`: delete the two music-video denylist lines.

`README.md`, `AGENTS.md`, `SERVICES.md`: remove every music-video and batatais section, row and sentence (search `grep -n -i "music\|batatais\|suno\|blender" README.md AGENTS.md SERVICES.md`). Keep the lesson-videos text as is; Task 2 renames it.

- [ ] **Step 4: Run the gate**

```bash
uv run python -m playwright install chromium
uv run pytest -q
```

Expected: all pass (the same count as the lesson-videos tests in the old repo: run `cd ~/Projects/plugins && uv run pytest -q --co $(git ls-files tests | grep '^tests/test_' | grep -v test_mv_) | tail -1` to get that number).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "New home: lesson-videos alone, cut from DanielLandi/plugins with its history

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
```

---

### Task 2: Rename lesson-videos to slide2video

**Files:**
- Move: `lesson-videos/` → `slide2video/`; `slide2video/scripts/lesson-videos.py` → `slide2video/scripts/slide2video.py`
- Modify: every file `grep -rlI "lesson-videos\|Lesson Videos" slide2video tests examples README.md AGENTS.md SERVICES.md pyproject.toml .github .claude-plugin` lists, by the rules below
- Modify: `slide2video/scripts/lv/worker.py` (`_alive`, `PROMPT`, messages), `slide2video/scripts/lv/version.py`
- Test: `tests/test_worker.py`, `tests/test_packaging.py`, `tests/test_skills.py`, `tests/test_version.py`

**Interfaces:**
- Produces: `config.ENTRY == PLUGIN_ROOT / "scripts" / "slide2video.py"`; `version.STEPS == "run /plugin update slide2video, then close and reopen Claude Code, then run /slide2video:serve"`; `worker.PROMPT == "Run /slide2video:make in site mode for this folder."`; conftest `PLUGIN = REPO / "slide2video"`.

**Rename rules** (apply in this order; the "keep" list wins):

| Keep exactly | Why |
|---|---|
| `LESSON_VIDEOS_HOME`, `LESSON_VIDEOS_SETTINGS`, `LESSON_VIDEOS_PROJECT`, every `LV_*` | internal env vars |
| `folder / "lesson-videos"` and the strings `lesson-videos/_work`, `lesson-videos/` inside the **Site mode** section of `skills/make/SKILL.md`, in `worker.py` (`_inside`, `_publish`, `timing_for`, `_with_slides`), in `site-contract/`, and in `tests/test_worker*.py`/`tests/test_site.py` where they describe a website lesson folder | website lesson folders keep `lesson-videos/` |
| `ingest.default_work` and `paths.py` folder logic | changed by Task 3, not here |
| `project.py` folder names (`settings_file`, `cache_dir`, `default_results`) | changed by Task 3 |
| `config.home()` | changed by Task 3 |
| `USER_AGENT = "lesson-videos/0.3 …"` → becomes `"slide2video/1.1 (+https://github.com/slide2video/slide2video-plugin)"` | rename (listed here so it isn't missed) |

Everything else: `/lesson-videos:` → `/slide2video:`; `lesson-videos.py` → `slide2video.py`; `/plugin update lesson-videos` → `/plugin update slide2video`; `lesson-videos@daniellandi` → `slide2video@slide2video`; `/plugin marketplace add DanielLandi/plugins` → `/plugin marketplace add slide2video/slide2video-plugin`; `github.com/DanielLandi/plugins/tree/main/lesson-videos` → `github.com/slide2video/slide2video-plugin/tree/main/slide2video`; links to `github.com/DanielLandi/plugins/releases/...sample...` stay until Task 6 re-points them; the product name "lesson-videos" in prose and messages → "slide2video".

- [ ] **Step 1: Write the failing tests**

In `tests/test_worker.py`, replace the first assertion of `test_alive_on_posix_trusts_kill_and_then_ps` and add one:

```python
    assert worker._alive(42, platform="darwin", run=ps("/usr/bin/python3 /x/slide2video.py worker --watch\n"))
    assert worker._alive(42, platform="darwin", run=ps("/usr/bin/python3 /x/lesson-videos.py worker --watch\n"))  # a 1.0.x worker still running
```

and add:

```python
def test_worker_prompt_and_messages_use_the_new_name():
    assert worker.PROMPT == "Run /slide2video:make in site mode for this folder."
    assert worker.DISCONNECTED_LINE == "Disconnected from the website. To start again, run /slide2video:serve."
```

In `tests/test_version.py` add:

```python
def test_update_steps_name_slide2video():
    from lv import version
    assert version.STEPS == "run /plugin update slide2video, then close and reopen Claude Code, then run /slide2video:serve"
```

In `tests/test_packaging.py` replace `test_versions_agree` and `test_cli_help_runs`:

```python
def test_versions_agree():
    plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == "slide2video")
    assert plugin["name"] == "slide2video"
    assert plugin["version"] == entry["version"] == lv.__version__
    assert entry["source"] == "./slide2video"
    assert market["name"] == "slide2video"


def test_cli_help_runs(capsys):
    from lv import cli
    try:
        cli.main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert "slide2video" in out and "lesson-videos" not in out
```

In `tests/test_skills.py` set `STEPS = "/plugin update slide2video`, then close and reopen Claude Code"` and change `"A newer lesson-videos"` to `"A newer slide2video"`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/test_worker.py tests/test_version.py tests/test_packaging.py tests/test_skills.py`
Expected: FAIL (names still lesson-videos).

- [ ] **Step 3: Move and rename**

```bash
git mv lesson-videos slide2video
git mv slide2video/scripts/lesson-videos.py slide2video/scripts/slide2video.py
```

Then apply the rename rules with careful per-file edits (not a blind global sed: the keep list must survive). Specific code changes:

`slide2video/scripts/lv/config.py`:

```python
ENTRY = PLUGIN_ROOT / "scripts" / "slide2video.py"
...
USER_AGENT = "slide2video/1.1 (+https://github.com/slide2video/slide2video-plugin)"
```

`slide2video/scripts/lv/version.py`:

```python
STEPS = ("run /plugin update slide2video, then close and reopen Claude Code, then run /slide2video:serve")
...
    return f"A newer slide2video ({latest}) is available. To update: {STEPS}."
```

`slide2video/scripts/lv/worker.py`:

```python
PROMPT = "Run /slide2video:make in site mode for this folder."
...
DISCONNECTED_LINE = "Disconnected from the website. To start again, run /slide2video:serve."
...
    return r.returncode != 0 or "slide2video" in r.stdout or "lesson-videos" in r.stdout
```

(and the `_alive` docstring: "is a slide2video (or older lesson-videos) one"; the watch start line: `with slide2video {lv.__version__}`).

`slide2video/scripts/lv/cli.py`: `prog="slide2video"`, `version=f"slide2video {__version__}"`, the module docstring, the `worker --status` line (`slide2video {lv.__version__}`), the `ingest` help text (`slide2video/_work/deck/`), the two "everything goes next to the deck, in slide2video/." lines, and the site-mode project message ("A slide2video project folder can't be used while working for slide2video.com.").

`slide2video/.claude-plugin/plugin.json`:

```json
{
  "name": "slide2video",
  "version": "1.0.1",
  "description": "Turn a slide deck into narrated, animated videos, one per chapter, with captions. The School style makes study videos with test tips and an end-of-video quiz.",
  "author": { "name": "Daniel Landi" },
  "homepage": "https://github.com/slide2video/slide2video-plugin",
  "license": "MIT",
  "keywords": ["education", "video", "slides", "narration", "teacher"]
}
```

`.claude-plugin/marketplace.json`: the entry becomes `"name": "slide2video"`, `"source": "./slide2video"`, description from `plugin.json`, version `1.0.1` (Task 6 bumps it).

`pyproject.toml`: `pythonpath = ["slide2video/scripts"]`. `.github/workflows/ci.yml`: `uv run slide2video/scripts/slide2video.py doctor --no-keys`. `.gitignore`: `slide2video/**/build/`. `tests/conftest.py`: `PLUGIN = REPO / "slide2video"` and the `lv_home` docstring "its own ~/.slide2video". Skill headings: `# slide2video setup`, `# slide2video: make videos for slide2video.com`; skill descriptions say "slide2video" where they said "lesson-videos". The skill text keeps "teacher" wording (School stays as is).

- [ ] **Step 4: Check nothing was missed**

```bash
grep -rnI "lesson-videos\|Lesson Videos" slide2video tests examples README.md AGENTS.md SERVICES.md pyproject.toml .github .claude-plugin
```

Expected: only lines on the keep list (website lesson folder paths in worker.py, site-contract, the make skill's Site mode section, website-lesson tests; `project.py`, `config.home`, `ingest.default_work`, `paths.py` docstring; the README's sample-video release link). Any other line: rename it.

- [ ] **Step 5: Run the gate**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Rename lesson-videos to slide2video: plugin, commands, script, messages and docs (internals unchanged)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
```

---

### Task 3: New folder names without losing anyone's files

**Files:**
- Modify: `slide2video/scripts/lv/config.py` (`home`, new `migrate_home`), `slide2video/scripts/lv/project.py` (`settings_file`, new `old_settings_file`, `cache_dir`, `default_results`), `slide2video/scripts/lv/worker.py` (`lessons_root`), `slide2video/scripts/lv/ingest.py` (`default_work`), `slide2video/scripts/lv/cli.py` (`main` calls `migrate_home`), docstrings in `keys.py`, `sfx.py`, `site.py`, `chromium.py`, `render.py`, `paths.py`, `page.py`
- Test: `tests/test_home_migration.py` (new), `tests/test_ingest.py`, `tests/test_worker.py`, `tests/test_project.py`

**Interfaces:**
- Consumes: Task 2's names.
- Produces: `config.home() -> Path` (`~/.slide2video` unless `LESSON_VIDEOS_HOME`); `config.migrate_home() -> None`; `project.settings_file() -> Path` (`…/slide2video/settings.json`); `project.old_settings_file() -> Path` (`…/lesson-videos/settings.json`); `project.cache_dir() -> Path`; `project.default_results() -> Path`; `worker.lessons_root() -> Path`; `ingest.default_work(deck) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_home_migration.py`:

```python
import os
import sys
from pathlib import Path

import pytest

from lv import config, ingest, project, worker
from lv.util import read_text, write_text


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Path.home() is a temp folder, and the test env overrides that pick the folders are removed."""
    home = tmp_path / "User Home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    for var in ("LESSON_VIDEOS_HOME", "LESSON_VIDEOS_SETTINGS", "LV_LESSONS_DIR", "APPDATA", "LOCALAPPDATA",
                "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    return home


def test_home_is_dot_slide2video(fake_home):
    assert config.home() == fake_home / ".slide2video"


def test_first_run_copies_the_old_home_and_leaves_it(fake_home):
    old = fake_home / ".lesson-videos"
    write_text(old / "keys.env", "ELEVENLABS_API_KEY=abc\n")
    write_text(old / "site-token.json", "{}")
    os.chmod(old / "site-token.json", 0o600)
    (old / "sfx").mkdir()
    config.migrate_home()
    new = fake_home / ".slide2video"
    assert read_text(new / "keys.env") == "ELEVENLABS_API_KEY=abc\n"
    assert (new / "sfx").is_dir()
    assert (old / "keys.env").is_file()                                   # old folder untouched
    if sys.platform != "win32":
        assert (new / "site-token.json").stat().st_mode & 0o777 == 0o600   # still owner-only
    assert not list(fake_home.glob(".slide2video*.partial*"))              # no leftovers


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need admin rights on Windows")
def test_a_symlinked_keys_file_stays_a_symlink(fake_home, tmp_path):
    secret = tmp_path / "secrets" / "keys.env"
    write_text(secret, "GEMINI_API_KEY=x\n")
    old = fake_home / ".lesson-videos"
    old.mkdir()
    (old / "keys.env").symlink_to(secret)
    config.migrate_home()
    link = fake_home / ".slide2video" / "keys.env"
    assert link.is_symlink() and link.resolve() == secret.resolve()


def test_nothing_is_copied_when_the_new_home_exists(fake_home):
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    write_text(fake_home / ".slide2video" / "keys.env", "NEW\n")
    config.migrate_home()
    assert read_text(fake_home / ".slide2video" / "keys.env") == "NEW\n"


def test_nothing_happens_without_an_old_home(fake_home):
    config.migrate_home()
    assert not (fake_home / ".slide2video").exists()


def test_an_explicit_home_is_never_migrated(fake_home, tmp_path, monkeypatch):
    monkeypatch.setenv("LESSON_VIDEOS_HOME", str(tmp_path / "elsewhere"))
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    config.migrate_home()
    assert not (tmp_path / "elsewhere").exists() and not (fake_home / ".slide2video").exists()


def test_a_leftover_partial_copy_is_replaced(fake_home):
    write_text(fake_home / ".lesson-videos" / "keys.env", "OLD\n")
    write_text(fake_home / ".slide2video.partial-123" / "half", "x")      # an earlier run was interrupted
    config.migrate_home()
    assert read_text(fake_home / ".slide2video" / "keys.env") == "OLD\n"
    assert not (fake_home / ".slide2video" / "half").exists()


def test_the_settings_file_is_copied(fake_home):
    old = project.old_settings_file()
    write_text(old, '{"project": "/somewhere"}')
    config.migrate_home()
    assert project.settings_file() != old
    assert read_text(project.settings_file()) == '{"project": "/somewhere"}'
    assert old.is_file()


def test_old_results_and_cache_folders_keep_being_used(fake_home):
    base = fake_home / ("Movies" if sys.platform == "darwin" else "Videos")
    assert project.default_results() == base / "slide2video"
    (base / "Lesson Videos").mkdir(parents=True)
    assert project.default_results() == base / "Lesson Videos"
    new_cache = project.cache_dir()
    assert "slide2video" in new_cache.as_posix()
    old_cache = Path(new_cache.as_posix().replace("slide2video", "lesson-videos"))
    old_cache.mkdir(parents=True)
    assert project.cache_dir() == old_cache


def test_the_worker_keeps_an_existing_lesson_videos_folder(fake_home):
    assert worker.lessons_root() == fake_home / "slide2video"
    (fake_home / "Lesson Videos").mkdir()
    assert worker.lessons_root() == fake_home / "Lesson Videos"


def test_a_chat_run_resumes_an_old_work_folder(tmp_path):
    deck = tmp_path / "Unit 1" / "deck.pptx"
    write_text(deck, "x")
    assert ingest.default_work(deck) == deck.parent.resolve() / "slide2video" / "_work"
    (deck.parent / "lesson-videos" / "_work").mkdir(parents=True)
    assert ingest.default_work(deck) == deck.parent.resolve() / "lesson-videos" / "_work"


def test_every_command_migrates_first(fake_home, monkeypatch, capsys):
    from lv import cli
    write_text(fake_home / ".lesson-videos" / "keys.env", "ELEVENLABS_API_KEY=abc\n")
    cli.main(["where", str(fake_home)])
    assert (fake_home / ".slide2video" / "keys.env").is_file()
```

Note on the cache test: `cache_dir()` on Windows ends in `slide2video\Cache`; the replace on the POSIX form gives the old `lesson-videos/Cache` path, so the test holds on all three OSes.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/test_home_migration.py`
Expected: FAIL (`migrate_home`, `old_settings_file` missing; old names returned).

- [ ] **Step 3: Implement**

`slide2video/scripts/lv/config.py` (replace `home`, add `migrate_home` below it):

```python
def home() -> Path:
    """Per-user folder for keys, sound effects and caches."""
    return Path(os.environ.get("LESSON_VIDEOS_HOME") or Path.home() / ".slide2video")


def _copy_once(old: Path, new: Path) -> None:
    """Copy old to new if new doesn't exist yet: into a temporary sibling first, then one rename, so an interrupted or
    concurrent copy never leaves a half-filled `new`. Symlinks stay symlinks; file modes are kept."""
    import shutil
    import tempfile
    if new.exists() or not old.exists():
        return
    new.parent.mkdir(parents=True, exist_ok=True)
    for stale in new.parent.glob(new.name + ".partial-*"):
        shutil.rmtree(stale, ignore_errors=True) if stale.is_dir() else stale.unlink(missing_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=new.name + ".partial-", dir=new.parent))
    try:
        if old.is_dir():
            shutil.copytree(old, tmp / "x", symlinks=True)
        else:
            shutil.copy2(old, tmp / "x")
        try:
            (tmp / "x").rename(new)
        except OSError:
            if not new.exists():            # someone else finished first: fine; anything else is a real error
                raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def migrate_home() -> None:
    """First run after the lesson-videos → slide2video rename: copy ~/.lesson-videos and the old settings file to their
    new names, leaving the old ones as they are. Folders that hold work are not copied (see project and worker)."""
    from . import project
    if not os.environ.get("LESSON_VIDEOS_HOME"):
        _copy_once(Path.home() / ".lesson-videos", home())
    if not os.environ.get("LESSON_VIDEOS_SETTINGS"):
        _copy_once(project.old_settings_file(), project.settings_file())
```

`slide2video/scripts/lv/project.py`:

```python
def _config_base() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def settings_file() -> Path:
    if value := os.environ.get("LESSON_VIDEOS_SETTINGS"):
        return Path(value).expanduser()
    return _config_base() / "slide2video" / "settings.json"


def old_settings_file() -> Path:
    """Where lesson-videos kept it; copied once by config.migrate_home."""
    return _config_base() / "lesson-videos" / "settings.json"


def _named(old: Path, new: Path) -> Path:
    """The new folder name, unless the old one exists: a project without results_dir/work_dir lines relies on it."""
    return old if old.is_dir() else new


def cache_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
        return _named(base / "lesson-videos", base / "slide2video")
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return _named(base / "lesson-videos" / "Cache", base / "slide2video" / "Cache")
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return _named(base / "lesson-videos", base / "slide2video")


def default_results() -> Path:
    base = Path.home() / ("Movies" if sys.platform == "darwin" else "Videos")
    return _named(base / "Lesson Videos", base / "slide2video")
```

`slide2video/scripts/lv/worker.py`:

```python
def lessons_root() -> Path:
    """Where website lessons are worked on. A ~/Lesson Videos left by lesson-videos keeps being used, so a lesson in
    progress continues after the update."""
    if value := os.environ.get("LV_LESSONS_DIR"):
        return Path(value)
    old = Path.home() / "Lesson Videos"
    return old if old.is_dir() else Path.home() / "slide2video"
```

`slide2video/scripts/lv/ingest.py`:

```python
def default_work(deck: Path) -> Path:
    """Next to the deck: slide2video/_work, or the lesson-videos/_work of a run started before the rename."""
    folder = Path(deck).resolve().parent
    old = folder / "lesson-videos" / "_work"
    return old if old.is_dir() else folder / "slide2video" / "_work"
```

`slide2video/scripts/lv/cli.py`, in `main` right after `args = build_parser().parse_args(argv)`:

```python
    try:
        from . import config
        config.migrate_home()
    except OSError as e:                     # never block a command over the one-time copy
        print(f"note: couldn't copy the old lesson-videos settings ({e}); they are still in place.", file=sys.stderr)
```

Docstrings and comments that name `~/.lesson-videos` (`keys.py`, `sfx.py`, `site.py`, `chromium.py`, `render.py`) say `~/.slide2video`; `paths.py` and `page.py` docstrings say `<deck folder>/slide2video/_work`. `keys.py` `TEMPLATE` first line: `# slide2video API keys`.

- [ ] **Step 4: Update the old-name tests that now describe new names**

In `tests/test_paths.py`, `tests/test_ingest.py`, `tests/test_project.py`, `tests/test_cli.py`, `tests/test_keys.py`: chat-mode folders in fixtures and assertions use `slide2video/_work` (e.g. `test_teacher_mode_in_work_folder`: `tmp_path / "Unit 1" / "slide2video" / "_work" / "ch1"`). `conftest.make_chapter` uses `"slide2video"`. Website-lesson tests (`test_worker*.py`, `test_site.py`) keep `lesson-videos`.

- [ ] **Step 5: Run the gate**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "slide2video folders: copy ~/.lesson-videos and the settings once; existing work folders keep their old names

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
```

---

### Task 4: The style format, School, and `LV styles` / `LV style`

**Files:**
- Create: `slide2video/styles/style.schema.json`, `slide2video/styles/school/style.json`, `slide2video/styles/school/guide.md`, `slide2video/scripts/lv/styles.py`
- Modify: `slide2video/scripts/lv/cli.py` (two subcommands)
- Test: `tests/test_styles.py` (new)

**Interfaces:**
- Produces: `styles.Style(id: str, data: dict, folder: Path, origin: str)` with property `guide -> Path`; `styles.installed() -> dict[str, Style]`; `styles.get(style_id: str) -> Style`; CLI `LV styles [--json]` and `LV style <id>` (prints `{**style.json, "guide": "<abs path>"}` as JSON).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_styles.py`:

```python
import json

import pytest

from conftest import PLUGIN
from lv import cli, styles
from lv.util import UserError, write_json, write_text

SCHOOL = json.loads((PLUGIN / "styles/school/style.json").read_text(encoding="utf-8")) if (PLUGIN / "styles/school/style.json").is_file() else None


def run(capsys, *argv):
    code = cli.main(list(argv))
    return code, capsys.readouterr()


def a_style(root, sid="business", **over):
    data = {**SCHOOL, "id": sid, "name": sid.title(), "public": False, **over}
    write_json(root / sid / "style.json", data)
    write_text(root / sid / "guide.md", f"# {sid}\n")
    return data


def test_every_plugin_style_is_valid_and_named_after_its_folder():
    found = styles.installed()
    assert set(found) == {p.name for p in (PLUGIN / "styles").iterdir() if p.is_dir()}
    assert all(s.origin == "plugin" and s.guide.is_file() for s in found.values())


def test_school_asks_exactly_what_lesson_videos_asked(capsys):
    code, out = run(capsys, "style", "school")
    assert code == 0
    s = json.loads(out.out)
    assert s["questions"][0]["id"] == "grade"
    assert s["questions"][0]["text"] == "What grade are the students?"
    assert s["check"] == {"id": "students", "file": "student-info.md",
                          "looks_for": "names of students, class photos, graded student work",
                          "remove": "Remove these slides", "keep": "They're not students",
                          "keep_decision": "not students"}
    assert s["public"] is True and s["guide"].endswith("guide.md")


def test_styles_lists_school_alone_by_default(capsys, monkeypatch):
    monkeypatch.delenv("LV_STYLES_DIR", raising=False)
    code, out = run(capsys, "styles", "--json")
    assert code == 0 and [s["id"] for s in json.loads(out.out)] == ["school"]


def test_styles_dir_adds_styles(capsys, monkeypatch, tmp_path):
    a_style(tmp_path / "private styles")
    monkeypatch.setenv("LV_STYLES_DIR", str(tmp_path / "private styles"))
    code, out = run(capsys, "styles")
    assert code == 0 and "school" in out.out and "business" in out.out and "private styles" in out.out


@pytest.mark.parametrize("problem, expected", [
    ("duplicate", "Two styles have the id 'school'"),
    ("schema", "questions"),
    ("folder", "must equal the folder name"),
    ("guide", "guide.md is missing"),
])
def test_bad_styles_are_named(monkeypatch, tmp_path, problem, expected):
    root = tmp_path / "extra"
    if problem == "duplicate":
        a_style(root, "school")
    elif problem == "schema":
        a_style(root, questions="not a list")
    elif problem == "folder":
        data = a_style(root)
        write_json(root / "business" / "style.json", {**data, "id": "other"})
    else:
        a_style(root)
        (root / "business" / "guide.md").unlink()
    monkeypatch.setenv("LV_STYLES_DIR", str(root))
    with pytest.raises(UserError, match=expected):
        styles.installed()


def test_reserved_question_ids_are_refused(monkeypatch, tmp_path):
    for i, qid in enumerate(("chapters", "voice", "issue-1", "problem")):
        root = tmp_path / f"r{i}"
        a_style(root, questions=[{"id": qid, "text": "?", "options": "from-deck"}])
        monkeypatch.setenv("LV_STYLES_DIR", str(root))
        with pytest.raises(UserError):
            styles.installed()


def test_unknown_style_lists_the_installed_ones(capsys, monkeypatch):
    monkeypatch.delenv("LV_STYLES_DIR", raising=False)
    code, out = run(capsys, "style", "travel")
    assert code == 1 and "No style 'travel'" in out.err and "school" in out.err


def test_missing_styles_dir_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("LV_STYLES_DIR", str(tmp_path / "nope"))
    with pytest.raises(UserError, match="isn't a folder"):
        styles.installed()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/test_styles.py`
Expected: FAIL (`lv.styles` missing).

- [ ] **Step 3: Write the schema**

`slide2video/styles/style.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "slide2video style",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "name", "description", "public", "questions", "check", "brief", "outline", "clips", "music"],
  "properties": {
    "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{0,31}$"},
    "name": {"type": "string", "minLength": 1, "maxLength": 40},
    "description": {"type": "string", "minLength": 1, "maxLength": 200},
    "public": {"type": "boolean"},
    "questions": {"type": "array", "maxItems": 3, "items": {"$ref": "#/$defs/question"}},
    "check": {"$ref": "#/$defs/check"},
    "brief": {"type": "string", "minLength": 1},
    "outline": {"type": "string", "minLength": 1},
    "clips": {"type": "string", "minLength": 1},
    "music": {"type": "string", "minLength": 1}
  },
  "$defs": {
    "qid": {
      "type": "string", "pattern": "^[a-z0-9_-]{1,32}$",
      "not": {"anyOf": [{"enum": ["chapters", "length", "voice", "music", "problem"]}, {"pattern": "^issue-"}]}
    },
    "question": {
      "type": "object", "additionalProperties": false, "required": ["id", "text", "options"],
      "properties": {
        "id": {"$ref": "#/$defs/qid"},
        "text": {"type": "string", "minLength": 1, "maxLength": 500},
        "options": {"oneOf": [
          {"const": "from-deck"},
          {"type": "array", "minItems": 1, "maxItems": 6, "items": {
            "type": "object", "additionalProperties": false, "required": ["label"],
            "properties": {"label": {"type": "string", "minLength": 1}, "detail": {"type": "string"}}}}
        ]},
        "hint": {"type": "string"},
        "other": {"type": "boolean"}
      }
    },
    "check": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "file", "looks_for", "remove", "keep", "keep_decision"],
      "properties": {
        "id": {"$ref": "#/$defs/qid"},
        "file": {"type": "string", "pattern": "^[a-z0-9-]+\\.md$"},
        "looks_for": {"type": "string", "minLength": 1},
        "remove": {"type": "string", "minLength": 1},
        "keep": {"type": "string", "minLength": 1},
        "keep_decision": {"type": "string", "pattern": "^[a-z][a-z ]{0,31}$", "not": {"const": "remove"}}
      }
    }
  }
}
```

(The question-id pattern is the card schema's (`site-contract/schemas/card.schema.json`), so every style question id is a valid card id. `maxItems: 3` keeps a card at 8 questions or fewer with the 4 shared questions and an issue question.)

- [ ] **Step 4: Write School**

`slide2video/styles/school/style.json` — exactly as in spec §4.2:

```json
{
  "id": "school",
  "name": "School",
  "description": "Study videos for students: a hook, the key ideas, a short quiz and a recap.",
  "public": true,
  "questions": [
    {"id": "grade", "text": "What grade are the students?", "options": "from-deck",
     "hint": "grade bands (Grades 3–5, 6–8, 9–12); recommend the one the deck fits"}
  ],
  "check": {"id": "students", "file": "student-info.md",
            "looks_for": "names of students, class photos, graded student work",
            "remove": "Remove these slides", "keep": "They're not students", "keep_decision": "not students"},
  "brief": "the essential question if the deck has one; key terms with definitions in the teacher's own wording; examples and lab data from the slides; likely test questions; common mistakes worth a \"trap\" warning",
  "outline": "hook, 6–12 content scenes, a 3-question quiz, recap for 4–6 minutes; for shorter videos scale down, e.g. one scene per key idea and a 1-question quiz",
  "clips": "real photos of living things or landscapes that benefit from motion; not drawings or clip-art, which Veo turns into realistic footage partway through; never diagrams with text, never photos of students",
  "music": "calm, light instrumental study music, no vocals, steady gentle beat"
}
```

`slide2video/styles/school/guide.md` (the School lines moved verbatim out of `skills/make/references/guide.md`; Task 5 deletes them there):

```markdown
# School style

Study videos for students, made from a teacher's deck. Follow this with the shared chapter guide.

## Narration
- Talk to "you", a student at the grade level from the interview, preparing for a test. Warm, upbeat, a little funny, never cringe or babyish. Short sentences. Contractions.
- Every concept: the class definition (close to the teacher's wording in `brief.md`) → a picture or animation that makes it obvious → a memory hook → **how it shows up on the test** (likely question, common trap, the exact vocabulary word to use).
- Open with a hook (15 s or less). End with a 3-question quiz (`q1`/`a1`… scenes, each `q` with `"hold": 4.5`) and a ~25 s recap that teases the next chapter.
- Target 4–6 minutes per chapter (about 600–850 words).

## Images
- Never use images of students.
```

- [ ] **Step 5: Implement `lv/styles.py`**

```python
"""Styles: what a project asks, checks and writes. Each style is a folder <id>/ with style.json (checked against
styles/style.schema.json) and guide.md. The plugin's own styles/ holds the public ones; LV_STYLES_DIR adds more
(set by setups that add their own styles)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import config
from .util import UserError, read_json

ROOT = config.PLUGIN_ROOT / "styles"
SCHEMA = ROOT / "style.schema.json"


@dataclass(frozen=True)
class Style:
    id: str
    data: dict
    folder: Path
    origin: str          # "plugin", or the LV_STYLES_DIR path it came from

    @property
    def guide(self) -> Path:
        return self.folder / "guide.md"


def _roots() -> list[tuple[Path, str]]:
    roots = [(ROOT, "plugin")]
    if extra := os.environ.get("LV_STYLES_DIR"):
        p = Path(extra).expanduser()
        if not p.is_dir():
            raise UserError(f"LV_STYLES_DIR is {extra}, which isn't a folder.")
        roots.append((p, str(p)))
    return roots


def _load(folder: Path, validator) -> dict:
    f = folder / "style.json"
    try:
        data = read_json(f)
    except (OSError, ValueError) as e:
        raise UserError(f"{folder}: no readable style.json ({e}).") from None
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        where = "/".join(map(str, errors[0].path)) or "(top)"
        raise UserError(f"{f}: {where}: {errors[0].message}")
    if data["id"] != folder.name:
        raise UserError(f"{f}: id {data['id']!r} must equal the folder name {folder.name!r}.")
    if not (folder / "guide.md").is_file():
        raise UserError(f"{folder}: guide.md is missing.")
    return data


def installed() -> dict[str, Style]:
    """Every installed style by id, the plugin's first. Any broken style is an error naming its folder."""
    import jsonschema
    validator = jsonschema.Draft202012Validator(read_json(SCHEMA))
    found: dict[str, Style] = {}
    for root, origin in _roots():
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            data = _load(folder, validator)
            if data["id"] in found:
                raise UserError(f"Two styles have the id {data['id']!r}: {found[data['id']].folder} and {folder}.")
            found[data["id"]] = Style(data["id"], data, folder, origin)
    return found


def get(style_id: str) -> Style:
    found = installed()
    if style_id not in found:
        raise UserError(f"No style {style_id!r}. Installed: {', '.join(found)}.")
    return found[style_id]
```

- [ ] **Step 6: Add the commands**

`cli.py`, in `build_parser` after the `status` parser:

```python
    sts = sub.add_parser("styles", help="the installed styles (School, plus any in LV_STYLES_DIR)")
    sts.add_argument("--json", action="store_true")
    sty = sub.add_parser("style", help="one style's questions, check, brief, outline, clips, music and guide path, as JSON")
    sty.add_argument("id")
```

In `dispatch`, before `from . import ingest`:

```python
    if args.cmd in ("styles", "style"):
        from . import styles
        if args.cmd == "style":
            s = styles.get(args.id)
            print(json.dumps({**s.data, "guide": str(s.guide)}, ensure_ascii=False, indent=1))
            return 0
        rows = list(styles.installed().values())
        if args.json:
            print(json.dumps([{"id": s.id, "name": s.data["name"], "description": s.data["description"],
                               "origin": s.origin} for s in rows], ensure_ascii=False))
        else:
            for s in rows:
                print(f"{s.id}: {s.data['name']}: {s.data['description']} ({s.origin})")
        return 0
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest -q tests/test_styles.py` then `uv run pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "Styles: style.json schema, the School style, LV styles and LV style

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
```

---

### Task 5: The make skill and chapter guide read the style

**Files:**
- Modify: `slide2video/skills/make/SKILL.md`, `slide2video/skills/make/references/guide.md`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `LV styles`, `LV style <id>` (Task 4); fields `questions`, `check.{id,file,looks_for,remove,keep,keep_decision}`, `brief`, `outline`, `clips`, `music`, `guide`.
- Produces: `WORK/style.txt` (one line: the style id) written by the skill.

- [ ] **Step 1: Write the failing tests**

In `tests/test_skills.py`, replace `test_make_skill_has_a_site_mode` and add three tests:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/test_skills.py`
Expected: FAIL.

- [ ] **Step 3: Edit `skills/make/SKILL.md`**

After the **Folders** paragraph (whose first bullet now reads: "…finished videos in `<folder>/slide2video/` and working files in `<folder>/slide2video/_work/` (…). If `<folder>/lesson-videos/_work/` already exists (a run started before the rename), use that instead, with finished videos in `<folder>/lesson-videos/`. Call the working folder **WORK**."), insert:

```markdown
**Style.** Each run is made in one style, which decides the extra interview questions, the brief, the scene outline, the music and the writing guide. Once WORK is known:
- If `WORK/style.txt` exists, its one line is the style id.
- Otherwise, if WORK already has `brief.md` or `plan.md` (a run started before styles), the style is `school`.
- Otherwise run `LV styles`: with one style installed, use it without asking; with more, ask the teacher which, showing each style's name and description.
- Write the id to `WORK/style.txt`, then run `LV style <id>` and keep its output. Below, "the style's `questions`", `check`, `brief`, `outline`, `clips`, `music` and `guide` all mean fields of that output. Read the style's guide (its `guide` path) along with `guide.md` before writing any `script.json` or `scenes.js`.
```

Step 2, first bullet becomes:

```markdown
- First the style's `questions`, in order. When a question's `options` is `"from-deck"`, write the options from the deck as its `hint` says and recommend one; otherwise offer its listed options.
```

Step 3: "Per chapter: the essential question if the deck has one; key terms …" becomes "Per chapter: what the style's `brief` lists." (keep the "Possible issues in the slides" sentences unchanged).

Step 4: "a scene outline (hook, 6–12 content scenes, a 3-question quiz, recap for 4–6 minutes; for shorter videos scale down, e.g. one scene per key idea and a 1-question quiz)" becomes "a scene outline (the style's `outline`)", and "0–2 photos per unit worth animating as AI clips (real photos of living things … never photos of students)" becomes "0–2 photos per unit worth animating as AI clips (the style's `clips` says which)".

Step 5: `LV music "WORK" --prompt "<the style's music prompt>"`.

Step 7: "the paths to `guide.md`, `brief.md`, `plan.md`" becomes "the paths to `guide.md` and the style's guide, `brief.md`, `plan.md`".

Site mode — add after the **Folders** bullet:

```markdown
- **Style:** a website lesson is always `school` for now: on the `start` turn write `school` to `WORK/style.txt`; every turn runs `LV style school` (a lesson with no `style.txt` is `school` too).
```

Replace the `student-info.md` bullet in **Files between turns**:

```markdown
  - `WORK/<check.file>`: the slide numbers flagged by the style's check (never copy anyone's name into any file),
    and at its end the teacher's decision, a line `Decision: remove` or `Decision: <check.keep_decision>`. Every turn
    that writes `brief.md`, `plan.md` or a chapter reads it first (if it exists) and leaves the flagged slides out
    when the decision is `remove`.
  - `interview.md`: the interview answers: the style's questions, chapters, length, voice, and the decision for each
    possible issue.
```

Replace the `start` row:

```markdown
| `start` | Step 1 (ingest and read every slide). Then the style's check: look at every slide for what `check.looks_for` names; the website forbids it. If found, write the flagged slide numbers to `WORK/<check.file>` (`check.file`) and don't write `brief.md` yet (the `answer` turn writes it after the teacher's decision). If none was found, steps 2–3: write `brief.md`. | If the check found something: `"questions"` with one question whose `"id"` is `check.id`, options labelled exactly `check.remove` and `check.keep`, and nothing else. Otherwise: the interview (the style's questions with their own ids, then chapter split, length, voice; options from step 2) plus one question per possible issue in the slides (follow the slide / follow the correction / leave it out). Give the possible-issue questions the ids `issue-1`, `issue-2`, …. |
```

In the `answer` row, item (2) becomes: "An answer to the question whose id is `check.id`: append `Decision: remove` (for `check.remove`) or `Decision: <check.keep_decision>` (for `check.keep`) as the last line of `WORK/<check.file>`; if the decision is `remove`, leave the flagged slides out everywhere (otherwise keep them); if `brief.md` doesn't exist yet, write it now (steps 2–3)." Item (3)'s "(grade, chapters, length, voice, …)" becomes "(the style's questions, chapters, length, voice, …)", and "read `student-info.md` if it exists" becomes "read `WORK/<check.file>` if it exists".

Card format example: replace the grade question with

```json
{"contract": 1, "kind": "questions", "message": "A few questions before I plan the videos.",
 "questions": [{"id": "length", "text": "About how long should each video be?",
                "options": [{"label": "2–3 minutes", "detail": "Short and focused", "recommended": true}], "other": true}]}
```

The Site-mode **Folders** bullet and the card file-path rules keep `lesson-videos/` (website lesson folders are unchanged).

- [ ] **Step 4: Edit `skills/make/references/guide.md`**

Under the intro sentence add: "Also follow the style's guide: the `guide` path that `LV style <id>` prints (the id is in `WORK/style.txt`). It says who the videos talk to, their tone, scene order and length."

In **Assets**, delete " Never use images of students." In **Narration style**, delete the four bullets that moved to `styles/school/guide.md` (talk to "you"…, every concept…, open with a hook…, and "Target 4–6 minutes per chapter (about 600–850 words).") and keep the text-to-speech bullet plus a bullet "Never invent facts or statistics beyond `brief.md`."

- [ ] **Step 5: Run the gate**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Make skill: School's questions, check, brief, outline, clips, music and tone come from LV style

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
```

---

### Task 6: 1.1.0, docs, the live check, and publishing

**Files:**
- Modify: `slide2video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `slide2video/scripts/lv/__init__.py` (version `1.1.0`); `README.md`, `slide2video/README.md`, `AGENTS.md`, `CLAUDE.md`, `SERVICES.md`, `slide2video/site-contract/README.md`
- Create: `<scratchpad>/livecheck/drive.py` (not committed)

**Interfaces:**
- Consumes: everything above.
- Produces: public repo `slide2video/slide2video-plugin` at 1.1.0; release `slide2video-sample-v2`.

- [ ] **Step 1: Bump to 1.1.0** in the three files (`__version__ = "1.1.0"`), run `uv run pytest -q tests/test_packaging.py` → PASS.

- [ ] **Step 2: Docs**

- `README.md` (repo root): what slide2video is, the two install lines, a link to `slide2video/README.md`, "School is the public style".
- `AGENTS.md`: the lesson-videos rules from the old `AGENTS.md` renamed (Tier B flow; version bump in `plugin.json`, marketplace entry and `lv/__init__.py`; the site-contract release rule naming `slide2video/site-contract/` and `slide2video-site`'s `contract/`; public repo rules; Windows and macOS; frozen engine; model IDs and prices only in `config.py`; Build & test with `uv run slide2video/scripts/slide2video.py doctor --no-keys`). Add **Styles**: a public style lives only in `slide2video/styles/`; a private style is never committed here; styles change what is asked and written, never the engine API or the job contract; `tests/test_styles.py` validates every style. Add **Kept names**: the list from Global Constraints and why. Work tracking: `-R slide2video/slide2video-plugin`.
- `SERVICES.md`: the lesson-videos rows with `~/.slide2video/keys.env`.
- `site-contract/README.md`: paths say `slide2video/site-contract/` and `slide2video/slide2video-site`.

Run `uv run pytest -q` → PASS (test_docs checks links). Commit "slide2video 1.1.0: version and docs".

- [ ] **Step 3: Live check (~$0.50 on Opus)**

```bash
S=/private/tmp/claude-501/-Users-daniellandi-Projects-plugins/78dc41e4-a379-4c49-9557-38c809c3ac73/scratchpad/livecheck
mkdir -p "$S/lesson/in" && cp ~/Projects/slide2video-plugin/examples/water-cycle.pptx "$S/lesson/in/"
sed 's#Projects/plugins/lesson-videos/scripts#Projects/slide2video-plugin/slide2video/scripts#' \
  /private/tmp/claude-501/-Users-daniellandi-Projects-plugins/78dc41e4-a379-4c49-9557-38c809c3ac73/scratchpad/abtest/drive.py > "$S/drive.py"
cd ~/Projects/slide2video-plugin && uv run python "$S/drive.py" "$S/lesson" opus 1 start
```

Expected: `opus start: exit 0`, then a `"questions"` card whose question ids, in order, are `grade`, `chapters`, `length`, `voice` (then `music` only if a Gemini key is set) and `issue-1` about the three-versus-four steps; the `grade` text is "What grade are the students?". Also check `$S/lesson/lesson-videos/_work/style.txt` contains `school`. If the card differs, fix the skill text and re-run; do not publish until it matches.

- [ ] **Step 4: Publish (Daniel's go-ahead; needs the `slide2video` organization)**

```bash
cd ~/Projects/slide2video-plugin
gh repo create slide2video/slide2video-plugin --public --source . --push \
  --description "Turn slide decks into narrated videos. Claude Code plugin."
gh release download lesson-videos-sample-v2 -R DanielLandi/plugins -D "$S/sample"
gh release create slide2video-sample-v2 -R slide2video/slide2video-plugin "$S"/sample/* \
  --title "Sample video: The Water Cycle (ElevenLabs narration)" \
  --notes "Made by slide2video from examples/water-cycle.pptx."
```

Then point the README sample links at `https://github.com/slide2video/slide2video-plugin/releases/tag/slide2video-sample-v2` (keep the v1 free-voice link to the old repo's release), `uv run pytest -q`, commit "README: sample video release in this repo", push.

- [ ] **Step 5: Install check** in a throwaway config:

```bash
export CLAUDE_CONFIG_DIR="$S/cc-config" && mkdir -p "$CLAUDE_CONFIG_DIR"
claude plugin marketplace add slide2video/slide2video-plugin
claude plugin install slide2video@slide2video
cat "$CLAUDE_CONFIG_DIR/plugins/installed_plugins.json"
unset CLAUDE_CONFIG_DIR
```

Expected: `slide2video@slide2video` at version `1.1.0`.

---

## Phase 2 — The old repo (`~/Projects/plugins`)

### Task 7: lesson-videos 1.0.2, the moved notice

**Files (old repo, branch `lesson-videos-1.0.2`):**
- Modify: `lesson-videos/scripts/lv/version.py` (`MOVED`), `lesson-videos/scripts/lv/cli.py` (`worker --status`), `lesson-videos/scripts/lv/worker.py` (watch start), `lesson-videos/skills/{setup,make,serve}/SKILL.md`, version `1.0.2` in `lesson-videos/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `lesson-videos/scripts/lv/__init__.py`
- Test: `tests/test_version.py`, `tests/test_worker_watch.py`, `tests/test_skills.py`

**Interfaces:**
- Produces: `version.MOVED: str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_version.py`:

```python
def test_moved_notice_gives_the_three_steps():
    from lv import version
    m = version.MOVED
    assert m.startswith("lesson-videos is now slide2video.")
    for step in ("/plugin marketplace add slide2video/slide2video-plugin", "/plugin install slide2video@slide2video",
                 "/plugin uninstall lesson-videos", "close and reopen Claude Code"):
        assert step in m


def test_worker_status_prints_the_moved_notice(monkeypatch, capsys):
    from lv import cli, site, version
    monkeypatch.setattr(site, "status", lambda: {"teacher_email": "t@example.com", "device_name": "Mac"})
    assert cli.main(["worker", "--status"]) == 0
    assert version.MOVED in capsys.readouterr().out
```

`tests/test_worker_watch.py`: find the test that checks the start line (`grep -n "Making videos for" tests/test_worker_watch.py`) and, next to that assertion, assert that `version.MOVED` is in the same captured output (add `from lv import version` at the top).

`tests/test_skills.py`:

```python
def test_skills_say_lesson_videos_moved():
    from lv import version
    for s in ("setup", "make", "serve"):
        _, text = frontmatter(s)
        assert "/plugin marketplace add slide2video/slide2video-plugin" in text
        assert "/plugin install slide2video@slide2video" in text and "/plugin uninstall lesson-videos" in text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/test_version.py tests/test_worker_watch.py tests/test_skills.py`
Expected: FAIL.

- [ ] **Step 3: Implement**

`lesson-videos/scripts/lv/version.py`:

```python
MOVED = ("lesson-videos is now slide2video. To switch: run /plugin marketplace add slide2video/slide2video-plugin, "
         "then /plugin install slide2video@slide2video, then /plugin uninstall lesson-videos, and close and reopen "
         "Claude Code. Your keys and settings come along.")
```

`cli.py`, `worker --status` branch, after the "Connected to …" print: `print(version.MOVED)`.

`worker.py`, right after the "Making videos for …" `out(...)` line in `watch`: `out(version.MOVED)` (`version` is already imported there for `update_line`; import it if not).

Each of `setup`, `make`, `serve` SKILL.md, right after the `# …` heading:

```markdown
**First, tell the teacher (not in site mode):** lesson-videos is now **slide2video**. To switch, type `/plugin marketplace add slide2video/slide2video-plugin`, then `/plugin install slide2video@slide2video`, then `/plugin uninstall lesson-videos`, and close and reopen Claude Code. Their keys and settings come along. Then carry on with this skill: lesson-videos still works until they switch.
```

Bump the three version strings to `1.0.2`.

- [ ] **Step 4: Run the gate**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Merge, push and tag (Daniel's go-ahead)**

```bash
git add -A && git commit -m "lesson-videos 1.0.2: says it is now slide2video, with the three steps to switch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
git checkout main && git merge --no-ff lesson-videos-1.0.2 -m "Merge lesson-videos 1.0.2: moved notice

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
git push origin main
git tag lesson-videos-v1.0.2 && git push origin lesson-videos-v1.0.2
```

---

### Task 8: Point the old entry at the tag, then remove lesson-videos from `main`

**Files (old repo, branch `remove-lesson-videos`):**
- Modify: `.claude-plugin/marketplace.json`, `tests/test_packaging.py` (first commit); then delete `lesson-videos/`, `examples/`, the lesson-videos tests, `tests/site_fake.py`, `tests/proxy-ca.pem`; modify `tests/conftest.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`, `AGENTS.md`, `README.md`, `SERVICES.md` (second commit)

**Interfaces:**
- Consumes: tag `lesson-videos-v1.0.2` (Task 7).

- [ ] **Step 1: Switch the entry to a `git-subdir` source pinned to the tag (the folder is still on `main`)**

The `lesson-videos` entry in `.claude-plugin/marketplace.json` becomes:

```json
{
  "name": "lesson-videos",
  "source": {"source": "git-subdir", "url": "DanielLandi/plugins", "path": "lesson-videos", "ref": "lesson-videos-v1.0.2"},
  "description": "Now slide2video: /plugin marketplace add slide2video/slide2video-plugin. This final release says how to switch.",
  "version": "1.0.2",
  "category": "education"
}
```

(Shape from the Claude Code docs' "Plugin sources": `git-subdir` takes `url` (full URL or `owner/repo`), `path`, `ref`. A relative source can't be pinned to a ref, which is why the entry changes.) In `tests/test_packaging.py::test_versions_agree`, replace `assert entry["source"] == "./lesson-videos"` with:

```python
    assert entry["source"] == {"source": "git-subdir", "url": "DanielLandi/plugins", "path": "lesson-videos",
                               "ref": "lesson-videos-v1.0.2"}
```

`uv run pytest -q` → PASS. Commit, merge `--no-ff` to `main`, push (Daniel's go-ahead).

- [ ] **Step 2: Verify the pinned entry installs 1.0.2**

```bash
export CLAUDE_CONFIG_DIR="$S/cc-old" && mkdir -p "$CLAUDE_CONFIG_DIR"
claude plugin marketplace add DanielLandi/plugins
claude plugin install lesson-videos@daniellandi
cat "$CLAUDE_CONFIG_DIR/plugins/installed_plugins.json"
grep -l "slide2video/slide2video-plugin" "$CLAUDE_CONFIG_DIR"/plugins/cache/daniellandi/lesson-videos/*/skills/serve/SKILL.md
unset CLAUDE_CONFIG_DIR
```

Expected: `lesson-videos@daniellandi` at `1.0.2` and the grep prints the file. **If it fails:** revert the entry to `"source": "./lesson-videos"` (and the test), push, and take the fallback in Step 3b.

- [ ] **Step 3a: Remove lesson-videos (the pinned entry works)**

```bash
git checkout -b remove-lesson-videos
git rm -r -q lesson-videos examples tests/site_fake.py tests/proxy-ca.pem \
  $(git ls-files tests | grep '^tests/test_' | grep -v '^tests/test_mv_')
```

`tests/conftest.py` keeps only what the music-video tests use: `pytest_plugins = ["mv_fixtures"]` and the imports they need; delete `PLUGIN`, `lv_home`, `lv_project`, `_silence`, `fake_speak`, `make_chapter`, `browser_ok` after confirming `grep -n "lv_home\|lv_project\|fake_speak\|make_chapter\|browser_ok\|from conftest" tests/test_mv_*.py tests/mv_fixtures.py` prints nothing (if something is used, keep that piece). `pyproject.toml`: `pythonpath = ["music-video/scripts"]`. CI: delete the "doctor (installs Chromium + ffmpeg…)" step. `.gitignore`: delete `lesson-videos/**/build/`. `AGENTS.md`: drop the lesson-videos paragraphs (intro, version and site-contract rules, Rules bullets on teachers/class material/engine/config, Build & test commands) and say: "lesson-videos moved to `slide2video/slide2video-plugin` (renamed slide2video). Its marketplace entry here serves the final 1.0.2 from the tag `lesson-videos-v1.0.2`; never edit it." Keep the music-video and batatais sections untouched; Build & test becomes `uv run pytest -q`. `README.md`: the lesson-videos row says "Moved: now [slide2video](https://github.com/slide2video/slide2video-plugin)"; drop its install line. `SERVICES.md`: drop the lesson-videos-only rows (ElevenLabs, Microsoft voice, Gemini, slide2video.com…), keep music-video's and batatais'.

- [ ] **Step 3b (fallback only): keep the folder frozen**

Leave `lesson-videos/` on `main` with `"source": "./lesson-videos"`, add as its README's first line `> ⚠️ ARCHIVED: lesson-videos is now slide2video: https://github.com/slide2video/slide2video-plugin`, and remove everything else in Step 3a except the folder itself.

- [ ] **Step 4: Gate**

Run: `uv run pytest -q`
Expected: PASS with only music-video tests (`uv run pytest -q --co | tail -1` lists none of the removed files). Then `git diff --stat main -- music-video batatais` prints nothing.

- [ ] **Step 5: Commit, merge, push (Daniel's go-ahead)**

```bash
git add -A && git commit -m "lesson-videos moved to slide2video/slide2video-plugin; its entry serves the final 1.0.2 from its tag

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
git checkout main && git merge --no-ff remove-lesson-videos -m "Merge: lesson-videos leaves this repo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Jon8rnwdem1pWDy6nyrDK4"
git push origin main
```

Re-run Step 2's install check: still `1.0.2`.

---

## Phase 3 — The website (`~/Projects/slide2video`)

### Task 9: slide2video.com names the new plugin

**Files (website repo, branch `slide2video-plugin-name`):**
- Modify: `src/contract.ts` (`UPDATE_STEPS`, `needsUpdate`, `siteBehind`, new `pluginName`), `src/pages.ts` (`versionLabel`, add-a-computer steps, `/lesson-videos:serve` texts), `src/ui.ts` (footer link), `src/legal.ts` (one word), `src/sample.ts` (comment), `AGENTS.md`
- Test: `test/disconnect.test.ts`, `test/landing.test.ts`, `test/pages.test.ts`, `test/plugin-version.test.ts`, `test/version.test.ts`

**Interfaces:**
- Produces: `pluginName(have: string | null): "slide2video" | "lesson-videos"` in `src/contract.ts` (`slide2video` from 1.1.0, else `lesson-videos`).

- [ ] **Step 1: Write the failing tests**

`test/version.test.ts` — add:

```ts
import { pluginName, needsUpdate, UPDATE_STEPS } from "../src/contract";

describe("plugin name", () => {
  it("names computers the way their owner installed the plugin", () => {
    expect(pluginName("1.1.0")).toBe("slide2video");
    expect(pluginName("1.0.1")).toBe("lesson-videos");
    expect(pluginName(null)).toBe("lesson-videos");
  });
  it("update steps name slide2video, and a lesson-videos computer is told how to switch", () => {
    expect(UPDATE_STEPS).toBe("run /plugin update slide2video, then close and reopen Claude Code, then run /slide2video:serve");
    expect(needsUpdate("0.7.0", "1.0.0")).toContain("/plugin marketplace add slide2video/slide2video-plugin");
    expect(needsUpdate("0.7.0", "1.0.0")).toContain("/plugin install slide2video@slide2video");
  });
});
```

`test/disconnect.test.ts`: its `PLUGIN` is the site's contract version (`1.0.0`), so the existing `lesson-videos ${PLUGIN}` expectations stay. Add one case, built like the existing "Online" one, whose device reports plugin `1.1.0` and expect `<span class="meta">Online · slide2video 1.1.0</span>`. Replace every `/lesson-videos:serve` with `/slide2video:serve`.

`test/landing.test.ts` and `test/pages.test.ts`: "Built on the open-source slide2video plugin" and the link `https://github.com/slide2video/slide2video-plugin`; the Privacy sentence "which version of the slide2video plugin they run."; the add-a-computer block contains `/plugin marketplace add slide2video/slide2video-plugin` and `/plugin install slide2video@slide2video` and `/slide2video:setup`.

- [ ] **Step 2: Run them to verify they fail**

Run: `npm test`
Expected: FAIL on the changed expectations.

- [ ] **Step 3: Implement**

`src/contract.ts`:

```ts
/** What the owner installed: slide2video from 1.1.0, lesson-videos before the rename. */
export function pluginName(have: string | null): "slide2video" | "lesson-videos" {
  const v = parseVersion(have);
  return v && cmp(v, [1, 1, 0]) >= 0 ? "slide2video" : "lesson-videos";
}
export const UPDATE_STEPS = "run /plugin update slide2video, then close and reopen Claude Code, then run /slide2video:serve";
const SWITCH_STEPS = "run /plugin marketplace add slide2video/slide2video-plugin, then /plugin install slide2video@slide2video, " +
  "then /plugin uninstall lesson-videos, then close and reopen Claude Code, then run /slide2video:serve";
export const needsUpdate = (have: string | null, site = PLUGIN) =>
  `This computer has ${parseVersion(have) ? `${pluginName(have)} ${have}` : "an older version of lesson-videos"}; ` +
  `slide2video.com needs ${parseVersion(site)![0]}.x. To update: ${pluginName(have) === "slide2video" ? UPDATE_STEPS : SWITCH_STEPS}.`;
export const siteBehind = (have: string) =>
  `slide2video.com hasn't caught up with ${pluginName(have)} ${have} yet. Nothing to do on this computer; try again later.`;
```

(`cmp` and `parseVersion` already exist in this file; check `cmp`'s argument type and pass the same tuple type.)

`src/pages.ts`: `versionLabel` text `${pluginName(have)} ${have}…`; lines 549–551 become

```
/plugin marketplace add slide2video/slide2video-plugin
/plugin install slide2video@slide2video
```

and `<code>/slide2video:setup</code>`; every `/lesson-videos:serve` → `/slide2video:serve`. `src/ui.ts`: `href="https://github.com/slide2video/slide2video-plugin"`, text "Built on the open-source slide2video plugin". `src/legal.ts`: "which version of the slide2video plugin" (legal text: show Daniel the diff before deploy, issue slide2video#24). `src/sample.ts` comment: "the video slide2video made from it". `AGENTS.md`: the contract source is `slide2video-plugin/slide2video/site-contract/` in `slide2video/slide2video-plugin`, and the sample deck's source is that repo's `examples/water-cycle.pptx`.

- [ ] **Step 4: Gate**

Run: `npm run check && npm test`
Expected: PASS. Then `grep -rn "lesson-videos" src/` lists only `pluginName`, `SWITCH_STEPS` and the "older version of lesson-videos" fallback.

- [ ] **Step 5: Commit and merge** (Tier B: `--no-ff` to `main`, push). **Do not deploy yet.**

---

### Task 10: Transfer the website repo, deploy, and switch Daniel's Mac

- [ ] **Step 1 (Daniel's go-ahead): transfer** `DanielLandi/slide2video` to the organization as `slide2video-site`:

```bash
gh api -X POST repos/DanielLandi/slide2video/transfer -f new_owner=slide2video -f new_name=slide2video-site
cd ~/Projects/slide2video && git remote set-url origin https://github.com/slide2video/slide2video-site.git && git fetch
```

Expected: `git fetch` works; `gh repo view slide2video/slide2video-site --json visibility` says PRIVATE.

- [ ] **Step 2 (Daniel's go-ahead, after showing the Privacy diff): deploy** with `npm run deploy`. Check `https://slide2video.com` home page footer link and, signed in, the Devices page and the "add a computer" steps.

- [ ] **Step 3: Daniel switches his Mac** with the three steps from the notice, reopens Claude Code, then:

```bash
uv run ~/.claude/plugins/cache/slide2video/slide2video/1.1.0/scripts/slide2video.py worker --status
ls ~/.slide2video/
```

Expected: "Connected to https://slide2video.com as … (this device: …, slide2video 1.1.0)"; `~/.slide2video/keys.env` is a symlink to the same secrets file as `~/.lesson-videos/keys.env`; the Devices page shows "slide2video 1.1.0". If it says the computer isn't connected, run `/slide2video:setup` to pair again.

- [ ] **Step 4: Memory and issues**: update the `slide2video-project` and `slide2video-pivot` memories (new repos, 1.1.0 shipped, sub-project 1 done); file a GitHub issue in `slide2video/slide2video-plugin` for sub-project 2 linking the spec's §1.
