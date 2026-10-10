# plugins

Public Claude Code marketplace `daniellandi`. It holds `lesson-videos` (narrated study videos) and `batatais`
(a Blender reconstruction workflow, also usable in Codex). Users install with
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
