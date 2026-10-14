---
name: make
description: Use when a teacher wants narrated study videos made from their slide deck (.pptx or .pdf). Reads the deck, writes a content brief in the teacher's wording, gets a costed plan approved, builds one reference chapter for feedback, then the rest, and saves MP4s with captions next to the deck. Resumes an unfinished run.
---

# Make lesson videos from a slide deck

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_SKILL_DIR}/../../scripts/lesson-videos.py"
```

If that path doesn't exist (in some claude.ai sessions `${CLAUDE_SKILL_DIR}` comes through empty), the plugin is under `/root/.claude/plugins/synced/`: use the `lesson-videos/scripts/lesson-videos.py` you find there.

If `uv` isn't found, or any command says a tool or key is missing, run the `setup` skill first.

Read `${CLAUDE_SKILL_DIR}/references/guide.md` before writing any `script.json` or `scenes.js`. The sample chapter in `${CLAUDE_SKILL_DIR}/references/sample/` shows every idiom.

**Folders.** Run `LV where` in the current folder first.
- If it says there is no project folder, everything goes next to the deck: for a deck at `<folder>/<deck>.pptx`, finished videos in `<folder>/lesson-videos/` and working files in `<folder>/lesson-videos/_work/` (`deck/`, `brief.md`, `plan.md`, `music/`, `clips/`, `ch1/`, `ch2/`…). Call `<folder>/lesson-videos/_work` **WORK**.
- If the teacher keeps lessons in a project folder, the lesson is a folder inside its lessons folder, one per course and unit (ask for both, e.g. `lessons/biology/unit-2`); create it and call it **WORK**. `LV where "WORK"` prints where each kind of file goes: the text (`brief.md`, `plan.md`, `chN/script.json`, `chN/scenes.js`) stays in WORK; images, clips, music and narration takes go under `sources`; what `ingest` extracts goes under `work`; finished videos under `videos`. Pass WORK (or `WORK/chN`) to every command, as below; the commands put each file in its place. Copy images with `LV asset` to the `assets:` folder that `LV where "WORK/chN"` prints. Put the deck and the other class files in a `class-materials/` folder inside the `videos` folder.

**Ground rules.**
- The teacher's slides are the only source of facts. Never add facts, numbers or examples that aren't in the deck or in files the teacher points you to.
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

## 2. Short interview (one message, sensible defaults offered)

- Grade level of the students.
- Chapters: propose a split from the deck's sections or titles (for example one video per unit/entry/lesson) and ask them to confirm or adjust.
- Length per video: default 4–6 minutes.
- Voice: with an ElevenLabs key (`LV keys check`), Jessica (warm, upbeat young American); without one, the free Microsoft voice (Ava), which needs no account. They can also ask for the computer's own voice (offline, more robotic) or captions only; record the choice as `"narrator"` in each `script.json` (see `guide.md`).
- Music and AI clips: only if a Gemini key is set (`LV keys check`).

## 3. Content brief

Write `WORK/brief.md`. Per chapter: the essential question if the deck has one; key terms with definitions **in the teacher's own wording**; examples and lab data from the slides; likely test questions; common mistakes worth a "trap" warning. Finish with a section **"Possible issues in the slides"**: contradictions between slides, typos in key terms, definitions worded two ways. Show the teacher that section and ask how to handle each item (follow the slide, follow the correction, or leave it out).

## 4. Plan and approval gate

Write `WORK/plan.md`: for each chapter, the title, the output file name (`Chapter N - <Title>.mp4`), a scene outline (hook, 6–12 content scenes, a 3-question quiz, recap for 4–6 minutes; for shorter videos scale down, e.g. one scene per key idea and a 1-question quiz), which deck images it uses, and 0–2 photos per unit worth animating as AI clips (real photos of living things or landscapes that benefit from motion; not drawings or clip-art, which Veo turns into realistic footage partway through; never diagrams with text, never photos of students). Then run:

```
LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music]
```

Show the teacher the outline in brief and the estimate, and **ask for approval**. Do not continue until they say yes. Note the approval and date at the top of `plan.md`.

## 5. Music and clips (only if approved and a Gemini key is set)

- Music: `LV music "WORK" --prompt "<calm, light instrumental study music, no vocals, steady gentle beat>"`. If it fails with a billing message, tell the teacher in one line and continue without music.
- Each clip: copy the source photo path from `WORK/deck/media/`, then `LV clip "<photo>" --work "WORK" --name <short-name> --prompt "<cinematic, realistic, slow camera move, describe the subject and its natural motion, no text>"`. Look at `WORK/clips/<name>-strip.jpg`: if the subject changes into something else partway, note how many seconds are usable and use `--max <seconds × 24>` below.

## 6. Reference chapter (chapter 1), then stop for feedback

Follow the workflow in `guide.md` for chapter 1 in `WORK/ch1/`:
1. Write `script.json` (narration per scene; `"music": "../music/bed.mp3"` only if music exists).
2. `LV narrate "WORK/ch1"`. It prints which voice it used. If it had to fall back (for example the free Microsoft voice was unavailable, or ElevenLabs credits ran out), tell the teacher in one line; running `narrate` again later switches back, and finished takes are kept.
3. Copy each image you use with `LV asset "WORK/deck/media/<file>" "WORK/ch1/assets/<name>.jpg"` (in a project folder, the target is in the `assets:` folder from `LV where "WORK/ch1"`) (it straightens, downscales to 1600 px and converts transparent PNGs; use `.png` as the target to keep transparency); for clips run `LV frames "WORK/clips/<name>.mp4" "WORK/ch1/assets/clip_<name>" [--max N]` (same `assets:` folder in a project; clips are in the `clips/` folder that `clip` printed).
4. Write `scenes.js`.
5. `LV stills "WORK/ch1" <one time per scene>` and look at the `stills.jpg` it prints. Fix overlaps, text running off cards, things hidden behind captions, empty-looking scenes, and every `cue miss` warning. Repeat until clean (2–3 rounds is normal).
6. `LV render "WORK/ch1"`. Rendering takes about a minute per minute of video on a fast computer and several on a slow laptop: use the Bash tool's longest timeout (10 minutes), and for long chapters on slow machines run it in the background and check its output.
7. Verify: `render` prints the video length next to the narration length (they should match), and saves four frames of the finished video to the `final.jpg` it prints; look at them.

Then **stop**. Tell the teacher where the video is (the path `render` printed) and ask about tone, pace, reading level, voice and look. Apply their feedback to chapter 1 (re-narrating only changed scenes is cheap) before moving on, and write the agreed style notes at the top of `plan.md` so later chapters (and later sessions) follow them.

## 7. Remaining chapters

Default: one chapter at a time, same steps as 6.1–6.7, checking in briefly after each. If the teacher asks for speed, you may hand chapters to parallel helper agents; give each the exact **LV** command line (with the real plugin path, since helpers don't get it substituted), the paths to `guide.md`, `brief.md`, `plan.md` (with the style notes), its own `WORK/chN/` folder, and the finished `WORK/ch1/` as the reference. Tell the teacher this uses much more of their Claude plan.

Between chapters, `LV status "WORK"` shows what's left. If the session ends, the next `/lesson-videos:make` resumes from step 0.

## 8. Wrap up

Write `README.md` in the folder with the finished videos: a table of the videos with their lengths, one line on what each covers, and these notes:
- Narration: say which voice was used: an AI voice from ElevenLabs, the free Microsoft Edge voice (an unofficial Microsoft service; for classroom, non-commercial use), the computer's built-in voice, or captions only. Music and clips, if any, are AI-generated (Google).
- If the deck contains photos or diagrams from other sources, check their licences before posting the videos publicly; keeping them unlisted or sharing the files directly is safer.
- If ElevenLabs' free plan was used, a published video's title must include "elevenlabs.io".
- Each `.vtt` file holds the captions (they are also burned into the video).

Tell the teacher the videos are done and where they are.

## Site mode (slide2video.com)

Use this mode when the folder you were started in has `site/turn.json`. The teacher is not at this computer:
they answer on slide2video.com, and `LV worker` ran you for one **turn**. Each turn is a new session that remembers
nothing from earlier turns except the files in the lesson folder, so keep every decision in the files listed
below. **Never ask in chat** and never wait for an answer: do the work for this turn, write `site/card.json`,
check it with `LV card "site/card.json"`, fix anything it reports, and **stop**.

- **Commands:** use the command in `site/lv.txt` exactly, in place of the command at the top of this skill (it is
  the same plugin with absolute paths). Only that command, file reading and file editing are allowed.
- Some commands are switched off in site mode (`open`, `pair`, `worker`, `init`, and `keys` except `keys check`); don't try them.
- **Replaces the chat steps:** site mode replaces every "ask the teacher" and "tell the teacher" in steps 0–8:
  questions go in a `questions` card, notices go in the card's `message`.
- **Files:** the deck and any other files are the `files` listed in `site/turn.json` (`kind` deck or extra),
  saved in `in/`.
- **Folders:** `WORK` is `lesson-videos/_work` (pass `--work "lesson-videos/_work"` to `ingest`); finished videos
  land in `lesson-videos/`.
- **Progress:** at each step, rewrite `site/progress.txt` with its lines plus one new line at the end, a line a
  teacher would understand ("Reading the deck", "Narrating 3 of 12 scenes", "Rendering chapter 1"). You can only
  read and write files, so write the whole file each time. The website shows the last line.
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
  - `student-info.md`: the slide numbers flagged for student information (never copy student names into any file),
    and at its end the teacher's decision, a line `Decision: remove` or `Decision: not students`. Every turn that
    writes `brief.md`, `plan.md` or a chapter reads it first (if it exists) and leaves the flagged slides out when
    the decision is `remove`.
  - `interview.md`: the interview answers: grade, chapters, length, voice, and the decision for each possible issue.
  - `review.md`: its first line is `Under review: chapter N`; write it with every `review` card.
- **One chapter per turn**, no parallel helper agents.

What to do for each `turn.kind`, and which card ends it:

| `turn.kind` | Do | Card |
|---|---|---|
| `start` | Step 1 (ingest and read every slide). Then check every slide for **student information** (names of students, class photos, graded student work): the website forbids it. If found, write the flagged slide numbers to `student-info.md`. Only then steps 2–3: write `brief.md`. | If student information was found: `"questions"` with one question whose `"id"` is `"students"`, options labelled exactly "Remove these slides" and "They're not students", and nothing else. Otherwise: the interview (grade, chapter split, length, voice; options from step 2) plus one question per possible issue in the slides (follow the slide / follow the correction / leave it out). |
| `answer` | Check the answers in this order. (1) An answer to `"question": "problem"` (see the failure paragraph below): act on it and continue from where the work stopped. (2) An answer to `"question": "students"`: append `Decision: remove` (for "Remove these slides") or `Decision: not students` (for "They're not students") as the last line of `student-info.md`; then leave the flagged slides out everywhere. (3) The interview: if `interview.md` doesn't exist yet and the answers include the interview, write `interview.md` (grade, chapters, length, voice, and the decision for each possible issue) before planning. If `interview.md` doesn't exist and there are no interview answers, send the interview card instead. Then, for every case, step 4: read `student-info.md` if it exists, write `plan.md`, run `estimate`. | If the interview was asked: the interview `questions` card. Otherwise `"plan"`: `markdown` = the outline in brief (with music and clips and their costs, if any); `estimate` = `{"usd": <total>, "minutes": <per video>, "chapters": <N>}`. |
| `change` | Revise `plan.md` from `feedback`, re-run `estimate`. | `"plan"` again. |
| `approve` | Note the approval and date at the top of `plan.md`. Steps 5–6 (music and clips only as the approval rule above allows), then chapter 1 (6.1–6.7). | `"review"` for chapter 1. |
| `feedback` | Read `review.md` for the chapter under review. Apply `feedback` to that chapter (re-narrate only changed scenes), re-render it. | `"review"` for the same chapter. |
| `continue` | Read `review.md` for the last chapter shown. Write the agreed style notes at the top of `plan.md` if not there yet. Make the next unfinished chapter after it (`LV status`). If none is left, step 8. | `"review"` for that chapter, or `"done"`. |

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
  that `render` printed, relative to this folder; files outside `lesson-videos/` are refused). Write
  `review.md` first. The worker uploads the files; don't add `version` or `timing`.
- `"done"`: `"chapters": [{"chapter": 1, "title": "…"}]` and `"readme"` (the README text from step 8).

Card file paths must be inside `lesson-videos/`: video `.mp4`, captions `.vtt`, stills `.jpg`, `.jpeg` or `.png`.
Anything else makes the card an error.

If something fails that the teacher must fix (a deck that can't be read, a key that was rejected), write a
`"questions"` card with one question whose `"id"` is `"problem"` and whose options say what to do next, and a message that explains the problem
in one line. Record where the work stopped in `plan.md`, so the next turn picks it up there.
