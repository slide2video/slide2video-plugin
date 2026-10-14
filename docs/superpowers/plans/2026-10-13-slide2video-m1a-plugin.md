# slide2video M1-A (plugin side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `lesson-videos` plugin everything a Mac needs to work for slide2video.com by hand: the job
contract (schemas), `pair`, `worker --once`, `worker --status`, `card`, and a site mode in the `make` skill.

**Architecture:** The canonical contract lives in `lesson-videos/site-contract/` (JSON Schemas + examples) and is
validated in Python by `lv/contract.py`. `lv/site.py` is the Mac's connection to the site (token in the macOS
Keychain, device API calls, pairing). `lv/worker.py` claims one turn, runs Claude Code headless in the lesson's
folder, and sends back the card Claude wrote. The `make` skill gets a "Site mode" section that turns its four
pause points into cards. Everything is tested against a fake site (a local HTTP server) with a fake `claude`.

**Tech Stack:** Python 3.11+ (uv script), `jsonschema` (Draft 2020-12), stdlib `http.server` for the fake site,
pytest.

**Spec:** `docs/superpowers/specs/2026-10-13-lesson-videos-site-design.md` (§5 contract, §6 Mac side; §11 M1).
M1-B (the website, repo `slide2video`) implements the other side of the same contract:
`docs/superpowers/plans/2026-10-13-slide2video-m1b-site.md`.

## Global Constraints

- Tier B repo: branch `slide2video-m1a` off `main`; gate is `uv run pytest -q`; merge to `main`, push.
- Version bump for teacher-visible changes: `lesson-videos/.claude-plugin/plugin.json`, the lesson-videos entry
  in `.claude-plugin/marketplace.json`, and `lesson-videos/scripts/lv/__init__.py` all go **0.4.5 → 0.5.0**
  (`tests/test_packaging.py` checks they agree).
- Skills call only `uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py" <command>` (the `LV` line); no
  bash-only syntax in skills. Python passes `encoding="utf-8"` on every file read/write and uses argument lists
  for subprocesses.
- Engine API (`lesson-videos/engine/engine.js`) is frozen: not touched by this plan.
- Never print or log an API key or the device token; logs sent to the site go through `keys.redact`.
- Site address: `config.SITE_URL = "https://slide2video.com"`, overridable with the env var `LV_SITE_URL`.
- Contract version: integer `1`, sent as header `X-LV-Contract: 1` on every device call. HTTP 426 from the site
  means "update the plugin".
- Device token storage: macOS Keychain, service `slide2video`, account = the site URL. Other platforms (tests,
  Linux) fall back to `~/.lesson-videos/site-token.json` with mode 0600.
- Lessons on the Mac live in `~/Lesson Videos/<title> (<lesson id>)/` (env `LV_LESSONS_DIR` overrides): deck in
  `in/`, work in `lesson-videos/_work/`, videos in `lesson-videos/`, and `site/` for `turn.json`, `card.json`,
  `progress.txt`, `lv.txt`, `claude.log`, `versions.json`.
- Claude runs as: `claude -p "Run /lesson-videos:make in site mode for this folder." --allowedTools
  "Bash(<LV line>:*)" Read Write Edit Glob Grep --disallowedTools WebFetch WebSearch` with the lesson folder as cwd.

### Device API this plan calls (implemented by M1-B; must match exactly)

| Call | Request | Response |
|---|---|---|
| `POST /api/device/pair/start` | `{"name": "<Mac name>"}`, no token | 200 `{"user_code", "device_code", "expires_in", "verify_url"}` |
| `POST /api/device/pair/poll` | `{"device_code"}`, no token | 200 `{"token", "teacher_email"}` · 428 pending · 410 expired |
| `GET /api/device/status` | token | 200 `{"teacher_email", "device_name", "contract"}` |
| `GET /api/device/next` | token | 200 `turn.json` · 204 nothing to do |
| `POST /api/device/turns/:id/heartbeat` | `{"progress": "…"}` | 204 |
| `GET /api/device/files/:id` | token | 200 bytes |
| `PUT /api/device/turns/:id/files?path=out/ch1/v1/x.mp4` | bytes, `Content-Type` | 201 `{"id"}` |
| `POST /api/device/turns/:id/finish` | `card.json` | 204 |

All with `X-LV-Contract: 1`; a mismatch gets 426 `{"error": "<message>"}`; a bad or revoked token gets 401.

## Review Focus

1. A card whose `video`/`captions`/`stills` path points outside the lesson folder (`../../.ssh/id_rsa`) must
   become an `error` card and upload nothing.
2. A turn whose file `path` is not `in/<plain name>` (e.g. `in/../x`, `in/.hidden`, `/etc/passwd`) must be
   refused before anything is written to disk.
3. Claude's log can contain an ElevenLabs or Gemini key (a failing `keys check` echoed by mistake): the log tail
   in an `error` card must be redacted.
4. Two LaunchAgent firings overlapping (M2) or a second manual run must not process the same turn twice: a lock
   file with a live PID makes the second run exit at once; a stale lock (dead PID) is taken over.
5. A Claude Code usage-limit message ("5-hour limit reached ∙ resets 3pm") must become `retry_after` at the next
   3 pm local time (tomorrow if 3 pm has passed), not an unhelpful failure.

Each line has its test in the task that owns the code (Tasks 3 and 4).

---

## File Structure

| File | Responsibility |
|---|---|
| `lesson-videos/site-contract/contract.json` | `{"version": 1}` |
| `lesson-videos/site-contract/schemas/{turn,card,timing}.schema.json` | the contract (canonical) |
| `lesson-videos/site-contract/examples/*.json` | sample documents both repos validate |
| `lesson-videos/scripts/lv/contract.py` | `VERSION`, `problems(kind, obj)` |
| `lesson-videos/scripts/lv/site.py` | site URL, token store, `call()`, `pair()`, `status()` |
| `lesson-videos/scripts/lv/worker.py` | `run_once()`, lesson folders, lock, heartbeat, publish, error cards, `timing_for()` |
| `lesson-videos/scripts/lv/cli.py` | new commands `card`, `pair`, `worker` |
| `lesson-videos/scripts/lv/config.py` | `SITE_URL` |
| `lesson-videos/scripts/lesson-videos.py`, `pyproject.toml` | add `jsonschema>=4.23` |
| `lesson-videos/skills/make/SKILL.md` | new "Site mode" section |
| `lesson-videos/skills/setup/SKILL.md` | optional "Connect this Mac to slide2video.com" step |
| `tests/test_contract.py`, `tests/test_site.py`, `tests/test_worker.py`, `tests/site_fake.py` | tests + fake site |
| `SERVICES.md` | slide2video.com added |

---

### Task 1: The contract (schemas, examples, validator, `card` command)

**Files:**
- Create: `lesson-videos/site-contract/contract.json`, `lesson-videos/site-contract/schemas/turn.schema.json`,
  `lesson-videos/site-contract/schemas/card.schema.json`, `lesson-videos/site-contract/schemas/timing.schema.json`,
  `lesson-videos/site-contract/examples/turn-start.json`, `turn-answer.json`, `card-questions.json`,
  `card-plan.json`, `card-review.json`, `card-done.json`, `card-error.json`, `timing.json`
- Create: `lesson-videos/scripts/lv/contract.py`
- Modify: `lesson-videos/scripts/lv/cli.py` (new `card` command), `lesson-videos/scripts/lesson-videos.py` and
  `pyproject.toml` (dependency)
- Test: `tests/test_contract.py`

**Interfaces:**
- Produces: `lv.contract.VERSION: int` (= 1); `lv.contract.problems(kind: str, obj) -> list[str]` where kind is
  `"turn" | "card" | "timing"` (empty list = valid); CLI `card <file>` prints `card ok` (exit 0) or one problem
  per line (exit 1).
- Note: `turn.json` has no `approval` field (spec §5.1 example listed it as `null`); the turn `kind`
  (`approve`/`change`) carries the decision. `turn.lease_seconds` is added (the lease the site granted).

- [ ] **Step 1: Add the dependency**

