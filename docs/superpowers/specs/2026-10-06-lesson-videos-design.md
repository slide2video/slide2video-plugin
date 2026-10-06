# lesson-videos — design

**Date:** 2026-10-06 · **Status:** approved in chat, awaiting written-spec review
**Repo:** `DanielLandi/plugins` (new, public) · **Plugin:** `lesson-videos` in marketplace `daniellandi`

## 1. Purpose

A teacher installs one Claude Code plugin and turns their own slide deck into
narrated, animated study videos: one 4–6 minute video per chapter or unit,
student-facing, test-oriented, with burned-in captions, an end-of-video quiz and
a recap. It packages the pipeline that produced the Marine Biology Unit 1 videos
(session `694fd0de`, 2026-10-05) so someone else can run it on their own Mac or
Windows PC.

**Who runs it:** a non-technical teacher with Claude Code (desktop app Code tab
or terminal) and a Claude plan. They create their own ElevenLabs key (required)
and Gemini key (optional).

**Success looks like:**
- From a clean Mac or Windows machine with only Claude Code installed, the
  teacher reaches a rendered first chapter by following the README and the two
  skills, without editing code or typing shell commands themselves.
- Videos match the quality and structure of the Unit 1 entries: synced reveals,
  captions, tips/traps, a 3-question quiz and a recap.
- API keys never appear in the chat, in Claude's context, or in the repo.
- Nothing paid happens before the teacher approves a costed plan.

## 2. Scope

**In:** chapter videos from a `.pptx` or `.pdf` deck (Google Slides and Keynote
via export to PPTX); dependency setup; guided ElevenLabs and Gemini key creation;
optional Lyria music bed and Veo clips; resumable runs; English narration.

**Out (v1):** summary deck, worksheet answer keys, notes PDF, the collage recap
film, YouTube or any other upload, non-English narration, Linux as a supported
target (it may work; CI does not promise it).

## 3. How it was built before, and what changes

The original pipeline lives in
`~/Projects/ihs/marine-biology/study-kit/videos/_source/`: `engine/engine.js`
(1920×1080 canvas runtime with widgets and standard title/quiz/recap scenes),
`engine/build.py` (ElevenLabs narration with word timestamps → `timing.js`,
stills contact sheet, parallel render, audio mix with ducked music and SFX),
`engine/render.js` (Node + Playwright frame-by-frame capture into ffmpeg),
`clips/make_clips.py` (Veo), and `GUIDE.md` (engine API and narration style).

It depends on things only Daniel's Mac has, all of which the plugin replaces:

| Original dependency | Replacement |
|---|---|
| Keys from `~/Projects/dotfiles/secrets/*/.env` | `~/.lesson-videos/keys.env` (env vars override) |
| Node + Playwright in `~/.cache/collage-studio/node` | Python Playwright, fetched by `uv` |
| SFX in `~/.cache/collage-studio/sfx` (collage-studio's synth + Kenney packs) | Port of the synth for every name the guide lists; Kenney `k_*` names dropped from the guide |
| Patrick Hand from the collage-studio plugin cache | Bundled `fonts/PatrickHand-Regular.ttf` + OFL text |
| `generate-video` skill's `providers.veo_generate` | `lv/clips.py` calling the Gemini REST API directly |
| collage-studio `music.lyria` | `lv/music.py` calling the Interactions API directly |
| ffmpeg/ffprobe from Homebrew | System ffmpeg if on PATH, else `static-ffmpeg` (both binaries, macOS arm64/x64 + Windows x64) |
| Hard-coded output dir `study-kit/videos` | `<deck folder>/lesson-videos/` |

## 4. Install experience

1. Install Claude Code (README links; on Windows, Git for Windows first).
2. In Claude Code: `/plugin marketplace add DanielLandi/plugins`, then
   `/plugin install lesson-videos@daniellandi`.
3. `/lesson-videos:setup` once.
4. Open Claude Code in the deck's folder and run `/lesson-videos:make`.

Updates reach teachers only when `lesson-videos/.claude-plugin/plugin.json`
`version` is bumped (auto-update is off by default).

## 5. `/lesson-videos:setup`

1. **uv.** If `uv` is not on PATH (also check `~/.local/bin`), Claude runs the
   official per-user installer; no admin rights:
   - macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. **`doctor`.** First run makes `uv` fetch Python and the script's inline
   dependencies, then installs Playwright Chromium, locates or fetches
   ffmpeg/ffprobe, synthesizes the SFX library into `~/.lesson-videos/sfx/`, and
   renders a 3-second test video. Prints a ✓/✗ checklist with a fix for each ✗.
3. **ElevenLabs (required).** Claude explains the plan choice (Free: ~10k
   characters/month ≈ one video, non-commercial, "elevenlabs.io" in the published
   title, personal e-mail; Starter: $6/month, 30k credits, commercial licence),
   notes the use-policy line on government entities so the teacher can decide,
   opens `https://elevenlabs.io/app/settings/api-keys` and walks through: create
   key `lesson-videos`, permissions Text to Speech + User read, a credit quota.
4. **Gemini (optional, skippable).** Explains that Veo and Lyria need billing (no
   free tier; $5 minimum prepay) and a personal Google account (school Workspace
   accounts often have AI Studio disabled; under-18 accounts are blocked). Opens
   `https://aistudio.google.com/api-keys`, then the billing setup and
   `https://aistudio.google.com/spend` to set a monthly cap (suggest $10).
5. **Keys entry.** `keys` creates `~/.lesson-videos/keys.env` (mode 600 on
   macOS) with two labeled empty lines and opens it in TextEdit (`open -e`) or
   Notepad. The teacher pastes and saves. Claude never asks for keys in chat and
   never reads the file; if a key is pasted into chat, Claude recommends
   replacing it.
6. **`keys check`.** Validates without printing values (shows only "set, ends
   in …ab12"): ElevenLabs `GET /v1/user/subscription` → characters left this
   month; Gemini `GET /v1beta/models` → key valid. Billing is verified the first
   time music or a clip is generated, since testing it costs money.
7. **Summary:** what is ready, what was skipped, estimated cost per video.

## 6. `/lesson-videos:make`

1. **Ingest.** `ingest <deck>` writes `_work/deck/`: `slides.md` (per slide:
   number, title, body text, speaker notes, which images it contains), `media/`
   (images extracted with slide numbers in their names), and labeled contact
   sheets for Claude to look at. PDF input also renders page images. The teacher
   may name extra files (worksheets) for Claude to read.
2. **Interview (short).** Grade level; chapter split (Claude proposes from the
   deck's sections/titles); target length (default 4–6 min); voice (default
   Jessica, `cgSgspJ2msm6clMCkdW9`); music and clips yes/no.
3. **Content brief** (`_work/brief.md`). Per chapter: key terms with definitions
   in the teacher's own wording, examples, likely test questions, and a section
   **"Possible issues in the slides"** (contradictions, typos) for the teacher.
   The narration may not state facts beyond the brief.
4. **Plan gate** (`_work/plan.md`). Chapters with scene outlines, photos used,
   0–2 photos to animate as clips, estimated ElevenLabs characters, Gemini cost
   in dollars and time. **No paid call happens before the teacher approves.**
5. **Music and clips** (if Gemini). One Lyria track (`lyria-3.5`, ~$0.08) used as
   a looped bed; Veo 3.1 Lite image-to-video, 8 s, 16:9, 720p (~$0.40 each),
   extracted to JPEG frames for `clip()`. Claude checks a frame strip for drift
   and trims the frame count if the subject changes.
6. **Reference chapter.** Claude builds chapter 1 end to end: `script.json` →
   `narrate` → `scenes.js` → `stills` (fix overlaps and overflow, 2–3 rounds) →
   `render` → verify (ffprobe duration ≈ narration, audio present, 3–4 sampled
   frames). **Then it stops and asks the teacher** about tone, pace and look.
7. **Remaining chapters**, one at a time by default; parallel subagents if the
   teacher asks (faster, much heavier Claude usage). All state is on disk:
   re-running `/lesson-videos:make` (or `status`) resumes. Narration is cached by
   a hash of voice, model, settings and text, so editing one scene re-voices
   only that scene.
8. **Output** in `<deck folder>/lesson-videos/`: `Chapter N - <Title>.mp4`
   (burned-in captions), a matching `.vtt`, and `README.md` listing the videos
   with an AI-voice disclosure and a reminder that third-party photos in the deck
   mean the videos should not be posted publicly without checking. Nothing is
   uploaded.

Project layout in the teacher's folder:

```
<deck folder>/lesson-videos/
  Chapter 1 - <Title>.mp4  Chapter 1 - <Title>.vtt  README.md
  _work/
    deck/ (slides.md, media/, contact-*.jpg)   brief.md   plan.md
    music/bed.mp3   clips/<name>.mp4
    ch1/ (script.json, scenes.js, assets/, fonts/, index.html, build/)
```

## 7. Repository layout

```
plugins/
  .claude-plugin/marketplace.json     name "daniellandi", one plugin entry
  AGENTS.md  CLAUDE.md (@AGENTS.md)  SERVICES.md  README.md  LICENSE (MIT)
  .github/workflows/ci.yml
  docs/superpowers/specs/  docs/superpowers/plans/
  lesson-videos/
    .claude-plugin/plugin.json        name, version 0.1.0, description, author
    README.md                         teacher-facing
    skills/setup/SKILL.md
    skills/make/SKILL.md
    skills/make/references/guide.md   engine API, layout rules, narration style
    skills/make/references/sample/    script.json + scenes.js (water-cycle sample)
    scripts/lesson-videos.py          entry point, PEP 723 inline dependencies
    scripts/lv/                       keys, tools, ingest, narrate, render, mix,
                                      captions, sfx, music, clips, estimate, status
    engine/engine.js
    fonts/                            Patrick Hand + Nunito (both OFL) with licences
  examples/make_sample_deck.py        builds examples/water-cycle.pptx (no photos)
  tests/
```

**One command form on every OS:**
`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py" <command>`. Claude Code
substitutes `${CLAUDE_PLUGIN_ROOT}` in skill text. It is not an environment
variable in Bash-tool commands, and neither are `CLAUDE_PLUGIN_DATA` or
`userConfig` values. That is why keys live in our own file and why the plugin
does not use a `bin/` directory (a bash script there would not run under
PowerShell).

**Commands:** `doctor [--no-keys]` (the flag skips key checks, for CI), `keys`
(open file), `keys check`, `ingest`, `narrate`, `stills`, `render`, `music`,
`clip` (one Veo clip), `frames` (clip → JPEG frames), `estimate`, `status`.

**Engine changes:** font stacks only. The emoji stack gains `"Segoe UI Emoji"`.
The text stack becomes `"Avenir Next", "Nunito", …`, with Nunito (OFL) bundled
because Avenir Next exists only on macOS and Windows would otherwise fall back to
Arial. Nunito is preloaded alongside Patrick Hand. Macs still render Avenir Next,
so the Unit 1 `scenes.js` files stay valid and serve as the parity test.
The page protocol (`window.__ready`, `__render(t)`, `__sfx()`, `FILM.duration`)
stays the same.

**Renderer:** a Python Playwright port of `render.js`. It keeps the same local
HTTP server and per-frame JPEG capture piped into ffmpeg, and runs N worker
processes (default `min(4, cpu_count // 2)`, at least 1) over frame ranges
before concatenating.

**Constants in one place** (`lv/config.py`): ElevenLabs model
`eleven_multilingual_v2`, `mp3_44100_128` (allowed on the free plan), voice
settings, default voice, Veo and Lyria model IDs. Preview model names change, so
they must be easy to update.

## 8. Error handling

- Missing key → names `keys` and what the key unlocks; Gemini absent → music and
  clips skipped with one plain line, never a failure.
- ElevenLabs 401/402/429 → plain message with characters left; finished scenes
  stay cached; retry up to 3 times only on network errors and 5xx.
- Gemini 403/429 or billing errors → "billing not enabled or quota reached" and
  continue without that asset.
- Renderer page errors → exit non-zero and print the browser console errors so
  Claude can fix the chapter's `scenes.js`.
- Every file read and write passes `encoding="utf-8"`. Paths use `pathlib`.
  Subprocess calls use argument lists, never shell strings. Paths with spaces
  are tested.
- Keys are never printed, logged or put in exception messages; HTTP errors are
  scrubbed of headers.

## 9. Testing

1. **Unit tests** (`uv run pytest`, offline): word-timing parsing and scene
   timing math, narration cache key, keys file parsing and masking, ingest of
   the sample deck, SFX synthesis, VTT output, cost estimate, and a 3-second
   render verified with ffprobe.
2. **Parity check** (local, not committed): re-render Marine Biology Entry 1
   from its existing `script.json`/`scenes.js` with the new renderer, reusing its
   cached narration (same hash formula, so no API calls), and compare sampled
   frames and duration with the original MP4.
3. **End-to-end on this Mac** with a fresh `LESSON_VIDEOS_HOME`: `doctor`,
   `keys check`, then `/lesson-videos:make` on the sample deck, producing one
   roughly 1-minute video. Spend: 1–2k ElevenLabs characters, about $0.50 of
   Gemini (one Lite clip and one music track). Approved by Daniel 2026-10-06.
4. **CI** (GitHub Actions, `macos-latest` and `windows-latest`): unit tests plus
   `doctor --no-keys` (uv install path, Chromium, ffmpeg, test render). This
   covers Windows for everything except Claude Code itself.
5. **Install test:** in a throwaway Claude Code config, add the marketplace from
   GitHub, install the plugin, and confirm both skills are listed.

## 10. Repo conventions

- Created from `DanielLandi/repo-template` as **public**; **Tier B** (short-lived
  branch → local gates → merge to `main`; `TIER=B ./bootstrap.sh`, no branch
  protection).
- `AGENTS.md` rules: never commit class material, student data or keys; bump
  `version` for every teacher-visible change; skills must not use bash-only
  syntax; UTF-8 everywhere.
- `SERVICES.md`: ElevenLabs and Gemini API (keys supplied by each user; the repo
  holds none), GitHub Actions.

## 11. Risks

- **Windows Claude Code runs commands in Git Bash or PowerShell.** Skills use
  only `uv run "<path>" args`, which works in both.
- **School networks or PCs** may block the uv installer, the Chromium download
  or GitHub (static-ffmpeg). `doctor` names the failing step and the README
  lists the domains to allow.
- **Preview model IDs** (Veo Lite, Lyria) may change. They live in `config.py`,
  and errors name the model.
- **ElevenLabs terms** (free-tier attribution, government-entity clause) are the
  teacher's decision. Setup states them and does not decide for them.
- **Claude usage:** a full unit is heavy on a Pro plan. Default one-at-a-time
  plus resumable state lets it span sessions.

## 12. Facts this design relies on (checked 2026-10-06)

- Plugin manifest, `${CLAUDE_PLUGIN_ROOT}` substitution, and env-var scope:
  https://code.claude.com/docs/en/plugins/manifest-reference.md ("Where each
  variable resolves": `CLAUDE_PLUGIN_OPTION_*` only reaches hooks).
- Marketplace commands: https://code.claude.com/docs/en/plugins/create-marketplace.md
- ElevenLabs pricing and licence: https://elevenlabs.io/pricing ·
  https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform ·
  https://elevenlabs.io/use-policy · voice library voices are not available on
  the free API tier, so the default voice must be a premade voice (verify Jessica
  during implementation).
- Gemini: https://ai.google.dev/gemini-api/docs/pricing (Veo 3.1 Lite $0.05/s at
  720p; Lyria 3.5 $0.08/song; no free tier) ·
  https://ai.google.dev/gemini-api/docs/music-generation (Interactions API) ·
  https://ai.google.dev/gemini-api/docs/workspace (school accounts).
- uv install: https://docs.astral.sh/uv/getting-started/installation/ ·
  static-ffmpeg: https://pypi.org/project/static-ffmpeg/
