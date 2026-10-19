# Open Questions (slide2video 2.2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A question the teacher put in the deck for the audience is shown as written and left open, slide2video's own quiz is labelled as its own, and the teacher sees both before anything is made.

**Architecture:** The rule lives in the make skill's Ground rules (style-neutral wording) and the School guide (School wording and the two on-screen badges). The engine's `quizQ` helper gains an optional `badge` so the two labels can be drawn; nothing is renamed. The reference chapter shows the new idiom so new chapters copy it. Plugin bump 2.1.0 → 2.2.0; the site contract is untouched.

**Tech Stack:** Markdown skills, JSON style, engine.js (canvas), Python tests with pytest (`uv run pytest -q`).

**Spec:** `/Users/daniellandi/Projects/slide2video/docs/superpowers/specs/2026-10-18-ai-position-and-open-questions-design.md` (website repo, branch `spec/ai-position-and-open-questions`). Read §4 and §9.

## Global Constraints

- Tier B: this branch `open-questions` off `main`; the gate is `uv run pytest -q` (needs `uv run python -m playwright install chromium` once); merge to `main` with `--no-ff`, push.
- Versions agree in `slide2video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `slide2video/scripts/lv/__init__.py`: **2.2.0**. `slide2video/site-contract/contract.json` `plugin` stays `2.1.0`.
- Engine API is frozen: add options, never rename. `quizA` unchanged.
- Skills: no bash-only syntax; every file read/write `encoding="utf-8"`.
- School-only words come from the style, not the make skill (`tests/test_skills.py::test_school_lives_only_in_its_style`): the make skill says "the audience", the School guide says "student"/"teacher"/"class".
- Public repo: no class material, nothing personal.
- Badge texts, exactly: `YOUR TEACHER'S QUESTION` and `EXTRA QUESTION`.

## Review Focus

