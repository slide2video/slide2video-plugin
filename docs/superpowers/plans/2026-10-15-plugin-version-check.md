# Plugin Version Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lesson-videos reports its version to slide2video.com on every call; a different major is refused with the
update steps, an older version within the major is told (in Claude Code and on the Devices list) that an update is
available.

**Architecture:** The plugin repo's `site-contract/contract.json` becomes `{"plugin": "1.0.0"}`; its major is the
contract version. The plugin sends `X-LV-Plugin` (plus the old `X-LV-Contract` during rollout) and remembers the
website's `X-LV-Latest`. The website stores each computer's version, refuses a different major with a 426 whose
message it owns, and shows the version on Devices and in the waiting-lesson panel.

**Tech Stack:** Python 3 stdlib + pytest (plugin, `uv run pytest -q` from `~/Projects/plugins`); Cloudflare
Workers + Hono + D1 + vitest (`npm run check && npm test` from `~/Projects/slide2video`).

**Spec:** `docs/superpowers/specs/2026-10-15-plugin-version-check-design.md` (plugins repo). Read it first.

## Global Constraints

- Two repos. Tasks 1–4 are in `~/Projects/plugins` on branch `plugin-version-check` (already created; the spec is
  committed there). Tasks 5–7 are in `~/Projects/slide2video` on a new branch `plugin-version-check` off `main`.
  Each repo's own `AGENTS.md` applies only inside that repo. Both are Tier B: branch, test, merge to `main`, push.
- Version format: `MAJOR.MINOR.PATCH`, digits only, each part 1–4 digits (`^\d{1,4}\.\d{1,4}\.\d{1,4}$`).
  Anything else counts as "too old" and is **never echoed** into a message or a page.
- New plugin version: **1.0.0** in `lesson-videos/.claude-plugin/plugin.json`, the `lesson-videos` entry of
  `.claude-plugin/marketplace.json`, and `lesson-videos/scripts/lv/__init__.py`.
- Update steps, verbatim, everywhere: `run /plugin update lesson-videos, then close and reopen Claude Code, then run
  /lesson-videos:serve`.
- `NEEDS_UPDATE` text: `This computer has lesson-videos {have}; slide2video.com needs {major}.x. To update: run
  /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve.` When the header
  is missing or unreadable, `lesson-videos {have}` becomes `an older version of lesson-videos` (Task 5's
  `needsUpdate` builds both).
- `SITE_BEHIND` text: `slide2video.com hasn't caught up with lesson-videos {have} yet. Nothing to do on this
  computer; try again later.`
- Plugin update line: `A newer lesson-videos ({latest}) is available. To update: run /plugin update lesson-videos,
  then close and reopen Claude Code, then run /lesson-videos:serve.`
- Python: `encoding="utf-8"` on every file read/write; no new dependencies. Website: every query scoped to the
  teacher; never log tokens.
- Do **not** deploy the website or apply the remote migration: that waits for Daniel (Task 8).

## Review Focus

1. **A junk `X-LV-Plugin` header** (`"1.0"`, `"1.0.0-beta"`, `"<script>"`, 5-digit parts) → refused as too old,
   and the junk never appears in the 426 message, the database or the Devices page. Pinned in Task 5 (parser) and
   Task 6 (stored as NULL, message says "an older version").
2. **A freshly paired computer** must not show "Needs an update" before its first call: pairing stores the version
   it paired with. Pinned in Task 6.
3. **`X-LV-Latest` on every non-refused answer**, including 204 from `/next` and raw file downloads. Pinned in
   Task 6.
4. **The website redeployed while `--watch` runs**: the update line appears once per new website version, never
   on every poll; a plugin newer than the website (same major) never warns. Pinned in Tasks 2 and 3.
5. **A computer that needs an update is never "Starting soon"** and shows no Disconnect button, even though its
   refused calls still update last-seen. Pinned in Task 7.

---

## Task 1: Contract and version in the plugin

**Files:**
- Modify: `lesson-videos/site-contract/contract.json`
- Modify: `lesson-videos/site-contract/README.md` (add a "Versions" paragraph)
- Modify: `lesson-videos/scripts/lv/contract.py`
- Create: `lesson-videos/scripts/lv/version.py`
- Modify: `lesson-videos/scripts/lv/__init__.py`, `lesson-videos/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Test: `tests/test_version.py` (new), `tests/test_contract.py`, `tests/test_packaging.py`

**Interfaces:**
- Produces: `lv.version.parse(s) -> tuple[int, int, int] | None`; `lv.version.update_line(latest) -> str | None`
  (the update line when `latest` parses, has the plugin's major, and is newer than `lv.__version__`; else None);
  `lv.version.STEPS` (the update steps string); `lv.contract.PLUGIN: str`; `lv.contract.VERSION: int` (major of
  `PLUGIN`).

- [ ] **Step 1: Write the failing tests**

`tests/test_version.py`:

```python
import pytest

import lv
from lv import version


@pytest.mark.parametrize("s, want", [
    ("1.0.0", (1, 0, 0)), ("12.34.5678", (12, 34, 5678)),
    ("1.0", None), ("1.0.0-beta", None), ("v1.0.0", None), ("", None), (None, None),
    ("12345.0.0", None), (" 1.0.0", None), ("<script>", None), (1, None),
])
def test_parse(s, want):
    assert version.parse(s) == want


def test_update_line_only_for_a_newer_version_with_the_same_major(monkeypatch):
    monkeypatch.setattr(lv, "__version__", "1.2.3")
    line = version.update_line("1.3.0")
    assert line == ("A newer lesson-videos (1.3.0) is available. To update: run /plugin update lesson-videos, "
                    "then close and reopen Claude Code, then run /lesson-videos:serve.")
    assert version.update_line("1.2.4").startswith("A newer lesson-videos (1.2.4)")
    for latest in ("1.2.3", "1.2.2", "1.0.0", "2.0.0", "0.9.0", "junk", None):
        assert version.update_line(latest) is None, latest
