# slide2video-plugin

Public Claude Code marketplace `slide2video`. It holds `slide2video` (narrated videos from slide decks). Users install with
`/plugin marketplace add slide2video/slide2video-plugin` then
`/plugin install slide2video@slide2video`.

## Contribution flow

This is a **Tier B repo** (solo dev tool): work on a short-lived branch off
`main`, run `uv run pytest -q` (the gate), merge to `main` with `--no-ff`, and
push. PRs are optional and only opened when asked.

**CI** (`.github/workflows/ci.yml`) runs on GitHub's macOS and Windows runners
with a 25-minute job limit and a 5-minute per-test limit. The local gate is the
real gate.

Teachers only receive a change when `slide2video/.claude-plugin/plugin.json`
`version` (and the matching entry in `.claude-plugin/marketplace.json` and
`slide2video/scripts/lv/__init__.py`) is bumped. Bump it for every
teacher-visible change; `tests/test_packaging.py` checks the three agree.

`slide2video/site-contract/contract.json` `plugin` is the plugin version slide2video.com is built for. When a
release changes anything the website or the worker relies on (the job contract, device calls, card or turn fields,
what the website shows about computers), set `plugin` to the new version, copy `site-contract/` to the website repo's
(`slide2video/slide2video-site`) `contract/`, and deploy the website. A breaking change to the contract is a **major** bump (and bumps the schemas'
`const`). Releases that change none of these need no website deploy: a computer newer than the website, within its major,
is fine. Publish the plugin release first (merge and push this repo), then deploy the website; never the reverse: a
website deployed first with a new major refuses every computer until the plugin ships.

The plugin talks to slide2video.com only (contract 2; there is no `--site` option). A change slide2video.com must understand
ships in a plugin release, published before the website deploy.

## Rules

- **Public repo.** Never commit class material (slides, worksheets, student
  work, teacher photos), student data, or API keys. Examples are generated
  (`examples/make_sample_deck.py`).
- **Windows and macOS.** Skills call only
  `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/slide2video.py" <command>`; no
  bash-only syntax in skills. Python passes `encoding="utf-8"` on every file
  read/write and uses argument lists for subprocesses.
- **Engine API is frozen** (`slide2video/engine/engine.js`): skills,
  `guide.md` and existing chapters depend on it. Add helpers, never rename.
- **Model IDs and prices** live only in `slide2video/scripts/lv/config.py`.

## Styles

A public style lives only in `slide2video/styles/` (today: `school`, the public
style). A private style is never committed here. Styles change what is asked and
written, never the engine API or the job contract. `tests/test_styles.py`
validates every style.

## Kept names

The rename to slide2video left these unchanged on purpose, because the website,
the worker, saved projects and existing video projects depend on them: the Python
package `lv`; env vars `LV_*` and `LESSON_VIDEOS_*`; headers `X-LV-Plugin` and
`X-LV-Contract`; the contents and schemas of `slide2video/site-contract/`
(`{"plugin": "2.0.0"}`, the version the website is built for); the Keychain entry; and
the `lesson-videos/` folder inside a website video project folder (worker `_inside`,
`_publish`, `timing_for`, `deck.json` paths). Do not rename them.

## Work tracking

GitHub Issues is the single source of truth for pending work. Capture
follow-ups with the `inbox` skill. For sandboxed sessions pass
`-R slide2video/slide2video-plugin` to `gh`.

## Build & test

```bash
# setup (once): uv installs Python and deps on first run
uv run slide2video/scripts/slide2video.py doctor --no-keys
uv run python -m playwright install chromium   # same browser for the test env
# test (THE gate before merging):
uv run pytest -q
# run a command the way the skills do:
uv run slide2video/scripts/slide2video.py --help
```

## External services

See [`SERVICES.md`](./SERVICES.md) — update it in the same commit whenever a
service dependency is added, removed, or re-keyed.

## Frozen directories

Anything under `docs/archive/` or any file with an `⚠️ ARCHIVED` banner is
historical reference only — never a source of truth for current behavior.
