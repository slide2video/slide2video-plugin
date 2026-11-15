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

**In a Cowork cloud session** (claude.ai on the web: a fresh Linux computer each time, the teacher's files arrive under `/root/.claude/uploads/`): read `${CLAUDE_SKILL_DIR}/references/cowork.md` first.

## Steps

The steps are in two files next to this skill. Read a file before you do any of its steps (it is short):
- `${CLAUDE_SKILL_DIR}/references/plan-steps.md`: **0.** resume, **1.** read the deck, **2.** short interview, **3.** content brief, **4.** plan and approval gate.
- `${CLAUDE_SKILL_DIR}/references/build-steps.md`: **5.** music and clips, **6.** reference chapter, **7.** remaining chapters, **8.** wrap up.

Working with the teacher in this session, start with `plan-steps.md` and read `build-steps.md` when the plan is approved (or when resuming past step 4). In site mode (below), each turn reads only the file its `turn.kind` needs.

## Site mode (slide2video.com)

Use this mode when the folder you were started in has `site/turn.json`. The teacher is not at this computer:
they answer on slide2video.com, and `LV worker` ran you for one **turn**. Each turn is a new session that remembers
nothing from earlier turns except the files in the lesson folder, so keep every decision in the files listed
below. **Never ask in chat** and never wait for an answer: do the work for this turn, write `site/card.json`,
check it with `LV card "site/card.json"`, fix anything it reports, and **stop**.

- **Commands:** use the command in `site/lv.txt` exactly, in place of the command at the top of this skill (it is
  the same plugin with absolute paths). Only that command, file reading and file editing are allowed; outside this
  folder you can read only the `references/` next to this skill (`guide.md`, the steps files, the sample chapter) and the style's guide. Run each command
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
- **Clips:** `clips` in `site/turn.json` is how many AI clips this video project may still have, and the person chose it on
  the website: never ask about clips, in any card. A turn with `mode` but no `clips` counts as `clips` 0. With 0, plan
  none: no clips in `plan.md`, in the plan card or in `estimate` (leave out `--clips`). With more, plan at most that
  many (0–2 photos per unit, the style's `clips` saying which) and pass the count to `estimate --clips`. `estimate` and
  `clip` refuse more than allowed; if `clip` refuses, make the chapter without that clip and say so in the card's
  message. A turn with neither `clips` nor `mode` plans clips as step 4 says.
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

**Steps for this turn:** before anything else, read the steps file the turn needs (see **Steps** above): `start`, `answer` and `change` turns read `references/plan-steps.md` next to this skill; `approve`, `feedback` and `continue` turns read `references/build-steps.md` next to it. "Step N" below means that step there.

What to do for each `turn.kind`, and which card ends it:

| `turn.kind` | Do | Card |
|---|---|---|
| `start` | As the `start` row of **Site mode: the `start` and `answer` turns** in `plan-steps.md` says. | As that row says. |
| `answer` | As the `answer` row of **Site mode: the `start` and `answer` turns** in `plan-steps.md` says. | As that row says. |
| `change` | Revise `plan.md` from `feedback`, re-run `estimate` (with `--json`, as in the `answer` row). | `"plan"` again, its `estimate` built as in the `answer` row. |
| `approve` | Note the approval and date at the top of `plan.md`. Steps 5–6 (music and clips only as the approval rule above allows), then chapter 1 (step 6: `LV chapter`, then 6.1–6.7). | `"review"` for chapter 1. |
| `feedback` | Read `review.md` for the chapter under review and its chapter file (`LV chapter "WORK" <N>` prints it). Apply `feedback` to that chapter (re-narrate only changed scenes), re-render it. | `"review"` for the same chapter. |
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
