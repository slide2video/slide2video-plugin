# slide2video plugin: new home, rename and styles (sub-project 1)

**Date:** 2026-10-15 · **Status:** design approved in chat; written spec awaiting review
**Repos:** `plugins` (`DanielLandi/plugins`: lesson-videos leaves, its final 1.0.2 release) → new public
`slide2video/slide2video-plugin` (the plugin renamed `slide2video`, version 1.1.0, with the style format) +
`slide2video` (website: moves to `slide2video/slide2video-site`; install instructions only)

## 1. Purpose and where this fits

The lesson-videos plugin becomes **slide2video**, gets its own home in a new GitHub organization, and learns
**styles**: a project is made in one style, and each style brings its own questions, content check and writing
guide. Today's plugin becomes the **School** style, unchanged in behavior.

This is the first of four sub-projects, each with its own spec and plan:

1. **This spec:** move, rename, style format, School. The live site (slide2video.com) changes only where it names
   the plugin (install steps, update steps, footer).
2. **pro.slide2video.com behind Cloudflare Access** (Daniel only): the same website code deployed as a second Worker
   with its own D1 database and R2 bucket; slide2video.com is deployed from a frozen `live` branch from then on.
   Hosted processing on Daniel's machines, the private styles repo and the first private style, the website's style
   picker, and a Keychain entry per website address so one computer can pair with both sites.
3. **On pro:** prepaid credits with Stripe, the public "Where your data goes" page, and new Terms and Privacy
   (Daniel approves the legal text).
4. **Launch:** open sign-up, and the switch: existing accounts, projects and files are copied into pro's database
   and bucket, slide2video.com is pointed at pro's Worker, and pro.slide2video.com redirects to it.

**Decisions taken in the brainstorm (2026-10-15):**

