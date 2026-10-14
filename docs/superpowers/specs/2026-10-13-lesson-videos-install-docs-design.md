# lesson-videos — install guides, key skills and Cowork support

**Date:** 2026-10-13 · **Status:** approved in chat, awaiting written-spec review
**Plugin:** `lesson-videos` 0.3.0 → **0.4.0** · **Branch:** `lesson-videos-install-docs`

## 1. Purpose

A teacher installed `lesson-videos` and it took them a long time. This change
makes the first contact simpler:

- The README says **why** the plugin exists and **shows what it makes** (sample
  stills and a full sample video) before any instructions.
- Installation moves into a `docs/install/` folder with one guide per way of
  running it: **Claude Code** (desktop app or CLI, recommended) and **Cowork on
  claude.ai** (nothing to install; for school laptops where apps can't be
  installed).
- Getting ElevenLabs and Google keys gets step-by-step guides with redacted real
  screenshots for non-technical teachers, and two skills that let Claude do the
  clicking through Claude in Chrome, saving the key without it ever entering the
  chat.
- Cowork actually works end to end, fixing the three blockers found in the
  2026-10-13 cloud test.

**Success looks like:**
- A teacher reading only the README understands what they'll get (stills +
  video) and picks an install path in under a minute.
- On a Pro/Max account with nothing installed, following `docs/install/cowork.md`
  produces a narrated (free voice) chapter from the sample deck.
- With Claude Code and Claude in Chrome, `/lesson-videos:elevenlabs-get-api-key`
  ends with a working saved key, and no key value appears in the transcript,
  in screenshots Claude took, or in command output.
- `uv run pytest -q` passes, including the new tests in §7.

## 2. Decisions taken in the brainstorm

| Question | Decision |
|---|---|
| Install paths | Two: Claude Code (recommended) and Cowork. The browser-only website is **dropped** (it would need per-deck Anthropic API billing). |
| Cowork | Guide **and** fixes in this change, verified by re-running the cloud test. |
| Keys in Cowork | The teacher attaches a keys file to each session; `LV keys load` imports it without printing it. |
| Key-guide pictures | Real screenshots from the maintainer's accounts, cropped and redacted, each shown to the maintainer before commit. |
| Sample results | 4 stills (WebP) in the repo; the full MP4 attached to a GitHub Release. |
| Local GUI for the CLI | A separate project after this one (GitHub issue), not mentioned in these docs yet. |

## 3. Findings this design rests on (cloud test, 2026-10-13)

Run in a claude.ai cloud session (Max plan) after adding the marketplace from
**Customize → Plugins → Add marketplace**:

- Linux VM, 2 vCPU, 7.8 GiB RAM; Python 3.13, uv, Node 22, ffmpeg 6.1 present;
  no Chromium.
- The plugin syncs whole (35 files: scripts, engine, fonts, sample) under
  `/root/.claude/plugins/synced/…/lesson-videos`; **`CLAUDE_PLUGIN_ROOT` is unset.**
- Default network setting is **"Package managers only"** (GitHub, npm, PyPI,
  crates, Ubuntu archive, Yarn). `cdn.playwright.dev`, `astral.sh`,
  `api.elevenlabs.io`, `generativelanguage.googleapis.com` and
  `speech.platform.bing.com` return 403 from the proxy. Users can add domains
  under **Settings → Capabilities → Additional allowed domains**.
- `playwright install chromium` fails (403); apt has no Chromium;
  **`npm @sparticuz/chromium` works** (Chromium 153) and the renderer runs with it.
- `doctor` re-ran `playwright install`, which failed and **pruned the browser
  folder that had been linked in**, breaking rendering until relinked.
- Narration fell back to captions only (no voice reachable, no system voice).
- Render: 82.4 s video in 135.5 s (≈1.65× real time), 1920×1080, 7.06 MB.

## 4. Docs layout and README

```
lesson-videos/
├── README.md                     rewritten (purpose, samples, choose a path)
└── docs/
    ├── install/
    │   ├── claude-code.md        desktop app + CLI, macOS/Windows, setup, make, troubleshooting
    │   └── cowork.md             add plugin, allow domains, attach keys file, run, download
    ├── keys/
    │   ├── README.md             what each key is for and costs; the Claude-in-Chrome note first
    │   ├── elevenlabs.md         numbered steps + screenshots
    │   ├── google.md             key, billing, spend cap; numbered steps + screenshots
    │   └── keys-file.md          making the keys file Cowork users attach
    ├── keys-template.txt         empty keys file to download (same text as keys.TEMPLATE)
    └── images/
        ├── sample-*.webp         4 stills from the water-cycle chapter
        ├── elevenlabs-*.webp     redacted screenshots
        └── google-*.webp         redacted screenshots
```

