# Make lesson videos: steps 0–4 (resume, read the deck, interview, brief, plan)

Part of the make skill (`SKILL.md`, next to this `references/` folder): **LV**, **WORK**, the style and the ground rules are as it says. Steps 5–8 are in `build-steps.md`.

## 0. Resume?

If `WORK` already exists, run `LV status "WORK"` and read `WORK/plan.md`. Tell the teacher where things stand and continue from the first unfinished chapter (skip the steps already done). If the style's guide has a **Look** section and `plan.md` has no `Look:` line, do what that section says for a resumed lesson before the next chapter.

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
- Music and AI clips: only if a Gemini key is set (`LV keys check`). In site mode the website may already have settled clips (see **Clips** under Site mode).

## 3. Content brief

Write `WORK/brief.md`. Per chapter, under a heading `## Chapter N — <Title>`: what the style's `brief` lists. Then a section **"The teacher's questions (left open)"**: every deck question with its slide number or file name, or `None found.` Finish with a section **"Possible issues in the slides"**: contradictions between slides, typos in key terms, definitions worded two ways, and any chart whose values `slides.md` couldn't give (`[Chart not read: …]`). Show the teacher that section and ask how to handle each item (follow the slide, follow the correction, or leave it out).

## 4. Plan and approval gate

Write `WORK/plan.md`: for each chapter, a heading `## Chapter N — <Title>` with, right under it, a line naming the deck's slides it covers, such as `Slides: 4-14` or `Slides: 2, 4-9, 12` (its build reads only these and the slides its outline mentions, so leave none out; `estimate` refuses a plan without them), the output file name (`Chapter N - <Title>.mp4`), a scene outline (the style's `outline`), which deck questions it shows open (from the brief's "left open" section), which deck images it uses, and 0–2 photos per unit worth animating as AI clips (the style's `clips` says which; in site mode only as **Clips** under Site mode allows). When the style's guide has a **Look** section, add the lesson's `Look:` line as it says. Then run:

```
LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music]
```

Show the teacher the outline in brief and the estimate, and **ask for approval**. Do not continue until they say yes. Note the approval and date at the top of `plan.md`.

## Site mode: the `start` and `answer` turns

Only in site mode (`SKILL.md`'s **Site mode** section): what these two turns do, and which card ends each.

| `turn.kind` | Do | Card |
|---|---|---|
| `start` | Step 1 (ingest and read every slide). Write the teacher's `instructions` to `WORK/instructions.md` (write `None.` if there are none) and check them against the deck as step 1 says; if something is impossible or conflicting, stop here and send the instructions card. Then the style's check: look at every slide for what `check.looks_for` names; the website forbids it. If found, write the flagged slide numbers to `WORK/<check.file>` (`check.file`) and don't write `brief.md` yet (the `answer` turn writes it after the teacher's decision). If none was found, steps 2–3: write `brief.md`. | If the instructions check found something: `"questions"` with one question per problem (ids `instructions-1`, `instructions-2`, …; the closest matches from the deck as options; no option is `recommended`; `"other": true`), a message saying the rest waits until these are settled, and nothing else. Else if the style's check found something: `"questions"` with one question whose `"id"` is `check.id`, options labelled exactly `check.remove` and `check.keep`, and nothing else. Otherwise: the interview (the style's questions with their own ids, then chapter split, length, voice; options from step 2) plus one question per possible issue in the slides (follow the slide / follow the correction / leave it out). Give the possible-issue questions the ids `issue-1`, `issue-2`, …. |
| `answer` | Check the answers in this order. (1) An answer to `"question": "problem"` (see the failure paragraph below): act on it and continue from where the work stopped. (2) Answers to `instructions-…` questions: append each clarification to `WORK/instructions.md` and check the instructions again; if something is still impossible or conflicting, send the instructions card again and stop. Otherwise do the rest of the `start` row (the style's check, then `brief.md`) and send its card. (3) An answer to the question whose id is `check.id`: append `Decision: remove` (for `check.remove`) or `Decision: <check.keep_decision>` (for `check.keep`; `check.keep_decision` is the style's word for it) as the last line of `WORK/<check.file>`; if the decision is `remove`, leave the flagged slides out everywhere (otherwise keep them); if `brief.md` doesn't exist yet, write it now (steps 2–3). (4) The interview: if `interview.md` doesn't exist yet and the answers include the interview, write `interview.md` (the style's questions, chapters, length, voice, and the decision for each possible issue) before planning. If `interview.md` doesn't exist and there are no interview answers, send the interview card and stop: no planning in this turn. Otherwise (`interview.md` exists or was just written in this turn), step 4: read `WORK/<check.file>` if it exists, write `plan.md`, run `estimate`. | If (2) asked again or did the rest of the `start` row: that card. If the interview was asked: the interview `questions` card. Otherwise `"plan"`: `markdown` = the outline in brief (including the deck questions left open; with music and clips and their costs, if any); `estimate` = the JSON that `LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music] --json` prints (`"usd"`, `"items"` and `"quantities"`), plus `"minutes": <per video>` and `"chapters": <N>`. |