| Topic | Decision |
|---|---|
| Name | lesson-videos → **slide2video**. Commands `/slide2video:setup`, `/slide2video:make`, `/slide2video:serve`. |
| Home | New GitHub organization `slide2video` (Daniel creates it on github.com). Public repo `slide2video/slide2video-plugin`, its own marketplace: `/plugin marketplace add slide2video/slide2video-plugin`, then `/plugin install slide2video@slide2video`. |
| What moves | lesson-videos only, with its git history. **music-video and batatais stay in `DanielLandi/plugins`, untouched.** |
| Version | slide2video continues the line at **1.1.0**, so the website (built for 1.0.x, refusing only another major) accepts old and new computers during the switch. |
| Old plugin | A final **lesson-videos 1.0.2** keeps working exactly like 1.0.1 and says everywhere that it has moved. |
| School | Today's plugin, **kept as it is**: "What grade are the students?", the student-information check, quiz and recap, the teacher wording, and today's voices (ElevenLabs, the free Microsoft voice, the computer's own voice, captions only). This replaces the earlier idea of rewording the plugin for everyone and of dropping the Microsoft voice; hosted processing (sub-project 2) never uses the Microsoft voice. |
| Other styles | Business meeting, Tech company, Travel agency, …: each its own questions and check. **Closed and proprietary, hosted only**: they live in a private repo installed only on Daniel's machines. A person's own computer only ever has School. |
| Picking a style | The person picks a style per project; that is the only extra step. With only School installed, nothing is asked. |
| Website repo | `DanielLandi/slide2video` moves to `slide2video/slide2video-site`, still private. GitHub redirects the old address. |

**Success:** a teacher on lesson-videos 1.0.1 runs `/plugin update lesson-videos`, sees the moved notice, installs
slide2video 1.1.0 with the three steps it gives, keeps their keys and settings without re-entering anything, and their
computer keeps making videos for slide2video.com. A School project asks exactly what it asks today. The old repo's
gate passes with only the music-video tests.

## 2. The new repo

```
slide2video-plugin/
  .claude-plugin/marketplace.json     marketplace "slide2video", one plugin "slide2video", source ./slide2video
  slide2video/                        the plugin (was lesson-videos/)
    .claude-plugin/plugin.json        name "slide2video", version 1.1.0
    skills/  scripts/  engine/  fonts/  docs/  site-contract/  README.md
    styles/
      style.schema.json
      school/style.json  school/guide.md
  examples/                           the water cycle deck and make_sample_deck.py
  tests/                              the lesson-videos tests, site_fake.py, the lesson-videos half of conftest.py
  docs/superpowers/                   the lesson-videos and slide2video specs and plans (history)
  .superpowers/design/                the website mockups
  pyproject.toml  uv.lock  LICENSE  README.md  AGENTS.md  CLAUDE.md  SERVICES.md  .github/workflows/ci.yml
```

It is built with `git filter-repo` from a fresh clone of `DanielLandi/plugins`, keeping only the paths above, so
`git log` of every moved file goes back to its first commit. The renames happen in later commits of the new repo, not
in the filter, so history shows them. `pyproject.toml` keeps only `pythonpath = ["slide2video/scripts"]`. CI runs the
same matrix (macOS and Windows) with `uv run slide2video/scripts/slide2video.py doctor --no-keys`.

The new repo's `AGENTS.md` carries over every lesson-videos rule from today's `AGENTS.md` (public repo and no class
material, Windows and macOS, frozen engine API, model IDs and prices only in `config.py`, the version-bump and
site-contract release rules) and adds the style rules from §4.6. `SERVICES.md` keeps the lesson-videos services.

The sample video release moves: `lesson-videos-sample-v2` (mp4 + vtt) is re-published in the new repo as
`slide2video-sample-v2`, and the README links it. The old release in `DanielLandi/plugins` stays, so old links work.

## 3. What gets renamed and what stays

People see these, so they change:

| Today | After |
|---|---|
| plugin `lesson-videos`, commands `/lesson-videos:*` | `slide2video`, `/slide2video:*` |
| `scripts/lesson-videos.py` (the **LV** command) | `scripts/slide2video.py` |
| README, guides, skill text, messages ("lesson-videos …") | "slide2video …" |
| hidden home folder `~/.lesson-videos/` (keys, SFX, the token fallback) | `~/.slide2video/` |
| settings `…/Preferences/lesson-videos/settings.json` (and the Windows/Linux equivalents) | `…/slide2video/settings.json` |
| cache `…/Caches/lesson-videos/` | `…/Caches/slide2video/` |
| website lessons folder `~/Lesson Videos/` | `~/slide2video/` |
| default project results `~/Movies/Lesson Videos/` | `~/Movies/slide2video/` |
| chat-mode output next to the deck: `<folder>/lesson-videos/` | `<folder>/slide2video/` |

**Nobody re-enters anything.** On every command, before anything else (`config.migrate_home()`):

- If `~/.slide2video/` doesn't exist and `~/.lesson-videos/` does, copy it, keeping symlinks as symlinks (a
  `keys.env` symlink to a secrets folder stays a symlink). The old folder is left as it is.
- The settings file is copied the same way (new missing, old present).
- **Folders that hold work are not moved or copied; an existing old folder keeps being used.** If `~/Lesson Videos/`
  exists, the worker keeps using it, so a lesson in progress on the website continues. The same goes for
  `~/Movies/Lesson Videos/` and the old cache folder: a registered project whose `config.yaml` has no `results_dir` or
  `work_dir` line uses these defaults, so a new name would hide its videos and extracted decks. For a chat-mode run, the make skill resumes an existing
  `<folder>/lesson-videos/_work/` if there is one, and starts new runs in `<folder>/slide2video/`.

Nobody sees these, so they stay:

- the Python package `lv` and the `LV_*` and `LESSON_VIDEOS_*` environment variables (`LESSON_VIDEOS_HOME` now
  overrides `~/.slide2video/`);
- the `X-LV-Plugin` and `X-LV-Contract` headers, the job contract, and the contract version (`site-contract/` is
  unchanged except for paths in its README);
- the Keychain entry (its per-site version comes in sub-project 2);
- in website mode, the `lesson-videos/` folder inside each lesson folder: the worker only publishes card files from
  inside it, and lessons already in progress have their files there.

The worker's lock check (`worker.py`: whether a pid belongs to this plugin) accepts both `lesson-videos` and
`slide2video` in the command line, and its prompt becomes "Run /slide2video:make in site mode for this folder."
`version.STEPS` and every update hint say `/plugin update slide2video`, then reopen Claude Code, then
`/slide2video:serve`.