In `lesson-videos/scripts/lesson-videos.py`, add `#   "jsonschema>=4.23",` to the `dependencies` list (keep it
alphabetical, after `"edge-tts>=7.3.1",`). In `pyproject.toml` add `"jsonschema>=4.23",` to `dependencies` after
`"edge-tts>=7.3.1",`. Run: `uv sync` — Expected: resolves and installs jsonschema.

- [ ] **Step 2: Write the schemas and examples**

`lesson-videos/site-contract/contract.json`:

```json
{"version": 1}
```

`lesson-videos/site-contract/schemas/turn.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://slide2video.com/contract/1/turn.schema.json",
  "title": "A turn: what the teacher sent, for the Mac",
  "type": "object",
  "required": ["contract", "lesson", "turn", "files"],
  "properties": {
    "contract": {"const": 1},
    "lesson": {
      "type": "object",
      "required": ["id", "title"],
      "properties": {
        "id": {"type": "string", "pattern": "^les_[0-9A-Za-z]{22}$"},
        "title": {"type": "string", "minLength": 1, "maxLength": 200}
      }
    },
    "turn": {
      "type": "object",
      "required": ["id", "seq", "kind"],
      "properties": {
        "id": {"type": "string", "pattern": "^trn_[0-9A-Za-z]{22}$"},
        "seq": {"type": "integer", "minimum": 1},
        "kind": {"enum": ["start", "answer", "approve", "change", "continue", "feedback", "revise", "delete"]},
        "lease_seconds": {"type": "integer", "minimum": 60}
      }
    },
    "files": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "kind", "sha256", "size", "path"],
        "properties": {
          "id": {"type": "string", "pattern": "^fil_[0-9A-Za-z]{22}$"},
          "name": {"type": "string", "minLength": 1, "maxLength": 200},
          "kind": {"enum": ["deck", "extra"]},
          "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "size": {"type": "integer", "minimum": 0},
          "path": {"type": "string", "pattern": "^in/[^/\\\\.][^/\\\\]*$"}
        }
      }
    },
    "instructions": {"type": ["string", "null"], "maxLength": 4000},
    "answers": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["question", "choice"],
        "properties": {
          "question": {"type": "string", "maxLength": 32},
          "choice": {"type": ["string", "null"], "maxLength": 120},
          "other": {"type": ["string", "null"], "maxLength": 2000}
        }
      }
    },
    "feedback": {"type": ["string", "null"], "maxLength": 4000},
    "notes": {"type": "array"},
    "delete": {"type": "boolean"}
  }
}
```

`lesson-videos/site-contract/schemas/card.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://slide2video.com/contract/1/card.schema.json",
  "title": "A card: what the Mac sends back for the teacher",
  "type": "object",
  "required": ["contract", "kind", "message"],
  "properties": {
    "contract": {"const": 1},
    "kind": {"enum": ["questions", "plan", "review", "done", "error"]},
    "message": {"type": "string", "maxLength": 2000}
  },
  "allOf": [
    {
      "if": {"properties": {"kind": {"const": "questions"}}},
      "then": {
        "required": ["questions"],
        "properties": {
          "questions": {
            "type": "array", "minItems": 1, "maxItems": 8,
            "items": {
              "type": "object",
              "required": ["id", "text", "options"],
              "properties": {
                "id": {"type": "string", "pattern": "^[a-z0-9_-]{1,32}$"},
                "text": {"type": "string", "minLength": 1, "maxLength": 500},
                "options": {
                  "type": "array", "minItems": 1, "maxItems": 6,
                  "items": {
                    "type": "object",
                    "required": ["label"],
                    "properties": {
                      "label": {"type": "string", "minLength": 1, "maxLength": 120},
                      "detail": {"type": "string", "maxLength": 300}
                    }
                  }
                },
                "other": {"type": "boolean"}
              }
            }
          }
        }
      }
    },
    {
      "if": {"properties": {"kind": {"const": "plan"}}},
      "then": {
        "required": ["markdown", "estimate"],
        "properties": {
          "markdown": {"type": "string", "minLength": 1, "maxLength": 20000},
          "estimate": {
            "type": "object",
            "required": ["usd", "minutes", "chapters"],
            "properties": {
              "usd": {"type": "number", "minimum": 0},
              "minutes": {"type": "number", "minimum": 0},
              "chapters": {"type": "integer", "minimum": 1}
            }
          }
        }
      }
    },
    {
      "if": {"properties": {"kind": {"const": "review"}}},
      "then": {
        "required": ["chapter", "video"],
        "properties": {
          "chapter": {"type": "integer", "minimum": 1},
          "version": {"type": "integer", "minimum": 1},
          "video": {"type": "string", "minLength": 1, "maxLength": 400},
          "captions": {"type": "string", "maxLength": 400},
          "stills": {"type": "string", "maxLength": 400},
          "timing": {"type": "string", "maxLength": 400},
          "resolved": {
            "type": "array",
            "items": {"type": "object", "required": ["note", "answer"],
                      "properties": {"note": {"type": "string"}, "answer": {"type": "string", "maxLength": 1000}}}
          },
          "cost_next": {"type": "object", "required": ["usd"], "properties": {"usd": {"type": "number", "minimum": 0}}}
        }
      }
    },
    {
      "if": {"properties": {"kind": {"const": "done"}}},
      "then": {
        "properties": {
          "chapters": {
            "type": "array",
            "items": {"type": "object", "required": ["chapter", "title"],
                      "properties": {"chapter": {"type": "integer", "minimum": 1}, "title": {"type": "string"}}}
          },
          "readme": {"type": "string", "maxLength": 20000}
        }
      }
    },
    {
      "if": {"properties": {"kind": {"const": "error"}}},
      "then": {
        "properties": {
          "log_tail": {"type": "string", "maxLength": 20000},
          "retry_after": {"type": ["string", "null"], "format": "date-time"}
        }
      }
    }
  ]
}
```

`lesson-videos/site-contract/schemas/timing.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://slide2video.com/contract/1/timing.schema.json",
  "title": "Scene timing of one video version, for the player's scene marks",
  "type": "object",
  "required": ["duration", "scenes"],
  "properties": {
    "duration": {"type": "number", "minimum": 0},
    "scenes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "start", "dur"],
        "properties": {
          "id": {"type": "string"},
          "start": {"type": "number", "minimum": 0},
          "dur": {"type": "number", "minimum": 0},
          "label": {"type": "string"},
          "first_words": {"type": "string"}
        }
      }
    }
  }
}
```

Examples (`lesson-videos/site-contract/examples/`):

`turn-start.json`:
```json
{"contract": 1,
 "lesson": {"id": "les_0123456789abcdefghijkl", "title": "Unit 3 – The Water Cycle"},
 "turn": {"id": "trn_0123456789abcdefghijkl", "seq": 1, "kind": "start", "lease_seconds": 1800},
 "files": [{"id": "fil_0123456789abcdefghijkl", "name": "water-cycle.pptx", "kind": "deck",
            "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "size": 51200,
            "path": "in/water-cycle.pptx"}],
 "instructions": "Grade 7 science; keep each video under 5 minutes."}
```

`turn-answer.json`:
```json
{"contract": 1,
 "lesson": {"id": "les_0123456789abcdefghijkl", "title": "Unit 3 – The Water Cycle"},
 "turn": {"id": "trn_1123456789abcdefghijkl", "seq": 2, "kind": "answer", "lease_seconds": 1800},
 "files": [{"id": "fil_0123456789abcdefghijkl", "name": "water-cycle.pptx", "kind": "deck",
            "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "size": 51200,
            "path": "in/water-cycle.pptx"}],
 "answers": [{"question": "grade", "choice": "Grades 6–8", "other": null},
             {"question": "steps", "choice": null, "other": "Teach all four steps"}]}
```

`card-questions.json`:
```json
{"contract": 1, "kind": "questions", "message": "A few questions before I plan the videos.",
 "questions": [
   {"id": "grade", "text": "What grade are the students?",
    "options": [{"label": "Grades 3–5"}, {"label": "Grades 6–8"}, {"label": "Grades 9–10"}], "other": true},
   {"id": "steps", "text": "The review asks for three main steps, but the deck teaches four. How should the video handle it?",
    "options": [{"label": "Teach 4, quiz on 4", "detail": "Quiz asks for the four steps"},
                {"label": "Follow the slide", "detail": "Keep three main steps"}], "other": true}]}
```

