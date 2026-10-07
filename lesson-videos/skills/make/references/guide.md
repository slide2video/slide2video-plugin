# Chapter video guide

How to build one chapter video with the lesson-videos engine. **LV** = the full `uv run "…/scripts/lesson-videos.py"` command line given to you by the make skill (or by whoever handed you this chapter). A chapter is a folder `WORK/chN/` with `script.json`, `scenes.js` and `assets/`. Copy the idioms in `sample/` (next to this file).

## Workflow
1. Write `script.json`. Top level: `chapter` (small top-right label, e.g. `"CHAPTER 2 · OSMOSIS"`), `title`, `out` (e.g. `"Chapter 2 - Osmosis and the Salty Potato Lab.mp4"`), optional `"music": "../music/bed.mp3"`, optional `"voice"` (ElevenLabs voice ID), optional `"narrator"`: `"auto"` (default: ElevenLabs if a key is set, else the free Microsoft voice, else the computer's own voice, else captions only), or one of `"elevenlabs"`, `"edge"` (free Microsoft voice; `"edge_voice"` picks it, default `en-US-AvaMultilingualNeural`), `"system"` (the computer's voice; `"system_voice"` picks it), `"none"` (captions only, timed at reading speed). With the computer's voice or captions only, word times are estimated, so reveals land within about half a second of the word. `scenes`: one object per scene with `id`, `say` (narration), optional `lead` (s before speech, default 0.5), `tail` (s after, default 0.7), `hold` (extra silent s, used for quiz countdowns), `min` (minimum s).
2. `LV narrate "WORK/chN"`: one ElevenLabs take per scene, cached by text, so re-running only re-voices changed scenes. Prints each scene's start and duration.
3. Write `scenes.js`: `Engine.assets({...})` plus one `scene(id, draw, opts)` per scene id.
4. `LV stills "WORK/chN" t1 t2 ...` (absolute seconds; one per scene, late enough that its reveals have happened) → `build/stills.jpg`. Read it and fix problems; it also prints `cue miss` warnings for cue words that never occur in the narration.
5. `LV render "WORK/chN"` → the MP4 and a `.vtt` next to the deck in `lesson-videos/`.