## 4. Styles

### 4.1 What a style is

A folder `styles/<id>/` with two files:

- `style.json`: what the make skill and the website need to know about the style;
- `guide.md`: its writing guide (who the videos talk to, tone, scene order, what to avoid). The shared chapter guide
  (`skills/make/references/guide.md`: workflow, engine API, assets, layout) stays shared and tells the reader to also
  follow the style's guide.

`styles/style.schema.json` (JSON Schema draft 2020-12) defines `style.json`:

| Field | Meaning |
|---|---|
| `id` | lowercase letters, digits and `-`; equals the folder name |
| `name`, `description` | shown when picking a style (one line each) |
| `public` | `true` only for styles in the public plugin |
| `questions` | the style's own interview questions, asked **before** the shared ones: `id`, `text`, `options` (`"from-deck"`: Claude writes the options from the deck, guided by `hint`; or a fixed list of `{label, detail?}`), optional `hint`, optional `other` (default `true`) |
| `check` | the content check on the first step: `id` (the card question id), `file` (the notes file in WORK), `looks_for`, `remove` (label of the option that removes the slides), `keep` (label of the option that keeps them), `keep_decision` (the word written after `Decision:` for `keep`) |
| `brief` | what `brief.md` records per chapter |
| `outline` | the default scene outline for `plan.md`, and how it scales for shorter videos |
| `clips` | which images may become AI clips |
| `music` | the prompt for `LV music` |

### 4.2 School

`styles/school/style.json` holds, word for word, what the make skill and `guide.md` say today:

```json
{
  "id": "school",
  "name": "School",
  "description": "Study videos for students: a hook, the key ideas, a short quiz and a recap.",
  "public": true,
  "questions": [
    {"id": "grade", "text": "What grade are the students?", "options": "from-deck",
     "hint": "grade bands (Grades 3–5, 6–8, 9–12); recommend the one the deck fits"}
  ],
  "check": {"id": "students", "file": "student-info.md",
            "looks_for": "names of students, class photos, graded student work",
            "remove": "Remove these slides", "keep": "They're not students", "keep_decision": "not students"},
  "brief": "the essential question if the deck has one; key terms with definitions in the teacher's own wording; examples and lab data from the slides; likely test questions; common mistakes worth a \"trap\" warning",
  "outline": "hook, 6–12 content scenes, a 3-question quiz, recap for 4–6 minutes; for shorter videos scale down, e.g. one scene per key idea and a 1-question quiz",
  "clips": "real photos of living things or landscapes that benefit from motion; not drawings or clip-art, which Veo turns into realistic footage partway through; never diagrams with text, never photos of students",
  "music": "calm, light instrumental study music, no vocals, steady gentle beat"
}
```

`styles/school/guide.md` is today's "Narration style" section of `guide.md` (talk to "you", a student at the grade
level from the interview; the test-focused concept pattern; hook, 3-question quiz and recap; 4–6 minutes) plus
"Never use images of students" from its Assets section. The shared `guide.md` keeps the rest, including the
text-to-speech rules, which apply to every style.

### 4.3 Where styles come from

- The plugin's own `styles/` (School).
- `LV_STYLES_DIR`, if set: a folder of more style folders in the same format. Only Daniel's hosted machines set it
  (sub-project 2), pointing at a clone of the private `slide2video/slide2video-styles`.

An id found in both places, a folder whose `style.json` doesn't match the schema, or an `id` that differs from its
folder name is an error naming the folder; commands that don't need styles are not affected.

### 4.4 Commands

- `LV styles`: one line per installed style: id, name, description, and where it came from (`plugin` or the
  `LV_STYLES_DIR` path). `--json` prints the list.
- `LV style <id>`: prints the style's `style.json` as JSON, plus `"guide"`: the absolute path of its `guide.md`.
  An unknown id is an error listing the installed ids.

Both are new subcommands in `cli.py`, implemented in a new `lv/styles.py` (loading, validation with the
`jsonschema` package already used for the contract, lookup). Both work in website mode.

