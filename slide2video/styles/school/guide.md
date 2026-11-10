# School style

Study videos for students, made from a teacher's deck. Follow this with the shared chapter guide.

## Narration
- Talk to "you", a student at the grade level from the interview, preparing for a test. Warm, upbeat, a little funny, never cringe or babyish. Short sentences. Contractions.
- Every concept: the class definition (close to the teacher's wording in `brief.md`) → a picture or animation that makes it obvious → a memory hook → **how it shows up on the test** (likely question, common trap, the exact vocabulary word to use).
- Open with a hook (15 s or less), drawn with `intro`: `mood: 'playful'` (as in the sample chapter) or `mood: 'themed'`, as the grade says (see Look), never with `titleCard` and never as a copy of the deck's title slide. End with a 3-question quiz and a ~25 s recap that teases the next chapter.
- A deck question (make skill, Ground rules) gets a `quizQ` scene with the slide's own words, `badge: "YOUR TEACHER'S QUESTION"`, `"hold": 4.5` and no `quizA` after it. The narration poses it and hands it back, e.g. "That one's yours. Pause here if you want to think it through." Nothing in the chapter answers it, and the quiz never rewords it. A slide with several questions is one scene: `q` = the slide's title, `choices` = its questions in its own words, with `numbered: true` so they read as questions, not options to pick.
- The quiz questions are slide2video's own: `q1`/`a1`… scenes, each `q` a `quizQ` with `badge: "EXTRA QUESTION"` and `"hold": 4.5`, followed by its `quizA`. They test what the content scenes explained.
- Target 4–6 minutes per chapter (about 600–850 words).

## Look
Each lesson gets the look of its own subject; no look is the default for everything.
- Choose it with the plan (step 4) and write it near the top of `plan.md` as one line, `Look: <look>` and why, e.g. `Look: history (a unit on the American Revolution)`. Every chapter's `scenes.js` starts with `Engine.theme('<look>')`, the same in every chapter. Content scenes use `bg(g, 'light', t)`.
- Pick by what the whole deck teaches, not by one example in it (a math deck with a word problem about fish is `math`):

  | The deck teaches | Look |
  |---|---|
  | Math (numbers, fractions, algebra, geometry, statistics), computing, engineering | `math` |
  | History, civics, government, geography, economics, other social studies | `history` |
  | Reading, writing, literature, drama, poetry, languages, art, music | `literature` |
  | Living things, the human body, health, ecology, plants, cells, genetics | `life` |
  | Space, astronomy, physics, forces and energy, rocks and Earth's layers | `space` |
  | Oceans, sea life, rivers, water, weather | `ocean` |
  | Anything else (chemistry, PE, several subjects), or when no row clearly fits | `classroom` |
- The deck's own colours: when most slides share strong colours of their own (not plain white with black text or a stock template), keep the look and take two of them, `Engine.theme('<look>', { main: '#hex', accent: '#hex' })`. Both are drawn on white, so each must be dark enough to read there.
- The grade: Grades 3–5 bright and playful: the opening is `intro` with `mood: 'playful'` and an emoji row, and an emoji on every quiz question. Grades 6–8: `playful` without emoji, or `themed`. Grades 9–12 calmer: the opening is `intro` with `mood: 'themed'` (no emoji), the deck's pictures and diagrams rather than emoji, and for serious topics (war, illness, death) always `themed` and no cartoon emoji, whatever the grade.
- A lesson resumed without a `Look:` line in `plan.md`: if no chapter is finished yet, choose the look now and add the line before writing chapter 1's `scenes.js`. If chapters are already finished (made before looks existed), keep their look: add `Look: none (earlier chapters kept as they are)` and no `Engine.theme` line in any chapter, unless the teacher asks for a new look.
- When the teacher asks for another look, change the `Look:` line in `plan.md` first (later chapters and helpers read it), then the `Engine.theme` line in every finished chapter, and render them again.

## Images
- Never use images of students.

## Wrap-up
Add to the README (make skill, step 8):
- Questions from the deck were shown but not answered; the quiz questions are slide2video's own.
- Before using these videos with a class, check your district's policy on AI-made material: https://slide2video.com/ai