## Engine API (globals)
`const { W, H, C, E, P, pop, clamp, lerp, text, measure, card, circle, arrow, line, check, cross, img, clip, bg, heading, badge, tip, bullets, label, emoji, titleCard, quizQ, quizA, recap, rr, molecule, wander, membrane, ring, table, rng, noise } = Engine;`
- `scene(id, (g, t, s) => {...}, opts)`: `g` = canvas 2D context (1920×1080), `t` = seconds since the scene started. `s.cue('word', n=0)` = local time the n-th occurrence of a word (prefix match, case- and punctuation-insensitive) is spoken; **sync every reveal to a cue word**. `s.after('word')` = when it ends. `s.end` = narration end, `s.dur` = scene length.
- `opts`: `dark: true` (dark background; adjusts label and captions), `bug: false` (hide the top-right label), `noCaptions: true`, `cut: true` (no crossfade), `sfx: [[cue, name, gainDb]]` where cue is seconds, `'word'` or `['word', n]`. A soft whoosh is added automatically at each scene change; keep sound effects tasteful (−12 to −16 dB).
- Sound effects available: `pop0` `pop1` `pop2` `pop3` (reveals), `sparkle0` `sparkle1` `sparkle2` (correct answers, big moments), `whoosh0` `whoosh1` `whoosh2`, `thump0` `thump1` (heavy landings), `zip0` `zip1` `zip2` (arrows, lines), `pluck0` `pluck1` `pluck2` `pluck3` (quiz questions, playful notes), `tape0` `tape1` `tape2`, `pencil0` `pencil1` `pencil2`, `crayon0` `crayon1`, `waves0`, `shutter0` (photos).
- Timing helpers: `P(t, start, dur=0.6, ease=E.out)` → 0..1; `pop(t, start)` = overshoot pop-in for scale; easings `E.lin/out/in/inOut/back/elastic`.
- `bg(g, 'paper'|'lab'|'sand'|'ocean'|'deep', t)`: ocean and deep are animated.
- `heading(g, 'Title with *accent*', t, {kicker: 'Small caps line'})`: top-left title. Use on every content scene.
- `text(g, str, x, y, {size, weight, color, align, maxW, lh, alpha, accent, shadow, font})` → height. `y` = top of the text block. Markup `*accent color*`, `_bold_`. Wraps at `maxW`. `measure(g, str, opts)` → `{w, h, lines}`.
- `card(g, x, y, w, h, {fill, r, stroke, lw, alpha, shadow})`, `rr(g, x, y, w, h, r)` path, `circle(g, x, y, r, fill, {stroke, alpha})`, `line(...)`, `arrow(g, x1, y1, x2, y2, {color, w, head, prog, bend, dash, alpha})` (`prog` animates drawing, `bend` curves it).
- `check(g, x, y, size, prog)`, `cross(...)`, `badge(g, 'LABEL', x, yCenter, {fill, color, size, scale, alpha})`, `ring(g, x, y, r, k)`.
- `tip(g, 'text', t, atTime, {label: 'TEST TIP', size})`: callout card above the captions. 1–2 per scene for exam tips and traps (`label: 'TRAP!'` or `'WATCH OUT'`).
- `bullets(g, items[], x, y, t, times[], {size, maxW})`, `table(g, rows, x, y, colW[], {rowTimes, t, size, rowH})`, `label(g, 'text', px, py, tx, ty, k)` leader-line label.
- `img(g, key, x, y, w, h, {fit: 'cover'|'contain', r, zoom, panX, panY, alpha, shadow})`: images registered with `Engine.assets({key: 'assets/file.jpg'})`. Slow Ken Burns: `zoom: 1.05 + 0.02 * t`.
- `clip(g, 'assets/clip_name', frameCount, t, x, y, w, h, {fps: 24, loop: false, fit: 'cover', r})`: plays a JPEG frame sequence made by `LV frames` (an 8 s clip = 192 frames).
- `emoji(g, '🐟', x, y, size, {scale, rot, alpha})`: great for icons. Emoji look slightly different on Windows and Mac.
- Science helpers: `molecule(g, x, y, 'water'|'salt'|'sugar'|'o2'|'co2'|color, scale, alpha)`, `wander(i, t, {x, y, w, h}, seed)` → `[x, y]` for particle fields, `membrane(g, x, y1, y2, t)`.
- Standard scenes: `titleCard(g, t, s, {kicker, title, sub, emojis, bg})`, `quizQ(g, t, s, {n, q, choices, emoji})` (countdown ring during `hold`), `quizA(g, t, s, {answer, why})`, `recap(g, t, s, items, times, {title, kicker, gap, next, nextAt})`.
- Layout: margins x 120..1800; headings y 40..170; content y 210..900; **captions are drawn automatically below y ≈ 930**, so keep content above 900. Minimum text size 30 px (prefer 36 or more). One idea per scene; big, bold, colorful; animate things in as they are spoken.
- Palette: `C.navy, C.sea, C.teal, C.aqua, C.foam, C.coral, C.sun, C.leaf, C.purple, C.pink, C.ink, C.grey, C.water`.

## Assets
Copy each deck image you use with `LV asset "WORK/deck/media/<file>" "WORK/chN/assets/<name>.jpg"` (straightened, at most 1600 px, transparent PNGs flattened; use a `.png` target to keep transparency). Use the contact sheets to pick them. A missing asset, clip frame or scene stops `stills` and `render` with an error naming it. Never use images of students.

## Narration style
- Talk to "you", a student at the grade level from the interview, preparing for a test. Warm, upbeat, a little funny, never cringe or babyish. Short sentences. Contractions.
- Every concept: the class definition (close to the teacher's wording in `brief.md`) → a picture or animation that makes it obvious → a memory hook → **how it shows up on the test** (likely question, common trap, the exact vocabulary word to use).
- Open with a hook (15 s or less). End with a 3-question quiz (`q1`/`a1`… scenes, each `q` with `"hold": 4.5`) and a ~25 s recap that teases the next chapter.
- Text-to-speech friendly: spell symbols as spoken ("C O two" or "carbon dioxide", "ten point three percent", "three hundred milliliters"); no abbreviations like "e.g."; no emoji in `say`. Captions show the `say` text, so keep it clean.
- Target 4–6 minutes per chapter (about 600–850 words). Never invent facts or statistics beyond `brief.md`.