### 4.5 The make skill

The skill keeps its structure and wording; the School-specific parts are read from the style instead:

- **Which style.** Step 0 checks `WORK/style.txt` (one line: the style id). If it is missing, the style is `school`
  for an existing WORK (runs started before 1.1.0) and, for a new run, the one chosen now: with one style installed
  (`LV styles`), that style without asking; with more, the person is asked, using each style's name and description.
  The choice is written to `WORK/style.txt`. Then `LV style <id>` gives everything below.
- **Step 2, interview:** the style's `questions` first, then the shared ones (chapters, length, voice, music and AI
  clips when a Gemini key is set). For School that is today's order: grade, chapters, length, voice, music.
- **Step 3, brief:** per chapter, what the style's `brief` says, then the shared "Possible issues in the slides".
- **Step 4, plan:** the scene outline from the style's `outline`; AI clips chosen by the style's `clips`.
- **Step 5, music:** the style's `music` prompt.
- **Chapters:** the shared `guide.md` plus the style's `guide.md` (both paths go to helper agents too).
- **Website mode, `start` turn:** the check uses the style's `check`: the flagged slides go to `WORK/<check.file>`,
  the card question gets `check.id` and the two labels `check.remove` and `check.keep`; the `answer` turn writes
  `Decision: remove` or `Decision: <check.keep_decision>`. The interview card lists the style's questions with their
  ids, then the shared ones. `interview.md` records the style's answers, chapters, length, voice and the issue
  decisions. In this sub-project, website mode always uses School (the turn has no style yet; sub-project 2 adds it).

The skill text addresses the person as it does today: the shared parts say "the teacher" where today's text does, so
School reads exactly as before. Rewording the shared text for other audiences is sub-project 2's work, when the first
other style exists.

### 4.6 Rules for styles (in `AGENTS.md`)

- A public style lives only in `styles/` of the public repo; a private style is never committed to it.
- A style changes what is asked and written, never the engine API (still frozen) or the job contract.
- The packaging test validates every style in `styles/`.

## 5. The old repo: lesson-videos 1.0.2, then removal

**lesson-videos 1.0.2** is 1.0.1 plus a notice. It still works fully, so a computer serving the website keeps making
videos until its owner switches. The notice, printed at the start of `setup`, `make` and `serve`, by
`worker --status`, and once when `worker --watch` starts:

> lesson-videos is now **slide2video**. To switch: run `/plugin marketplace add slide2video/slide2video-plugin`, then
> `/plugin install slide2video@slide2video`, then `/plugin uninstall lesson-videos`, and close and reopen Claude Code.
> Your keys and settings come along.

Version bump as usual (`plugin.json`, the marketplace entry, `lv/__init__.py`; `test_packaging.py` checks them).

**Then lesson-videos leaves `main`.** The `lesson-videos/` folder, `examples/`, the lesson-videos tests, `site_fake.py`,
the lesson-videos part of `conftest.py` (the `lv_home` autouse fixture and `lv_project`), the doctor step in CI and the
lesson-videos path in `pyproject.toml` are removed. The marketplace entry stays and keeps serving 1.0.2:

- **Preferred:** the entry's source points at the git tag `lesson-videos-v1.0.2` of `DanielLandi/plugins`, so the
  folder can leave `main`. The plan checks first that a Claude Code marketplace entry can name a git ref.
- **Fallback:** if it can't, `lesson-videos/` stays on `main`, frozen at 1.0.2, with a one-line `⚠️ ARCHIVED` README
  banner; its tests have moved, so nothing in the old repo tests it any more.

The docs in `docs/superpowers/` that moved stay in the old repo too (history; nothing there is used at run time).
`AGENTS.md`, `README.md` and `SERVICES.md` drop lesson-videos and point to the new repo. music-video and batatais,
their tests, `mv_fixtures.py` and their marketplace entries are not touched.

## 6. The website

