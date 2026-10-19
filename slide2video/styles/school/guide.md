# School style

Study videos for students, made from a teacher's deck. Follow this with the shared chapter guide.

## Narration
- Talk to "you", a student at the grade level from the interview, preparing for a test. Warm, upbeat, a little funny, never cringe or babyish. Short sentences. Contractions.
- Every concept: the class definition (close to the teacher's wording in `brief.md`) → a picture or animation that makes it obvious → a memory hook → **how it shows up on the test** (likely question, common trap, the exact vocabulary word to use).
- Open with a hook (15 s or less). End with a 3-question quiz and a ~25 s recap that teases the next chapter.
- A deck question (make skill, Ground rules) gets a `quizQ` scene with the slide's own words, `badge: "YOUR TEACHER'S QUESTION"`, `"hold": 4.5` and no `quizA` after it. The narration poses it and hands it back, e.g. "That one's yours. Pause here if you want to think it through." Nothing in the chapter answers it, and the quiz never rewords it. A slide with several questions is one scene: `q` = the slide's title, `choices` = its questions in its own words, with `numbered: true` so they read as questions, not options to pick.
- The quiz questions are slide2video's own: `q1`/`a1`… scenes, each `q` a `quizQ` with `badge: "EXTRA QUESTION"` and `"hold": 4.5`, followed by its `quizA`. They test what the content scenes explained.
- Target 4–6 minutes per chapter (about 600–850 words).

## Images
- Never use images of students.

## Wrap-up
Add to the README (make skill, step 8):
- Questions from the deck were shown but not answered; the quiz questions are slide2video's own.
- Before using these videos with a class, check your district's policy on AI-made material: https://slide2video.com/ai
