# slide2video.com design pass: identity, screens and four new details from the computer

**Status:** approved screens (2026-10-14), spec for review.
**Issue:** DanielLandi/slide2video#11 (Design pass: UX, visual design, graphics and logo).
**Approved mockups:** Claude Design canvas "slide2video design" (https://claude.ai/artifact/JhS3KPdkNu5YJovbJ7Pyc7),
section "Direction A: every screen", plus the lesson page `Main.dc.html` with its three states.
**Builds on:** `2026-10-13-lesson-videos-site-design.md` (M1: the site, the device loop, the contract).

## 1. Goal

The site works but looks like a bare demo. This pass gives it a real identity and reshapes the main flows so a
teacher who has never seen it can upload a deck, answer the questions, approve the plan and review each chapter
without help. Same features as M1, plus four details the computer reports to the site.

**Who uses it:** invited teachers, on school laptops and sometimes a classroom projector; not technical.

**Success:**
- Every signed-in page, the public Terms and Privacy pages and the not-invited page use the new identity.
- Each lesson shows where it is (a step line), whose turn it is, and one obvious next action.
- The four details (cost breakdown, progress bar, Claude's suggested answer, slide count) appear when a plugin that
  sends them is used, and the page reads correctly without them.
- No security rule is loosened: the CSP stays as it is (no inline styles or scripts), fonts are served by the site.
- An old plugin (0.5.x) keeps working with the new site; the new plugin keeps working with the current site and on
  its own in Claude Code (no site at all).

**Out of scope:** a public landing page; customising the Cloudflare Access sign-in page; a background worker on the
computer; Windows support; end-to-end encryption.

## 2. Identity: "Study notebook"

The site uses the videos' own palette and fonts, so the site and the videos read as one brand.

### 2.1 Colour tokens

Defined once in `app.css` as custom properties; every rule uses tokens. Light is the primary theme; dark follows
`prefers-color-scheme: dark`. Text pairs meet 4.5:1 (3:1 for text 24px and up).

| Token | Light | Dark | Role |
|---|---|---|---|
| `--paper` | `#FBF8F1` | `#101826` | page ground |
| `--card` | `#FFFFFF` | `#172233` | cards, inputs |
| `--ink` | `#16212E` | `#ECEFF3` | body text |
| `--heading` | `#0B2545` | `#F4F1EA` | headings, wordmark |
| `--muted` | `#5E6875` | `#A7B1BE` | secondary text |
| `--line` | `#E7DFCF` | `#2A3A52` | borders, the card's bottom edge |
| `--line-soft` | `#F0EADD` | `#22314A` | row dividers |
| `--primary` | `#0B2545` | `#FFC145` | primary button fill |
| `--on-primary` | `#FFFFFF` | `#0B2545` | primary button text |
| `--link` | `#137F7A` | `#6FD3C9` | links, "done" steps |
| `--teal` | `#1FA7A0` | `#1FA7A0` | logo, progress fill |
| `--foam` | `#E8F7F5` | `#163B3E` | soft teal panels, progress track |
| `--sun` | `#FFC145` | `#FFC145` | logo, current step, highlights |
| `--sun-soft` | `#FFF4E0` | `#3A3018` | selected choice, code box, attestation |
| `--pill-bg` / `--pill-ink` | `#FFE9B8` / `#7A4A00` | `#4A3A12` / `#FFE2A0` | "waiting for you" pills |
| `--turn` | `#C2412D` | `#FF8A73` | "your turn" notes, current step label |
| `--danger` | `#A3321F` | `#FF8A80` | destructive text and buttons |
| `--danger-line` | `#E9B4A9` | `#6B2A22` | the delete section's border |

### 2.2 Type

- **Nunito** (400, 700, 800) for all text; **Patrick Hand** for short handwritten notes: step labels, section
  labels on the lessons list, "your turn" lines, "What happens next". Both come from `lesson-videos/fonts/` (Open
  Font License), converted to latin-subset WOFF2 and served by the Worker at `/fonts/<name>.woff2` with
  `Cache-Control: public, max-age=31536000, immutable` and versioned file names. `font-display: swap`; fallback
  stacks `system-ui, -apple-system, "Segoe UI", sans-serif` and `"Comic Sans MS", cursive`. The licence texts
  ship beside them (`/fonts/OFL-*.txt`).
- Code and pairing codes use the system monospace stack (`ui-monospace, Menlo, Consolas, monospace`): no third font.
- Scale (px): 14 · 15 · 17 (body) · 19 · 20 · 22 · 26 · 40 (page title). Line height 1.55 for text, 1.1 for titles.

### 2.3 Logo

- **Mark:** two rounded slides, teal behind and navy in front, with a sun-yellow play triangle on the front one
  (the mockup's 48×40 SVG). Served as `/logo.svg`; also inline in the header.
- **Wordmark:** "slide2video" in Nunito 800, the **2** in a sun-yellow circle.
- **Favicon:** `/favicon.svg` (the mark alone) and a 32px PNG fallback, `<link rel="icon">` on every page.

### 2.4 Shape and spacing

Radius 12px for controls, 16px for cards, 99px for pills. Cards: `--card` fill, 1px `--line` border and a 3px
`--line` bottom edge (no blur shadows). Spacing steps 4 · 8 · 12 · 16 · 24 · 32. Touch targets at least 44px;
primary buttons 52px high. Content width 1120px (760px for Account), 24px side gutter (16px on phones).

## 3. Components

Server-rendered HTML with classes from `app.css` (no `style=` attributes: the CSP forbids them). `app.js` only
enhances; every page works without it.

| Component | What it is |
|---|---|
| Header | logo and wordmark (links to Lessons); nav: Lessons · Devices · Account (· Admin for the admin); the current page underlined in `--sun` |
| Buttons | primary (`--primary`), secondary (2px outline), danger (`--danger`); a link styled as a button for navigation |
| Step line | an ordered list: done (teal tick), current (sun dot with a `--turn` ring, `aria-current="step"`), to do (dashed circle); labels in Patrick Hand; scrolls sideways inside its own box on a phone |
| Status panel | the lesson's current state as a card: title, one line of detail, and the next action (§4.3) |
| Pill | a short status on the lessons list (`--pill-bg` for "waiting for you", `--foam` for "being made") |
| Choice card | a radio or checkbox inside a large bordered label; selected = 2px `--heading` border on `--sun-soft` |
| Drop zone | a file input inside a dashed teal label; works as a plain file picker; `app.js` adds drag and drop |
| Progress bar | `role="progressbar"` with `aria-valuenow`; shown only when the computer sent a fraction |
| Code box | the pairing code input: monospace 30px, upper-case, on `--sun-soft` |
| Notice | soft panels: teal (`--foam`) for information, sun (`--sun-soft`) for the student-information confirmation |
| Empty state | a small drawing (slide, dashed arrow, video) and the three-step start |

## 4. Screens

Every screen follows its approved artboard. Copy below is the copy to use.

### 4.1 Lessons (`/`)

- Title "Lessons" and a "New lesson" button.
- Lessons in three groups, each hidden when empty:
  - **Waiting for you:** the latest card is questions, plan, review or an error the teacher can act on. A card
    per lesson: picture, title, a pill ("4 questions to answer", "Plan ready to approve", "Chapter 2 ready to
    watch", "Something went wrong") and a call to action ("Answer them →", "Review the plan →", "Watch it →",
    "See what happened →").
  - **Being made:** a turn is queued or running, a plan limit is pausing it, or a deleted lesson is being removed
    from the computer. A row per lesson with its status line and, when the computer sent one, a progress bar.
  - **Finished:** done. A row with the number of chapters, the date it finished, and "Download all": the lesson's
    newest videos, captions and pictures as one zip, from a new route `GET /api/lessons/:id/export` built on the
    existing account export code (same streaming, scoped to one lesson and its teacher).
- The card picture is the newest chapter picture when there is one, else a tile in the palette with the title's
  first letter in Patrick Hand.
- **First visit** (no lessons): the empty state with three steps. Step 1, "Connect your home computer", links to
  Devices and shows as done once a device is connected; step 2 links to New lesson.
- The page keeps refreshing every 30 seconds while anything is being made (as today).

### 4.2 New lesson (`/lessons/new`)

- Drop zone for the deck (.pptx or .pdf, up to 100 MB). After choosing, a file row shows name, size and Replace.
- **Title** is filled from the file name (without extension, underscores and dashes as spaces) when still empty;
  the hint says "Taken from the deck. Change it if you like."
- Other files (optional) drop zone; Notes for Claude (optional) with an example placeholder.
- The no-student-information confirmation in a sun notice; "Upload and start" and "Cancel".
- Side panel "What happens next" (three steps) and the home computer's name and when it was last seen. With no
  device connected, the panel says so and links to Devices; the form still works (the lesson waits).

### 4.3 Lesson (`/lessons/:id`)

- Header: back link, title, and a line: file name · slide count (once known) · chapters (once planned) · started.
- **Step line:** Uploaded, Questions, Plan, Chapter 1…N, Done. N comes from the plan's `estimate.chapters` once a
  plan exists; before that a single "Chapters" step stands in. A changed plan updates N.
- **Status panel**, one of:
  - **Your turn** (questions, plan, review, actionable error): the card itself (§4.4–4.7), with a handwritten
    "Your turn" line.
  - **Working:** "Your computer is making …" with the step's text, how long ago it started, and the progress bar
    when a fraction was sent. "You can close this page; it shows up here when it's ready."
  - **Waiting for the computer:** the computer drawing, "Waiting for your computer", when it was last seen, "On that
    computer, run the line from setup in Terminal.", and a link to the connection guide.
  - **Paused for the plan limit**, **removed device**, **being removed**, **couldn't remove**: the existing texts
    and actions, in the same panel.
- **Earlier steps:** small link cards for past questions, plan and chapters; each opens that card read-only on the
  page (an anchor), not a separate page.

### 4.4 Questions card

- Heading "Claude read your deck and has N questions" (N from the card); the card's `message` under it.
- Each question is a fieldset of choice cards; an option's `detail` is a second line. An option with
  `recommended: true` carries "Claude suggests this" in Patrick Hand; nothing is preselected.
- "Other" becomes a choice card with a text field that `app.js` focuses when picked.
- A question whose id is `students`, or any id starting `issue`, sits in a sun-dashed panel (the "possible problem"
  look). Other ids use the plain look.
- "Send answers" and "Your computer writes the plan next. You can close this page meanwhile."

### 4.5 Plan card

- Heading "The plan: N chapters, about M minutes each" (from `estimate`), the plan text (the existing safe
  markdown subset), and "Every chapter gets captions and a picture for your slides."
- Cost panel: "Estimated cost", the total, and, when `estimate.items` exists, one row per item (label, detail,
  amount; "free" for 0). Then "Paid to the services on your own accounts. Claude's work is covered by your Claude
  plan." With no items: the total and that line only.
- "Approve and start", and "Ask for changes" (a `<details>` with the feedback box and "Send changes").

### 4.6 Review card

- Chapter heading and version chip; the video with captions; "Looks good, continue" and "Suggest a change" (opens
  the feedback box); downloads: video, captions, picture; the next chapter's cost when sent ("Continuing makes
  chapter 3: about $0.28."); resolved notes as today.

### 4.7 Done and error cards

- Done: "Finished" with the chapter list, every newest video to download, "Download all", and the readme.
- Error: as today ("Something went wrong" or "Paused", message, details, Try again), in the new card style.

### 4.8 Devices (`/devices`)

- Intro: "A device is a computer of yours, usually at home, that makes the videos for the lessons you upload here.
  It uses Claude Code signed in to your own Claude account." **Connected:** one row per device: name, "Last seen …", and "making N lessons" when
  N > 0; Remove (with the existing confirmation).
- **Add a device:** "About 15 minutes, once per computer · Mac today, Windows soon", then four numbered steps:
  install Claude Code (link to the install guide); add the plugin (the two lines in a dark code block with a Copy
  button that `app.js` adds); run setup; type the code (the code box and Connect, with the warning "Only type a code
  that your own computer is showing right now. Codes last 10 minutes."). Below: the Terminal-line note and the
  full-guide link (the GitHub guide added in plugin 0.5.1).

### 4.9 Account (`/account`)

- "Signed in as …". **Your data:** "N lessons · X MB of files and videos · N devices", "Download everything (.zip)".
- **Good to know:** the site never runs Claude and never sends lessons to anyone else's computer; Terms · Privacy.
- **Delete my account** in a danger-bordered section, unchanged behaviour.

### 4.10 Admin, Terms, Privacy, not invited

No artboards: they take the header, type and components above. Terms and Privacy keep their text, set at 65
characters per line. The not-invited page gets the logo and its existing text.

## 5. Four details from the computer

All four are **optional** additions to contract version 1. The schemas set no `additionalProperties: false`, so
the current site already accepts and ignores them, and the new site treats each as absent when missing.

### 5.1 Cost breakdown (plan card)

- Contract: `estimate.items`, an optional array of at most 8 `{"label": string 1–80, "usd": number ≥ 0,
  "detail": string ≤ 120 (optional)}`. `estimate.usd` stays the total and is what approval approves.
- Plugin: `LV estimate … --json` prints `{"usd": <total>, "items": [...]}` built from the same numbers as today's
  text report: narration (free voice: 0, "free voice"; ElevenLabs: 0 with detail "about N characters of your
  ElevenLabs plan"), music (`LYRIA_PRICE`), clips (`N × VEO_SECONDS × VEO_PRICE_PER_SECOND`, detail "N clips"). The
  text output without `--json` is unchanged. The make skill's site mode builds the plan card's `estimate` from it.

### 5.2 Progress bar (working state)

- Contract (heartbeat): `POST /api/device/turns/:id/heartbeat` accepts an optional `"fraction"`, a number from 0
  to 1. The site stores it in a new `turns.progress_fraction` column (migration `0002`), clears it when a turn is
  claimed, and rejects other types with 400 as it does for `progress`.
- Plugin: in site mode a progress line may end with ` [a/b]` (for example `Narrating scenes [3/12]`). The worker
  strips it from the text it sends and sends `fraction = a / b` when `0 ≤ a ≤ b` and `b > 0`; anything else is sent
  as plain text with no fraction. The make skill's site-mode progress rule says when to add it (counted steps:
  scenes narrated, chapters rendered).

### 5.3 Claude's suggested answer (questions card)

- Contract: a question option may carry `"recommended": true`; at most one per question (the site shows only the
  first if more arrive).
- Plugin: the make skill's site mode marks the option it would choose by default (the same defaults it already
  states in the message), and names each possible-issue question `issue-<n>` so the site can set it apart (§4.4).

### 5.4 Slide count

- Contract: any card may carry `"slides"`, an integer 1–500.
- Plugin: `ingest` also writes `deck.json` (`{"slides": N}`) beside `slides.md` in `<WORK>/deck/`. The worker adds
  `"slides"` to every card it uploads when that file exists and the card has none. Claude doesn't need to know.
- Site: a new nullable `lessons.slides` column (migration `0002`), set whenever a finished turn's card carries
  `slides`. Shown on the lesson header and nowhere before it is known (the upload page shows the file size only).

### 5.5 Compatibility

| Plugin | Site | Result |
|---|---|---|
| 0.5.x | new | works; no breakdown, no bar, no suggestion, no slide count |
| 0.6.0 | current (M1) | works; extra fields stored in the card body and ignored; `fraction` ignored |
| 0.6.0 | new | everything shown |
| 0.6.0 | none (Claude Code alone) | unchanged; `deck.json` is one extra file; `estimate` text output unchanged |

**Order:** deploy the site first, then publish plugin 0.6.0 (version bumped in `plugin.json`, the marketplace entry
and `lv/__init__.py`). The canonical schema change lands in `lesson-videos/site-contract/` and is copied to the
site's `contract/` in the same change set, as today.

## 6. Constraints

- CSP unchanged: `style-src 'self'`, `script-src 'self'`, fonts from `'self'`. No CDN, no inline style attributes.
- Public paths: `/fonts/*`, `/logo.svg` and `/favicon.svg` join the Access bypass app (beside `app.css`), since the
  public pages and the not-invited page use them.
- Engine API of the plugin unchanged; `estimate`'s text output unchanged.
- Model IDs and prices stay in `lv/config.py`.
- No new client library; `app.js` stays small (drop zone, title fill, Other focus, copy button, refresh, times).
- Existing tests keep their promises (isolation, escaping, deletion, pairing); where a test asserts old wording,
  the wording change is deliberate and the test is updated with it.

## 7. Testing

- **Site** (`npm run check && npm test`):
  - every page renders without `style=` attributes and passes the existing escaping and safety checks;
  - lessons list grouping for each state; first-visit empty state with and without a device;
  - step line: before a plan, with N chapters, after a changed plan, done;
  - plan card with and without `items`; questions with `recommended` and with two recommended options;
  - heartbeat `fraction`: stored, cleared on claim, wrong types rejected; bar shown only with a fraction;
  - `slides` stored from a card and shown; absent without it;
  - cards from a 0.5.x plugin (no new fields) render as before;
  - `/fonts/*`, `/logo.svg`, `/favicon.svg` served with the security headers and long cache.
- **Plugin** (`uv run pytest -q`): `estimate --json` numbers match the text report; worker strips ` [a/b]`, sends
  the fraction, rejects bad fractions; worker adds `slides` from `deck.json`; `ingest` writes `deck.json`; schema
  examples include the new fields and still validate; packaging versions agree.
- **By hand:** the deployed site in light and dark, at phone width and on a projector-size window; one real lesson
  with the 0.6.0 plugin once a computer can be connected.