- **Where the website names the plugin**, it names slide2video. This is the only change to slide2video.com in this
  sub-project, deployed only when Daniel says so; `contract/` is unchanged.
  - `pages.ts`: the "add a computer" steps (`/plugin marketplace add slide2video/slide2video-plugin`,
    `/plugin install slide2video@slide2video`, `/slide2video:setup`) and every `/lesson-videos:serve`.
  - `contract.ts`: `UPDATE_STEPS` and the version messages say slide2video.
  - The Devices list shows "slide2video 1.1.0" for a computer on 1.1.0 or newer and "lesson-videos 1.0.1" below it, so
    each computer is named the way its owner installed it.
  - `ui.ts`: the footer link points to `github.com/slide2video/slide2video-plugin` ("Built on the open-source
    slide2video plugin").
  - `legal.ts`: Privacy names "the slide2video plugin" in its list of what is stored. Legal text changes only with
    Daniel's approval (slide2video#24); this one-word change is shown to him with the deploy.
- **The repo moves** to `slide2video/slide2video-site` (GitHub's transfer; the old address redirects). Its
  `AGENTS.md` paths to the contract change to `slide2video-plugin/slide2video/site-contract/`.
- The sample deck download (`/sample/water-cycle.pptx`) keeps its file; the website's `AGENTS.md` names the new repo's
  `examples/` as its source.

## 7. Testing

**New repo, `uv run pytest -q` (the gate):**

- Every moved lesson-videos test passes after the rename (paths, command names, messages).
- `test_styles.py`:
  - every folder in `styles/` validates against the schema and its `id` equals its folder name;
  - `LV style school` prints the question `grade` with "What grade are the students?", and the check `students`
    with "Remove these slides", "They're not students" and `not students`;
  - `LV styles` lists School alone by default, and also a style from a temporary `LV_STYLES_DIR`;
  - a duplicate id, a schema mismatch and an unknown id each give an error naming the cause.
- `test_paths.py`: the first-run copy (old home present and new missing → copied with a symlink kept; new present →
  nothing copied; the old folder untouched), the settings copy, and the worker keeping `~/Lesson Videos/` when it
  exists.
- `test_skills.py`: the make skill uses `LV style`, `LV styles` and `style.txt`, and no longer writes the grade
  question or the student labels itself; the shared `guide.md` names the style guide.
- `test_packaging.py`: plugin name `slide2video`, the marketplace (name `slide2video`, source `./slide2video`) and
  the three versions agree.

**Live check before the release (about $0.50 on Opus):** a website-mode `start` turn on the water cycle sample with
the new plugin, through the same local driver used for the Opus/Sonnet comparison. Its questions card must have the
ids `grade`, `chapters`, `length`, `voice`, the grade question's text unchanged, and an `issue-1` question for the
three-versus-four-steps problem, as 1.0.1's did.

**Old repo:** `uv run pytest -q` passes with only the music-video tests, and CI no longer runs the lesson-videos
doctor. Before lesson-videos leaves `main`, 1.0.2's notice is tested in `test_skills.py` and `test_worker.py`.

**Website:** `npm run check && npm test` for the install-instruction change.

## 8. Rollout

1. **Daniel** creates the GitHub organization `slide2video`.
2. **Build the new repo:** filter, rename, styles and School, the gate, the live check; publish
   `slide2video/slide2video-plugin` with release 1.1.0 and the sample video release.
3. **Release lesson-videos 1.0.2** in `DanielLandi/plugins` (merge and push).
4. **Remove lesson-videos from the old repo's `main`** (preferred or fallback path from §5).
5. **Transfer the website repo** to the organization, update its install instructions, run its gate, and deploy once
   Daniel says so.
6. **Daniel** switches his own Mac with the three steps of the notice; `worker --status` still says "Connected to
   slide2video.com" and the Devices page shows "slide2video 1.1.0". Pairing again is needed only if it says so.

## 9. Out of scope

- pro.slide2video.com, the `live` branch, hosted processing, the private styles repo, the first private style, the
  website's style picker, the `style` field in the job contract, and the per-site Keychain entry (sub-project 2).
- Rewording the shared skill text for audiences other than teachers (sub-project 2).
- Credits, Stripe, the data disclosure page, new Terms and Privacy (sub-project 3).
- Open sign-up and the switch from slide2video.com to pro (sub-project 4).
- Style-specific drawing helpers (`helpers.js` loaded after the engine): added when a private style needs them.