`card-plan.json`:
```json
{"contract": 1, "kind": "plan", "message": "Here's the plan. Nothing that costs money happens until you approve it.",
 "markdown": "## Chapter 1 – The Water Cycle (~3 min)\n- Hook: the essential question\n- Evaporation\n- Condensation (trap: clouds are liquid)\n- Precipitation\n- Collection\n- Quiz (3 questions)\n- Recap",
 "estimate": {"usd": 0, "minutes": 3, "chapters": 1}}
```

`card-review.json`:
```json
{"contract": 1, "kind": "review", "message": "Chapter 1 is ready. What would you change?",
 "chapter": 1, "version": 1,
 "video": "out/ch1/v1/Chapter 1 - The Water Cycle.mp4",
 "captions": "out/ch1/v1/Chapter 1 - The Water Cycle.vtt",
 "stills": "out/ch1/v1/final.jpg",
 "timing": "out/ch1/v1/timing.json"}
```

`card-done.json`:
```json
{"contract": 1, "kind": "done", "message": "All chapters are done.",
 "chapters": [{"chapter": 1, "title": "The Water Cycle"}],
 "readme": "| Video | Length |\n|---|---|\n| Chapter 1 - The Water Cycle | 2:41 |"}
```

`card-error.json`:
```json
{"contract": 1, "kind": "error",
 "message": "Your Claude plan's usage limit was reached; this continues automatically when it resets.",
 "log_tail": "5-hour limit reached ∙ resets 3pm", "retry_after": "2026-10-14T15:00:00-07:00"}
```

`timing.json`:
```json
{"duration": 161.2,
 "scenes": [{"id": "hook", "start": 0, "dur": 15.2, "label": "Hook", "first_words": "Where does rain come from?"},
            {"id": "condensation", "start": 15.2, "dur": 22.4, "label": "Condensation",
             "first_words": "When warm, moist air rises"}]}
```

- [ ] **Step 3: Write the failing tests**

`tests/test_contract.py`:

```python
import json

import pytest

from conftest import PLUGIN
from lv import cli, contract

EXAMPLES = PLUGIN / "site-contract" / "examples"


def _ex(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_version_is_an_integer():
    assert contract.VERSION == 1


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.glob("*.json")))
def test_examples_are_valid(name):
    kind = "timing" if name == "timing.json" else name.split("-")[0]
    assert contract.problems(kind, _ex(name)) == []


def test_question_without_options_is_rejected():
    card = _ex("card-questions.json")
    del card["questions"][0]["options"]
    assert any("options" in p for p in contract.problems("card", card))


def test_unknown_card_kind_is_rejected():
    assert contract.problems("card", {"contract": 1, "kind": "chat", "message": "hi"})


def test_wrong_contract_version_is_rejected():
    card = _ex("card-done.json")
    card["contract"] = 2
    assert contract.problems("card", card)


@pytest.mark.parametrize("path", ["in/../x.pptx", "in/.hidden", "/etc/passwd", "in/a/b.pptx", "out/x.pptx", "in/a\\b"])
def test_turn_file_paths_must_be_plain_names_in_in(path):
    turn = _ex("turn-start.json")
    turn["files"][0]["path"] = path
    assert contract.problems("turn", turn)


def test_card_command(tmp_path, capsys):
    good = tmp_path / "card.json"
    good.write_text(json.dumps(_ex("card-plan.json")), encoding="utf-8")
    assert cli.main(["card", str(good)]) == 0
    assert "card ok" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"contract": 1, "kind": "plan", "message": "x"}), encoding="utf-8")
    assert cli.main(["card", str(bad)]) == 1
    assert "markdown" in capsys.readouterr().out
```

- [ ] **Step 4: Run them to see them fail**

Run: `uv run pytest -q tests/test_contract.py`
Expected: FAIL / ERROR with `ImportError: cannot import name 'contract' from 'lv'`.

- [ ] **Step 5: Implement `lv/contract.py` and the `card` command**

`lesson-videos/scripts/lv/contract.py`:

```python
"""The job contract with slide2video.com. Canonical schemas live in lesson-videos/site-contract/; the site keeps
a pinned copy and checks the version every device call sends."""
from __future__ import annotations

from functools import lru_cache

from . import config
from .util import read_json

CONTRACT_DIR = config.PLUGIN_ROOT / "site-contract"
VERSION: int = read_json(CONTRACT_DIR / "contract.json")["version"]


@lru_cache(maxsize=None)
def _validator(kind: str):
    import jsonschema
    schema = read_json(CONTRACT_DIR / "schemas" / f"{kind}.schema.json")
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def problems(kind: str, obj) -> list[str]:
    """Plain-language schema problems ('' path = the top level); empty when obj is valid."""
    errors = sorted(_validator(kind).iter_errors(obj), key=lambda e: str(list(e.absolute_path)))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(top)'}: {e.message}" for e in errors]
```

In `lv/cli.py` `build_parser()`, after the `frames` parser, add:

```python
    cd = sub.add_parser("card", help="check a site-mode card (site/card.json) before stopping")
    cd.add_argument("file", type=Path)
```

In `dispatch()`, before `if args.cmd == "open":`, add:

```python
    if args.cmd == "card":
        from . import contract
        from .util import read_json
        try:
            obj = read_json(args.file)
        except (OSError, ValueError) as e:
            print(f"{args.file}: not readable JSON ({e})")
            return 1
        bad = contract.problems("card", obj)
        print("card ok" if not bad else "\n".join(bad))
        return 0 if not bad else 1
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest -q tests/test_contract.py`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add lesson-videos/site-contract lesson-videos/scripts/lv/contract.py lesson-videos/scripts/lv/cli.py \
  lesson-videos/scripts/lesson-videos.py pyproject.toml uv.lock tests/test_contract.py
git commit -m "lesson-videos: slide2video job contract (schemas, examples, card command)"
```

---

### Task 2: The connection to the site (`lv/site.py`, `pair`, `worker --status`) and the fake site

**Files:**
- Create: `lesson-videos/scripts/lv/site.py`, `tests/site_fake.py`
- Modify: `lesson-videos/scripts/lv/config.py`, `lesson-videos/scripts/lv/cli.py`, `tests/conftest.py`
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: `contract.VERSION`; `net.request(url, data=None, headers=None, method=None, timeout=120,
  retries=2, raw=False)` and `net.ApiError(status, detail, url)`.
- Produces:
  - `site.site_url() -> str`
  - `site.store` with `get(site) -> str | None`, `set(site, token)`, `delete(site)` (replaceable in tests)
  - `site.call(path, data=None, method=None, raw=False, headers=None, auth=True, timeout=120)` → parsed JSON
    (`{}` for an empty 2xx body) or bytes when `raw=True`; raises `UserError` on 426 (site's message) and on
    401 when `auth` (the "connect this Mac" message), `net.ApiError` otherwise.
  - `site.pair(name=None, sleep=None, out=print, clock=time.monotonic) -> str` (teacher email; `sleep`
    defaults to `time.sleep` looked up at call time)
  - `site.status() -> dict` (`teacher_email`, `device_name`, `contract`)
  - `site.NOT_PAIRED: str`
  - Test fixture `fake_site` (from `tests/site_fake.py`): a running `FakeSite` with `.url`, `.turns` (list of
    turn dicts to hand out), `.files` (`{file_id: bytes}`), `.uploads` (`{path: (content_type, bytes)}`),
    `.finished` (`[(turn_id, card)]`), `.heartbeats` (`[(turn_id, progress)]`), `.pair_polls_pending` (int),
    `.contract` (int), `.token` (str); plus fixture `paired` that points `LV_SITE_URL` at it and stores its token.

- [ ] **Step 1: Write the fake site**

`tests/site_fake.py`:

```python
"""A stand-in for slide2video.com's device API, for the worker and pairing tests."""
from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class FakeSite:
    def __init__(self):
        self.turns, self.files, self.uploads, self.finished, self.heartbeats = [], {}, {}, [], []
        self.pair_polls_pending, self.pair_expired, self.contract = 1, False, 1
        self.token = "s2v_test-token-0123456789"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _handler(self):
        site = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None):
                body = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else b"")
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def _route(self, method):
                u = urllib.parse.urlparse(self.path)
                if self.headers.get("X-LV-Contract") != str(site.contract):
                    return self._send(426, {"error": "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos"})
                if u.path == "/api/device/pair/start":
                    return self._send(200, {"user_code": "KQ7-4M2", "device_code": "dc_1", "expires_in": 600,
                                            "verify_url": f"{site.url}/devices"})
                if u.path == "/api/device/pair/poll":
                    if site.pair_expired:
                        return self._send(410, {"error": "expired"})
                    if site.pair_polls_pending > 0:
                        site.pair_polls_pending -= 1
                        return self._send(428, {"error": "pending"})
                    return self._send(200, {"token": site.token, "teacher_email": "teacher@example.org"})
                if self.headers.get("Authorization") != f"Bearer {site.token}":
                    return self._send(401, {"error": "unauthorized"})
                if u.path == "/api/device/status":
                    return self._send(200, {"teacher_email": "teacher@example.org", "device_name": "Test Mac", "contract": 1})
                if u.path == "/api/device/next":
                    return self._send(200, site.turns.pop(0)) if site.turns else self._send(204)
                parts = u.path.strip("/").split("/")
                if parts[:3] == ["api", "device", "files"]:
                    data = site.files.get(parts[3])
                    return self._send(200, raw=data) if data is not None else self._send(404, {"error": "no file"})
                if parts[:3] == ["api", "device", "turns"] and len(parts) == 5:
                    tid, action = parts[3], parts[4]
                    if action == "heartbeat":
                        site.heartbeats.append((tid, json.loads(self._body())["progress"]))
                        return self._send(204)
                    if action == "files" and method == "PUT":
                        path = urllib.parse.parse_qs(u.query)["path"][0]
                        site.uploads[path] = (self.headers.get("Content-Type"), self._body())
                        return self._send(201, {"id": "fil_up"})
                    if action == "finish":
                        site.finished.append((tid, json.loads(self._body())))
                        return self._send(204)
                return self._send(404, {"error": "not found"})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PUT(self):
                self._route("PUT")

        return H

    def close(self):
        self.server.shutdown()


