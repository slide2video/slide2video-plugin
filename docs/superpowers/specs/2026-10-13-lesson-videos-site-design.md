# slide2video.com — a website for lesson-videos, processed on the teacher's own Mac

**Date:** 2026-10-13 · **Status:** approved in chat, awaiting written-spec review
**Repos:** new `slide2video` (the website at **slide2video.com**) + `plugins` (`lesson-videos` plugin: site mode, `lv pair`,
`lv worker`, the job contract) · **Supersedes:** the local studio page in issue #1

## 1. Purpose

Teachers can't always sit at the computer that makes their videos. A teacher should be able to:

1. sign in to a website from a **school computer** (nothing installed there),
2. upload a slide deck or PDF,
3. answer Claude's questions and approve the plan **on the website**,
4. have their **own Mac at home** do the work on their **own Claude subscription**, unattended,
5. watch each finished chapter on the website, add **notes at specific timestamps**, and send them back so the
   Mac redoes just those scenes.

After the one-time setup on the Mac (install Claude Code and the plugin, pair the Mac) the teacher never needs a
terminal.

**Success:** a teacher uploads during a free period at school; the Mac at home builds the chapter; the next day
they review and annotate it on the website.

## 2. Decisions taken in the brainstorm

| Topic | Decision |
|---|---|
| Who signs in (v1) | Daniel and a few invited teachers. Terms, privacy policy and Washington student-data compliance (Northshore School District) from day one. |
| Student data | **Never, by rule.** Teacher-made material only: an upload tick box, a check by Claude in site mode, and the Terms (§9.2). |
| Where processing happens | Only on Macs the teacher has paired to their own account (issue #1: no volunteer machines, no processing on the site). |
| How the Mac picks up work | **Unattended background helper** (LaunchAgent) running Claude Code headless. |
| Sign-in | **Emailed one-time code** (any email address) against an allow-list of invited emails. |
| Retention | **Until the teacher deletes** the lesson or their account; deletion is immediate and complete. |
| Platform | **Cloudflare:** Workers (site + API), R2 (files), D1 (data), Cloudflare Access (sign-in). |
| Code location | **New repo `slide2video`.** Canonical job contract lives in the `plugins` repo (§5). |
| Name and address | **slide2video.com** (Daniel's domain), added to Cloudflare DNS so the Worker and Access can serve it. The plugin keeps its name, `lesson-videos`. |
| Scope | One spec for the whole system; built in three milestones (§11), each with its own plan. |

## 3. Findings this design rests on

- **Northshore signs the standard Washington Student Data Privacy Agreement (WA-SDPA)** with its vendors
  through the Student Data Privacy Consortium (signed examples: Seesaw, McGraw-Hill, Pearson; sdpc.A4L.org).
- **Washington's SUPER Act (RCW 28A.604)** covers online services used at a school's direction that collect
  *student personal information*: no targeted advertising to students, no student profiles beyond school
  purposes, use limited to the contract, the same duties flowed down to subcontractors, contracts binding a
  successor in a merger.
- Because decks never contain student information (§2), the site should fall largely outside those duties. It
  still follows their basics (no ads, no selling, no profiling, a subprocessor list, deletion, breach notice) so
  that signing a WA-SDPA, if Northshore asks, needs no redesign.
- **R2 and D1 guarantee a region only for the EU and FedRAMP jurisdictions;** for the US they take a *location
  hint* (western North America). The privacy policy says exactly that. If Northshore requires guaranteed US
  storage, the fallback is Supabase pinned to us-west-2 (the job contract and the Mac side are unchanged).
- **Cloudflare Access** (Zero Trust, free up to 50 users) offers a one-time PIN login by email against an
  allow-list and passes a signed JWT (`Cf-Access-Jwt-Assertion`) to the Worker. The site never handles
  passwords, codes or sessions.
- The `make` skill already pauses at exactly four kinds of points (interview + possible issues, plan approval,
  chapter 1 feedback, a check-in after each later chapter) and already resumes from the work folder
  (`/lesson-videos:make` step 0). Site mode reuses both.
- A live Cowork run on 0.4.4 confirmed the interview fits multiple-choice cards (4 questions with options, one
  of them the deck's planted inconsistency) and the plan fits one approve/change card.

**Not a legal opinion.** The Terms and privacy policy (§9.3) are drafts to be reviewed by the district or a
lawyer before any teacher is invited.

## 4. Architecture

```
School computer (browser)            Cloudflare                              Teacher's Mac
────────────────────────    ──────────────────────────────────    ─────────────────────────────────
sign in (emailed code) ───▶ Access: allow-listed emails only
upload, answer cards,       Worker "slide2video"            lv worker (LaunchAgent, every 5 min)
approve, watch, annotate ─▶   • web pages + JSON API      ◀──────   • device token from the Keychain
                              • verifies the Access JWT             • claims its owner's next turn
                              • scopes every query to the teacher   • runs `claude -p` (site mode)
                            D1: teachers, devices, lessons,         • uploads outputs + the next card
                                files, turns, cards, notes, events
                            R2: t/<teacher>/<lesson>/…
```

**The site is the teacher's side of the conversation.** In site mode Claude does not ask questions in a chat:
at each pause point it writes a **card** and stops. The teacher answers the card on the site, which queues the
next **turn**; the Mac resumes from the lesson's work folder.

- The **site never runs Claude** and never sends anything to Anthropic.
- All files pass through the Worker (R2 binding); there are no public or presigned URLs. Video is served with
  HTTP range support so seeking works.
- One Worker serves pages and API. Access protects every path except `/api/device/*`, which accepts only device
  tokens (Access "bypass" policy for that path).
- Address: **https://slide2video.com** (Worker custom domain; Access application on the same hostname). `/terms`
  and `/privacy` are public (Access bypass), like `/api/device/*`.

## 5. The job contract (shared by both repos)

Canonical JSON Schemas live in `plugins/lesson-videos/site-contract/` with `CONTRACT_VERSION` (integer, starts
at 1). `slide2video/contract/` holds a pinned copy plus the version it was copied from.

- Every device request sends `X-LV-Contract: <n>`. A site on a different major version answers **426** with
  `{"error": "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos"}`, and `lv worker`
  prints that message.
- Both test suites validate the same sample files (`site-contract/examples/*.json`) against the schemas.

### 5.1 `turn.json` (site → Mac; written to `<lesson>/site/turn.json`)

```json
{
  "contract": 1,
  "lesson": {"id": "les_…", "title": "Unit 3 – The Water Cycle"},
  "turn": {"id": "trn_…", "seq": 4, "kind": "answer"},
  "files": [{"id": "fil_…", "name": "water-cycle.pptx", "kind": "deck", "sha256": "…", "path": "in/water-cycle.pptx"}],
  "instructions": "Free text the teacher typed at upload (optional)",
  "answers": [{"question": "q1", "choice": "Grades 6–8", "other": null}],
  "approval": null,
  "feedback": null,
  "notes": [],
  "delete": false
}
```

`kind` is one of `start` (new lesson), `answer` (questions card), `approve` / `change` (plan card),
`continue` / `feedback` (review card), `revise` (notes, §8), `delete` (§9.4). Only the fields for that kind are
set.

### 5.2 `card.json` (Mac → site; Claude writes `<lesson>/site/card.json`)

```json
{"contract": 1, "kind": "questions", "message": "One line for the teacher",
 "questions": [{"id": "q1", "text": "What grade are the students?",
                "options": [{"label": "Grades 6–8", "detail": "Middle school"}], "other": true}]}
```

- `questions`: as above. The first card of a lesson always includes any **possible student information** found
  in the slides (§9.2) and the **possible issues in the slides** (make step 3).
- `plan`: `{"markdown": "<outline>", "estimate": {"usd": 0.0, "minutes": 3, "chapters": 1}}`; the site shows
  **Approve** and **Change something** (free text).
- `review`: `{"chapter": 1, "version": 2, "video": "out/ch1/v2/Chapter 1 - The Water Cycle.mp4",
  "captions": "….vtt", "stills": "…stills.jpg", "timing": "…timing.json", "resolved": [{"note": "nte_…",
  "answer": "Moved the photo left; the caption no longer covers it."}], "cost_next": {"usd": 0.0}}`; the site
  shows the player (§8), a feedback box and **Looks good, continue**.
- `done`: the wrap-up (make step 8): list of chapters and the README text.
- `error`: `{"message": "…", "log_tail": "…", "retry_after": null | "<ISO time>"}` (written by `lv worker`,
  not Claude, when Claude fails or hits a usage limit, §6.4).

### 5.3 `timing.json` (Mac → site, one per video version)

`{"duration": 161.2, "scenes": [{"id": "condensation", "start": 15.2, "dur": 22.4, "label": "Condensation",
"first_words": "When warm, moist air rises…"}]}`, derived from `build/timing.js`.

### 5.4 Device API (`/api/device/*`, bearer token)

| Method & path | Purpose |
|---|---|
| `POST /pair/start` | → `{user_code: "KQ7-4M2", device_code, expires_in: 600}` (no token needed) |
| `POST /pair/poll` | `{device_code}` → `{token}` once the teacher entered the code, else 428 |
| `GET /next` | claim the oldest queued turn for this teacher whose lesson is new or homed here → `turn.json` + lease (30 min), or 204 |
| `POST /turns/:id/heartbeat` | renew the lease; body `{progress: "Rendering chapter 1"}` |
| `GET /files/:id` | download an input file (range supported) |
| `PUT /turns/:id/files?path=out/…` | upload an output file (≤ 100 MB) |
| `POST /turns/:id/finish` | body = `card.json`; marks the turn `done` (or `failed` for `error`) |
| `GET /status` | `{teacher, device, contract}`, for `lv worker --status` |

Every call updates the device's `last_seen`. A revoked token gets 401 and `lv worker` tells the teacher to pair
again.

## 6. The Mac side (plugin: `lv pair`, `lv worker`, site mode)

### 6.1 Pairing

`/lesson-videos:setup` gains an optional last step, "Connect this Mac to the website?", which runs `lv pair`:
it calls `pair/start`, prints the site address and the code, and polls `pair/poll` every 5 s for 10 minutes. The
teacher signs in anywhere and enters the code under **Devices → Add a Mac** (and names it). The token is stored
in the **macOS Keychain** (`security add-generic-password -s slide2video -a <site>`), never in a file;
the site stores only its SHA-256.

### 6.2 The background helper

- `lv worker --install` (run by setup after pairing) writes
  `~/Library/LaunchAgents/net.daniellandi.lesson-videos.worker.plist` with `StartInterval` 300 s, running
  `~/.lesson-videos/worker-launcher` (a small script that finds the newest installed lesson-videos under
  `~/.claude/plugins/cache/` and runs its `lesson-videos.py worker --once`). Plugin updates therefore never
  break the agent. The full paths of `uv` and `claude` found at install time are recorded in
  `~/.lesson-videos/worker.json` (LaunchAgents start with a minimal PATH). `--uninstall` removes it.
- `worker --once`: if no turn → exit in under a second. With a turn: run it under `caffeinate -i`, one turn at
  a time (a lock file prevents overlapping runs).
- Lessons live in `~/Lesson Videos/<lesson title> (<lesson id>)/`, the same layout `make` uses today (deck in
  `in/`, work in `lesson-videos/_work/`, videos in `lesson-videos/`), plus `site/` for `turn.json`,
  `card.json` and `progress.txt`.
- `lv worker --status` prints the paired site, teacher, last check, and the current turn.

### 6.3 Running Claude unattended

For each turn the worker downloads missing inputs (by sha256), writes `site/turn.json`, and runs, in the lesson
folder:

```
claude -p "Run /lesson-videos:make in site mode for this folder." \
  --allowedTools "Bash(<uv> run <plugin>/scripts/lesson-videos.py:*)" Read Write Edit Glob Grep \
  --disallowedTools WebFetch WebSearch
```

- Tools are limited to the plugin's own `LV` commands and file access; no web tools, no other shell commands.
  The deck is the teacher's own, but this caps what stray text in a slide could make Claude do.
- Every minute the worker sends a heartbeat with the last line of `site/progress.txt`. The make skill writes
  that line at each step (e.g. "Narrating 3 of 12 scenes", "Rendering chapter 1").
- On exit the worker requires a valid `site/card.json` (schema-checked), uploads the files it names, then calls
  `finish`.

### 6.4 Failures

| Situation | Behaviour |
|---|---|
| Claude exits non-zero, or no/invalid card | `error` card with the last 40 log lines (keys redacted with `keys.redact`) and **Try again** |
| Usage limit of the Claude plan reached | `error` card "Your Claude plan's limit was reached; this continues automatically after <time>"; the turn is re-queued with `not_before` |
| Mac asleep or off mid-turn | the lease expires; the turn returns to `queued`; the next run resumes from the work folder |
| Mac never checks in | lesson page shows "Your Mac was last seen <when>" |
| Contract mismatch | 426 → "Update the lesson-videos plugin on this Mac" |

### 6.5 Site mode in the `make` skill

A new section in `skills/make/SKILL.md`, used when `site/turn.json` exists:

- Never ask in chat. At each pause point write `site/card.json` and **stop**: interview + possible issues →
  `questions`; plan → `plan`; chapter 1 and each later chapter → `review`; wrap-up → `done`.
- Read the teacher's input from `turn.json` instead of the chat (answers, approval, feedback, notes).
- Write one short line to `site/progress.txt` at each step.
- Defaults instead of follow-up questions: anything the cards didn't settle uses the skill's existing defaults.
- No parallel helper agents in site mode (one chapter per turn).

## 7. The website

Pages (server-rendered HTML from the Worker plus a small amount of JavaScript; no framework required):

- **Lessons:** list with status ("Waiting for your answer", "Your Mac is working: Rendering chapter 1",
  "Chapter 2 ready to review", "Done").
- **New lesson:** title, files (deck + optional extras), optional instructions, the required student-data tick
  box (§9.2). Creates the lesson and a `start` turn.
- **Lesson:** the current card (questions with clickable options and an "Other" box; plan with Approve/Change;
  review with the player), plus history of previous cards and the chapter list with downloads.
- **Devices:** paired Macs with last seen, **Add a Mac** (code entry), **Revoke**.
- **Account:** export (zip of the teacher's files and a JSON of their data), delete account.
- **Admin** (only the admin email): invite/remove teachers (updates the Access allow-list via the Cloudflare
  API) and per-teacher storage use.
- **Terms**, **Privacy** (public, outside Access).

While a turn is `queued` or `running`, the card is read-only and shows the progress line.

## 8. Timestamp notes and revisions

- The player shows **scene marks** on the progress bar (from `timing.json`) and the current scene's label.
- **Add a note** (button or `N`) pauses and stamps time and scene ("1:20 · Condensation"); the teacher types the
  note. A chapter can also have one general note. Notes are drafts until **Send notes to my Mac (n)**, which
  creates one `revise` turn carrying all of them.
- Site mode, `revise`: map each note to its scene by time; change only those scenes in `script.json` /
  `scenes.js`; re-narrate only scenes whose words changed (cached takes are reused, so ElevenLabs costs only the
  changed sentences, and the card states the cost when it is not zero); stills check on the changed scenes;
  render as the next version; `review` card answers each note in one line.
- Answered notes become **resolved**; the teacher can reopen one. A **v1 / v2** switch keeps the playback
  position. **Looks good, continue** moves on.

## 9. Security and privacy

### 9.1 Security

- The Worker verifies the Access JWT on every request (signature against the team's certs, `aud`, expiry) and
  looks up the teacher by its email; an email without a `teachers` row gets 403.
- Every D1 query is scoped by `teacher_id`; ids are random (`les_` + 22 base62 chars). Tests prove a teacher
  cannot read, list, change or delete another teacher's lessons, files, notes, cards or devices.
- Device tokens: 32 random bytes, stored as SHA-256, accepted only on `/api/device/*`, scoped to their teacher;
  pairing codes expire after 10 minutes; a teacher gets 5 wrong code entries per hour, and `pair/start` is
  rate-limited per IP.
- Uploads: `.pptx`, `.pdf`, `.docx`, `.png`, `.jpg`; ≤ 100 MB per file; names sanitised. Everything except
  video is served with `Content-Disposition: attachment`. Headers: strict CSP, `X-Content-Type-Options`,
  `Referrer-Policy: no-referrer`, `frame-ancestors 'none'`.
- `events` table: upload, delete, export, device paired/revoked, invite changes (sign-ins are in Access logs).
- Secrets (Access audience, Cloudflare API token for the admin page) are Worker secrets, never in the repo.

### 9.2 Student information: never, by rule

1. New-lesson form: required tick box "These files contain no student names, photos or work."
2. Site mode's first `questions` card lists anything in the slides that looks like student information (name
   lists, class photos, graded work) and asks to remove it; the lesson stops until the teacher confirms.
3. The Terms forbid uploading it.

### 9.3 Legal pages (drafted in the site repo; reviewed before inviting anyone)

- **Terms:** invite-only; teacher-made material only; no student information; teachers keep ownership of their
  slides and videos; the service may change or stop with notice; contact.
- **Privacy policy:** what is stored (account email, files, cards, notes, device names, the event log); where
  (Cloudflare, location hint western North America, not guaranteed); how long (until deleted); who processes
  what (Cloudflare: hosting, storage, sign-in. On the teacher's own Mac, by the teacher's choice and under their
  own accounts: Anthropic via their Claude subscription, Microsoft or ElevenLabs for narration, Google for music
  and clips. The site itself sends nothing to them); no ads, no selling, no profiling; export and deletion on
  request; breach notice within 72 hours; how to ask for a signed WA-SDPA.

### 9.4 Deletion

- **Lesson:** R2 prefix and D1 rows deleted at once, except a tombstone (lesson id, home Mac, folder name; no
  title, files or text) carrying a `delete` turn for the home Mac. The Mac removes the lesson folder at its next
  check-in and reports back; then the tombstone is deleted too. The Lessons page shows "Removing from your Mac"
  until then.
- **Account:** every lesson as above, every device revoked, the email removed from the Access allow-list.

## 10. Testing

- **Site (`slide2video`):** Vitest with `@cloudflare/vitest-pool-workers` (local D1 and R2). Access JWTs
  signed by a test key. Covers: sign-in rejection paths, ownership (cross-teacher access on every route),
  pairing (expiry, attempts), turn claim/lease/expiry/re-queue, `not_before`, upload limits, range requests,
  deletion, contract mismatch (426).
- **Contract:** both repos validate `site-contract/examples/*.json`; the site repo's test fails if its pinned
  copy differs from the version it declares.
- **Plugin (`plugins`):** pytest for `lv pair` and `lv worker` against a fake local site (HTTP server fixture),
  with the Keychain and `claude` faked; card validation; launcher path finding; `timing.json` export.
- **End to end, per milestone:** one real run on Daniel's Mac against a preview deployment, with the sample deck.

## 11. Milestones (one plan each)

- **M1, the loop by hand:** site repo, Access, invites/admin, upload, lessons, all card types, player (no notes),
  downloads, deletion, export, legal pages; plugin: contract schemas, `lv pair`, `lv worker --once` run by hand,
  site mode in `make`. Done when a teacher can go from upload to a downloaded chapter with the worker run
  manually.
- **M2, unattended:** first a spike: does `claude -p`, launched by a LaunchAgent, run on the subscription login
  without prompts? Then the LaunchAgent and launcher, `caffeinate`, heartbeats and progress, usage-limit
  re-queue, Devices page with last seen.
- **M3, notes:** timestamp notes, `revise` turns, versions and the v1/v2 switch.

## 12. Out of scope (v1)

Open sign-up; Windows workers; moving a lesson between Macs; drawing on frames or comment threads; sharing
links for students or colleagues; guaranteed US data residency (fallback noted in §3);
processing anywhere but the teacher's own Mac.
