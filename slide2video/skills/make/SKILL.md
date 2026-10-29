---
name: make
description: Use when a teacher wants narrated study videos made from their slide deck (.pptx or .pdf). Reads the deck, writes a content brief in the teacher's wording, gets a costed plan approved, builds one reference chapter for feedback, then the rest, and saves MP4s with captions next to the deck. Resumes an unfinished run.
---

# Make lesson videos from a slide deck

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/slide2video.py"
```

If that path doesn't exist (in some claude.ai sessions `${CLAUDE_SKILL_DIR}` comes through empty), the plugin is under `/root/.claude/plugins/synced/`: use the `slide2video/scripts/slide2video.py` you find there.

If `uv` isn't found, or any command says a tool or key is missing, run the `setup` skill first.

Read `${CLAUDE_SKILL_DIR}/references/guide.md` before writing any `script.json` or `scenes.js`. The sample chapter in `${CLAUDE_SKILL_DIR}/references/sample/` shows every idiom.

**Folders.** Run `LV where` in the current folder first.
- If it says there is no project folder, everything goes next to the deck: for a deck at `<folder>/<deck>.pptx`, finished videos in `<folder>/slide2video/` and working files in `<folder>/slide2video/_work/` (`deck/`, `brief.md`, `plan.md`, `music/`, `clips/`, `ch1/`, `ch2/`…). If `<folder>/lesson-videos/_work/` already exists (a run started before the rename), use that instead, with finished videos in `<folder>/lesson-videos/`. Call the working folder **WORK**.
- If the teacher keeps lessons in a project folder, the lesson is a folder inside its lessons folder, one per course and unit (ask for both, e.g. `lessons/biology/unit-2`); create it and call it **WORK**. `LV where "WORK"` prints where each kind of file goes: the text (`brief.md`, `plan.md`, `chN/script.json`, `chN/scenes.js`) stays in WORK; images, clips, music and narration takes go under `sources`; what `ingest` extracts goes under `work`; finished videos under `videos`. Pass WORK (or `WORK/chN`) to every command, as below; the commands put each file in its place. Copy images with `LV asset` to the `assets:` folder that `LV where "WORK/chN"` prints. Put the deck and the other class files in a `class-materials/` folder inside the `videos` folder.

**Style.** Each run is made in one style, which decides the extra interview questions, the brief, the scene outline, the music and the writing guide. Once WORK is known:
- If `WORK/style.txt` exists, its one line is the style id.
- Otherwise, if WORK already has `brief.md` or `plan.md` (a run started before styles), the style is `school`.
- Otherwise run `LV styles`: with one style installed, use it without asking; with more, ask the teacher which, showing each style's name and description.
- Write the id to `WORK/style.txt`, then run `LV style <id>` and keep its output. Below, "the style's `questions`", `check`, `brief`, `outline`, `clips`, `music` and `guide` all mean fields of that output. Read the style's guide (its `guide` path) along with `guide.md` before writing any `script.json` or `scenes.js`.

**Ground rules.**
- The teacher's slides are the only source of facts. Never add facts, numbers or examples that aren't in the deck or in files the teacher points you to.
- The teacher's questions stay the teacher's. A question the deck (or a file the teacher added) asks the audience and leaves open (review, recap, exit ticket, homework, discussion, practice problems) is a **deck question**: shown as written and handed back with a pause, never answered, hinted at, pointed to ("it's on slide 7") or reworded into a quiz question. Speaker notes don't count as the deck answering: the audience never sees them, so a question answered only in the notes stays open (the notes remain a source of facts for the content scenes). If the slides themselves answer a question, that's content: explain it as usual. Deck questions on slides get their own scene (a slide with several questions is one scene); deck questions in added files are listed in `brief.md` and `plan.md` as left open and are not put in the video unless the teacher asks.
- Nothing that costs money (narration, music, clips) happens before the teacher approves the plan in step 4.
- Nothing is uploaded or published.
- Keep the teacher informed in plain words; they don't need to see commands.

**In a Cowork cloud session** (claude.ai on the web: a fresh Linux computer each time, the teacher's files arrive under `/root/.claude/uploads/`):
- Run `LV doctor --no-keys` once at the start. It installs what's missing (a browser from npm if the normal download is blocked) and names any website the teacher must allow under Settings → Capabilities → Additional allowed domains; tell them in plain words and that they need to start a new chat afterwards.
- Keys come as an attached **.zip** of their keys file. Run `LV keys load "<path of the attached .zip>"`. **Never open, unzip, read or `cat` it yourself**; `keys load` prints only which keys it found. If the teacher attached the keys file unzipped (a plain text file whose contents you can already see), don't use or repeat the keys: tell them to delete those keys on the websites, make new ones, and attach them zipped next time ([guide](../../docs/keys/keys-file.md)).
- The deck is among the attached files; use its folder as `<folder>` above. When a chapter is rendered, share the MP4 and its `.vtt` as downloadable files; that's not publishing. A file over 30 MB can't be downloaded: re-render that chapter with `--fps 24` and say so.

## 0. Resume?

If `WORK` already exists, run `LV status "WORK"` and read `WORK/plan.md`. Tell the teacher where things stand and continue from the first unfinished chapter (skip the steps already done).

## 1. Read the deck

Find the deck in the current folder (ask if there are several). Keynote, Google Slides or old `.ppt` files must be exported to `.pptx` first; `ingest` explains how. Run:

```
LV ingest "<deck path>" --work "WORK"
```

`WORK/deck/` below means the `deck/` folder that `ingest` printed. Read `WORK/deck/slides.md` in full and look at every `WORK/deck/contact-*.jpg` (and `deck/pages/` for PDFs). Ask whether there are other files to use (worksheets, labs, review sheets); read them too.

Then check the teacher's instructions (what they asked for when they started) against the deck, **before anything else**. If something they asked for is impossible or conflicting (a slide number past the last slide, a slide, title or topic that isn't in the deck, two requests that clash), ask about that first and nothing else: no interview and no other question until it is settled. Offer the closest matches from the deck as options but recommend none, since only the teacher knows what they meant; if the answer still doesn't fit the deck, ask again. Vague wishes ("make it fun") need no question.

## 2. Short interview (one message, sensible defaults offered)

- First the style's `questions`, in order. When a question's `options` is `"from-deck"`, write the options from the deck as its `hint` says and recommend one; otherwise offer its listed options.
- Chapters: propose a split from the deck's sections or titles (for example one video per unit/entry/lesson) and ask them to confirm or adjust.
- Length per video: default 4–6 minutes.
- Voice: with an ElevenLabs key (`LV keys check`), Jessica (warm, upbeat young American woman; the default) or Daniel (steady British man, news-presenter tone), recorded as `"voice"` in each `script.json`; without one, the free Microsoft voice (Ava), which needs no account. They can also ask for the computer's own voice (offline, more robotic) or captions only; record the choice as `"narrator"` in each `script.json` (see `guide.md`). If `LV keys check` prints **Allowed voices**, offer only those.
- Music and AI clips: only if a Gemini key is set (`LV keys check`).

## 3. Content brief

Write `WORK/brief.md`. Per chapter: what the style's `brief` lists. Then a section **"The teacher's questions (left open)"**: every deck question with its slide number or file name, or `None found.` Finish with a section **"Possible issues in the slides"**: contradictions between slides, typos in key terms, definitions worded two ways, and any chart whose values `slides.md` couldn't give (`[Chart not read: …]`). Show the teacher that section and ask how to handle each item (follow the slide, follow the correction, or leave it out).

## 4. Plan and approval gate

Write `WORK/plan.md`: for each chapter, the title, the output file name (`Chapter N - <Title>.mp4`), a scene outline (the style's `outline`), which deck questions it shows open (from the brief's "left open" section), which deck images it uses, and 0–2 photos per unit worth animating as AI clips (the style's `clips` says which). Then run:

```
LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music]
```

Show the teacher the outline in brief and the estimate, and **ask for approval**. Do not continue until they say yes. Note the approval and date at the top of `plan.md`.

## 5. Music and clips (only if approved and a Gemini key is set)

- Music: `LV music "WORK" --prompt "<the style's music prompt>"`. If it fails with a billing message, tell the teacher in one line and continue without music.
- Each clip: copy the source photo path from `WORK/deck/media/`, then `LV clip "<photo>" --work "WORK" --name <short-name> --prompt "<realistic footage of this exact photo: name the subject and keep it exactly as it is; only gentle natural motion (water, leaves, clouds, light); no text, no people added, no new objects>"`. A clip is 10 seconds. Look at `WORK/clips/<name>-strip.jpg`: if the subject changes into something else partway, or something appears that isn't in the photo, note how many seconds are usable and use `--max <seconds × 24>` below. The model may move the camera its own way (it often pulls back slowly); that's fine.

## 6. Reference chapter (chapter 1), then stop for feedback

Follow the workflow in `guide.md` for chapter 1 in `WORK/ch1/`:
1. Write `script.json` (narration per scene; `"music": "../music/bed.mp3"` only if music exists).
2. `LV narrate "WORK/ch1"`. It prints which voice it used. If it had to fall back (for example the free Microsoft voice was unavailable, or ElevenLabs credits ran out), tell the teacher in one line; running `narrate` again later switches back, and finished takes are kept.
3. Copy each image you use with `LV asset "WORK/deck/media/<file>" "WORK/ch1/assets/<name>.jpg"` (in a project folder, the target is in the `assets:` folder from `LV where "WORK/ch1"`) (it straightens, downscales to 1600 px and converts transparent PNGs; use `.png` as the target to keep transparency); for clips run `LV frames "WORK/clips/<name>.mp4" "WORK/ch1/assets/clip_<name>" [--max N]` (same `assets:` folder in a project; clips are in the `clips/` folder that `clip` printed).
4. Write `scenes.js`. Every chart, table and number from the deck appears unchanged: follow "Numbers from the deck" in `guide.md` and do its check.
5. `LV stills "WORK/ch1" <one time per scene>` and look at the `stills.jpg` it prints. Fix overlaps, text running off cards, things hidden behind captions, empty-looking scenes, and every `cue miss` warning. Repeat until clean (2–3 rounds is normal).
6. `LV render "WORK/ch1"`. Rendering takes about a minute per minute of video on a fast computer and several on a slow laptop: use the Bash tool's longest timeout (10 minutes), and for long chapters on slow machines run it in the background and check its output.
7. Verify: `render` prints the video length next to the narration length (they should match), and saves four frames of the finished video to the `final.jpg` it prints; look at them.

Then **stop**. Tell the teacher where the video is (the path `render` printed) and ask about tone, pace, reading level, voice and look. Apply their feedback to chapter 1 (re-narrating only changed scenes is cheap) before moving on, and write the agreed style notes at the top of `plan.md` so later chapters (and later sessions) follow them.

## 7. Remaining chapters

Default: one chapter at a time, same steps as 6.1–6.7, checking in briefly after each. If the teacher asks for speed, you may hand chapters to parallel helper agents; give each the exact **LV** command line (with the real plugin path, since helpers don't get it substituted), the paths to `guide.md` and the style's guide, `brief.md`, `plan.md` (with the style notes), its own `WORK/chN/` folder, and the finished `WORK/ch1/` as the reference. Tell the teacher this uses much more of their Claude plan.

Between chapters, `LV status "WORK"` shows what's left. If the session ends, the next `/slide2video:make` resumes from step 0.

## 8. Wrap up

Write `README.md` in the folder with the finished videos: a table of the videos with their lengths, one line on what each covers, and these notes:
- Narration: say which voice was used: an AI voice from ElevenLabs, the free Microsoft Edge voice (an unofficial Microsoft service; for classroom, non-commercial use), the computer's built-in voice, or captions only. Music and clips, if any, are AI-generated (Google).
- If the deck contains photos or diagrams from other sources, check their licences before posting the videos publicly; keeping them unlisted or sharing the files directly is safer.
- If ElevenLabs' free plan was used, a published video's title must include "elevenlabs.io".
- Each `.vtt` file holds the captions (they are also burned into the video).

Add any notes the style's guide lists for the wrap-up.

Tell the teacher the videos are done and where they are.

## Site mode (slide2video.com)

Use this mode when the folder you were started in has `site/turn.json`. The teacher is not at this computer:
they answer on slide2video.com, and `LV worker` ran you for one **turn**. Each turn is a new session that remembers
nothing from earlier turns except the files in the lesson folder, so keep every decision in the files listed
below. **Never ask in chat** and never wait for an answer: do the work for this turn, write `site/card.json`,
check it with `LV card "site/card.json"`, fix anything it reports, and **stop**.

- **Commands:** use the command in `site/lv.txt` exactly, in place of the command at the top of this skill (it is
  the same plugin with absolute paths). Only that command, file reading and file editing are allowed. Run each command
  as its own Bash call that starts with the text of `site/lv.txt`, followed by its arguments: never `cd`, a variable,
  `eval` or another command before it, and never `;`, `&&` or a pipe. Anything else is refused. Read and write files
  (progress, notes, cards) with the file tools, not the shell.
- Some commands are switched off in site mode (`open`, `pair`, `worker`, `init`, and `keys` except `keys check`); don't try them.
- **Replaces the chat steps:** site mode replaces every "ask the teacher" and "tell the teacher" in steps 0–8:
  questions go in a `questions` card, notices go in the card's `message`.
- **Files:** the deck and any other files are the `files` listed in `site/turn.json` (`kind` deck or extra),
  saved in `in/`.
- **Folders:** `WORK` is `lesson-videos/_work` (pass `--work "lesson-videos/_work"` to `ingest`); finished videos
  land in `lesson-videos/`.
- **Style:** a website lesson is always `school` for now: on the `start` turn write `school` to `WORK/style.txt`; every turn runs `LV style school` (a lesson with no `style.txt` is `school` too). `check.id`, `check.file`, `check.remove`, `check.keep` and `check.keep_decision` are fields of the `check` that `LV style school` prints: use their values, never the names.
- **Progress:** at each step, rewrite `site/progress.txt` with its lines plus one new line at the end, a line a
  teacher would understand ("Reading the deck", "Narrating 3 of 12 scenes", "Rendering chapter 1"). You can only
  read and write files, so write the whole file each time. The website shows the last line. When a step counts through items (scenes narrated, chapters rendered),
  end the line with ` [done/total]`, for example `Narrating scenes [3/12]`; the website shows it as a progress bar.
- **Notes:** when you notice something the teacher would find worth knowing (what the deck holds, a choice you made and why, an issue in the slides), rewrite `site/notes.txt` with its lines plus one new line at the end: one plain sentence of at most 120 characters, for example `51 slides, in 3 journal entries` or `Slide 21 spells it "Pheoophyta"; I'll ask which spelling to use`. Never a name of a person, nothing the style's check looks for, no file paths or commands. The website shows the last few while this turn runs; one note every few minutes of work is plenty.
- **Input:** the kind is the `kind` inside `turn` in `site/turn.json`. `instructions` (start) and `feedback`
  (change, feedback) are the teacher's words. `answers` (answer) are entries shaped like
  `{"question": "<id>", "choice": "<option label or null>", "other": "<typed text or null>"}`; `other` holds the
  teacher's own words when they chose Other. Anything the cards didn't settle uses this skill's defaults, and
  the card's message says which defaults were used.