class DictStore:
    def __init__(self):
        self.tokens = {}

    def get(self, site):
        return self.tokens.get(site)

    def set(self, site, token):
        self.tokens[site] = token

    def delete(self, site):
        self.tokens.pop(site, None)


@pytest.fixture
def fake_site(monkeypatch):
    from lv import site as lvsite
    s = FakeSite()
    monkeypatch.setenv("LV_SITE_URL", s.url)
    monkeypatch.setattr(lvsite, "store", DictStore())
    yield s
    s.close()


@pytest.fixture
def paired(fake_site):
    from lv import site as lvsite
    lvsite.store.set(fake_site.url, fake_site.token)
    return fake_site
```

In `tests/conftest.py`, change `pytest_plugins = ["mv_fixtures"]` to `pytest_plugins = ["mv_fixtures", "site_fake"]`.

- [ ] **Step 2: Write the failing tests**

`tests/test_site.py`:

```python
import pytest

from lv import cli, net, site
from lv.util import UserError


def test_site_url_defaults_to_slide2video(monkeypatch):
    monkeypatch.delenv("LV_SITE_URL", raising=False)
    assert site.site_url() == "https://slide2video.com"


def test_pair_waits_for_the_code_then_stores_the_token(fake_site):
    lines = []
    email = site.pair(name="Test Mac", sleep=lambda s: None, out=lines.append)
    assert email == "teacher@example.org"
    assert site.store.get(fake_site.url) == fake_site.token
    assert any("KQ7-4M2" in l for l in lines) and any("/devices" in l for l in lines)
    assert not any(fake_site.token in l for l in lines)


def test_pair_expired_code(fake_site):
    fake_site.pair_expired = True
    with pytest.raises(UserError) as e:
        site.pair(name="Test Mac", sleep=lambda s: None, out=lambda s: None)
    assert "expired" in str(e.value)


def test_call_without_token_says_connect(fake_site):
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert e.value.args[0] == site.NOT_PAIRED


def test_revoked_token_says_connect(paired):
    site.store.set(paired.url, "s2v_revoked")
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert e.value.args[0] == site.NOT_PAIRED


def test_contract_mismatch_says_update(paired):
    paired.contract = 2
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert "/plugin update lesson-videos" in str(e.value)


def test_empty_204_is_an_empty_dict(paired):
    assert site.call("/api/device/next") == {}


def test_cli_pair_and_status(fake_site, monkeypatch, capsys):
    monkeypatch.setattr(site.time, "sleep", lambda s: None)
    assert cli.main(["pair", "--name", "Test Mac"]) == 0
    out = capsys.readouterr().out
    assert "connected" in out and fake_site.token not in out
    assert cli.main(["worker", "--status"]) == 0
    assert "teacher@example.org" in capsys.readouterr().out


def test_file_store_is_private(tmp_path, monkeypatch):
    import os
    s = site.FileStore()
    s.set("https://slide2video.com", "s2v_x")
    assert s.get("https://slide2video.com") == "s2v_x"
    if os.name == "posix":
        assert oct(s._file().stat().st_mode & 0o777) == "0o600"
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest -q tests/test_site.py`
Expected: FAIL / ERROR with `ImportError: cannot import name 'site' from 'lv'`.

- [ ] **Step 4: Implement**

In `lesson-videos/scripts/lv/config.py`, after `EDGE_HOST = …`, add:

```python
SITE_URL = "https://slide2video.com"      # the website; LV_SITE_URL overrides it (tests, previews)
```

`lesson-videos/scripts/lv/site.py`:

```python
"""slide2video.com: this Mac's connection (pairing, its token in the Keychain, device API calls). The token is
never printed."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time

from . import config, contract, net
from .util import UserError, read_json, write_json

NOT_PAIRED = ("This Mac isn't connected to slide2video.com (or it was removed there). Run /lesson-videos:setup "
              "and choose to connect this Mac.")
UPDATE = "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos"


def site_url() -> str:
    return (os.environ.get("LV_SITE_URL") or config.SITE_URL).rstrip("/")


class KeychainStore:
    """macOS Keychain, service 'slide2video', account = the site address."""
    service = "slide2video"

    def get(self, site: str) -> str | None:
        r = subprocess.run(["security", "find-generic-password", "-s", self.service, "-a", site, "-w"],
                           capture_output=True, encoding="utf-8")
        return r.stdout.strip() or None if r.returncode == 0 else None

    def set(self, site: str, token: str) -> None:
        subprocess.run(["security", "add-generic-password", "-U", "-s", self.service, "-a", site, "-w", token],
                       capture_output=True, check=True)

    def delete(self, site: str) -> None:
        subprocess.run(["security", "delete-generic-password", "-s", self.service, "-a", site], capture_output=True)


class FileStore:
    """Fallback where there is no Keychain: ~/.lesson-videos/site-token.json, readable only by this user."""

    def _file(self):
        return config.home() / "site-token.json"

    def _read(self) -> dict:
        f = self._file()
        return read_json(f) if f.exists() else {}

    def get(self, site: str) -> str | None:
        return self._read().get(site)

    def set(self, site: str, token: str) -> None:
        d = self._read()
        d[site] = token
        write_json(self._file(), d)
        if os.name == "posix":
            os.chmod(self._file(), 0o600)

    def delete(self, site: str) -> None:
        d = self._read()
        if d.pop(site, None) is not None:
            write_json(self._file(), d)


store = KeychainStore() if sys.platform == "darwin" and shutil.which("security") else FileStore()


def _error_message(detail: str) -> str:
    import json
    try:
        return str(json.loads(detail).get("error") or "")
    except (ValueError, AttributeError):
        return ""


def call(path: str, data=None, method=None, raw=False, headers=None, auth=True, timeout=120):
    h = {"X-LV-Contract": str(contract.VERSION), **(headers or {})}
    if auth:
        token = store.get(site_url())
        if not token:
            raise UserError(NOT_PAIRED)
        h["Authorization"] = f"Bearer {token}"
    try:
        return net.request(site_url() + path, data=data, headers=h, method=method, raw=raw, timeout=timeout)
    except net.ApiError as e:
        if e.status == 426:
            raise UserError(_error_message(e.detail) or UPDATE) from None
        if e.status == 401 and auth:
            raise UserError(NOT_PAIRED) from None
        raise


def pair(name=None, sleep=None, out=print, clock=time.monotonic) -> str:
    """Show a code to type on the website, wait for it, keep the token. Returns the teacher's email."""
    sleep = sleep or time.sleep
    name = (name or platform.node().removesuffix(".local") or "Mac")[:60]
    start = call("/api/device/pair/start", {"name": name}, auth=False)
    out(f"On any computer, sign in at {start['verify_url']}, choose Add a Mac, and type this code: "
        f"{start['user_code']}")
    out(f"The code works for {start['expires_in'] // 60} minutes. Waiting…")
    deadline = clock() + start["expires_in"]
    while clock() < deadline:
        sleep(5)
        try:
            got = call("/api/device/pair/poll", {"device_code": start["device_code"]}, auth=False)
        except net.ApiError as e:
            if e.status == 428:
                continue
            if e.status == 410:
                break
            raise
        store.set(site_url(), got["token"])
        return got["teacher_email"]
    raise UserError("The code expired before it was entered. Run the pairing again for a new code.")


