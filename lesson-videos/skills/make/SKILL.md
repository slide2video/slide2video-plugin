---
name: make
description: Use when a teacher wants narrated study videos made from their slide deck (.pptx or .pdf). Reads the deck, writes a content brief in the teacher's wording, gets a costed plan approved, builds one reference chapter for feedback, then the rest, and saves MP4s with captions next to the deck. Resumes an unfinished run.
---

# Make lesson videos from a slide deck

In this skill, **LV** means this command (keep the quotes):

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/lesson-videos.py"
```

If `uv` isn't found, or any command says a tool or key is missing, run the `setup` skill first.

Read `${CLAUDE_PLUGIN_ROOT}/skills/make/references/guide.md` before writing any `script.json` or `scenes.js`. The sample chapter in `${CLAUDE_PLUGIN_ROOT}/skills/make/references/sample/` shows every idiom.

**Folders.** For a deck at `<folder>/<deck>.pptx`, everything goes in `<folder>/lesson-videos/`: finished videos at its top level, working files in `_work/` (`deck/`, `brief.md`, `plan.md`, `music/`, `clips/`, `ch1/`, `ch2/`…). Call `<folder>/lesson-videos/_work` **WORK**.

**Ground rules.**
- The teacher's slides are the only source of facts. Never add facts, numbers or examples that aren't in the deck or in files the teacher points you to.
- Nothing that costs money (narration, music, clips) happens before the teacher approves the plan in step 4.
- Nothing is uploaded or published.
- Keep the teacher informed in plain words; they don't need to see commands.

## 0. Resume?

If `WORK` already exists, run `LV status "WORK"` and read `WORK/plan.md`. Tell the teacher where things stand and continue from the first unfinished chapter (skip the steps already done).

## 1. Read the deck

Find the deck in the current folder (ask if there are several). Keynote, Google Slides or old `.ppt` files must be exported to `.pptx` first; `ingest` explains how. Run:

```
LV ingest "<deck path>"
```

Read `WORK/deck/slides.md` in full and look at every `WORK/deck/contact-*.jpg` (and `deck/pages/` for PDFs). Ask whether there are other files to use (worksheets, labs, review sheets); read them too.

## 2. Short interview (one message, sensible defaults offered)

- Grade level of the students.
- Chapters: propose a split from the deck's sections or titles (for example one video per unit/entry/lesson) and ask them to confirm or adjust.
- Length per video: default 4–6 minutes.
- Voice: default Jessica (warm, upbeat young American). They can pick another premade ElevenLabs voice by name.
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
2. `LV narrate "WORK/ch1"`.
3. Copy each image you use with `LV asset "WORK/deck/media/<file>" "WORK/ch1/assets/<name>.jpg"` (it straightens, downscales to 1600 px and converts transparent PNGs; use `.png` as the target to keep transparency); for clips run `LV frames "WORK/clips/<name>.mp4" "WORK/ch1/assets/clip_<name>" [--max N]`.
4. Write `scenes.js`.
5. `LV stills "WORK/ch1" <one time per scene>` and look at `WORK/ch1/build/stills.jpg`. Fix overlaps, text running off cards, things hidden behind captions, empty-looking scenes, and every `cue miss` warning. Repeat until clean (2–3 rounds is normal).
6. `LV render "WORK/ch1"`. Rendering takes about a minute per minute of video on a fast computer and several on a slow laptop: use the Bash tool's longest timeout (10 minutes), and for long chapters on slow machines run it in the background and check its output.
7. Verify: `render` prints the video length next to the narration length (they should match), and saves four frames of the finished video to `WORK/ch1/build/final.jpg`; look at them.

Then **stop**. Tell the teacher where the video is (`<folder>/lesson-videos/Chapter 1 - ….mp4`) and ask about tone, pace, reading level, voice and look. Apply their feedback to chapter 1 (re-narrating only changed scenes is cheap) before moving on, and write the agreed style notes at the top of `plan.md` so later chapters (and later sessions) follow them.

## 7. Remaining chapters

Default: one chapter at a time, same steps as 6.1–6.7, checking in briefly after each. If the teacher asks for speed, you may hand chapters to parallel helper agents; give each the exact **LV** command line (with the real plugin path, since helpers don't get it substituted), the paths to `guide.md`, `brief.md`, `plan.md` (with the style notes), its own `WORK/chN/` folder, and the finished `WORK/ch1/` as the reference. Tell the teacher this uses much more of their Claude plan.

Between chapters, `LV status "WORK"` shows what's left. If the session ends, the next `/lesson-videos:make` resumes from step 0.

## 8. Wrap up

Write `<folder>/lesson-videos/README.md`: a table of the videos with their lengths, one line on what each covers, and these notes:
- Narration is an AI voice (ElevenLabs); music and clips, if any, are AI-generated (Google).
- If the deck contains photos or diagrams from other sources, check their licences before posting the videos publicly; keeping them unlisted or sharing the files directly is safer.
- On the ElevenLabs free plan, a published video's title must include "elevenlabs.io".
- Each `.vtt` file holds the captions (they are also burned into the video).

Tell the teacher the videos are done and where they are.