- **Questions:** at most 8 per card. If there are more, keep the most important and decide the rest with the
  defaults, saying so in the message.
- **Approval:** `approve` approves exactly the plan card's estimate. Only make music or clips if the plan card
  listed them with their cost; otherwise make none. When the plan card's `markdown` includes music or clips, it
  must list them with their costs.
- **Files between turns** (in `WORK`):
  - `instructions.md`: the teacher's `instructions` from the `start` turn, word for word (only the `start` turn
    carries them), then each clarification the teacher gave about them. Every turn that writes `brief.md`, `plan.md`
    or a chapter follows it.
  - `WORK/<check.file>`: the slide numbers flagged by the style's check (never copy anyone's name into any file),
    and at its end the teacher's decision, a line `Decision: remove` or `Decision: <check.keep_decision>`. Every turn
    that writes `brief.md`, `plan.md` or a chapter reads it first (if it exists) and leaves the flagged slides out
    when the decision is `remove`.
  - `interview.md`: the interview answers: the style's questions, chapters, length, voice, and the decision for each
    possible issue.
  - `review.md`: its first line is `Under review: chapter N`; write it with every `review` card.
- **One chapter per turn**, no parallel helper agents.

What to do for each `turn.kind`, and which card ends it:

| `turn.kind` | Do | Card |
|---|---|---|
| `start` | Step 1 (ingest and read every slide). Write the teacher's `instructions` to `WORK/instructions.md` (write `None.` if there are none) and check them against the deck as step 1 says; if something is impossible or conflicting, stop here and send the instructions card. Then the style's check: look at every slide for what `check.looks_for` names; the website forbids it. If found, write the flagged slide numbers to `WORK/<check.file>` (`check.file`) and don't write `brief.md` yet (the `answer` turn writes it after the teacher's decision). If none was found, steps 2–3: write `brief.md`. | If the instructions check found something: `"questions"` with one question per problem (ids `instructions-1`, `instructions-2`, …; the closest matches from the deck as options; no option is `recommended`; `"other": true`), a message saying the rest waits until these are settled, and nothing else. Else if the style's check found something: `"questions"` with one question whose `"id"` is `check.id`, options labelled exactly `check.remove` and `check.keep`, and nothing else. Otherwise: the interview (the style's questions with their own ids, then chapter split, length, voice; options from step 2) plus one question per possible issue in the slides (follow the slide / follow the correction / leave it out). Give the possible-issue questions the ids `issue-1`, `issue-2`, …. |
| `answer` | Check the answers in this order. (1) An answer to `"question": "problem"` (see the failure paragraph below): act on it and continue from where the work stopped. (2) Answers to `instructions-…` questions: append each clarification to `WORK/instructions.md` and check the instructions again; if something is still impossible or conflicting, send the instructions card again and stop. Otherwise do the rest of the `start` row (the style's check, then `brief.md`) and send its card. (3) An answer to the question whose id is `check.id`: append `Decision: remove` (for `check.remove`) or `Decision: <check.keep_decision>` (for `check.keep`; `check.keep_decision` is the style's word for it) as the last line of `WORK/<check.file>`; if the decision is `remove`, leave the flagged slides out everywhere (otherwise keep them); if `brief.md` doesn't exist yet, write it now (steps 2–3). (4) The interview: if `interview.md` doesn't exist yet and the answers include the interview, write `interview.md` (the style's questions, chapters, length, voice, and the decision for each possible issue) before planning. If `interview.md` doesn't exist and there are no interview answers, send the interview card and stop: no planning in this turn. Otherwise (`interview.md` exists or was just written in this turn), step 4: read `WORK/<check.file>` if it exists, write `plan.md`, run `estimate`. | If (2) asked again or did the rest of the `start` row: that card. If the interview was asked: the interview `questions` card. Otherwise `"plan"`: `markdown` = the outline in brief (including the deck questions left open; with music and clips and their costs, if any); `estimate` = the JSON that `LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music] --json` prints (`"usd"`, `"items"` and `"quantities"`), plus `"minutes": <per video>` and `"chapters": <N>`. |
| `change` | Revise `plan.md` from `feedback`, re-run `estimate` (with `--json`, as in the `answer` row). | `"plan"` again, its `estimate` built as in the `answer` row. |
| `approve` | Note the approval and date at the top of `plan.md`. Steps 5–6 (music and clips only as the approval rule above allows), then chapter 1 (6.1–6.7). | `"review"` for chapter 1. |
| `feedback` | Read `review.md` for the chapter under review. Apply `feedback` to that chapter (re-narrate only changed scenes), re-render it. | `"review"` for the same chapter. |
| `continue` | Read `review.md` for the last chapter shown. Write the agreed style notes at the top of `plan.md` if not there yet. Make the next unfinished chapter after it (`LV status`). If none is left, step 8. | `"review"` for that chapter, or `"done"`. |

Card formats (all start with `"contract": 2`, `"kind"` and a one-line `"message"` for the teacher):

```json
{"contract": 2, "kind": "questions", "message": "A few questions before I plan the videos.",
 "questions": [{"id": "length", "text": "About how long should each video be?",
                "options": [{"label": "2–3 minutes", "detail": "Short and focused", "recommended": true}], "other": true}]}
```

- `"questions"`: up to 8 questions; ids are short lowercase words; each has 1–6 options (`label`, optional
  `detail`); `"other": true` lets the teacher type their own answer. Mark the option you'd choose by default with
  `"recommended": true` (at most one per question); the website shows it as Claude's suggestion and never picks it for
  the teacher.
- `"plan"`: `"markdown"` and `"estimate"` as above. `estimate.usd` is the plan's whole cost in US dollars, one
  number (a free voice counts as $0); take it from the `--json` output, never add up the lines `LV estimate` prints.
- `"review"`: `"chapter": N`, `"video"` (the MP4 path relative to this folder, e.g.
  `"lesson-videos/Chapter 1 - The Water Cycle.mp4"`), `"captions"` (its `.vtt`), `"stills"` (the `final.jpg`
  that `render` printed, relative to this folder; files outside `lesson-videos/` are refused). Write
  `review.md` first. The worker uploads the files; don't add `version` or `timing`.
- `"done"`: `"chapters": [{"chapter": 1, "title": "…"}]` and `"readme"` (the README text from step 8).

Card file paths must be inside `lesson-videos/`: video `.mp4`, captions `.vtt`, stills `.jpg`, `.jpeg` or `.png`.
Anything else makes the card an error. Use the paths `render` printed; `LV card` checks them too.

If something fails that the teacher must fix (a deck that can't be read, a key that was rejected), write a
`"questions"` card with one question whose `"id"` is `"problem"` and whose options say what to do next, and a message that explains the problem
in one line. Record where the work stopped in `plan.md`, so the next turn picks it up there.