def status() -> dict:
    return call("/api/device/status")
```

Note on `net.request` and 428/410: they are not in its retry list, so they surface as `ApiError` at once.

In `lv/cli.py` `build_parser()`, after the `card` parser, add:

```python
    pr = sub.add_parser("pair", help="connect this Mac to slide2video.com (shows a code to type on the website)")
    pr.add_argument("--name", help="what the website calls this Mac (default: its computer name)")
    wk = sub.add_parser("worker", help="take this Mac's next job from slide2video.com and run it")
    wk.add_argument("--once", action="store_true", help="run at most one job, then exit (the default)")
    wk.add_argument("--status", action="store_true", help="show which account this Mac is connected to")
```

In `dispatch()`, after the `card` branch, add:

```python
    if args.cmd == "pair":
        from . import site
        email = site.pair(name=args.name)
        print(f"This Mac is connected to {site.site_url()} for {email}.")
        return 0
    if args.cmd == "worker":
        from . import site
        if args.status:
            s = site.status()
            print(f"Connected to {site.site_url()} as {s['teacher_email']} (this Mac: {s['device_name']}).")
            return 0
        from . import worker
        return worker.run_once()
```

(`lv/worker.py` arrives in Task 3; until then `worker` without `--status` raises ImportError, which no test in
this task exercises.)

- [ ] **Step 5: Run the tests**

Run: `uv run pytest -q tests/test_site.py tests/test_contract.py`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add lesson-videos/scripts/lv/site.py lesson-videos/scripts/lv/config.py lesson-videos/scripts/lv/cli.py \
  tests/site_fake.py tests/conftest.py tests/test_site.py
git commit -m "lesson-videos: connect a Mac to slide2video.com (pair, worker --status, Keychain token)"
```

---

### Task 3: `worker --once` (claim, run Claude, publish, error cards)

**Files:**
- Create: `lesson-videos/scripts/lv/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `site.call`, `site.site_url`, `contract.problems`, `contract.VERSION`, `keys.redact`,
  `narrate.read_timing(ch_dir) -> dict` (keys `duration`, `scenes[{id, start, dur, …}]`),
  `paths.chapter(ch_dir).code` (folder holding `script.json`), `util.safe_name`, fixtures `fake_site`/`paired`.
- Produces:
  - `worker.lessons_root() -> Path`; `worker.lesson_dir(lesson: dict) -> Path`
  - `worker.claude_command(lv: str) -> list[str]`; `worker.lv_command() -> str`
  - `worker.run_claude(cmd: list[str], cwd: Path, log: Path) -> int`
  - `worker.run_once(claude=None, out=print) -> int` (0 = idle or sent a non-error card; 1 = sent an error card)
  - `worker.error_card(message: str, log: str, now=None) -> dict`
  - `worker.timing_for(ch_dir: Path) -> dict | None`

- [ ] **Step 1: Write the failing tests**

`tests/test_worker.py`:

```python
import datetime as dt
import hashlib
import json
import os

import pytest

from lv import worker
from lv.util import read_json, write_json, write_text

DECK = b"pretend pptx bytes"
LES = "les_0123456789abcdefghijkl"


def _turn(kind="start", tid="trn_0123456789abcdefghijkl", path="in/water-cycle.pptx", **extra):
    return {"contract": 1, "lesson": {"id": LES, "title": "Unit 3: Water/Cycle"},
            "turn": {"id": tid, "seq": 1, "kind": kind, "lease_seconds": 1800},
            "files": [{"id": "fil_0123456789abcdefghijkl", "name": "water-cycle.pptx", "kind": "deck",
                       "sha256": hashlib.sha256(DECK).hexdigest(), "size": len(DECK), "path": path}], **extra}


@pytest.fixture
def lessons(tmp_path, monkeypatch):
    root = tmp_path / "Lesson Videos"
    monkeypatch.setenv("LV_LESSONS_DIR", str(root))
    return root


def _claude_writing(card, also=None, code=0, log="ok\n"):
    calls = []

    def fake(cmd, cwd, logfile):
        calls.append((cmd, cwd))
        logfile.write_text(log, encoding="utf-8")
        if also:
            also(cwd)
        if card is not None:
            write_json(cwd / "site" / "card.json", card)
        return code
    fake.calls = calls
    return fake


QUESTIONS = {"contract": 1, "kind": "questions", "message": "Questions",
             "questions": [{"id": "grade", "text": "Grade?", "options": [{"label": "6–8"}]}]}


def test_no_turn_is_quiet(paired, lessons):
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert paired.finished == []