**README, top to bottom:**
1. One sentence on what it does, then why: the teacher's own slides become
   videos students can rewatch, in the teacher's wording, with the facts taken
   only from the slides.
2. **Sample results:** 4 stills (hook, diagram, quiz, recap) and a "Watch the
   full sample" link to the Release MP4. A one-line note that it was made from
   `examples/water-cycle.pptx` with the free voice.
3. What each video has (today's list, trimmed).
4. **Get started:** a two-row table, Claude Code (recommended: install once,
   smoothest, keys remembered, videos next to your deck) and Cowork (nothing
   to install; good for locked-down school laptops; a few more steps each
   time). Each row links its guide.
5. **Optional: better voice, music and clips:** one line of cost each, link to
   `docs/keys/`.
6. Privacy and good-to-know points, shortened; the troubleshooting table moves
   to `docs/install/claude-code.md` (Cowork-specific rows go in `cowork.md`).
7. Credits and licence line.

`docs/keys/README.md` opens with: *"Have Claude Code and the Claude in Chrome
extension? Type `/lesson-videos:elevenlabs-get-api-key` (or
`google-get-api-key`) and Claude opens the pages and clicks through for you;
you only sign in and, for Google, add billing."*

The `docs/` folder ships inside the plugin (≈1 MB of images), well under the
200 MB / 5,000-file plugin limits.

## 5. Key skills and key commands

### 5.1 Skills (Claude Code only; they need Claude in Chrome)

`skills/elevenlabs-get-api-key/SKILL.md` and `skills/google-get-api-key/SKILL.md`.

Common rules, stated in both skills:
- First check Claude in Chrome is connected (`tabs_context_mcp`). If not, say
  so in one line and point to the matching `docs/keys/*.md` guide; stop.
- Work in a new tab. The teacher signs up / signs in themselves; Claude never
  types passwords, creates accounts, or enters payment details.
- Claude may fill the key's name and permissions, but **asks the teacher before
  clicking the final Create/Save**.
- **Key secrecy:** from the moment the key is displayed until the teacher says
  they clicked Copy and closed the dialog, Claude takes **no screenshots and
  no page reads** of that tab. Then it runs `LV keys paste <service>`.
- If the teacher pastes a key into chat anyway, tell them to delete that key
  on the website and create a new one.

ElevenLabs flow: open `elevenlabs.io/app/settings/api-keys` → teacher signs in
→ Create API Key, name `lesson-videos`, permissions Text to Speech (access) and
User (read), optional credit quota (suggest 30,000) → confirm → Create →
teacher copies and closes → `LV keys paste elevenlabs` → report the masked
result and remaining characters. The plan explanation (free vs Starter, free-plan
rules, use-policy note) is the same text as setup step 3, moved here and
referenced from setup.

Google flow: open `aistudio.google.com/api-keys` → teacher signs in (personal
account; school accounts often block AI Studio) → Create API key (let it create
a project) → teacher copies and closes → `LV keys paste gemini` → open the
billing page; the teacher links billing and makes the $5 prepayment → open the
spend page; Claude proposes a monthly cap ($10) and sets it after the teacher
confirms.

`skills/setup/SKILL.md`: steps 3–5 keep the explanations but, when Claude in
Chrome is connected, hand off to these skills instead of the manual steps;
otherwise link to the `docs/keys/` guides and keep the existing `LV keys`
editor flow.

### 5.2 Commands (`scripts/lv/keys.py`, `cli.py`)

- `LV keys paste <elevenlabs|gemini>`
  - Reads the clipboard: macOS `pbpaste`; Windows `powershell -NoProfile -Command Get-Clipboard`;
    Linux `wl-paste` or `xclip -o -selection clipboard` when present.
  - Strips whitespace; must match the service's shape (ElevenLabs `sk_` + ≥16
    alphanumerics; Gemini `AIza` + ≥30 of `[0-9A-Za-z_-]`). On mismatch:
    *"The clipboard doesn't hold an ElevenLabs key. Click Copy next to the key
    and try again."* The clipboard content is never echoed.
  - Writes the value into `keys.env` (creating it from `TEMPLATE`, replacing
    the variable's line in place, chmod 600 on POSIX), clears the clipboard
    (`pbcopy` / `Set-Clipboard -Value $null` / empty write), then runs the
    check for that service and prints the masked row.
- `LV keys load <file>`
  - Parses the file with `keys.parse`, keeps only known variables with
    non-placeholder values, writes them into `keys.env` the same way, prints
    one masked row per key found, and *"No keys found in that file"* otherwise.
  - The `make` skill's Cowork note: when the teacher attaches a keys file, run
    `LV keys load` on it; never open it with Read or `cat`.
- Shared helper `keys.store(var, value)` used by both; nothing in either path
  prints or logs the value (`redact` stays as the backstop for error text).

**Open check, done first in the Cowork re-test (§7.3):** whether claude.ai
inlines a text attachment's content into the conversation. If it does, the
template and guide use the extension `.lvkeys` (treated as a binary upload),
and `keys load` accepts any extension.

## 6. Cowork fixes

### 6.1 Script paths
All skills and `guide.md` call
`uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"` instead of
`${CLAUDE_PLUGIN_ROOT}`. Claude Code and Cowork both substitute
`CLAUDE_SKILL_DIR` (claude.com/docs/skills/how-to, "Add scripts"). The
sample folder and `guide.md` paths follow the same base. The make skill's
parallel-helper paragraph keeps "give each helper the real plugin path".

### 6.2 Chromium
- `config.chromium_path() -> str | None`: `LV_CHROMIUM` env var if set and
  executable → else the path in `~/.lesson-videos/chromium.txt` if it still
  exists → else `None` (Playwright's own browser).
- `render.page_for` (and anything else that launches Chromium) passes
  `executable_path=config.chromium_path()` when not `None`.
- `doctor`:
  1. Try launching the browser that `chromium_path()` / Playwright would use
     (headless, then close). If it launches, ✓ and **no download**.
  2. Else `playwright install chromium` (today's path).
  3. If that fails, `npm` is on PATH and the OS is Linux: `npm install
     --prefix ~/.lesson-videos/chromium-npm @sparticuz/chromium`, run
     `node -e "require('@sparticuz/chromium').executablePath().then(p=>console.log(p))"`
     from that prefix, copy the binary to `~/.lesson-videos/chromium/chrome`,
     write that path to `chromium.txt`, and re-test the launch.
  4. Else ✗ with today's "downloads blocked" message.
- Nothing is placed in Playwright's browser folder, so its pruning can't remove it.

### 6.3 Clearer `doctor` messages in the cloud
When a host fails with the proxy's 403 / "allowlist" text, the Narration line
and the key checks say: *"Blocked by Claude's network setting. In claude.ai go
to Settings → Capabilities → Additional allowed domains and add
`speech.platform.bing.com`"* (respectively `api.elevenlabs.io`,
`generativelanguage.googleapis.com`). `docs/install/cowork.md` lists the same
domains with screenshots of that settings screen (redacted).

## 7. Testing and verification

### 7.1 Unit tests (`uv run pytest -q`)
- `tests/test_keys.py`: `keys paste` with a fake clipboard reader stores the
  value, clears the clipboard, and **captured stdout/stderr never contain the
  value**; refuses a non-key without echoing it; per-OS clipboard command
  selection. `keys load` imports known vars, ignores others and placeholders,
  never prints values. `store` replaces an existing line and keeps the file
  mode 600.
- `tests/test_doctor.py`: Chromium order (env → saved path → Playwright →
  npm fallback) with injected launch/install/npm runners; no install attempted
  when the existing browser launches; proxy-blocked message names the domain.
- `tests/test_packaging.py`: version 0.4.0 in the three places; no file under
  `lesson-videos/skills/` contains `CLAUDE_PLUGIN_ROOT`; the two new skills
  exist with valid frontmatter.
- New `tests/test_docs.py`: every relative link and image in
  `lesson-videos/README.md` and `lesson-videos/docs/**/*.md` resolves to a file;
  no image is over 400 KB; `docs/keys-template.txt` equals `keys.TEMPLATE`.

### 7.2 Local
- `/lesson-videos:make` on `examples/water-cycle.pptx`, one chapter, free voice.
  Pick 4 stills, convert to WebP (≤ 1600 px wide), commit under `docs/images/`.
- Upload the MP4 to a GitHub Release (`lesson-videos-sample-v1`) — **only after
  the maintainer confirms** (publishing).

### 7.3 Cloud (claude.ai through Claude in Chrome, maintainer's account)
After the branch is merged and pushed (the marketplace auto-syncs):
1. Attachment check: attach a dummy keys file with fake values; see whether
   the content shows in the conversation. Decide `.txt` vs `.lvkeys` (§5.2).
2. With `speech.platform.bing.com` added to allowed domains **by the
   maintainer** (a security setting Claude doesn't change), run doctor, narrate
   and render the sample: expect the free voice, Chromium via npm, no prune.
3. If anything fails, fix on a new branch and repeat.

### 7.4 Screenshots
Captured through Claude in Chrome in the maintainer's ElevenLabs and Google
accounts; cropped to the relevant area; names, emails, balances and every key
value blacked out **before** the image leaves the scratchpad; each shown to the
maintainer for approval before commit. A key created only for screenshots is
deleted afterwards with the maintainer's confirmation.

## 8. Out of scope
- The local HTML GUI for the CLI (separate issue and spec).
- Any website.
- Music and AI clips in Cowork beyond what attaching a keys file and allowing
  the Google domain already enable (documented, not separately tested).
- Translating the docs.