```

In `tests/test_contract.py` replace `test_version_is_an_integer` with:

```python
def test_contract_version_is_the_plugin_major():
    assert contract.PLUGIN == "1.0.0"
    assert contract.VERSION == 1
```

In `tests/test_packaging.py` add (and add `from lv import contract, version` to the imports):

```python
def test_site_contract_matches_the_plugin_major_and_is_not_newer():
    have, site = version.parse(lv.__version__), version.parse(contract.PLUGIN)
    assert have and site
    assert site[0] == have[0] and site <= have
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_version.py tests/test_contract.py tests/test_packaging.py`
Expected: FAIL (`lv.version` missing; `contract.PLUGIN` missing).

- [ ] **Step 3: Implement**

`lesson-videos/site-contract/contract.json`:

```json
{"plugin": "1.0.0"}
```

`lesson-videos/scripts/lv/version.py`:

```python
"""Plugin versions (MAJOR.MINOR.PATCH, digits only) and the line that says a newer one is available."""
from __future__ import annotations

import re

import lv

_VERSION = re.compile(r"(\d{1,4})\.(\d{1,4})\.(\d{1,4})")
STEPS = ("run /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve")


def parse(s) -> tuple[int, int, int] | None:
    m = _VERSION.fullmatch(s) if isinstance(s, str) else None
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def update_line(latest) -> str | None:
    """What to tell the teacher when the website is built for a newer version with this plugin's major."""
    have, site = parse(lv.__version__), parse(latest)
    if not have or not site or site[0] != have[0] or site <= have:
        return None
    return f"A newer lesson-videos ({latest}) is available. To update: {STEPS}."
```

`lesson-videos/scripts/lv/contract.py`: replace the `VERSION` line and the docstring's last sentence:

```python
"""The job contract with slide2video.com. Canonical schemas live in lesson-videos/site-contract/; the site keeps
a pinned copy. contract.json names the plugin version the site is built for; its major is the contract version."""
...
CONTRACT_DIR = config.PLUGIN_ROOT / "site-contract"
PLUGIN: str = read_json(CONTRACT_DIR / "contract.json")["plugin"]
VERSION: int = int(PLUGIN.split(".")[0])
```

Version files: `"version": "1.0.0"` in `lesson-videos/.claude-plugin/plugin.json` and in the `lesson-videos` entry
of `.claude-plugin/marketplace.json`; `__version__ = "1.0.0"` in `lesson-videos/scripts/lv/__init__.py`.

`lesson-videos/site-contract/README.md`, append:

```markdown
## Versions