def test_start_turn_downloads_runs_claude_and_sends_card(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    fake = _claude_writing(QUESTIONS)
    assert worker.run_once(claude=fake) == 0
    folder = worker.lesson_dir({"id": LES, "title": "x"})
    assert folder.name == f"Unit 3- Water-Cycle ({LES})"
    assert (folder / "in" / "water-cycle.pptx").read_bytes() == DECK
    assert read_json(folder / "site" / "turn.json")["turn"]["kind"] == "start"
    assert (folder / "site" / "lv.txt").read_text(encoding="utf-8").strip() == worker.lv_command()
    assert fake.calls[0][1] == folder
    assert paired.finished == [("trn_0123456789abcdefghijkl", QUESTIONS)]


def test_existing_deck_with_same_hash_is_not_downloaded_again(paired, lessons):
    folder = worker.lesson_dir({"id": LES, "title": "Unit 3: Water/Cycle"})
    write_text(folder / "in" / "keep.txt", "")
    (folder / "in" / "water-cycle.pptx").write_bytes(DECK)
    paired.turns.append(_turn())  # paired.files is empty: a download would 404
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert paired.finished[0][1]["kind"] == "questions"


def test_damaged_download_becomes_error(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = b"something else"
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 1
    assert paired.finished[0][1]["kind"] == "error" and "damaged" in paired.finished[0][1]["message"]


@pytest.mark.parametrize("path", ["in/../x.pptx", "/etc/passwd", "in/.hidden"])
def test_bad_turn_paths_are_refused_before_writing(paired, lessons, path):
    paired.turns.append(_turn(path=path))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    fake = _claude_writing(QUESTIONS)
    assert worker.run_once(claude=fake) == 1
    assert fake.calls == [] and paired.finished[0][1]["kind"] == "error"
    assert not (lessons.parent / "x.pptx").exists()


def _chapter(folder):
    ch = folder / "lesson-videos" / "_work" / "ch1"
    write_json(ch / "script.json", {"chapter": "1", "title": "Water", "scenes": [
        {"id": "hook", "say": "Where does rain come from? Let us find out today together."},
        {"id": "condensation", "say": "When warm, moist air rises it cools."}]})
    write_text(ch / "build" / "timing.js", "window.TIMING = " + json.dumps(
        {"duration": 20.0, "scenes": [{"id": "hook", "start": 0, "dur": 8.0}, {"id": "condensation", "start": 8.0, "dur": 12.0}]}) + ";\n")
    out = folder / "lesson-videos"
    (out / "Chapter 1 - Water.mp4").write_bytes(b"mp4")
    (out / "Chapter 1 - Water.vtt").write_bytes(b"WEBVTT")
    (ch / "build" / "final.jpg").write_bytes(b"jpg")


REVIEW = {"contract": 1, "kind": "review", "message": "Chapter 1 is ready.", "chapter": 1,
          "video": "lesson-videos/Chapter 1 - Water.mp4", "captions": "lesson-videos/Chapter 1 - Water.vtt",
          "stills": "lesson-videos/_work/ch1/build/final.jpg"}


def test_review_card_uploads_video_captions_stills_and_timing(paired, lessons):
    paired.turns += [_turn("approve"), _turn("feedback", tid="trn_1123456789abcdefghijkl")]
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(REVIEW, also=_chapter)) == 0
    sent = paired.finished[0][1]
    assert sent["version"] == 1
    assert sent["video"] == "out/ch1/v1/Chapter 1 - Water.mp4"
    assert paired.uploads["out/ch1/v1/Chapter 1 - Water.mp4"] == ("video/mp4", b"mp4")
    assert paired.uploads["out/ch1/v1/Chapter 1 - Water.vtt"][0] == "text/vtt"
    timing = json.loads(paired.uploads["out/ch1/v1/timing.json"][1])
    assert timing["scenes"][1] == {"id": "condensation", "start": 8.0, "dur": 12.0, "label": "Condensation",
                                   "first_words": "When warm, moist air rises it cools."}
    assert worker.run_once(claude=_claude_writing(REVIEW, also=_chapter)) == 0
    assert paired.finished[1][1]["video"] == "out/ch1/v2/Chapter 1 - Water.mp4"


def test_card_path_outside_the_lesson_is_an_error(paired, lessons, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    paired.turns.append(_turn("approve"))
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    card = {**REVIEW, "video": "../../secret.txt"}
    assert worker.run_once(claude=_claude_writing(card)) == 1
    assert paired.uploads == {} and paired.finished[0][1]["kind"] == "error"


def test_claude_failure_sends_redacted_log(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    log = "starting\nkey was sk_0123456789abcdef0123456789abcdef\ncrashed\n"
    assert worker.run_once(claude=_claude_writing(None, code=1, log=log)) == 1
    card = paired.finished[0][1]
    assert card["kind"] == "error" and "sk_0123" not in card["log_tail"] and "crashed" in card["log_tail"]


def test_invalid_card_is_an_error(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing({"contract": 1, "kind": "plan", "message": "x"})) == 1
    assert "couldn't be read" in paired.finished[0][1]["message"]


def test_usage_limit_sets_retry_after():
    now = dt.datetime(2026, 10, 14, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
    card = worker.error_card("Claude stopped.", "5-hour limit reached ∙ resets 3pm\n", now=now)
    assert card["retry_after"] == "2026-10-14T15:00:00-07:00" and "usage limit" in card["message"]
    later = now.replace(hour=16)
    assert worker.error_card("x", "limit reached ∙ resets 3pm", now=later)["retry_after"].startswith("2026-10-15T15:00")
    assert worker.error_card("x", "some other failure", now=now)["retry_after"] is None


def test_delete_turn_removes_the_folder_without_claude(paired, lessons):
    folder = worker.lesson_dir({"id": LES, "title": "Unit 3: Water/Cycle"})
    write_text(folder / "in" / "x.txt", "x")
    paired.turns.append(_turn("delete", delete=True))
    fake = _claude_writing(QUESTIONS)
    assert worker.run_once(claude=fake) == 0
    assert not folder.exists() and fake.calls == []
    assert paired.finished[0][1]["kind"] == "done"


def test_live_lock_makes_a_second_run_exit(paired, lessons):
    lessons.mkdir(parents=True)
    (lessons / ".worker.lock").write_text(str(os.getpid()), encoding="utf-8")
    paired.turns.append(_turn())
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert paired.finished == [] and len(paired.turns) == 1


def test_stale_lock_is_taken_over(paired, lessons):
    lessons.mkdir(parents=True)
    (lessons / ".worker.lock").write_text("999999999", encoding="utf-8")
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(QUESTIONS)) == 0
    assert len(paired.finished) == 1 and not (lessons / ".worker.lock").exists()


def test_heartbeat_sends_the_progress_line(paired, lessons, monkeypatch):
    monkeypatch.setattr(worker, "HEARTBEAT", 0.05)
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK

    def slow(cwd):
        import time
        write_text(cwd / "site" / "progress.txt", "Reading the deck\nNarrating 3 of 12 scenes\n")
        time.sleep(0.3)
    assert worker.run_once(claude=_claude_writing(QUESTIONS, also=slow)) == 0
    assert ("trn_0123456789abcdefghijkl", "Narrating 3 of 12 scenes") in paired.heartbeats


def test_claude_command_limits_tools(monkeypatch):
    monkeypatch.setattr(worker.shutil, "which", lambda n: f"/usr/local/bin/{n}")
    cmd = worker.claude_command('"/usr/bin/uv" run "/p/lesson-videos.py"')
    assert cmd[1:3] == ["-p", worker.PROMPT]
    assert 'Bash("/usr/bin/uv" run "/p/lesson-videos.py":*)' in cmd
    i = cmd.index("--disallowedTools")
    assert cmd[i + 1:] == ["WebFetch", "WebSearch"]
    assert not any(t.startswith("Bash") and t != 'Bash("/usr/bin/uv" run "/p/lesson-videos.py":*)' for t in cmd)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_worker.py`
Expected: ERROR `ImportError: cannot import name 'worker' from 'lv'`.

- [ ] **Step 3: Implement `lv/worker.py`**

```python
"""`worker --once`: take this Mac's next turn from slide2video.com, run Claude Code on it in the lesson's folder,
and send back the card Claude wrote (or an error card)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import urllib.parse
from pathlib import Path

from . import config, contract, keys, narrate, paths, site
from .util import UserError, read_json, read_text, safe_name, write_json, write_text

PROMPT = "Run /lesson-videos:make in site mode for this folder."
HEARTBEAT = 60                 # seconds between lease renewals
CLAUDE_TIMEOUT = 3 * 3600      # one turn never runs longer than this
CONTENT_TYPES = {".mp4": "video/mp4", ".vtt": "text/vtt", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".json": "application/json"}
LIMIT = re.compile(r"(usage limit|limit reached|out of (?:extra )?usage)", re.I)
RESET = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)", re.I)


def lessons_root() -> Path:
    return Path(os.environ.get("LV_LESSONS_DIR") or Path.home() / "Lesson Videos")


def lesson_dir(lesson: dict) -> Path:
    """The lesson's folder, found by its id (the title on the site may have changed since)."""
    root, tag = lessons_root(), f"({lesson['id']})"
    if root.exists():
        for d in root.iterdir():
            if d.is_dir() and d.name.endswith(tag):
                return d
    return root / f"{safe_name(lesson['title'])[:80]} {tag}"


def lv_command() -> str:
    return f'"{shutil.which("uv") or "uv"}" run "{config.ENTRY}"'


def claude_command(lv: str) -> list[str]:
    claude = shutil.which("claude")
    if not claude:
        raise UserError("Claude Code isn't installed on this Mac (no `claude` command). Install it from "
                        "https://claude.com/claude-code, sign in once, then try again.")
    return [claude, "-p", PROMPT, "--allowedTools", f"Bash({lv}:*)", "Read", "Write", "Edit", "Glob", "Grep",
            "--disallowedTools", "WebFetch", "WebSearch"]


def run_claude(cmd: list[str], cwd: Path, log: Path) -> int:
    with open(log, "w", encoding="utf-8") as f:
        return subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              timeout=CLAUDE_TIMEOUT).returncode


def _reset_time(log: str, now: dt.datetime) -> dt.datetime:
    m = RESET.search(log)
    if not m:
        return now + dt.timedelta(hours=1)
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    t = now.replace(hour=hour, minute=int(m.group(2) or 0), second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)


def error_card(message: str, log: str, now=None) -> dict:
    card = {"contract": contract.VERSION, "kind": "error", "message": message,
            "log_tail": keys.redact("\n".join(log.splitlines()[-40:]))[:20000], "retry_after": None}
    if LIMIT.search(log):
        card["message"] = "Your Claude plan's usage limit was reached; this continues automatically when it resets."
        card["retry_after"] = _reset_time(log, now or dt.datetime.now().astimezone()).isoformat()
    return card


def timing_for(ch_dir: Path) -> dict | None:
    """Scene marks for the player: id, start, length, a label and the first words of the narration."""
    try:
        T = narrate.read_timing(ch_dir)
        say = {s["id"]: s.get("say", "") for s in read_json(paths.chapter(ch_dir).code / "script.json")["scenes"]}
    except (OSError, ValueError, KeyError, UserError):
        return None
    return {"duration": T["duration"], "scenes": [
        {"id": s["id"], "start": s["start"], "dur": s["dur"], "label": s["id"].replace("_", " ").replace("-", " ").title(),
         "first_words": " ".join(say.get(s["id"], "").split()[:8])} for s in T["scenes"]]}


def _lock(root: Path) -> Path | None:
    root.mkdir(parents=True, exist_ok=True)
    f = root / ".worker.lock"
    try:
        fd = os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            os.kill(int(read_text(f).strip()), 0)
            return None                      # another run is alive
        except PermissionError:
            return None                      # alive, owned by someone else
        except (ValueError, ProcessLookupError, OSError):
            f.unlink(missing_ok=True)        # stale
            return _lock(root)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return f


def _last_line(f: Path) -> str:
    try:
        lines = [l for l in read_text(f).splitlines() if l.strip()]
    except OSError:
        return ""
    return lines[-1][:200] if lines else ""


class _Heartbeat(threading.Thread):
    def __init__(self, turn_id: str, progress: Path):
        super().__init__(daemon=True)
        self.turn_id, self.progress, self.done = turn_id, progress, threading.Event()

    def run(self):
        while not self.done.wait(HEARTBEAT):
            try:
                site.call(f"/api/device/turns/{self.turn_id}/heartbeat", {"progress": _last_line(self.progress)})
            except Exception:  # noqa: BLE001  a missed heartbeat only shortens the lease
                pass


def _sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _fetch_inputs(turn: dict, folder: Path) -> None:
    for f in turn["files"]:
        dest = folder / f["path"]
        if dest.is_file() and _sha256(dest) == f["sha256"]:
            continue
        data = site.call(f"/api/device/files/{f['id']}", raw=True, timeout=600)
        if hashlib.sha256(data).hexdigest() != f["sha256"]:
            raise UserError(f"{f['name']} arrived damaged; try again.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _upload(turn_id: str, path: str, data: bytes, content_type: str) -> None:
    site.call(f"/api/device/turns/{turn_id}/files?path={urllib.parse.quote(path)}", data=data, method="PUT",
              headers={"Content-Type": content_type}, timeout=900)


def _next_version(folder: Path, chapter: int) -> int:
    f = folder / "site" / "versions.json"
    d = read_json(f) if f.exists() else {}
    d[str(chapter)] = d.get(str(chapter), 0) + 1
    write_json(f, d)
    return d[str(chapter)]


def _inside(folder: Path, rel: str) -> Path:
    p = (folder / rel).resolve()
    if folder.resolve() not in p.parents or not p.is_file():
        raise UserError(f"The card names {rel!r}, which isn't a file in this lesson's folder.")
    return p


def _publish(card: dict, folder: Path, turn_id: str) -> dict:
    """Upload what a review card names and point the card at the uploaded copies (out/chN/vK/…)."""
    if card["kind"] != "review":
        return card
    local = {k: _inside(folder, card[k]) for k in ("video", "captions", "stills") if card.get(k)}
    ch = card["chapter"]
    card = {**card, "version": _next_version(folder, ch)}
    base = f"out/ch{ch}/v{card['version']}"
    for k, f in local.items():
        _upload(turn_id, f"{base}/{f.name}", f.read_bytes(), CONTENT_TYPES.get(f.suffix.lower(), "application/octet-stream"))
        card[k] = f"{base}/{f.name}"
    timing = timing_for(folder / "lesson-videos" / "_work" / f"ch{ch}")
    if timing:
        _upload(turn_id, f"{base}/timing.json", json.dumps(timing).encode("utf-8"), "application/json")
        card["timing"] = f"{base}/timing.json"
    return card


def _finish(turn_id: str, card: dict) -> None:
    site.call(f"/api/device/turns/{turn_id}/finish", card)


def _log_text(log: Path) -> str:
    return read_text(log) if log.exists() else ""


def _run_turn(turn: dict, claude, out) -> int:
    tid, kind = turn["turn"]["id"], turn["turn"]["kind"]
    folder = lesson_dir(turn["lesson"])
    out(f"Working on “{turn['lesson']['title']}” ({kind}).")
    if kind == "delete":
        shutil.rmtree(folder, ignore_errors=True)
        _finish(tid, {"contract": contract.VERSION, "kind": "done", "message": "Removed from this Mac."})
        return 0
    sitedir = folder / "site"
    sitedir.mkdir(parents=True, exist_ok=True)
    (sitedir / "card.json").unlink(missing_ok=True)
    write_text(sitedir / "progress.txt", "Starting\n")
    log = sitedir / "claude.log"
    try:
        _fetch_inputs(turn, folder)
        write_json(sitedir / "turn.json", turn)
        lv = lv_command()
        write_text(sitedir / "lv.txt", lv + "\n")
        beat = _Heartbeat(tid, sitedir / "progress.txt")
        beat.start()
        try:
            code = claude(claude_command(lv), folder, log)
        finally:
            beat.done.set()
        card_file = sitedir / "card.json"
        if code != 0 or not card_file.exists():
            card = error_card("Claude stopped before it finished this step.", _log_text(log))
        else:
            card = read_json(card_file)
            bad = contract.problems("card", card)
            card = (error_card("Claude's reply couldn't be read: " + "; ".join(bad[:3]), _log_text(log)) if bad
                    else _publish(card, folder, tid))
    except subprocess.TimeoutExpired:
        card = error_card("Claude took more than 3 hours on this step and was stopped.", _log_text(log))
    except ValueError as e:  # card.json that isn't JSON
        card = error_card(f"Claude's reply couldn't be read: {e}", _log_text(log))
    except UserError as e:
        card = error_card(str(e), _log_text(log))
    _finish(tid, card)
    out(f"Sent back: {card['kind']}. {card['message']}")
    return 1 if card["kind"] == "error" else 0


def run_once(claude=None, out=print) -> int:
    root = lessons_root()
    lock = _lock(root)
    if lock is None:
        out("Another worker run is still going.")
        return 0
    try:
        turn = site.call("/api/device/next")
        if not turn:
            return 0
        bad = contract.problems("turn", turn)
        if bad:
            tid = (turn.get("turn") or {}).get("id")
            if tid:
                _finish(tid, error_card("This job doesn't match what this plugin understands: " + "; ".join(bad[:3]), ""))
            return 1
        return _run_turn(turn, claude or run_claude, out)
    finally:
        lock.unlink(missing_ok=True)
```

Note: the bad-turn branch only finishes when the turn id itself is well formed enough to read; a turn id that
fails its own pattern is still posted back (the site validates ownership by token, not by id shape).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q tests/test_worker.py`
Expected: all pass. If `test_bad_turn_paths_are_refused_before_writing` fails for `/etc/passwd`, check the turn
schema's `path` pattern from Task 1 (it must start with `^in/`).

- [ ] **Step 5: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: all pass (the earlier 473 plus the new tests).

```bash
git add lesson-videos/scripts/lv/worker.py tests/test_worker.py
git commit -m "lesson-videos: worker --once runs one slide2video turn with Claude Code and sends back the card"
```

---

### Task 4: Site mode in the `make` skill, the setup step, docs and release 0.5.0

**Files:**
- Modify: `lesson-videos/skills/make/SKILL.md`, `lesson-videos/skills/setup/SKILL.md`, `SERVICES.md`,
  `lesson-videos/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `lesson-videos/scripts/lv/__init__.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: commands `card`, `pair`, `worker` (Tasks 1–3); `site/turn.json`, `site/lv.txt`, `site/progress.txt`,
  `site/card.json` (Task 3's folder layout).
- Produces: the skill text Claude follows when `worker` runs it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_skills.py`:

```python
def test_make_skill_has_a_site_mode():
    _, text = frontmatter("make")
    site = text.split("## Site mode", 1)[1]
    for needed in ("site/turn.json", "site/card.json", "site/progress.txt", "site/lv.txt", "LV card",
                   '"questions"', '"plan"', '"review"', '"done"', "student", "Never ask", "stop"):
        assert needed in site, needed


def test_setup_offers_to_connect_this_mac():
    _, text = frontmatter("setup")
    assert "LV pair" in text and "slide2video.com" in text
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_skills.py -k "site_mode or connect_this_mac"`
Expected: FAIL (`IndexError: list index out of range` for the missing `## Site mode`).

- [ ] **Step 3: Write the site mode section**

Append to `lesson-videos/skills/make/SKILL.md` (after section 8):

````markdown
## Site mode (slide2video.com)

Use this mode when the folder you were started in has `site/turn.json`. The teacher is not at this computer:
they answer on slide2video.com, and `LV worker` ran you for one **turn**. **Never ask in chat** and never wait
for an answer: do the work for this turn, write `site/card.json`, check it with `LV card "site/card.json"`, fix
anything it reports, and **stop**.

- **LV in site mode:** use the command line in `site/lv.txt` exactly, in place of the LV line above (it is the
  same plugin with absolute paths). Only that command, file reading and file editing are allowed.
- **Folders:** the deck is in `in/`; `WORK` is `lesson-videos/_work` (pass `--work "lesson-videos/_work"` to
  `ingest`); finished videos land in `lesson-videos/`.
- **Progress:** at each step, append one short line to `site/progress.txt` that a teacher would understand
  ("Reading the deck", "Narrating 3 of 12 scenes", "Rendering chapter 1"). The website shows the last line.
- **The teacher's input** is in `site/turn.json`: `turn.kind`, plus `instructions` (start), `answers` (answer),
  `feedback` (change, feedback). Anything the cards didn't settle uses this skill's defaults.
- **One chapter per turn**, no parallel helper agents.

What to do for each `turn.kind`, and which card ends it:

| `turn.kind` | Do | Card |
|---|---|---|
| `start` | Steps 0–3: ingest, read everything, write `brief.md`. First check every slide for **student information** (names of students, class photos, graded student work): the website forbids it. | `"questions"`: if student information was found, one question listing it ("Remove these slides" / "They're not students"), and nothing else. Otherwise the interview (grade, chapter split, length, voice; options from step 2) plus one question per possible issue in the slides (follow the slide / follow the correction / leave it out). |
| `answer` | Apply the answers. If the student-information question was answered "Remove", leave those slides out entirely. Step 4: write `plan.md`, run `estimate`. | `"plan"`: `markdown` = the outline in brief; `estimate` = `{"usd": <total>, "minutes": <per video>, "chapters": <N>}`. |
| `change` | Revise `plan.md` from `feedback`, re-run `estimate`. | `"plan"` again. |
| `approve` | Note the approval and date at the top of `plan.md`. Steps 5–6: music/clips if approved, then chapter 1 (6.1–6.7). | `"review"` for chapter 1. |
| `feedback` | Apply `feedback` to the chapter just reviewed (re-narrate only changed scenes), re-render it. | `"review"` for the same chapter. |
| `continue` | Write the agreed style notes at the top of `plan.md` if not there yet. Make the next unfinished chapter (`LV status`). If none is left, step 8. | `"review"` for that chapter, or `"done"`. |

Card formats (all start with `"contract": 1`, `"kind"` and a one-line `"message"` for the teacher):

```json
{"contract": 1, "kind": "questions", "message": "A few questions before I plan the videos.",
 "questions": [{"id": "grade", "text": "What grade are the students?",
                "options": [{"label": "Grades 6–8", "detail": "Middle school"}], "other": true}]}
```

- `"questions"`: up to 8 questions; ids are short lowercase words; each has 1–6 options (`label`, optional
  `detail`); `"other": true` lets the teacher type their own answer.
- `"plan"`: `"markdown"` and `"estimate"` as above.
- `"review"`: `"chapter": N`, `"video"` (the MP4 path relative to this folder, e.g.
  `"lesson-videos/Chapter 1 - The Water Cycle.mp4"`), `"captions"` (its `.vtt`), `"stills"` (the `final.jpg`
  that `render` printed, relative to this folder). The worker uploads them; don't add `version` or `timing`.
- `"done"`: `"chapters": [{"chapter": 1, "title": "…"}]` and `"readme"` (the README text from step 8).

If something fails that the teacher must fix (a deck that can't be read, a key that was rejected), write a
`"questions"` card whose message explains it in one line, with one question and options for what to do next.
````

- [ ] **Step 4: Add the setup step**

In `lesson-videos/skills/setup/SKILL.md`, append as the last section:

```markdown
## Connect this Mac to slide2video.com (optional)

Only if the teacher was invited to slide2video.com and wants this Mac to make videos for lessons they upload
there. On a Mac, run `LV pair`. It prints a short code and the website address: the teacher signs in there (on
any computer), chooses **Add a Mac** and types the code. Then run `LV worker --status` to confirm the
connection. For now, run `LV worker --once` whenever the website says a lesson is waiting for this Mac.
```

- [ ] **Step 5: SERVICES.md and version 0.5.0**

In `SERVICES.md`, add a row/entry in the same format as the existing ones for **slide2video.com**: used by
`lesson-videos` (`pair`, `worker`); auth = a per-Mac device token in the macOS Keychain (service
`slide2video`); what is sent = the files the teacher uploaded on the site come down, the videos, captions,
stills and timing Claude made go up.

Bump `0.4.5` → `0.5.0` in `lesson-videos/.claude-plugin/plugin.json`, the lesson-videos entry of
`.claude-plugin/marketplace.json` (only that entry), and `lesson-videos/scripts/lv/__init__.py`.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -q`
Expected: all pass, including `test_skills_use_only_real_commands` (it now sees `LV card`, `LV pair`,
`LV worker`, which are real commands) and `test_packaging.py`.

- [ ] **Step 7: Commit**

```bash
git add lesson-videos/skills/make/SKILL.md lesson-videos/skills/setup/SKILL.md SERVICES.md \
  lesson-videos/.claude-plugin/plugin.json .claude-plugin/marketplace.json lesson-videos/scripts/lv/__init__.py \
  tests/test_skills.py
git commit -m "lesson-videos 0.5.0: site mode for slide2video.com (make skill), connect-this-Mac step in setup"
```

---

### Task 5: Real run against a local site (needs M1-B), then merge

This task runs after M1-B's Task 8 (`npm run dev` serving the site locally with a seeded teacher). If M1-B is not
ready, stop after Task 4, merge, and leave this task for the M1-B executor (it is repeated there as its final
task).

- [ ] **Step 1: Pair against the local site**

Run: `LV_SITE_URL=http://localhost:8787 uv run lesson-videos/scripts/lesson-videos.py pair --name "Dev Mac"`
Expected: prints a code; entering it on `http://localhost:8787/devices` (signed in with the dev bypass from M1-B)
makes the command print `This Mac is connected to http://localhost:8787 for <email>.`

- [ ] **Step 2: One full lesson by hand**

Upload `examples/water-cycle.pptx` on the local site, then run
`LV_SITE_URL=http://localhost:8787 uv run lesson-videos/scripts/lesson-videos.py worker --once` after each answer on
the site. Expected sequence of cards: `questions` → `plan` → `review` (chapter 1, playable on the site) →
`done` after **Looks good, continue**. If Claude reports a permission denial on the LV command, record the exact
command it tried in the ledger: the `--allowedTools` rule format is what M2's spike settles.

- [ ] **Step 3: Merge and push**

```bash
git checkout main && git pull --ff-only && git merge --no-ff slide2video-m1a -m "Merge lesson-videos 0.5.0 (slide2video site mode)"
uv run pytest -q && git push origin main && git branch -d slide2video-m1a
```
