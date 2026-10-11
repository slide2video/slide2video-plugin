# plugins

Public Claude Code marketplace `daniellandi`. It holds `lesson-videos` (narrated study videos), `music-video`
(theme → Suno song → code-rendered music video) and `batatais` (a Blender reconstruction workflow, also usable in
Codex). Users install with
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

## Batatais ownership

`batatais/` is the canonical public package. Keep its skill and compatibility
installer here; do not maintain recipe copies in Blender or HAIK. Bump both
Batatais manifests and its marketplace version together when the package changes.

## music-video

- **macOS-first.** The published commands avoid bash-only syntax so Windows can follow, but only macOS is tested.
  Skills call only `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`.
- **Version bump:** `music-video/.claude-plugin/plugin.json`, its `.claude-plugin/marketplace.json` entry and
  `music-video/scripts/musicvideo/__init__.py` agree; `tests/test_mv_packaging.py` checks them.
- **Privacy:** the plugin and its tests (`tests/test_mv_*.py`, `tests/mv_fixtures.py`) contain nothing personal and
  no seasonal-holiday references. `tests/test_mv_privacy.py` scans them with the local, gitignored
  `.private-terms.txt` (kept by the maintainer, never committed) plus generic checks for home paths,
  emails and tokens. A publish runs `MV_PUBLISH=1 uv run pytest -q`, which fails without the denylist.
- **Vendored code:** `music-video/studio/transitions/` is MIT code from remotion-transitions. Never edit it;
  re-vendor with `music-video/studio/tools/vendor-transitions.sh`.
- **Folders:** project (specs, albums, video code), install (`~/Library/Application Support/music-video/`: the
  engine and models), work (`~/Library/Caches/music-video/work/`), results (`results_dir`). Nothing is written into
  the plugin folder.
- **The engine's own gate** (needs the engine installed once):
  `uv run music-video/scripts/music-video.py doctor`, then `npm test` in the engine folder it prints, and
  `uv run pytest -m studio -q` (a fresh workspace renders a still). The plain `uv run pytest -q` skips it.