`contract.json` `plugin` is the plugin version slide2video.com is built for. Its major is the contract version
(the schemas' `"contract": {"const": N}`). Every device call sends `X-LV-Plugin: <the plugin's version>`; the
website refuses a different major with a 426 whose `error` the plugin prints as is, and answers every other call
with `X-LV-Latest: <plugin>` so an older plugin can say an update is available.
```

- [ ] **Step 4: Run the whole gate**

Run: `uv run pytest -q`
Expected: PASS (`test_versions_agree` passes with all three at 1.0.0).

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/site-contract lesson-videos/scripts/lv/contract.py lesson-videos/scripts/lv/version.py \
  lesson-videos/scripts/lv/__init__.py lesson-videos/.claude-plugin/plugin.json .claude-plugin/marketplace.json \
  tests/test_version.py tests/test_contract.py tests/test_packaging.py
git commit -m "lesson-videos 1.0.0: contract.json names the plugin version; its major is the contract version"
```

## Task 2: The plugin sends its version and remembers the website's

**Files:**
- Modify: `lesson-videos/scripts/lv/net.py` (`request`: optional `on_headers`)
- Modify: `lesson-videos/scripts/lv/site.py` (`call`, `UPDATE`, `LATEST`)
- Modify: `lesson-videos/scripts/lv/cli.py:189-192` (`worker --status`)
- Modify: `tests/site_fake.py` (send `X-LV-Latest`, record `X-LV-Plugin`)
- Test: `tests/test_net.py`, `tests/test_site.py`

**Interfaces:**
- Consumes: `lv.version.update_line`, `lv.version.STEPS`, `lv.__version__`, `lv.contract.VERSION`.
- Produces: `net.request(..., on_headers=None)` calls `on_headers(response.headers)` after a successful open;
  `lv.site.LATEST: str | None` (last `X-LV-Latest` seen, any value); `FakeSite.latest` (str | None, header to
  send), `FakeSite.plugin_headers` (list of received `X-LV-Plugin` values).

- [ ] **Step 1: Write the failing tests**

`tests/test_net.py`, add:

```python
def test_on_headers_sees_the_response_headers(monkeypatch):
    class WithHeaders(Resp):
        headers = {"X-LV-Latest": "1.2.0"}
    monkeypatch.setattr(net, "_open", lambda req, timeout: WithHeaders(b"{}"))
    seen = []
    net.request("https://x.test/a", on_headers=seen.append, sleep=lambda s: None)
    assert seen == [{"X-LV-Latest": "1.2.0"}]
```

`tests/test_site.py`, add (and `import lv` at the top):

```python
def test_call_sends_its_version_and_the_old_contract_header(paired):
    site.call("/api/device/status")
    assert paired.plugin_headers[-1] == lv.__version__ == "1.0.0"
    assert paired.contract == 1  # the fake still checks X-LV-Contract: 1, as today's website does


def test_call_remembers_the_websites_version(paired, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    site.call("/api/device/status")
    assert site.LATEST is None  # an older website sends none
    paired.latest = "1.1.0"
    site.call("/api/device/next")  # 204 answers carry it too
    assert site.LATEST == "1.1.0"


def test_a_refusal_prints_the_websites_own_words(paired):
    paired.refuse = "slide2video.com hasn't caught up with lesson-videos 1.0.0 yet. Nothing to do on this computer; try again later."
    with pytest.raises(UserError) as e:
        site.call("/api/device/status")
    assert str(e.value) == paired.refuse


def test_the_fallback_update_message_says_to_reopen_claude_code():
    assert site.UPDATE == ("Update the lesson-videos plugin on this computer: run /plugin update lesson-videos, "
                           "then close and reopen Claude Code, then run /lesson-videos:serve.")


def test_status_names_the_version_and_an_available_update(paired, capsys, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    assert cli.main(["worker", "--status"]) == 0
    out = capsys.readouterr().out
    assert "(this device: Test Mac, lesson-videos 1.0.0)." in out and "newer" not in out
    paired.latest = "1.1.0"
    assert cli.main(["worker", "--status"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[1] == ("A newer lesson-videos (1.1.0) is available. To update: run /plugin update lesson-videos, "
                      "then close and reopen Claude Code, then run /lesson-videos:serve.")
    paired.latest = "1.0.0"
    assert cli.main(["worker", "--status"]) == 0
    assert "newer" not in capsys.readouterr().out
```

`tests/site_fake.py`: in `FakeSite.__init__` add `self.latest, self.plugin_headers, self.refuse = None, [], None`.
In `H._send`, before `self.end_headers()`:

```python
                if site.latest and code != 426:
                    self.send_header("X-LV-Latest", site.latest)
```

At the top of `H._route`, before the contract check:

```python
                site.plugin_headers.append(self.headers.get("X-LV-Plugin"))
                if site.refuse:
                    return self._send(426, {"error": site.refuse})
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_net.py tests/test_site.py`
Expected: FAIL (`on_headers` unexpected keyword; no `X-LV-Plugin`; `LATEST` missing; old status text).

- [ ] **Step 3: Implement**

`net.py`, `request` signature gains `on_headers=None`; inside the `with _open(req, timeout) as r:` block:

```python
            with _open(req, timeout) as r:
                if on_headers is not None:
                    on_headers(r.headers)
                payload = r.read()
```

`site.py`:

```python
import lv
from . import config, contract, net, version
...
UPDATE = f"Update the lesson-videos plugin on this computer: {version.STEPS}."
LATEST: str | None = None  # the plugin version the website said it is built for (X-LV-Latest), last seen


def _note_latest(headers) -> None:
    global LATEST
    value = headers.get("X-LV-Latest")
    if value:
        LATEST = value


def call(path: str, data=None, method=None, raw=False, headers=None, auth=True, timeout=120, retries=2):
    # X-LV-Contract only for websites deployed before 1.0.0; drop it in a later release
    h = {"X-LV-Plugin": lv.__version__, "X-LV-Contract": str(contract.VERSION), **(headers or {})}
    ...
        return net.request(site_url() + path, data=data, headers=h, method=method, raw=raw, timeout=timeout,
                           retries=retries, on_headers=_note_latest)
```

`cli.py` `worker --status` branch:

```python
        if args.status:
            import lv
            from . import version
            s = site.status()
            print(f"Connected to {site.site_url()} as {s['teacher_email']} "
                  f"(this device: {s['device_name']}, lesson-videos {lv.__version__}).")
            line = version.update_line(site.LATEST)
            if line:
                print(line)
            return 0
```

- [ ] **Step 4: Run the whole gate**

Run: `uv run pytest -q`
Expected: PASS. `test_cli_pair_and_status` still finds the teacher's email.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/net.py lesson-videos/scripts/lv/site.py lesson-videos/scripts/lv/cli.py \
  tests/site_fake.py tests/test_net.py tests/test_site.py
git commit -m "lesson-videos: every website call sends X-LV-Plugin; --status names the version and a newer one"
```

## Task 3: `worker --watch` names its version and says when an update is available

**Files:**
- Modify: `lesson-videos/scripts/lv/worker.py` (`watch`)
- Test: `tests/test_worker_watch.py`

**Interfaces:**
- Consumes: `lv.site.LATEST`, `lv.version.update_line`, `lv.__version__`, `FakeSite.latest`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_worker_watch.py`, change the expected start line in
`test_watch_start_line_names_the_site_teacher_and_computer` to:

```python
    assert lines[0] == (f"Making videos for {paired.url} as teacher@example.org on Test Mac with lesson-videos 1.0.0. "
                        "Waiting for lessons… (stop with Ctrl-C, or Disconnect on the website)")
```

Add (with `from lv import site` in the imports):

```python
UPDATE_11 = ("A newer lesson-videos (1.1.0) is available. To update: run /plugin update lesson-videos, then close "
             "and reopen Claude Code, then run /lesson-videos:serve.")


def test_watch_says_once_that_an_update_is_available_and_keeps_working(paired, lessons, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    paired.latest = "1.1.0"
    polls = []

    def sleep(s):  # three idle polls, then Disconnect
        polls.append(s)
        if len(polls) == 3:
            paired.stop_next = True
    a, lines = Awake(), []
    assert worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep,
                        awake_on=a.keep, awake_off=a.release) == 0
    assert lines[1] == UPDATE_11 and lines.count(UPDATE_11) == 1
    assert lines[-1].startswith("Disconnected from the website")


def test_watch_says_it_again_when_the_website_moves_on_while_it_runs(paired, lessons, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    polls = []

    def sleep(s):
        polls.append(s)
        if len(polls) == 1:
            paired.latest = "1.1.0"
        if len(polls) == 3:
            paired.latest = "1.2.0"
        if len(polls) == 5:
            paired.stop_next = True
    a, lines = Awake(), []
    worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep, awake_on=a.keep, awake_off=a.release)
    updates = [l for l in lines if l.startswith("A newer lesson-videos")]
    assert [u.split(")")[0] for u in updates] == ["A newer lesson-videos (1.1.0", "A newer lesson-videos (1.2.0"]


def test_watch_says_nothing_when_the_plugin_is_as_new_or_newer(paired, lessons, monkeypatch):
    monkeypatch.setattr(site, "LATEST", None)
    for latest in ("1.0.0", "0.9.0", "2.0.0", "junk"):
        paired.latest, paired.stop_next = latest, False

        def sleep(s):
            paired.stop_next = True
        a, lines = Awake(), []
        worker.watch(claude=_claude_writing(QUESTIONS), out=lines.append, sleep=sleep, awake_on=a.keep, awake_off=a.release)
        assert not any("newer lesson-videos" in l for l in lines), latest
```

Replace `test_watch_stops_on_contract_mismatch` with:

```python
def test_watch_stops_with_the_websites_refusal(paired, lessons):
    paired.refuse = ("This computer has lesson-videos 1.0.0; slide2video.com needs 2.x. To update: run /plugin update "
                     "lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve.")
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and lines[-1] == paired.refuse and a.on == 0


def test_watch_stops_on_contract_mismatch_from_an_older_website(paired, lessons):
    paired.contract = 2
    code, lines, sleeps, a = _watch(_claude_writing(QUESTIONS))
    assert code == 1 and "Update the lesson-videos plugin" in lines[-1] and a.on == 0
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_worker_watch.py`
Expected: FAIL (start line without the version; no update line).

- [ ] **Step 3: Implement** in `worker.watch` (imports: `import lv` and `from . import version`):

```python
        handle, awake = awake_on(out=out), True
        out(f"Making videos for {site.site_url()}{as_who} with lesson-videos {lv.__version__}. Waiting for lessons… "
            "(stop with Ctrl-C, or Disconnect on the website)")
        told = None

        def tell_update():                  # once per website version that is newer than this plugin
            nonlocal told
            line = version.update_line(site.LATEST)
            if line and site.LATEST != told:
                told = site.LATEST
                out(line)
        tell_update()
```

and call `tell_update()` right after each successful `_once` call in the loop (after `failures = 0`).

- [ ] **Step 4: Run the whole gate**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/worker.py tests/test_worker_watch.py
git commit -m "lesson-videos: worker --watch names its version and says once when a newer one is available"
```

## Task 4: Skills, install guide and the repo rule

**Files:**
- Modify: `lesson-videos/skills/serve/SKILL.md` (§1, §3)
- Modify: `lesson-videos/docs/install/slide2video.md:74` (troubleshooting row) and add a row for "hasn't caught up"
- Modify: `AGENTS.md` (`lesson-videos` contribution text: the rule from spec §7)
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write the failing tests** in `tests/test_skills.py`:

```python
STEPS = "/plugin update lesson-videos`, then close and reopen Claude Code"


def test_serve_update_says_to_reopen_claude_code():
    _, text = frontmatter("serve")
    assert STEPS in text
    assert "hasn't caught up" in text and "nothing to do on this computer" in text.lower()
    assert "A newer lesson-videos" in text


def test_install_guide_update_row_says_to_reopen_claude_code():
    guide = (PLUGIN / "docs/install/slide2video.md").read_text(encoding="utf-8")
    assert STEPS in guide and "hasn't caught up" in guide
```

(Use the module's existing `PLUGIN` import; add `from conftest import PLUGIN` if absent.)

- [ ] **Step 2: Run** `uv run pytest -q tests/test_skills.py` — Expected: FAIL.

- [ ] **Step 3: Write the text**

(`setup/SKILL.md` has no update wording today, so it needs no change; `grep -n "plugin update" lesson-videos/skills`
should list only `serve`.)

`serve/SKILL.md` §3, replace the "Update the lesson-videos plugin" clause with:

```markdown
  Disconnect; a "connect" message means the pairing was removed (offer step 1); a "needs" or "Update the
  lesson-videos plugin" message means: run `/plugin update lesson-videos`, then close and reopen Claude Code, then
  run this skill again (the worker keeps its old code until Claude Code is reopened); "hasn't caught up" means the
  website isn't updated yet: nothing to do on this computer, try again later.
- A line "A newer lesson-videos (…) is available" is only advice: the worker keeps making videos. Tell the teacher
  in plain words and offer the same three steps for when no step is in progress.
```

and in §1, after the `worker --status` sentence: `It also names the plugin version; if it says a newer one is
available, mention it (it isn't urgent).`

`docs/install/slide2video.md`, replace the row at line 74 and add one after it:

```markdown
| "Update the lesson-videos plugin on this computer" or "slide2video.com needs …" | In Claude Code, type `/plugin update lesson-videos`, then close and reopen Claude Code, then run `/lesson-videos:serve`. |
| "slide2video.com hasn't caught up with lesson-videos …" | Nothing to do on this computer: the website gets updated soon. Try again later. |
```

`AGENTS.md` (repo root, in the paragraph about bumping `lesson-videos` versions), add:

```markdown
`lesson-videos/site-contract/contract.json` `plugin` is the plugin version slide2video.com is built for. When a
release changes anything the website or the worker relies on (the job contract, device calls, card or turn fields,
what the website shows about computers), set `plugin` to the new version, copy `site-contract/` to slide2video's
`contract/`, and deploy the website. A breaking change to the contract is a **major** bump (and bumps the schemas'
`const`). Releases that touch neither need no website deploy: a computer newer than the website, within its major,
is fine.
```

- [ ] **Step 4: Run the whole gate** `uv run pytest -q` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/skills/serve/SKILL.md lesson-videos/docs/install/slide2video.md AGENTS.md tests/test_skills.py
git commit -m "lesson-videos: serve and the install guide give the update steps with reopening Claude Code; repo rule"
```

## Task 5: The website's contract and version helpers

Work in `~/Projects/slide2video`: `git switch -c plugin-version-check` off an up-to-date `main`.

**Files:**
- Modify: `contract/contract.json` (copy of the plugin's: `{"plugin": "1.0.0"}`)
- Modify: `contract/README.md` (copy the plugin's `site-contract/README.md`)
- Modify: `src/contract.ts`
- Modify: `AGENTS.md` (Paired repo section, spec §7)
- Test: `test/version.test.ts` (new), `test/scaffold.test.ts:24`

**Interfaces:**
- Produces (from `src/contract.ts`): `PLUGIN: string`; `CONTRACT_VERSION: number` (major of `PLUGIN`);
  `type Version = [number, number, number]`; `parseVersion(s: unknown): Version | null`;
  `checkPlugin(have: string | null, site = PLUGIN): "ok" | "old" | "behind"`;
  `updateAvailable(have: string | null, site = PLUGIN): boolean`;
  `needsUpdate(have: string | null, site = PLUGIN): string`; `siteBehind(have: string): string`;
  `UPDATE_STEPS: string`. `UPDATE_PLUGIN` is removed.

- [ ] **Step 1: Write the failing tests** `test/version.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { CONTRACT_VERSION, PLUGIN, checkPlugin, needsUpdate, parseVersion, siteBehind, updateAvailable } from "../src/contract";

describe("plugin versions", () => {
  it("parses MAJOR.MINOR.PATCH, digits only", () => {
    expect(parseVersion("1.0.0")).toEqual([1, 0, 0]);
    expect(parseVersion("12.34.5678")).toEqual([12, 34, 5678]);
    for (const bad of ["1.0", "1.0.0-beta", "v1.0.0", "", " 1.0.0", "12345.0.0", "<script>", null, undefined, 1])
      expect(parseVersion(bad), String(bad)).toBeNull();
  });

  it("the website is built for contract.json's plugin, and its major is the contract version", () => {
    expect(PLUGIN).toBe("1.0.0");
    expect(CONTRACT_VERSION).toBe(1);
  });

  it("refuses a different major and junk, passes the same major", () => {
    expect(checkPlugin("2.1.0", "2.1.0")).toBe("ok");
    expect(checkPlugin("2.0.0", "2.1.0")).toBe("ok");
    expect(checkPlugin("2.9.9", "2.1.0")).toBe("ok");
    expect(checkPlugin("1.4.0", "2.1.0")).toBe("old");
    expect(checkPlugin(null, "2.1.0")).toBe("old");
    expect(checkPlugin("2.1", "2.1.0")).toBe("old");
    expect(checkPlugin("3.0.0", "2.1.0")).toBe("behind");
  });

  it("an update is available only for an older version with the same major", () => {
    expect(updateAvailable("2.0.0", "2.1.0")).toBe(true);
    expect(updateAvailable("2.1.0", "2.1.0")).toBe(false);
    expect(updateAvailable("2.2.0", "2.1.0")).toBe(false);
    expect(updateAvailable("1.9.0", "2.1.0")).toBe(false);
    expect(updateAvailable(null, "2.1.0")).toBe(false);
  });

  it("says what to do, and never echoes an unreadable version", () => {
    expect(needsUpdate("1.4.0", "2.1.0")).toBe("This computer has lesson-videos 1.4.0; slide2video.com needs 2.x. " +
      "To update: run /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve.");
    expect(needsUpdate("<b>junk</b>", "2.1.0")).toBe("This computer has an older version of lesson-videos; " +
      "slide2video.com needs 2.x. To update: run /plugin update lesson-videos, then close and reopen Claude Code, " +
      "then run /lesson-videos:serve.");
    expect(siteBehind("3.0.0")).toBe("slide2video.com hasn't caught up with lesson-videos 3.0.0 yet. " +
      "Nothing to do on this computer; try again later.");
  });
});
```

In `test/scaffold.test.ts` change line 24 to `expect(CONTRACT_VERSION).toBe(Number(contract.plugin.split(".")[0]));`.

- [ ] **Step 2: Run** `npm test -- test/version.test.ts test/scaffold.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement**

Copy the contract: `cp ~/Projects/plugins/lesson-videos/site-contract/contract.json contract/contract.json` and
`cp ~/Projects/plugins/lesson-videos/site-contract/README.md contract/README.md` (schemas and examples are
unchanged; confirm with `diff -r ~/Projects/plugins/lesson-videos/site-contract contract`, which should print
nothing).

`src/contract.ts` top:

```ts
import contract from "../contract/contract.json";

export type Version = [number, number, number];
export const parseVersion = (s: unknown): Version | null => {
  const m = typeof s === "string" ? /^(\d{1,4})\.(\d{1,4})\.(\d{1,4})$/.exec(s) : null;
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
};
const cmp = (a: Version, b: Version) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2];

/** The plugin version this website is built for (contract.json); its major is the contract version. */
export const PLUGIN: string = contract.plugin;
const SITE = parseVersion(PLUGIN);
if (!SITE) throw new Error(`contract/contract.json: unreadable plugin version ${PLUGIN}`);
export const CONTRACT_VERSION: number = SITE[0];

export function checkPlugin(have: string | null, site = PLUGIN): "ok" | "old" | "behind" {
  const v = parseVersion(have), s = parseVersion(site)!;
  return !v || v[0] < s[0] ? "old" : v[0] > s[0] ? "behind" : "ok";
}
export function updateAvailable(have: string | null, site = PLUGIN): boolean {
  const v = parseVersion(have), s = parseVersion(site)!;
  return !!v && v[0] === s[0] && cmp(v, s) < 0;
}
export const UPDATE_STEPS = "run /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve";
export const needsUpdate = (have: string | null, site = PLUGIN) =>
  `This computer has ${parseVersion(have) ? `lesson-videos ${have}` : "an older version of lesson-videos"}; ` +
  `slide2video.com needs ${parseVersion(site)![0]}.x. To update: ${UPDATE_STEPS}.`;
export const siteBehind = (have: string) =>
  `slide2video.com hasn't caught up with lesson-videos ${have} yet. Nothing to do on this computer; try again later.`;
```

Remove `UPDATE_PLUGIN` and the old `CONTRACT_VERSION` line. (`src/device.ts` still imports `UPDATE_PLUGIN` until
Task 6, so `npm run check` fails between the two tasks; run only the two test files in Step 4.)

`AGENTS.md` Paired repo section, replace "Device calls carry `X-LV-Contract`; a mismatch answers 426." with:

```markdown
`contract/contract.json` `plugin` is the plugin version this website is built for; every computer is compared
with it (`X-LV-Plugin`: a different major is refused with 426, an older one is told to update). Changing it means
deploying.
```

- [ ] **Step 4: Run** `npm test -- test/version.test.ts test/scaffold.test.ts` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add contract src/contract.ts AGENTS.md test/version.test.ts test/scaffold.test.ts
git commit -m "Contract: the plugin version the site is built for (1.0.0), version helpers and messages"
```

## Task 6: Device API checks and records the version

**Files:**
- Create: `migrations/0005_plugin_version.sql`
- Modify: `src/device.ts:1-30` (middleware), `src/device.ts` pair/poll INSERT, `deviceAuth`, `/status`
- Modify: `test/helpers.ts:35-42` (`asDevice` sends `X-LV-Plugin`)
- Modify: `test/pairing.test.ts:8-17`
- Test: `test/plugin-version.test.ts` (new)

**Interfaces:**
- Consumes: `PLUGIN`, `checkPlugin`, `needsUpdate`, `siteBehind` from Task 5.
- Produces: column `devices.plugin_version TEXT` (a readable version or NULL); `asDevice(token, path, init = {},
  plugin: string | null = PLUGIN)` — `null` sends no header.

- [ ] **Step 1: Write the failing tests**

`test/helpers.ts` `asDevice`:

```ts
export function asDevice(token: string | null, path: string, init: RequestInit = {}, plugin: string | null = PLUGIN): Promise<Response> {
  const headers = new Headers(init.headers);
  if (plugin) headers.set("X-LV-Plugin", plugin);
```

(import `PLUGIN` from `../src/contract`.) In `test/pairing.test.ts`, the `post` helper's last parameter becomes
`plugin: string | null = PLUGIN` and the first test becomes:

```ts
  it("refuses a plugin with another major, with the steps to update", async () => {
    const r = await post("/api/device/pair/start", { name: "Mac" }, null, "0.7.0");
    expect(r.status).toBe(426);
    expect((await r.json<any>()).error).toContain("then close and reopen Claude Code");
  });
```

`test/plugin-version.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { PLUGIN, needsUpdate, siteBehind } from "../src/contract";
import { DECK, asDevice, asTeacher, newLesson, pairDevice, seedTeacher } from "./helpers";

const stored = async (id: string) =>
  (await env.DB.prepare("SELECT plugin_version, last_seen FROM devices WHERE id = ?").bind(id).first<any>())!;

describe("plugin version on device calls", () => {
  it("pairing records the version, so a new computer never shows as needing an update", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    expect((await stored(d.id)).plugin_version).toBe(PLUGIN);
  });

  it("answers every passing call with X-LV-Latest, 204 and file downloads included", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    const idle = await asDevice(d.token, "/api/device/next");
    expect(idle.status).toBe(204);
    expect(idle.headers.get("X-LV-Latest")).toBe(PLUGIN);
    expect((await asDevice(d.token, "/api/device/status")).headers.get("X-LV-Latest")).toBe(PLUGIN);
    await newLesson(t.email, { start: true });
    const turn = await (await asDevice(d.token, "/api/device/next")).json<any>();
    const file = await asDevice(d.token, `/api/device/files/${turn.files[0].id}`);
    expect(file.status).toBe(200);
    expect(file.headers.get("X-LV-Latest")).toBe(PLUGIN);
    expect(new Uint8Array(await file.arrayBuffer())).toEqual(DECK);
  });

  it("records the version on every call and stores junk as NULL, never echoing it", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    await env.DB.prepare("UPDATE devices SET last_seen = 0 WHERE id = ?").bind(d.id).run();
    const r = await asDevice(d.token, "/api/device/next", {}, "<b>1.0</b>");
    expect(r.status).toBe(426);
    expect(r.headers.get("X-LV-Latest")).toBeNull();
    const msg = (await r.json<any>()).error;
    expect(msg).toBe(needsUpdate(null));
    expect(msg).not.toContain("<b>");
    const row = await stored(d.id);
    expect(row.plugin_version).toBeNull();
    expect(row.last_seen).toBeGreaterThan(0); // refused, but it did call in
  });

  it("refuses a missing version and an older major, recording what it can", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    const none = await asDevice(d.token, "/api/device/next", {}, null);
    expect(none.status).toBe(426);
    expect((await none.json<any>()).error).toBe(needsUpdate(null));
    const old = await asDevice(d.token, "/api/device/next", {}, "0.7.0");
    expect((await old.json<any>()).error).toBe(needsUpdate("0.7.0"));
    expect((await stored(d.id)).plugin_version).toBe("0.7.0");
  });

  it("tells a newer major that the website is behind, and lets a newer minor through", async () => {
    const t = await seedTeacher();
    const d = await pairDevice(t.email);
    const next = Number(PLUGIN.split(".")[0]) + 1;
    const ahead = await asDevice(d.token, "/api/device/status", {}, `${next}.0.0`);
    expect(ahead.status).toBe(426);
    expect((await ahead.json<any>()).error).toBe(siteBehind(`${next}.0.0`));
    const minor = PLUGIN.replace(/^(\d+)\.(\d+)\./, (_, a, b) => `${a}.${Number(b) + 1}.`);
    expect((await asDevice(d.token, "/api/device/status", {}, minor)).status).toBe(200);
    expect((await stored(d.id)).plugin_version).toBe(minor);
  });

  it("a wrong token is 401 whatever the version (nothing recorded, nothing refused by version)", async () => {
    expect((await asDevice("s2v_" + "x".repeat(30), "/api/device/next", {}, "0.7.0")).status).toBe(401);
  });

  it("only the teacher's own computers record anything", async () => {
    const a = await seedTeacher();
    const b = await seedTeacher();
    const da = await pairDevice(a.email);
    const db = await pairDevice(b.email);
    await asDevice(da.token, "/api/device/next", {}, "0.7.0");
    expect((await stored(db.id)).plugin_version).toBe(PLUGIN);
    expect(await (await asTeacher(b.email, "/devices")).text()).not.toContain("0.7.0");
  });
});
```

- [ ] **Step 2: Run** `npm test -- test/plugin-version.test.ts test/pairing.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement**

`migrations/0005_plugin_version.sql`:

```sql
-- the lesson-videos version this computer last called in with (X-LV-Plugin), NULL when unreadable or never sent
ALTER TABLE devices ADD COLUMN plugin_version TEXT;
```

`src/device.ts`: imports become `import { PLUGIN, cardProblems, checkPlugin, needsUpdate, parseVersion, siteBehind } from "./contract";`
(drop `CONTRACT_VERSION, UPDATE_PLUGIN` unless still used; `/status` keeps `contract: CONTRACT_VERSION`, so keep
importing `CONTRACT_VERSION`). Replace the `X-LV-Contract` middleware with:

```ts
/** Every device call names its plugin version (X-LV-Plugin). Another major is refused; the message says what to do. */
const refusal = (c: Context<AppEnv>): Response | null => {
  const have = c.req.header("X-LV-Plugin") ?? null;
  const v = checkPlugin(have);
  return v === "ok" ? null : c.json({ error: v === "old" ? needsUpdate(have) : siteBehind(have!) }, 426);
};
// every answer that wasn't a refusal says which version the website is built for, so an older plugin can say so
device.use("*", async (c, next) => {
  await next();
  if (c.res.status !== 426) c.res.headers.set("X-LV-Latest", PLUGIN);
});
// pairing has no computer to record yet: refuse up front
device.use("/pair/*", async (c, next) => refusal(c) ?? next());
```

(`import { Hono, type Context, type MiddlewareHandler } from "hono";`.) If `c.res.headers.set` throws on the
file route's `Response` (immutable headers), wrap it: `c.res = new Response(c.res.body, c.res); c.res.headers.set(...)`.

In `/pair/poll`, the INSERT stores the version (the `/pair/*` check guarantees it is readable):

```ts
  await db.prepare("INSERT INTO devices (id, teacher_id, name, token_hash, created_at, last_seen, plugin_version) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .bind(id, claimed.teacher_id, claimed.name, await sha256Hex(token), now(), now(), c.req.header("X-LV-Plugin")!).run();
```

In `deviceAuth`, replace the `last_seen` update and refuse after recording:

```ts
  const have = c.req.header("X-LV-Plugin") ?? null;
  await c.env.DB.prepare("UPDATE devices SET last_seen = ?, plugin_version = ? WHERE id = ?")
    .bind(now(), parseVersion(have) ? have : null, d.id).run();
  const refused = refusal(c);
  if (refused) return refused;
  c.set("device", d);
  await next();
```

Apply the migration to the test and local databases: the vitest config reads `migrations/` itself;
`npm run db:local` updates the local dev database.

- [ ] **Step 4: Run** `npm run check && npm test` — Expected: PASS (all existing device tests now send
`X-LV-Plugin: 1.0.0` through `asDevice`).

- [ ] **Step 5: Commit**

```bash
git add migrations/0005_plugin_version.sql src/device.ts test/helpers.ts test/pairing.test.ts test/plugin-version.test.ts
git commit -m "Device API: X-LV-Plugin recorded per computer, another major refused with the steps, X-LV-Latest on answers"
```

## Task 7: Devices list and the waiting lesson show the version

**Files:**
- Modify: `src/pages.ts` (`DeviceSeen`, `readyDevice`, `lessonState`, the lesson lead panel, `/devices`)
- Test: `test/pages.test.ts` (lesson page), `test/disconnect.test.ts` or a new `describe` in
  `test/plugin-version.test.ts` (Devices list)

**Interfaces:**
- Consumes: `PLUGIN`, `checkPlugin`, `updateAvailable`, `UPDATE_STEPS` from Task 5; `devices.plugin_version`.
- Produces: `versionLabel(have: string | null, site = PLUGIN): { needsUpdate: boolean; text: string }` exported
  from `src/pages.ts` for unit tests; `LessonState.outdated?: string | null` (name of the computer that must update).

- [ ] **Step 1: Write the failing tests** — append to `test/plugin-version.test.ts` (import `versionLabel` from
`../src/pages`, `text` helper as in pages.test: `(p: string) => p.replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&")`):

```ts
describe("versions on the website", () => {
  it("labels a version: current, update available, or needs an update", () => {
    expect(versionLabel("2.1.0", "2.1.0")).toEqual({ needsUpdate: false, text: "lesson-videos 2.1.0" });
    expect(versionLabel("2.0.0", "2.1.0")).toEqual({ needsUpdate: false, text: "lesson-videos 2.0.0 · update available (2.1.0)" });
    expect(versionLabel("2.2.0", "2.1.0")).toEqual({ needsUpdate: false, text: "lesson-videos 2.2.0" });
    expect(versionLabel("1.4.0", "2.1.0")).toEqual({ needsUpdate: true, text: "Needs an update" });
    expect(versionLabel(null, "2.1.0")).toEqual({ needsUpdate: true, text: "Needs an update" });
  });

  it("Devices shows each computer's version, and Needs an update with the steps and no Disconnect", async () => {
    const t = await seedTeacher();
    const ok = await pairDevice(t.email, "Kitchen Mac");
    const old = await pairDevice(t.email, "Garage Mac");
    await asDevice(old.token, "/api/device/next", {}, "0.7.0");
    const p = text(await (await asTeacher(t.email, "/devices")).text());
    expect(p).toContain(`Kitchen Mac<span class="meta">Online · lesson-videos ${PLUGIN}</span>`);
    expect(p).toContain(`Garage Mac<span class="meta">Needs an update</span>`);
    expect(p).toContain("run /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve");
    expect(p).toContain(`/api/devices/${ok.id}/disconnect`);
    expect(p).not.toContain(`/api/devices/${old.id}/disconnect`);
  });

  it("a waiting lesson whose computer needs an update says so, never Starting soon", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email, "Garage Mac");
    await asDevice(mac.token, "/api/device/next", {}, "0.7.0"); // refused, but last seen just now
    const id = await newLesson(t.email);
    const page = text(await (await asTeacher(t.email, `/lessons/${id}`)).text());
    expect(page).toContain("<h2>Garage Mac needs an update</h2>");
    expect(page).toContain("before it can make this video");
    expect(page).toContain("then close and reopen Claude Code");
    expect(page).not.toContain("Starting soon");
    expect(text(await (await asTeacher(t.email, "/lessons")).text())).toContain("Waiting for Garage Mac to update");
  });

  it("an up-to-date computer still takes a new lesson when another one needs an update", async () => {
    const t = await seedTeacher();
    await pairDevice(t.email, "Kitchen Mac");
    const old = await pairDevice(t.email, "Garage Mac");
    await asDevice(old.token, "/api/device/next", {}, "0.7.0");
    const id = await newLesson(t.email);
    const page = text(await (await asTeacher(t.email, `/lessons/${id}`)).text());
    expect(page).toContain("Kitchen Mac is connected and starts on this in a minute or so.");
  });
});
```

- [ ] **Step 2: Run** `npm test -- test/plugin-version.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement** in `src/pages.ts` (import `PLUGIN, UPDATE_STEPS, checkPlugin, updateAvailable` from
`./contract`):

```ts
type DeviceSeen = { last_seen: number | null; stop_requested_at: number | null; stopped_at: number | null; plugin_version: string | null };

/** A computer's plugin version as the teacher sees it. */
export function versionLabel(have: string | null, site = PLUGIN): { needsUpdate: boolean; text: string } {
  if (checkPlugin(have, site) !== "ok") return { needsUpdate: true, text: "Needs an update" };
  return { needsUpdate: false, text: `lesson-videos ${have}${updateAvailable(have, site) ? ` · update available (${site})` : ""}` };
}
const UPDATE_NOTE = html`<p class="turn-note">On that computer, ${UPDATE_STEPS}.</p>`;
```

`readyDevice` returns `{ ready: Ready | null; outdated: string | null }`: select `d.plugin_version` too, compute
`const current = results.filter((d) => !versionLabel(d.plugin_version).needsUpdate)`; `ready` comes from `current`
as before; `outdated` is `results[0].name` when `results.length > 0 && current.length === 0`, else `null`.

In `lessonState`'s queued branch:

```ts
    const { ready, outdated } = await readyDevice(db, l.teacher_id, l.home_device_id);
    if (ready) return { ...base, busy: true, ready,
      status: ready.busy ? `Next in line on ${ready.name}` : `Starting soon on ${ready.name}` };
    if (outdated) return { ...base, busy: true, outdated, status: `Waiting for ${outdated} to update` };
```

and add `outdated?: string | null` to `LessonState`. Lead panel, before the `s.busy && s.ready` branch:

```ts
  else if (s.busy && s.outdated) lead = html`<section class="card"><div class="row">${COMPUTER_ART}<div class="grow stack">
<h2>${s.outdated} needs an update</h2><p>It has to be updated before it can make this video.</p>${UPDATE_NOTE}</div></div></section>`;
```

(The test expects "before it can make this video": keep that phrase in the `<p>`.)

`/devices`: add `plugin_version` to the SELECT and its row type. In the row:

```ts
    const ver = versionLabel(d.plugin_version);
    const meta = ver.needsUpdate ? ver.text : `${state} · ${ver.text}`;
    return html`<div class="item">${COMPUTER_ART}<span class="name">${d.name}<span class="meta">${meta}${n ? ` · making ${plural(n, "lesson")}` : ""}</span>${ver.needsUpdate ? UPDATE_NOTE : ""}</span>
${online && !stopping && !ver.needsUpdate ? html`<form class="inline" data-api="POST /api/devices/${d.id}/disconnect" ...` : ""}
```

Existing Devices tests assert exact meta (find them with `grep -rn 'class="meta"\|Stopping…\|Disconnected<' test`;
`test/disconnect.test.ts` and `test/pages.test.ts` have them): update them to `Online · lesson-videos ${PLUGIN}` / `Stopping… · lesson-videos ${PLUGIN}` /
`Disconnected · lesson-videos ${PLUGIN}` (import `PLUGIN`), keeping what each test checks.

- [ ] **Step 4: Run** `npm run check && npm test` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages.ts test
git commit -m "Devices and waiting lessons show each computer's lesson-videos version and when it needs an update"
```

## Task 8: Merge, push, and hand over the rollout

- [ ] **Step 1:** plugins: `uv run pytest -q` passes; merge `plugin-version-check` into `main` (`git merge --no-ff`),
  push. This publishes lesson-videos 1.0.0 to teachers; it still works against today's website (it sends
  `X-LV-Contract: 1` too).
- [ ] **Step 2:** slide2video: `npm run check && npm test` pass; merge `plugin-version-check` into `main`, push.
  **Do not deploy.**
- [ ] **Step 3:** Tell Daniel the rollout that remains, in order, and wait for his go:
  1. On each computer: `/plugin update lesson-videos`, reopen Claude Code, `/lesson-videos:serve`.
  2. `npx wrangler d1 migrations apply slide2video --remote`, then `npm run deploy` (with the other undeployed
     changes already on `main`).
  3. Check Devices shows "Online · lesson-videos 1.0.0".