- A deck with no questions: `brief.md`'s section must read `None found.`, not be skipped (Task 2 test asserts the string).
- A question the slide itself answers ("What is evaporation?" then the definition) stays content; the rule text must say so in one sentence (Task 2 test asserts "If the slides themselves answer").
- Answer key in speaker notes (the sample deck's Review slide): stays open (Task 2 test asserts "Speaker notes don't count").
- Site mode: the teacher approves from the plan card, so the plan card's `markdown` must carry the open questions (Task 2 test asserts the site-mode `plan` row mentions them).
- A WORK folder from before 2.2.0 resumes with the old plan: nothing in this plan changes resume; `LV status` unchanged.

---

### Task 1: `quizQ` gets an optional `badge`

**Files:**
- Modify: `slide2video/engine/engine.js:283-286`
- Modify: `slide2video/skills/make/references/guide.md:29`
- Test: `tests/test_skills.py`

**Interfaces:**
- Produces: `quizQ(ctx, t, s, {n, q, choices, emoji, badge})`; `badge` defaults to `` `QUIZ · QUESTION ${o.n}` `` when absent or empty.

- [ ] **Step 1: Write the failing test** (append to `tests/test_skills.py`)

```python
def test_quiz_question_badge_is_configurable():
    engine = (PLUGIN / "engine/engine.js").read_text(encoding="utf-8")
    assert "o.badge || `QUIZ · QUESTION ${o.n}`" in engine
    guide = (PLUGIN / "skills/make/references/guide.md").read_text(encoding="utf-8")
    assert "quizQ(g, t, s, {n, q, choices, emoji, badge})" in guide
```

- [ ] **Step 2: Run it**: `uv run pytest -q tests/test_skills.py::test_quiz_question_badge_is_configurable` → FAIL (assert).

- [ ] **Step 3: Implement.** In `quizQ`: defaults become `{ n: 1, q: '', choices: null, emoji: '🤔', badge: '', ...o }`; the `badge(...)` call's label becomes `` o.badge || `QUIZ · QUESTION ${o.n}` ``. In `guide.md` line 29 change `quizQ(g, t, s, {n, q, choices, emoji})` to `quizQ(g, t, s, {n, q, choices, emoji, badge})` and add after "(countdown ring during `hold`)": ", `badge` replaces the `QUIZ · QUESTION n` label".

- [ ] **Step 4: Run** `uv run pytest -q tests/test_skills.py` → all PASS (`test_sample_chapter_renders` still renders).

- [ ] **Step 5: Commit**: `git add slide2video/engine/engine.js slide2video/skills/make/references/guide.md tests/test_skills.py && git commit -m "engine: quizQ takes an optional badge"`

### Task 2: The rule in the make skill

**Files:**
- Modify: `slide2video/skills/make/SKILL.md` (Ground rules ≈ line 30; step 3 ≈ line 67; step 4 ≈ line 71; step 8 ≈ line 103; site-mode table, the `answer` row's `"plan"` card ≈ line 164)
- Test: `tests/test_skills.py`

**Interfaces:**
- Produces: the brief section heading `The teacher's questions (left open)`, used by Task 3's outline wording and by the School guide.

- [ ] **Step 1: Write the failing test**

```python
def test_deck_questions_stay_open():
    _, text = frontmatter("make")
    for needed in ("The teacher's questions stay the teacher's.", "never answered, hinted at, pointed to",
                   "Speaker notes don't count", "If the slides themselves answer a question, that's content",
                   "are not put in the video unless the teacher asks",
                   '**"The teacher\'s questions (left open)"**', "None found.",
                   "which deck questions it shows open", "notes the style's guide lists for the wrap-up"):
        assert needed in text, needed
    site = text.split("## Site mode", 1)[1]
    assert "deck questions left open" in site
```

- [ ] **Step 2: Run it** → FAIL.

- [ ] **Step 3: Edit `SKILL.md`.** Exact copy:

Ground rules, new bullet right after "The teacher's slides are the only source of facts…":

> - The teacher's questions stay the teacher's. A question the deck (or a file the teacher added) asks the audience and leaves open (review, recap, exit ticket, homework, discussion, practice problems) is a **deck question**: shown as written and handed back with a pause, never answered, hinted at, pointed to ("it's on slide 7") or reworded into a quiz question. Speaker notes don't count as the deck answering: the audience never sees them, so a question answered only in the notes stays open (the notes remain a source of facts for the content scenes). If the slides themselves answer a question, that's content: explain it as usual. Deck questions on slides get their own scene (a slide with several questions is one scene); deck questions in added files are listed in `brief.md` and `plan.md` as left open and are not put in the video unless the teacher asks.

Step 3, before the "Possible issues in the slides" sentence: `Then a section **"The teacher's questions (left open)"**: every deck question with its slide number or file name, or \`None found.\`` (keep "Possible issues" as the last section: change "Finish with" to "Then").

Step 4, in the `plan.md` sentence after "a scene outline (the style's `outline`)": `, which deck questions it shows open (from the brief's "left open" section)`.

Step 8, after the bullet list: `Add any notes the style's guide lists for the wrap-up.`

Site mode, `answer` row, the `"plan"` card: after "`markdown` = the outline in brief" add " (including the deck questions left open)".

- [ ] **Step 4: Run** `uv run pytest -q tests/test_skills.py` → PASS (including `test_school_lives_only_in_its_style`).

- [ ] **Step 5: Commit**: `git commit -am "make: the teacher's questions stay open"`

### Task 3: The School style

**Files:**
- Modify: `slide2video/styles/school/style.json` (`brief`, `outline`)
- Modify: `slide2video/styles/school/guide.md`
- Test: `tests/test_styles.py`

**Interfaces:**
- Consumes: Task 1's `badge` option; Task 2's brief section name.

- [ ] **Step 1: Write the failing test**

```python
def test_school_leaves_the_teachers_questions_open(capsys):
    code, out = run(capsys, "style", "school")
    assert code == 0
    s = json.loads(out.out)
    assert "to leave open" in s["brief"] and "shown open" in s["outline"]
    guide = (PLUGIN / "styles/school/guide.md").read_text(encoding="utf-8")
    for needed in ("YOUR TEACHER'S QUESTION", "EXTRA QUESTION", "no `quizA` after it", "never rewords",
                   "## Wrap-up", "https://slide2video.com/ai", "district's policy"):
        assert needed in guide, needed
```

- [ ] **Step 2: Run it** → FAIL.

- [ ] **Step 3: Edit.** `style.json`: `brief` gains, at the end, `; the deck's own questions (review, recap, homework), each with its slide number, to leave open`. `outline` becomes `hook, 6–12 content scenes, the deck's own questions shown open where the deck has them, a 3-question quiz, recap for 4–6 minutes; for shorter videos scale down, e.g. one scene per key idea and a 1-question quiz`.

`guide.md`, under Narration, replace the "End with a hook… 3-question quiz" bullet with:

> - Open with a hook (15 s or less). End with a 3-question quiz and a ~25 s recap that teases the next chapter.
> - A deck question (make skill, Ground rules) gets a `quizQ` scene with the slide's own words, `badge: "YOUR TEACHER'S QUESTION"`, `"hold": 4.5` and no `quizA` after it. The narration poses it and hands it back, e.g. "That one's yours. Pause here if you want to think it through." Nothing in the chapter answers it, and the quiz never rewords it.
> - The quiz questions are slide2video's own: `q1`/`a1`… scenes, each `q` a `quizQ` with `badge: "EXTRA QUESTION"` and `"hold": 4.5`, followed by its `quizA`. They test what the content scenes explained.

Append:

> ## Wrap-up
> Add to the README (make skill, step 8):
> - Questions from the deck were shown but not answered; the quiz questions are slide2video's own.
> - Before using these videos with a class, check your district's policy on AI-made material: https://slide2video.com/ai

- [ ] **Step 4: Run** `uv run pytest -q tests/test_styles.py tests/test_skills.py` → PASS.

- [ ] **Step 5: Commit**: `git commit -am "school: deck questions stay open, quiz labelled as extra"`

### Task 4: The reference chapter shows the idiom

**Files:**
- Modify: `slide2video/skills/make/references/sample/script.json`, `slide2video/skills/make/references/sample/scenes.js:51-52`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write the failing test**

```python
def test_reference_chapter_shows_a_deck_question_open():
    sample = PLUGIN / "skills/make/references/sample"
    ids = [s["id"] for s in json.loads((sample / "script.json").read_text(encoding="utf-8"))["scenes"]]
    assert ids.index("tq") < ids.index("q1") and "ta" not in ids
    scenes = (sample / "scenes.js").read_text(encoding="utf-8")
    assert "badge: \"YOUR TEACHER'S QUESTION\"" in scenes and 'badge: "EXTRA QUESTION"' in scenes
```

- [ ] **Step 2: Run it** → FAIL.

- [ ] **Step 3: Edit.** `script.json`: insert before `q1`:
`{"id": "tq", "hold": 4.5, "say": "Your slides end with a review: name the three main steps, which step turns liquid into gas, and whether clouds are gas or liquid. Those are yours. Pause here if you want to think them through."}`
and change `q1`'s `say` to `"Now one extra question from me. Pause if you need more time. A puddle disappears on a sunny afternoon. Which step is that?"`.
`scenes.js`: before the `q1` scene add
`scene('tq', (g, t, s) => quizQ(g, t, s, { badge: "YOUR TEACHER'S QUESTION", q: 'Review', choices: ['Name the three main steps of the water cycle.', 'Which step turns liquid into gas?', 'Are clouds made of gas or liquid?'], emoji: '📝' }), { dark: true, sfx: [[0.1, 'pluck1', -10]] });`
and give `q1` `badge: "EXTRA QUESTION"` (keep `n: 1`).

- [ ] **Step 4: Run** `uv run pytest -q tests/test_skills.py` → PASS (`test_sample_chapter_renders` renders the new scene; look at its stills if it fails on layout).

- [ ] **Step 5: Commit**: `git commit -am "reference chapter: the deck's review stays open; the quiz is labelled extra"`

### Task 5: Teacher-facing text and the 2.2.0 bump

**Files:**
- Modify: `slide2video/README.md:21`, `slide2video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `slide2video/scripts/lv/__init__.py`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write the failing test**

```python
def test_readme_says_deck_questions_stay_open_and_links_the_ai_page():
    text = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert "Questions already in your deck are shown but never answered" in text
    assert "https://slide2video.com/ai" in text
    for f in (PLUGIN / ".claude-plugin/plugin.json", REPO / ".claude-plugin/marketplace.json"):
        assert "shown but never answered" in f.read_text(encoding="utf-8"), f
```

(`REPO` comes from `conftest`, as `PLUGIN` does.)

- [ ] **Step 2: Run it** → FAIL.

- [ ] **Step 3: Edit.** README bullet: `- A short pause-and-answer quiz and a recap. Questions already in your deck are shown but never answered: they stay yours.` After the "Videos are 4–6 minutes…" line add: `**Where we stand on AI in education:** https://slide2video.com/ai`. Both descriptions: append ` Questions already in the deck are shown but never answered.` Set the three versions to `2.2.0`.

- [ ] **Step 4: Run the gate**: `uv run pytest -q` → all PASS.

- [ ] **Step 5: Commit**: `git commit -am "slide2video 2.2.0: the teacher's questions stay open"`

### Task 6: Ship

- [ ] `git checkout main && git merge --no-ff open-questions -m "Merge: slide2video 2.2.0, the teacher's questions stay open" && git push`
- [ ] Then the website plan (`slide2video/docs/superpowers/plans/2026-10-18-ai-page-and-open-questions.md`), in the same sitting, so the README's link goes live within minutes.
