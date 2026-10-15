# slide2video design pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give slide2video.com the approved "Study notebook" identity and flows, a public landing page with an animated
diagram, usage numbers for each teacher and the admin, and four optional details the computer reports (cost breakdown, progress fraction, suggested answer, slide
count), shipped as site first, then plugin lesson-videos 0.6.0.

**Architecture:** Two repos. `~/Projects/plugins` (Tier B, branch `slide2video-design-pass`) owns the job contract
and the plugin. `~/Projects/slide2video` (Tier B, private) is a Hono Worker with server-rendered HTML, one stylesheet
and one script served as files (strict CSP: no inline style or script). Part A changes the contract (optional
fields only), Part B rebuilds the site's pages on a small UI kit and deploys it, Part C teaches the plugin to send
the new fields and releases it.

**Tech Stack:** TypeScript, Hono, Cloudflare Workers + D1 + R2 + Access, vitest with `@cloudflare/vitest-plugin`;
Python 3 via `uv`, pytest, jsonschema.

**Spec:** `docs/superpowers/specs/2026-10-14-slide2video-design-pass-design.md` (in `~/Projects/plugins`). Approved
mockups: Claude Design canvas https://claude.ai/artifact/JhS3KPdkNu5YJovbJ7Pyc7 (section "Direction A: every
screen", `Main.dc.html`, `Landing.dc.html`).

## Global Constraints

- **Which repo's rules apply:** Part A and Part C run in `~/Projects/plugins` and follow its `AGENTS.md`. Part B runs
  in `~/Projects/slide2video` and follows that repo's `AGENTS.md`; ignore the plugins repo's rules there (no version
  bumps, no `uv run pytest` gate). Commit messages need no prefix in either repo.
- Commit trailers on every commit: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01QvLH1HsAz7PKPN79tppXCM`.
- Gates: plugins `uv run pytest -q`; slide2video `npm run check && npm test`.
- CSP stays exactly `default-src 'self'; img-src 'self' data: blob:; media-src 'self'; script-src 'self'; style-src
  'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`. No `style=` attribute, no `<style>`, no inline
  `<script>`, no CDN. `test/pages.test.ts`'s `expectSafe` must keep passing on every page.
- One font: Nunito (`/fonts/nunito-v1.woff2`), no handwriting font anywhere in the site. Code uses
  `ui-monospace, Menlo, Consolas, monospace`.
- Colour tokens exactly as spec §2.1 (light and dark).
- Contract stays version 1; the new fields are optional: `estimate.items` (≤ 8 of `{label 1–80, usd ≥ 0, detail
  ≤ 120}`), option `recommended: boolean`, card `slides` (integer 1–500), heartbeat `fraction` (number 0–1).
- Usage rows hold numbers only (no titles, names, answers or file names); kept on lesson deletion; ids dropped on
  account deletion.
- Addresses: lessons list at `/lessons`; `/` is the public landing page. Pairing `verify_url` stays `/devices`.
- Copy: plain words a teacher would use; "computer"/"device", never "Mac", in anything a teacher sees.
- Plugin: Engine API frozen; `estimate` text output unchanged; model IDs and prices only in `lv/config.py`; every
  file read/write passes `encoding="utf-8"`.
- Order: Part A → Part B (deploy) → Part C (publish). The plugin is pushed only after the site is live.

## Review Focus

1. **Cards from a 0.5.x plugin** (no `items`, `recommended`, `slides`; heartbeat without `fraction`): every page
   renders as before, with no empty cost table, tag or bar. Pinned by tests in Tasks B1, B6 and B7.
2. **Unusual titles** (leading spaces, emoji first, very long): the lessons list's letter tile shows one whole
   character and the card wraps instead of overflowing. Pinned in Task B4.
3. **A plan with odd chapter counts** (0, missing, 500): the step line never shows zero chapter steps or hundreds of
   them (clamped to 20). Pinned in Task B6.
4. **Progress counts that don't make sense** (`[5/3]`, `[0/0]`, `[a/b]`, a fraction of 1.5): the plugin sends no
   fraction and the site refuses out-of-range ones. Pinned in Tasks B1 and C3.
5. **A session cookie for someone not (or no longer) invited**, or an expired or forged one: `/` shows the landing
   page and never redirects or shows teacher data. Pinned in Task B9.

---

# Part A: the contract (plugins repo)

### Task A1: Optional card fields in the contract schema

**Files:**
- Modify: `lesson-videos/site-contract/schemas/card.schema.json`
- Modify: `lesson-videos/site-contract/examples/card-plan.json`, `lesson-videos/site-contract/examples/card-questions.json`
- Test: `tests/test_contract.py`

**Interfaces:**
- Produces: the schema the site copies in Task B1 and the plugin validates against in Part C.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_contract.py`)

```python
def test_new_optional_fields_are_checked():
    plan = _ex("card-plan.json")
    plan["estimate"]["items"] = [{"label": "", "usd": 1}]
    assert any("items" in p for p in contract.problems("card", plan))
    plan["estimate"]["items"] = [{"label": "Music", "usd": -1}]
    assert any("items" in p for p in contract.problems("card", plan))
    q = _ex("card-questions.json")
    q["slides"] = 0
    assert any("slides" in p for p in contract.problems("card", q))
    q = _ex("card-questions.json")
    q["questions"][0]["options"][0]["recommended"] = "yes"
    assert any("recommended" in p for p in contract.problems("card", q))


def test_cards_without_the_new_fields_stay_valid():
    plan = _ex("card-plan.json")
    plan["estimate"].pop("items")
    q = _ex("card-questions.json")
    q.pop("slides")
    for question in q["questions"]:
        for o in question["options"]:
            o.pop("recommended", None)
    assert contract.problems("card", plan) == []
    assert contract.problems("card", q) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_contract.py`
Expected: FAIL (`KeyError: 'items'` / `'slides'` from the examples, and no problems reported for the bad values).

- [ ] **Step 3: Change the schema and examples**

In `card.schema.json`, top-level `"properties"` becomes:

```json
  "properties": {
    "contract": {"const": 1},
    "kind": {"enum": ["questions", "plan", "review", "done", "error"]},
    "message": {"type": "string", "maxLength": 2000},
    "slides": {"type": "integer", "minimum": 1, "maximum": 500}
  },
```

The option item's `"properties"` (inside `questions` → `options` → `items`) becomes:

```json
                    "properties": {
                      "label": {"type": "string", "minLength": 1, "maxLength": 120},
                      "detail": {"type": "string", "maxLength": 300},
                      "recommended": {"type": "boolean"}
                    }
```

The plan `estimate` `"properties"` becomes:

```json
            "properties": {
              "usd": {"type": "number", "minimum": 0},
              "minutes": {"type": "number", "minimum": 0},
              "chapters": {"type": "integer", "minimum": 1},
              "items": {
                "type": "array", "maxItems": 8,
                "items": {
                  "type": "object",
                  "required": ["label", "usd"],
                  "properties": {
                    "label": {"type": "string", "minLength": 1, "maxLength": 80},
                    "usd": {"type": "number", "minimum": 0},
                    "detail": {"type": "string", "maxLength": 120}
                  }
                }
              }
            }
```

`examples/card-plan.json`:

```json
{"contract": 1, "kind": "plan", "message": "Here's the plan. Nothing that costs money happens until you approve it.",
 "markdown": "## Chapter 1 – The Water Cycle (~3 min)\n- Hook: the essential question\n- Evaporation\n- Condensation (trap: clouds are liquid)\n- Precipitation\n- Collection\n- Quiz (3 questions)\n- Recap",
 "estimate": {"usd": 0, "minutes": 3, "chapters": 1,
              "items": [{"label": "Narration (free voice)", "usd": 0}]}}
```

`examples/card-questions.json`:

```json
{"contract": 1, "kind": "questions", "message": "A few questions before I plan the videos.", "slides": 12,
 "questions": [
   {"id": "grade", "text": "What grade are the students?",
    "options": [{"label": "Grades 3–5"}, {"label": "Grades 6–8", "recommended": true}, {"label": "Grades 9–10"}], "other": true},
   {"id": "issue-1", "text": "The review asks for three main steps, but the deck teaches four. How should the video handle it?",
    "options": [{"label": "Teach 4, quiz on 4", "detail": "Quiz asks for the four steps", "recommended": true},
                {"label": "Follow the slide", "detail": "Keep three main steps"}], "other": true}]}
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS (all, including `test_examples_are_valid`).

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/site-contract tests/test_contract.py
git commit -m "lesson-videos contract: optional cost items, suggested option and slide count"
```

---

# Part B: the site (slide2video repo)

All paths below are relative to `~/Projects/slide2video`. Work on `main` in small commits (Tier B), pushing only in
Task B11.

### Task B1: Contract copy, migration, heartbeat fraction and slide count

**Files:**
- Modify: `contract/schemas/card.schema.json`, `contract/examples/*` (copied from the plugins repo)
- Create: `migrations/0002_design_pass.sql`
- Modify: `src/device.ts` (heartbeat and finish), `src/turns.ts` (claim)
- Test: `test/turns.test.ts`

**Interfaces:**
- Produces: `turns.progress_fraction REAL` (NULL or 0–1), `lessons.slides INTEGER` (NULL or 1–500), used by Tasks
  B4 and B6.

- [ ] **Step 1: Copy the contract**

```bash
cp ~/Projects/plugins/lesson-videos/site-contract/schemas/*.json contract/schemas/
cp ~/Projects/plugins/lesson-videos/site-contract/examples/*.json contract/examples/
git diff --stat contract
```

Expected: `card.schema.json`, `card-plan.json` and `card-questions.json` change; nothing else.

- [ ] **Step 2: Write the failing tests** (append inside the top-level `describe` of `test/turns.test.ts`; add
  `env` from `cloudflare:workers` and `asTeacher` to the imports if missing)

```ts
  it("stores a heartbeat's fraction, replaces it on each heartbeat, refuses a bad one, and clears it on a new claim", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    await newLesson(t.email);
    const turn = await claim(mac.token);
    const hb = (body: object) =>
      asDevice(mac.token, `/api/device/turns/${turn.turn.id}/heartbeat`, { method: "POST", body: JSON.stringify(body) });
    const row = () => env.DB.prepare("SELECT progress, progress_fraction FROM turns WHERE id = ?").bind(turn.turn.id)
      .first<{ progress: string | null; progress_fraction: number | null }>();
    expect((await hb({ progress: "Narrating scenes", fraction: 0.25 })).status).toBe(204);
    expect(await row()).toEqual({ progress: "Narrating scenes", progress_fraction: 0.25 });
    expect((await hb({ progress: "Rendering" })).status).toBe(204);
    expect(await row()).toEqual({ progress: "Rendering", progress_fraction: null });
    for (const bad of [-0.1, 1.5, "0.5", null, true]) {
      expect((await hb({ progress: "x", fraction: bad })).status, String(bad)).toBe(400);
    }
    expect((await hb({ progress: "Rendering", fraction: 1 })).status).toBe(204);
    await env.DB.prepare("UPDATE turns SET lease_until = 0 WHERE id = ?").bind(turn.turn.id).run();
    expect((await claim(mac.token)).turn.id).toBe(turn.turn.id);
    expect((await row())!.progress_fraction).toBeNull();
  });

  it("keeps the slide count a card carries, and keeps it when a later card has none", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    const slides = () => env.DB.prepare("SELECT slides FROM lessons WHERE id = ?").bind(id).first<{ slides: number | null }>();
    expect((await slides())!.slides).toBeNull();
    const first = await claim(mac.token);
    expect((await finish(mac.token, first.turn.id, { ...QUESTIONS, slides: 12 })).status).toBe(204);
    expect((await slides())!.slides).toBe(12);
    await asTeacher(t.email, `/api/lessons/${id}/answer`, { method: "POST",
      body: JSON.stringify({ answers: [{ question: "grade", choice: "Grades 6–8", other: null }] }) });
    const second = await claim(mac.token);
    expect((await finish(mac.token, second.turn.id, PLAN)).status).toBe(204);
    expect((await slides())!.slides).toBe(12);
  });

  it("refuses a card whose slide count is out of range", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    await newLesson(t.email);
    const turn = await claim(mac.token);
    expect((await finish(mac.token, turn.turn.id, { ...QUESTIONS, slides: 0 })).status).toBe(422);
    expect((await finish(mac.token, turn.turn.id, { ...QUESTIONS, slides: 501 })).status).toBe(422);
  });
```

- [ ] **Step 3: Run them to see them fail**

Run: `npx vitest run test/turns.test.ts`
Expected: FAIL (`no such column: progress_fraction`; the bad fractions answer 204).

- [ ] **Step 4: Implement**

`migrations/0002_design_pass.sql`:

```sql
-- design pass: what the computer reports beyond the card (spec §5.2, §5.4)
ALTER TABLE turns ADD COLUMN progress_fraction REAL;
ALTER TABLE lessons ADD COLUMN slides INTEGER;
```

`src/device.ts`, the heartbeat handler becomes:

```ts
device.post("/turns/:id/heartbeat", async (c) => {
  const body = await readObject(c);
  if (!body || (body.progress !== undefined && typeof body.progress !== "string")) return c.json({ error: "bad request" }, 400);
  // a fraction belongs to the progress line it came with: a heartbeat without one clears it
  const f = body.fraction;
  if (f !== undefined && (typeof f !== "number" || !Number.isFinite(f) || f < 0 || f > 1)) return c.json({ error: "bad request" }, 400);
  const progress = typeof body.progress === "string" ? cleanProgress(body.progress).slice(0, 200) : null;
  const r = await c.env.DB.prepare(
    `UPDATE turns SET lease_until = ?3, progress = COALESCE(?4, progress), progress_fraction = ?5 WHERE ${HELD}`,
  ).bind(c.req.param("id"), c.get("device").id, now() + LEASE, progress, typeof f === "number" ? f : null).run();
  return r.meta.changes ? c.body(null, 204) : c.json({ error: NOT_HELD }, 409);
});
```

In the finish handler's batch, replace
`db.prepare("UPDATE lessons SET updated_at = ? WHERE id = ?").bind(t, turn.lesson_id),` with:

```ts
    db.prepare("UPDATE lessons SET updated_at = ?1, slides = COALESCE(?2, slides) WHERE id = ?3")
      .bind(t, typeof card.slides === "number" ? card.slides : null, turn.lesson_id),
```

`src/turns.ts`, in the claim's first `UPDATE turns SET state = 'running', …, progress = NULL` add
`, progress_fraction = NULL` right after `progress = NULL`.

- [ ] **Step 5: Run the gate**

Run: `npm run check && npm test`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add contract migrations/0002_design_pass.sql src/device.ts src/turns.ts test/turns.test.ts
git commit -m "slide2video: accept progress fractions and slide counts from the computer (contract copy, migration 0002)"
```

### Task B2: The site's own files (font, pictures, logo, icon)

**Files:**
- Create: `assets/fonts/nunito-v1.woff2`, `assets/fonts/OFL-Nunito.txt`, `assets/img/sample-1-hook.webp`,
  `assets/img/sample-2-diagram.webp`, `assets/img/sample-3-quiz.webp`, `assets/logo.svg`, `assets/favicon.svg`
- Create: `tools/gen-assets.mjs`, `src/assets.gen.ts` (generated, committed), `src/assets.ts`
- Modify: `src/index.ts`, `package.json` (script `assets`), `AGENTS.md` (one line)
- Test: `test/assets.test.ts`

**Interfaces:**
- Produces: public URLs `/fonts/nunito-v1.woff2`, `/fonts/OFL-Nunito.txt`, `/img/sample-1-hook.webp`,
  `/img/sample-2-diagram.webp`, `/img/sample-3-quiz.webp`, `/logo.svg`, `/favicon.svg`; `serveAsset(c)` in
  `src/assets.ts`.

- [ ] **Step 1: Make the font and copy the files**

```bash
mkdir -p assets/fonts assets/img tools
uvx --from 'fonttools[woff]' pyftsubset ~/Projects/plugins/lesson-videos/fonts/Nunito.ttf \
  --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2190-2193,U+2212,U+2215,U+2713,U+FEFF,U+FFFD' \
  --layout-features='*' --flavor=woff2 --output-file=assets/fonts/nunito-v1.woff2
cp ~/Projects/plugins/lesson-videos/fonts/OFL-Nunito.txt assets/fonts/
for f in sample-1-hook sample-2-diagram sample-3-quiz; do cp ~/Projects/plugins/lesson-videos/docs/images/$f.webp assets/img/; done
ls -la assets/fonts assets/img
```

Expected: the woff2 is under 120 KB; three webp files of about 30 KB.

`assets/logo.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="40" viewBox="0 0 48 40"><rect x="10" y="2" width="34" height="24" rx="4" fill="#1FA7A0"/><rect x="3" y="9" width="34" height="26" rx="4" fill="#0B2545"/><path d="M16 15 L27 22 L16 29 Z" fill="#FFC145"/></svg>
```

`assets/favicon.svg` (square):

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 -4 48 48"><rect x="10" y="2" width="34" height="24" rx="4" fill="#1FA7A0"/><rect x="3" y="9" width="34" height="26" rx="4" fill="#0B2545"/><path d="M16 15 L27 22 L16 29 Z" fill="#FFC145"/></svg>
```

- [ ] **Step 2: Write the generator**

`tools/gen-assets.mjs`:

```js
// Builds src/assets.gen.ts from assets/: the site serves its few files from the Worker itself (no other host),
// so the CSP stays 'self'. Run `npm run assets` after changing anything in assets/.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = { ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".webp": "image/webp", ".svg": "image/svg+xml" };
const FILES = ["fonts/nunito-v1.woff2", "fonts/OFL-Nunito.txt", "img/sample-1-hook.webp", "img/sample-2-diagram.webp",
  "img/sample-3-quiz.webp", "logo.svg", "favicon.svg"];
const out = {};
for (const rel of FILES) {
  out["/" + rel] = { type: TYPES[path.extname(rel)], b64: fs.readFileSync(path.join(root, "assets", rel)).toString("base64") };
}
fs.writeFileSync(path.join(root, "src", "assets.gen.ts"),
  "// Generated by tools/gen-assets.mjs from assets/: do not edit. Run `npm run assets` after changing a file there.\n" +
  "export const ASSETS: Record<string, { type: string; b64: string }> = " + JSON.stringify(out, null, 1) + ";\n");
```

In `package.json` `"scripts"` add `"assets": "node tools/gen-assets.mjs",`. Run `npm run assets`.

- [ ] **Step 3: Write the failing test**

`test/assets.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { exports } from "cloudflare:workers";
import { BASE } from "./helpers";

describe("the site's own files", () => {
  it("serves them without sign-in, with the right type, security headers and caching", async () => {
    const cases: [string, string, string][] = [
      ["/fonts/nunito-v1.woff2", "font/woff2", "public, max-age=31536000, immutable"],
      ["/fonts/OFL-Nunito.txt", "text/plain; charset=utf-8", "public, max-age=31536000, immutable"],
      ["/img/sample-1-hook.webp", "image/webp", "public, max-age=31536000, immutable"],
      ["/img/sample-2-diagram.webp", "image/webp", "public, max-age=31536000, immutable"],
      ["/img/sample-3-quiz.webp", "image/webp", "public, max-age=31536000, immutable"],
      ["/logo.svg", "image/svg+xml", "public, max-age=86400"],
      ["/favicon.svg", "image/svg+xml", "public, max-age=86400"],
    ];
    for (const [p, type, cache] of cases) {
      const r = await exports.default.fetch(BASE + p);
      expect(r.status, p).toBe(200);
      expect(r.headers.get("Content-Type"), p).toBe(type);
      expect(r.headers.get("Cache-Control"), p).toBe(cache);
      expect(r.headers.get("Content-Security-Policy"), p).toContain("default-src 'self'");
      expect((await r.arrayBuffer()).byteLength, p).toBeGreaterThan(100);
    }
    const font = new Uint8Array(await (await exports.default.fetch(BASE + "/fonts/nunito-v1.woff2")).arrayBuffer());
    expect(new TextDecoder().decode(font.slice(0, 4))).toBe("wOF2");
  });

  it("answers 404 for a file it doesn't have", async () => {
    for (const p of ["/fonts/nope.woff2", "/img/x.webp", "/fonts/OFL-Other.txt"]) {
      expect((await exports.default.fetch(BASE + p)).status, p).toBe(404);
    }
  });
});
```

- [ ] **Step 4: Run it to see it fail**

Run: `npx vitest run test/assets.test.ts`
Expected: FAIL (401 from `teacherAuth`).

- [ ] **Step 5: Implement**

`src/assets.ts`:

```ts
import type { Context } from "hono";
import type { AppEnv } from "./env";
import { ASSETS } from "./assets.gen";

const decoded = new Map<string, Uint8Array>();

function bytes(path: string, b64: string): Uint8Array {
  let b = decoded.get(path);
  if (!b) {
    const s = atob(b64);
    b = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    decoded.set(path, b);
  }
  return b;
}

/** The site's own font, pictures, logo and icon. Versioned names (fonts/, img/) are cached for a year. */
export function serveAsset(c: Context<AppEnv>): Response {
  const path = c.req.path;
  const a = ASSETS[path];
  if (!a) return c.notFound();
  const versioned = path.startsWith("/fonts/") || path.startsWith("/img/");
  return c.body(bytes(path, a.b64), 200, {
    "Content-Type": a.type,
    "Cache-Control": versioned ? "public, max-age=31536000, immutable" : "public, max-age=86400",
  });
}
```

`src/index.ts`: import `serveAsset` and register above the `teacherAuth` line (beside `/app.css`):

```ts
app.get("/fonts/:file", serveAsset);
app.get("/img/:file", serveAsset);
app.get("/logo.svg", serveAsset);
app.get("/favicon.svg", serveAsset);
```

`AGENTS.md`: under the build section add the line
`- Static files (font, pictures, logo) live in assets/; run npm run assets after changing one, and commit src/assets.gen.ts.`

- [ ] **Step 6: Run the gate**

Run: `npm run check && npm test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add assets tools src/assets.ts src/assets.gen.ts src/index.ts package.json AGENTS.md test/assets.test.ts
git commit -m "slide2video: serve the site's own font, sample pictures, logo and icon"
```

### Task B3: The UI kit: stylesheet, page frame, public pages, lessons at /lessons

**Files:**
- Modify: `src/client.ts` (replace `APP_CSS`)
- Create: `src/ui.ts`
- Modify: `src/pages.ts` (`layout`, `publicPage`, list route moves to `/lessons`, links to `/` → `/lessons`)
- Modify: `src/auth.ts` (not-invited page and 401 use the frame)
- Modify: `src/index.ts` (`/app.js` becomes public)
- Test: `test/pages.test.ts`, `test/auth.test.ts`, and every test that requests `"/"` as the lessons list

**Interfaces:**
- Produces (`src/ui.ts`): `LOGO: Raw`, `WORDMARK: Raw`, `type NavItem = { href: string; label: string; current?:
  boolean; cta?: boolean }`, `SIGN_IN: NavItem`, `shell(o: { title: string; body: Raw; nav: NavItem[]; home: string;
  refresh?: number; script?: boolean; narrow?: boolean; description?: string }): string`, `signInPage(): string`.
- Produces (`src/pages.ts`): `layout(c, title, body, opts?: { refresh?: number; current?: "lessons" | "devices" |
  "account" | "admin"; narrow?: boolean })`. Every class used by Tasks B4–B9 is defined in this task's stylesheet.

- [ ] **Step 1: Write the failing tests** (in `test/pages.test.ts`)

Replace the old "public pages" sign-in assertion `expect((await exports.default.fetch(BASE + "/")).status).toBe(401);`
with `expect((await exports.default.fetch(BASE + "/lessons")).status).toBe(401);`, change every
`get(<email>, "/")` and `asTeacher(<email>, "/")` in the test files to `"/lessons"` (`grep -n '"/")' test/*.ts`), and
add:

```ts
describe("page frame", () => {
  it("puts the logo, the nav with the current page, the icon and the footer on every signed-in page", async () => {
    const t = await seedTeacher();
    const page = await get(t.email, "/devices");
    expect(page).toContain('<a class="brand" href="/lessons">');
    expect(page).toContain('<span class="wm">slide<b>2</b>video</span>');
    expect(page).toContain('<a href="/devices" aria-current="page">Devices</a>');
    expect(page).toContain('<a href="/lessons">Lessons</a>');
    expect(page).toContain('<link rel="icon" href="/favicon.svg" type="image/svg+xml">');
    expect(page).toContain('<script src="/app.js"></script>');
    expect(page).not.toContain(t.email); // the email moved to Account
    expectSafe(page);
  });

  it("sends the old home address to /lessons", async () => {
    const t = await seedTeacher();
    const r = await asTeacher(t.email, "/");
    expect(r.status).toBe(302);
    expect(r.headers.get("Location")).toBe("/lessons");
  });

  it("answers an unsigned teacher page with a sign-in page and an API call with JSON", async () => {
    const page = await exports.default.fetch(BASE + "/devices");
    expect(page.status).toBe(401);
    const text = await page.text();
    expect(text).toContain('<a class="button primary" href="/lessons">Sign in</a>');
    expectSafe(text);
    const api = await exports.default.fetch(BASE + "/api/lessons");
    expect(api.status).toBe(401);
    expect(await api.json()).toEqual({ error: "Your sign-in ran out. Reload the page to sign in again." });
  });

  it("serves app.js without sign-in", async () => {
    const r = await exports.default.fetch(BASE + "/app.js");
    expect(r.status).toBe(200);
    expect(r.headers.get("Content-Type")).toContain("text/javascript");
  });

  it("gives Terms and Privacy the frame and a Sign in link, without the script", async () => {
    for (const p of ["/terms", "/privacy"]) {
      const page = await (await exports.default.fetch(BASE + p)).text();
      expect(page, p).toContain('<a href="/lessons" class="cta">Sign in</a>');
      expect(page, p).toContain('<div class="prose">');
      expect(page, p).not.toContain("<script");
    }
  });
});
```

In `test/auth.test.ts`, change any assertion on the old 401 text `"Sign in at slide2video.com."` to
`toContain("Sign in to continue")`, and on the not-invited page to `toContain("hasn't been invited yet")`.

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/pages.test.ts test/auth.test.ts`
Expected: FAIL (no `brand` link, `/lessons` 404, `/app.js` 401).

- [ ] **Step 3: Write `src/ui.ts`**

```ts
import { html, raw, type Raw } from "./http";

/** The mark: two slides, the front one plays. Decorative next to the wordmark. */
export const LOGO = raw('<svg viewBox="0 0 48 40" aria-hidden="true" focusable="false"><rect x="10" y="2" width="34" ' +
  'height="24" rx="4" fill="#1FA7A0"/><rect x="3" y="9" width="34" height="26" rx="4" fill="#0B2545"/>' +
  '<path d="M16 15 L27 22 L16 29 Z" fill="#FFC145"/></svg>');
export const WORDMARK = raw('<span class="wm">slide<b>2</b>video</span>');

export type NavItem = { href: string; label: string; current?: boolean; cta?: boolean };
export const SIGN_IN: NavItem = { href: "/lessons", label: "Sign in", cta: true };

/** Every page's frame: head, header (logo and nav), main, footer. `script` adds /app.js. */
export function shell(o: { title: string; body: Raw; nav: NavItem[]; home: string; refresh?: number; script?: boolean;
  narrow?: boolean; description?: string }): string {
  const nav = o.nav.map((n) => html`<a href="${n.href}"${n.current ? raw(' aria-current="page"') : ""}${n.cta ? raw(' class="cta"') : ""}>${n.label}</a>`);
  return html`<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${o.title}</title>
${o.description ? html`<meta name="description" content="${o.description}">` : ""}<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/app.css"></head>
<body${o.refresh ? html` data-refresh="${o.refresh}"` : ""}><header class="site"><div class="bar">
<a class="brand" href="${o.home}">${LOGO}${WORDMARK}</a>
${nav.length ? html`<nav aria-label="Main">${nav}</nav>` : ""}</div></header>
<main class="page${o.narrow ? " narrow" : ""}">${o.body}</main>
<footer class="site"><div class="bar"><span>slide2video.com</span><a href="/terms">Terms</a><a href="/privacy">Privacy</a>
<a href="https://github.com/DanielLandi/plugins" rel="noopener noreferrer">Built on the open-source lesson-videos plugin</a></div></footer>
${o.script ? raw('<script src="/app.js"></script>') : ""}</body></html>`.s;
}

/** What a teacher page answers without a valid sign-in. */
export const signInPage = () => shell({ title: "Sign in · slide2video", home: "/", nav: [],
  body: html`<div class="prose"><h1>Sign in to continue</h1><p>This page is for invited teachers.</p>
<p><a class="button primary" href="/lessons">Sign in</a></p></div>` });
```

- [ ] **Step 4: Replace `APP_CSS` in `src/client.ts`** (keep `APP_JS` unchanged in this task)

```ts
export const APP_CSS = `
@font-face{font-family:Nunito;src:url(/fonts/nunito-v1.woff2) format("woff2");font-weight:200 1000;font-style:normal;font-display:swap}
:root{color-scheme:light dark;--paper:#FBF8F1;--card:#FFFFFF;--ink:#16212E;--heading:#0B2545;--muted:#5E6875;--line:#E7DFCF;
--line-soft:#F0EADD;--primary:#0B2545;--on-primary:#FFFFFF;--link:#137F7A;--teal:#1FA7A0;--foam:#E8F7F5;--sun:#FFC145;
--sun-soft:#FFF4E0;--pill-bg:#FFE9B8;--pill-ink:#7A4A00;--turn:#C2412D;--danger:#A3321F;--danger-line:#E9B4A9;
--code-bg:#0B2545;--code-ink:#FFFFFF;--font:Nunito,system-ui,-apple-system,"Segoe UI",sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--paper:#101826;--card:#172233;--ink:#ECEFF3;--heading:#F4F1EA;--muted:#A7B1BE;
--line:#2A3A52;--line-soft:#22314A;--primary:#FFC145;--on-primary:#0B2545;--link:#6FD3C9;--foam:#163B3E;--sun-soft:#3A3018;
--pill-bg:#4A3A12;--pill-ink:#FFE2A0;--turn:#FF8A73;--danger:#FF8A80;--danger-line:#6B2A22;--code-bg:#0A111C}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:17px/1.55 var(--font);color:var(--ink);background:var(--paper)}
a{color:var(--link)}a:hover{color:var(--heading)}
h1,h2,h3{color:var(--heading);text-wrap:balance;overflow-wrap:anywhere;margin:0}
h1{font-size:2.35rem;line-height:1.1;font-weight:800}
h2{font-size:1.5rem;line-height:1.2;font-weight:800}
h3{font-size:1.15rem;font-weight:800}
h4{margin:0;font-size:1rem}
p{margin:0}
:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
.bar{max-width:1120px;margin:0 auto;padding:14px 24px;display:flex;flex-wrap:wrap;align-items:center;gap:12px 28px}
header.site{border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--heading)}
.brand svg{width:36px;height:30px;flex:none}
.wm{font-weight:800;font-size:1.25rem;letter-spacing:-.01em;white-space:nowrap}
.wm b{display:inline-block;width:1.3em;height:1.3em;line-height:1.3em;text-align:center;border-radius:50%;background:var(--sun);color:#0B2545;margin:0 2px}
header nav{display:flex;flex-wrap:wrap;align-items:center;gap:8px 24px;margin-left:auto;font-weight:700}
header nav a{color:var(--muted);text-decoration:none;padding-bottom:2px;border-bottom:3px solid transparent}
header nav a:hover{color:var(--heading)}
header nav a[aria-current=page]{color:var(--heading);border-bottom-color:var(--sun)}
header nav a.cta{display:inline-flex;align-items:center;min-height:44px;padding:0 18px;border:0;border-radius:12px;background:var(--primary);color:var(--on-primary)}
footer.site{margin-top:48px;border-top:1px solid var(--line)}
footer.site .bar{font-size:.9rem;color:var(--muted);gap:8px 24px;padding-bottom:40px}
main.page{max-width:1120px;margin:0 auto;padding:28px 24px 24px;display:flex;flex-direction:column;gap:24px}
main.page.narrow{max-width:760px}
.stack{display:flex;flex-direction:column;gap:16px;min-width:0}
.row{display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.between{justify-content:space-between}
.grow{flex:999 1 420px;min-width:0}
.split{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start}
.split>.main{flex:999 1 520px;min-width:0}
.split>.side{flex:1 1 280px;min-width:0}
.title{display:flex;flex-direction:column;gap:4px}
.back{font-size:.9rem;font-weight:700;text-decoration:none}
.meta,.muted{color:var(--muted)}
.small{font-size:.9rem}
.label{font-size:.82rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.label.you{color:var(--turn)}.label.making{color:var(--link)}
.turn-note{font-weight:800;color:var(--turn)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 3px 0 var(--line);padding:24px;display:flex;flex-direction:column;gap:16px;min-width:0;overflow-wrap:anywhere}
.card-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px}
.notice{background:var(--foam);border-radius:12px;padding:14px 16px}
.notice.sun{background:var(--sun-soft);border:2px solid var(--sun)}
.warn,.error{color:var(--danger);font-weight:700}
.ok{color:var(--link);font-weight:700}
button,.button{display:inline-flex;align-items:center;justify-content:center;gap:8px;font:inherit;font-weight:800;min-height:48px;padding:0 20px;border-radius:12px;border:2px solid var(--primary);background:var(--card);color:var(--heading);cursor:pointer;text-decoration:none}
button.primary,.button.primary{background:var(--primary);border-color:var(--primary);color:var(--on-primary);min-height:52px;font-size:1.05rem}
button.danger,.button.danger{border-color:var(--danger-line);color:var(--danger)}
button.danger.solid{background:var(--danger);border-color:var(--danger);color:#FFFFFF}
button.link{min-height:44px;padding:0 8px;border:0;background:none;color:var(--link)}
button:disabled{opacity:.6;cursor:wait}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px}
label{display:flex;flex-direction:column;gap:6px;font-weight:700;color:var(--heading)}
.hint{font-weight:600;font-size:.9rem;color:var(--muted)}
input,textarea{font:inherit;font-weight:400;width:100%;padding:12px 14px;border:2px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
textarea{resize:vertical}
input[type=radio],input[type=checkbox]{width:22px;height:22px;margin:2px 0 0;flex:none;accent-color:var(--heading)}
input[type=file]{border:0;padding:0}
fieldset{margin:0;padding:0;border:0;display:flex;flex-direction:column;gap:10px;min-width:0}
legend{padding:0 0 10px;font-weight:800;font-size:1.1rem;color:var(--heading)}
.choices{display:flex;flex-wrap:wrap;gap:10px}
label.choice{flex:1 1 240px;flex-direction:row;align-items:flex-start;gap:10px;padding:12px 14px;border:2px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);font-weight:400;cursor:pointer}
label.choice:has(input:checked){border-color:var(--heading);background:var(--sun-soft)}
label.choice strong{color:var(--heading)}
.detail{display:block;font-size:.9rem;font-weight:400;color:var(--muted)}
label.check{flex-direction:row;align-items:flex-start;gap:12px;font-weight:400;color:var(--ink)}
.tag{display:inline-block;margin-left:6px;font-size:.78rem;font-weight:800;padding:1px 8px;border-radius:99px;background:var(--foam);color:var(--link);vertical-align:middle}
fieldset.issue{padding:16px;border:2px dashed var(--sun);border-radius:14px;background:var(--sun-soft)}
fieldset.issue legend{padding:0 8px}
input.own{max-width:520px}
.steps-line{overflow-x:auto}
.steps-line ol{list-style:none;margin:0;padding:4px 0;display:flex;min-width:560px}
.steps-line li{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;font-size:.95rem;font-weight:700;color:var(--muted);text-align:center}
.steps-line .dot{width:22px;height:22px;border-radius:50%;border:3px dashed var(--line)}
.steps-line .done{color:var(--link)}
.steps-line .done .dot{border:0;background:var(--link)}
.steps-line .done .dot::after{content:"✓";display:block;color:var(--card);font-size:13px;font-weight:800;line-height:22px}
.steps-line .now{color:var(--turn)}
.steps-line .now .dot{border:3px solid var(--turn);background:var(--sun)}
.pill{display:inline-flex;align-self:flex-start;font-size:.85rem;font-weight:800;padding:2px 10px;border-radius:99px;background:var(--pill-bg);color:var(--pill-ink)}
.pill.making{background:var(--foam);color:var(--link)}
.lesson-cards{display:flex;flex-wrap:wrap;gap:16px}
a.lesson-card{flex:1 1 360px;min-width:0;display:flex;gap:16px;align-items:center;padding:16px;background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 3px 0 var(--line);text-decoration:none;color:var(--ink)}
a.lesson-card:hover{border-color:var(--heading)}
.lesson-card .body{min-width:0;display:flex;flex-direction:column;gap:4px}
.lesson-card .name{font-weight:800;font-size:1.15rem;color:var(--heading);overflow-wrap:anywhere}
.lesson-card .go{font-size:.9rem;font-weight:800;color:var(--link)}
.thumb{flex:none;width:112px;aspect-ratio:16/9;border-radius:8px;object-fit:cover;display:grid;place-items:center;font-weight:800;font-size:1.6rem;color:#FFFFFF}
.tint-0{background:#0F4C75}.tint-1{background:#137F7A}.tint-2{background:#1E5B3A}.tint-3{background:#7A4A00}.tint-4{background:#5B3A8C}.tint-5{background:#A3321F}
.rows{background:var(--card);border:1px solid var(--line);border-radius:16px;display:flex;flex-direction:column}
.rows>.item{display:flex;flex-wrap:wrap;align-items:center;gap:8px 20px;padding:16px 20px;border-top:1px solid var(--line-soft)}
.rows>.item:first-child{border-top:0}
.rows .name{flex:1 1 220px;min-width:0;font-weight:800;color:var(--heading);overflow-wrap:anywhere}
.rows .name .meta{display:block;font-weight:600;font-size:.9rem}
.rows .what{flex:2 1 320px;min-width:0;display:flex;flex-direction:column;gap:6px}
progress{display:block;width:100%;height:12px;border:0;border-radius:99px;background:var(--foam);overflow:hidden;appearance:none;-webkit-appearance:none}
progress::-webkit-progress-bar{background:var(--foam);border-radius:99px}
progress::-webkit-progress-value{background:var(--teal);border-radius:99px}
progress::-moz-progress-bar{background:var(--teal);border-radius:99px}
.empty{flex-direction:row;flex-wrap:wrap;gap:32px;align-items:center}
.empty svg,.art{flex:none;width:220px;max-width:100%;height:auto}
.art.small{width:56px}
ol.numbered{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px;counter-reset:n}
ol.numbered>li{display:flex;gap:14px;align-items:flex-start;counter-increment:n}
ol.numbered>li::before{content:counter(n);flex:none;width:34px;height:34px;border-radius:50%;background:var(--sun);color:#0B2545;font-weight:800;text-align:center;line-height:34px}
ol.numbered>li.done::before{content:"✓";background:var(--link);color:var(--card)}
ol.numbered>li>div{min-width:0;flex:1;display:flex;flex-direction:column;gap:6px}
ol.numbered.ruled>li{padding:14px 0;border-top:1px solid var(--line-soft)}
ol.numbered.ruled>li:first-child{border-top:0}
.drop{position:relative;display:flex;flex-direction:column;align-items:center;gap:8px;padding:32px 20px;border:3px dashed var(--teal);border-radius:16px;background:var(--card);text-align:center;font-weight:600;color:var(--muted);cursor:pointer}
.drop.small{padding:14px 16px;border-width:2px;border-color:var(--line);flex-direction:row;text-align:left}
.drop.over{background:var(--foam)}
.drop strong{font-size:1.15rem;color:var(--heading)}
.drop .pick{color:var(--link);font-weight:800;text-decoration:underline}
.drop input[type=file]{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
.file-row{display:flex;align-items:center;gap:14px;padding:12px 16px;background:var(--card);border:1px solid var(--line);border-radius:12px}
.file-row .what{flex:1;min-width:0;display:flex;flex-direction:column}
.aside{background:var(--foam);border-radius:16px;padding:22px;display:flex;flex-direction:column;gap:14px}
.cost{border:2px solid var(--heading);border-radius:16px;background:var(--card);padding:24px;display:flex;flex-direction:column;gap:14px}
.cost .total{font-size:2.6rem;font-weight:800;line-height:1;color:var(--heading);font-variant-numeric:tabular-nums}
.cost dl{margin:0;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;font-size:.95rem;font-variant-numeric:tabular-nums}
.cost dd{margin:0;text-align:right}
.video video{display:block;width:100%;aspect-ratio:16/9;border-radius:12px;background:#000}
img{max-width:100%;height:auto}
.downloads{display:flex;flex-direction:column;gap:6px;font-weight:700;border-top:1px solid var(--line);padding-top:14px}
pre.code{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:.9rem/1.5 var(--mono);background:var(--code-bg);color:var(--code-ink);padding:12px 14px;border-radius:10px}
code{font-family:var(--mono);font-size:.9em;background:var(--foam);padding:1px 6px;border-radius:4px}
pre.code code{background:none;padding:0;color:inherit}
input.code-box{width:220px;max-width:100%;font:1.9rem var(--mono);letter-spacing:.12em;text-transform:uppercase;text-align:center;border:3px solid var(--heading);background:var(--sun-soft);color:var(--heading)}
.danger-zone{border:2px solid var(--danger-line);border-radius:16px;background:var(--card);padding:24px;display:flex;flex-direction:column;gap:12px}
.danger-zone h2{color:var(--danger)}
details{min-width:0}
summary{cursor:pointer;font-weight:800;color:var(--link);min-height:44px;display:flex;align-items:center;gap:8px}
details.past{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 16px}
details.past[open]{padding-bottom:16px}
details.past summary{color:var(--heading)}
.past-list{display:flex;flex-direction:column;gap:10px}
pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:.85rem/1.5 var(--mono);background:var(--paper);padding:10px;border-radius:8px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse}
td,th{text-align:left;vertical-align:top;padding:10px 8px;border-bottom:1px solid var(--line-soft);overflow-wrap:anywhere}
th{color:var(--heading)}
ul{margin:0;padding-left:22px}
ul.list{display:flex;flex-direction:column;gap:8px}
form.inline{display:inline}
.prose{max-width:68ch;display:flex;flex-direction:column;gap:12px}
.prose h2{margin-top:16px}
.plan-text{display:flex;flex-direction:column;gap:10px}
p[data-msg]{font-weight:700}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media (max-width:600px){body{font-size:16px}.bar{padding:12px 16px}main.page{padding:20px 16px}h1{font-size:1.9rem}
.card,.cost,.danger-zone{padding:18px}.thumb{width:84px}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
`;
```

- [ ] **Step 5: Use the frame in `src/pages.ts` and `src/auth.ts`**

`src/pages.ts`: import `shell, SIGN_IN, type NavItem` from `./ui` and replace `layout` and `publicPage`:

```ts
type Section = "lessons" | "devices" | "account" | "admin";

/** A signed-in page. `refresh` (seconds) makes app.js reload it, for while a computer is working. */
function layout(c: Context<AppEnv>, title: string, body: Raw,
  opts: { refresh?: number; current?: Section; narrow?: boolean } = {}): string {
  const item = (href: string, label: string, s: Section): NavItem => ({ href, label, current: opts.current === s });
  const nav = [item("/lessons", "Lessons", "lessons"), item("/devices", "Devices", "devices"), item("/account", "Account", "account"),
    ...(isAdmin(c) ? [item("/admin", "Admin", "admin")] : [])];
  return shell({ title: `${title} · slide2video`, body, nav, home: "/lessons", refresh: opts.refresh, script: true, narrow: opts.narrow });
}

/** A public page (Terms, Privacy): no sign-in, no script. */
export function publicPage(title: string, body: Raw): string {
  return shell({ title: `${title} · slide2video`, body: html`<div class="prose">${body}</div>`, nav: [SIGN_IN], home: "/" });
}
```

Then, in `src/pages.ts`:
- every `layout(c, X, body, N)` with a number becomes `layout(c, X, body, { refresh: N, current: … })`; give each page
  its `current` (`"lessons"` for `/lessons`, `/lessons/new`, `/lessons/:id`; `"devices"`; `"account"`; `"admin"`);
- the list route `pages.get("/", …)` becomes `pages.get("/lessons", …)`, and add
  `pages.get("/", (c) => c.redirect("/lessons", 302));` (Task B9 replaces it with the landing page);
- every `href="/"` becomes `href="/lessons"` and `data-next="/"` becomes `data-next="/lessons"`.

`src/auth.ts`: import `{ shell, signInPage }` from `./ui`; replace `notInvited` and the 401 line:

```ts
const notInvited = (email: string) => shell({ title: "Not invited · slide2video", home: "/", nav: [],
  body: html`<div class="prose"><h1>Not invited yet</h1><p>${email} hasn't been invited yet. Ask the person who told you
about slide2video to invite this address.</p></div>` });
```

In `teacherAuth`: `if (!email) return c.req.path.startsWith("/api/") ? c.json({ error: "Your sign-in ran out. Reload the page to sign in again." }, 401) : c.html(signInPage(), 401);`
and `if (!t) return c.html(notInvited(email), 403);` (it returns a string now).

`src/index.ts`: move `app.get("/app.js", …)` above the `teacherAuth` line (it holds no data; signed-in pages must
load it on paths Access no longer covers).

- [ ] **Step 6: Run the gate**

Run: `npm run check && npm test`
Expected: PASS. Fix any remaining test that asserted the old header (`<strong>slide2video</strong>`) or the email in the
header by asserting the email on `/account` instead.

- [ ] **Step 7: Commit**

```bash
git add src test
git commit -m "slide2video: Study notebook stylesheet and page frame; lessons list at /lessons"
```

### Task B4: Lessons list (groups, cards, first visit) and per-lesson download

**Files:**
- Modify: `src/pages.ts` (`/lessons` route, `lessonState` adds `working` and selects `progress_fraction`; `Lesson`
  type adds `created_at`, `slides`), `src/export.ts` (`lessonZip`), `src/teacher-api.ts` (route)
- Test: `test/pages.test.ts`, `test/lessons.test.ts`

**Interfaces:**
- Consumes: `turns.progress_fraction` (B1), `layout`/classes (B3).
- Produces: `LessonState.working: boolean` (a running turn whose lease hasn't run out), `Turn.progress_fraction:
  number | null`; route `GET /api/lessons/:id/export` (zip of the newest version of each chapter's video, captions and
  picture); `lessonZip(c, lessonId)` in `src/export.ts`.

- [ ] **Step 1: Write the failing tests**

In `test/pages.test.ts` add:

```ts
/** The part of a page under one section label, up to the next section. */
const section = (page: string, label: string) => {
  const i = page.indexOf(`>${label}</h2>`);
  if (i < 0) return "";
  const j = page.indexOf("<section", i);
  return page.slice(i, j < 0 ? undefined : j);
};

describe("lessons list", () => {
  it("groups lessons: waiting for you, being made, finished", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const asked = await newLesson(t.email, { title: "Asked" });
    const q = await claim(mac.token);
    await finish(mac.token, q.turn.id, QUESTIONS);
    await newLesson(t.email, { title: "Queued" });
    const page = text(await get(t.email, "/lessons"));
    const you = section(page, "Waiting for you");
    expect(you).toContain(`href="/lessons/${asked}"`);
    expect(you).toContain("1 question to answer");
    expect(you).toContain("Answer them →");
    expect(section(page, "Being made")).toContain("Queued");
    expect(section(page, "Being made")).toContain("Waiting for your computer");
    expect(page).not.toContain(">Finished</h2>");
    expectSafe(await get(t.email, "/lessons"));
  });

  it("shows a progress bar while the computer reports a fraction", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    await newLesson(t.email);
    const turn = await claim(mac.token);
    await asDevice(mac.token, `/api/device/turns/${turn.turn.id}/heartbeat`, { method: "POST",
      body: JSON.stringify({ progress: "Narrating scenes", fraction: 0.4 }) });
    expect(await get(t.email, "/lessons")).toContain('<progress max="100" value="40"');
    await asDevice(mac.token, `/api/device/turns/${turn.turn.id}/heartbeat`, { method: "POST", body: JSON.stringify({ progress: "Rendering" }) });
    expect(await get(t.email, "/lessons")).not.toContain("<progress");
  });

  it("lists a finished lesson with its chapters and a Download all link", async () => {
    const { t, mac, id, turn } = await homed("Done lesson");
    await finish(mac.token, turn.turn.id, { contract: 1, kind: "done", message: "All done",
      chapters: [{ chapter: 1, title: "One" }, { chapter: 2, title: "Two" }] });
    const fin = section(text(await get(t.email, "/lessons")), "Finished");
    expect(fin).toContain("Done lesson");
    expect(fin).toContain("2 chapters");
    expect(fin).toContain(`href="/api/lessons/${id}/export"`);
  });

  it("shows the three-step start on a first visit, with step 1 done once a computer is connected", async () => {
    const t = await seedTeacher();
    let page = await get(t.email, "/lessons");
    expect(page).toContain("Your first lesson, in three steps");
    expect(page).toContain('href="/devices"');
    expect(page).not.toContain('<li class="done">');
    await pairDevice(t.email);
    page = await get(t.email, "/lessons");
    expect(page).toContain('<li class="done">');
  });

  it("shows one whole first character in the letter tile, whatever the title starts with", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    await newLesson(t.email, { title: "  🌊 Ocean currents" });
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, QUESTIONS);
    expect(await get(t.email, "/lessons")).toContain('aria-hidden="true">🌊</span>');
  });
});
```

In `test/lessons.test.ts` add (import `unzipSync` from `fflate`, plus `claim`, `pairDevice`, `upload` from helpers if
missing):

```ts
  it("downloads one lesson's newest chapter files as a zip, and only for its own teacher", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    const turn = await claim(mac.token);
    const bytes = (s: string) => new TextEncoder().encode(s);
    for (const p of ["out/ch1/v1/old.mp4", "out/ch1/v2/new.mp4", "out/ch1/v2/new.vtt", "out/ch1/v2/timing.json", "out/ch2/v1/two.mp4"]) {
      expect((await upload(mac.token, turn.turn.id, p, bytes(p))).status, p).toBe(201);
    }
    const r = await asTeacher(t.email, `/api/lessons/${id}/export`);
    expect(r.status).toBe(200);
    expect(r.headers.get("Content-Disposition")).toBe('attachment; filename="Water-Cycle.zip"');
    expect(Object.keys(unzipSync(new Uint8Array(await r.arrayBuffer()))).sort())
      .toEqual(["Chapter 1/new.mp4", "Chapter 1/new.vtt", "Chapter 2/two.mp4"]);
    const other = await seedTeacher();
    expect((await asTeacher(other.email, `/api/lessons/${id}/export`)).status).toBe(404);
  });
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/pages.test.ts test/lessons.test.ts`
Expected: FAIL (no sections, no export route).

- [ ] **Step 3: Implement the per-lesson zip** (`src/export.ts`, append; `teacher-api.ts` gets
  `teacherApi.get("/lessons/:id/export", (c) => lessonZip(c, c.req.param("id")));` and the import)

```ts
/** One lesson's newest version of each chapter (video, captions, picture) as a zip named after the lesson. */
export async function lessonZip(c: Context<AppEnv>, lessonId: string): Promise<Response> {
  const t = c.get("teacher");
  const db = c.env.DB;
  const lesson = await db.prepare("SELECT id, title FROM lessons WHERE id = ? AND teacher_id = ? AND deleted_at IS NULL")
    .bind(lessonId, t.id).first<{ id: string; title: string }>();
  if (!lesson) return c.json({ error: "not found" }, 404);
  const { results } = await db.prepare(
    "SELECT name, path, r2_key, created_at FROM files WHERE lesson_id = ? AND teacher_id = ? AND path LIKE 'out/ch%' ORDER BY path",
  ).bind(lesson.id, t.id).all<{ name: string; path: string; r2_key: string; created_at: number }>();
  const parsed = results.flatMap((f) => {
    const m = f.path.match(/^out\/ch(\d+)\/v(\d+)\//);
    return m ? [{ ...f, ch: Number(m[1]), v: Number(m[2]) }] : [];
  });
  const newest = new Map<number, number>();
  for (const f of parsed) newest.set(f.ch, Math.max(newest.get(f.ch) ?? 0, f.v));
  // timing.json is for the site's player, not for the class
  const files = parsed.filter((f) => f.v === newest.get(f.ch) && !f.name.toLowerCase().endsWith(".json"));
  const bucket = c.env.FILES;
  async function* entries() {
    for (const f of files) {
      const obj = await bucket.get(f.r2_key);
      if (!obj) continue;
      try {
        yield { name: `Chapter ${f.ch}/${f.name}`, input: obj.body, size: obj.size, lastModified: new Date(f.created_at * 1000) };
      } finally {
        if (!obj.bodyUsed) await obj.body.cancel().catch(() => {});
      }
    }
  }
  const zip = downloadZip(entries());
  await logEvent(db, t.id, "export", lesson.id);
  const base = lesson.title.normalize("NFKD").replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-").slice(0, 60) || "lesson";
  return new Response(zip.body, { headers: { "Content-Type": "application/zip", "Cache-Control": "private, no-store",
    "Content-Disposition": `attachment; filename="${base}.zip"` } });
}
```

- [ ] **Step 4: Implement the list** (`src/pages.ts`)

Types: `Lesson` gains `created_at: number; slides: number | null`; `Turn` gains `progress_fraction: number | null`;
`LessonState` gains `working: boolean`. In `lessonState`, select `progress_fraction` in the turn query, return
`working: false` from the tombstone branch, and add `working` to `base`:

```ts
  const stale = turn?.state === "running" && (turn.lease_until ?? 0) < now();
  const base = { revoked, deleteFailed: false, turn, card, working: turn?.state === "running" && !stale };
```

(move the `stale` line above `base`; keep every status string as it is.)

Add these helpers above the route and replace the `/lessons` route:

```ts
const EMPTY_ART = raw('<svg viewBox="0 0 220 150" aria-hidden="true" focusable="false"><rect x="10" y="30" width="90" height="64" rx="6" fill="#FBF8F1" stroke="#0B2545" stroke-width="3"/><path d="M24 50 h50 M24 64 h62 M24 78 h40" stroke="#CFC5B0" stroke-width="5" stroke-linecap="round"/><path d="M108 62 c14 -10 22 -10 34 0" fill="none" stroke="#C2412D" stroke-width="3" stroke-linecap="round" stroke-dasharray="6 6"/><path d="M138 54 l6 8 l-9 3" fill="none" stroke="#C2412D" stroke-width="3" stroke-linecap="round"/><rect x="120" y="70" width="92" height="62" rx="6" fill="#0F4C75"/><circle cx="192" cy="86" r="8" fill="#FFC145"/><path d="M158 90 L176 101 L158 112 Z" fill="#FFFFFF"/></svg>');

type Group = "you" | "making" | "finished";
const groupOf = (l: Lesson, s: LessonState): Group =>
  l.deleted_at || s.busy ? "making" : s.card?.kind === "done" ? "finished" : "you";
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const tint = (title: string) => [...title].reduce((a, ch) => a + ch.codePointAt(0)!, 0) % 6;

/** What a lesson waiting for the teacher says on the list: its pill and its call to action. */
function nextAction(s: LessonState): { pill: string; go: string } {
  if (s.revoked) return { pill: "Can't continue", go: "See why →" };
  if (!s.turn) return { pill: "Upload didn't finish", go: "See what to do →" };
  const b = s.card ? JSON.parse(s.card.body) : {};
  if (s.card?.kind === "questions") return { pill: `${plural((b.questions ?? []).length, "question")} to answer`, go: "Answer them →" };
  if (s.card?.kind === "plan") return { pill: "Plan ready to approve", go: "Review the plan →" };
  if (s.card?.kind === "review") return { pill: `Chapter ${b.chapter} ready to watch`, go: "Watch it →" };
  return { pill: "Something went wrong", go: "See what happened →" };
}

async function lessonCard(db: D1Database, l: Lesson, s: LessonState): Promise<Raw> {
  const still = await db.prepare(
    "SELECT path FROM files WHERE lesson_id = ? AND teacher_id = ? AND kind = 'stills' ORDER BY created_at DESC LIMIT 1",
  ).bind(l.id, l.teacher_id).first<{ path: string }>();
  const letter = [...l.title.trim()][0]?.toUpperCase() ?? "?";
  const thumb = still ? html`<img class="thumb" src="${fileUrl(l.id, still.path)}" alt="">`
    : html`<span class="thumb tint-${tint(l.title)}" aria-hidden="true">${letter}</span>`;
  const { pill, go } = nextAction(s);
  return html`<a class="lesson-card" href="/lessons/${l.id}">${thumb}<span class="body"><span class="name">${l.title}</span>
<span class="pill">${pill}</span><span class="go">${go}</span></span></a>`;
}

const progressBar = (s: LessonState) => s.working && s.turn?.progress_fraction != null
  ? html`<progress max="100" value="${Math.round(s.turn.progress_fraction * 100)}" aria-label="Progress of this step">${Math.round(s.turn.progress_fraction * 100)}%</progress>`
  : "";

function makingRow(l: Lesson, s: LessonState): Raw {
  const name = l.deleted_at ? html`<span class="name muted">Deleted lesson</span>` : html`<a class="name" href="/lessons/${l.id}">${l.title}</a>`;
  const retry = s.deleteFailed
    ? html`<form class="inline" data-api="POST /api/lessons/${l.id}/retry-delete" data-kind="none"><button>Try again</button></form>` : "";
  return html`<div class="item">${name}<span class="what"><span>${s.status}</span>${progressBar(s)}</span>${retry}</div>`;
}

function finishedRow(l: Lesson, s: LessonState): Raw {
  const b = JSON.parse(s.card!.body);
  const n = Array.isArray(b.chapters) ? b.chapters.length : 0;
  return html`<div class="item"><a class="name" href="/lessons/${l.id}">${l.title}</a>
<span class="what muted">${n ? `${plural(n, "chapter")} · ` : ""}finished ${when(s.card!.created_at)}</span>
<a href="/api/lessons/${l.id}/export" download>Download all</a></div>`;
}

const firstVisit = (hasDevice: boolean) => html`<section class="card empty">${EMPTY_ART}<div class="grow stack">
<h2>Your first lesson, in three steps</h2><ol class="numbered">
<li${hasDevice ? raw(' class="done"') : ""}><div><span><strong>Connect your home computer.</strong> It makes the videos with your own Claude account.</span>
${hasDevice ? html`<span class="muted small">Connected.</span>` : html`<a href="/devices">Go to Devices</a>`}</div></li>
<li><div><span><strong>Upload a slide deck</strong> (.pptx or .pdf), from any computer, including this one.</span><a href="/lessons/new">New lesson</a></div></li>
<li><div><span><strong>Answer a few questions, approve the plan, and watch each chapter</strong> as it's ready.</span></div></li>
</ol><p class="turn-note">No student names, photos or work in what you upload.</p></div></section>`;

pages.get("/lessons", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const { results } = await db.prepare("SELECT * FROM lessons WHERE teacher_id = ? ORDER BY updated_at DESC").bind(t.id).all<Lesson>();
  const you: Raw[] = [], making: Raw[] = [], finished: Raw[] = [];
  let busy = false;
  for (const l of results) {
    const s = await lessonState(db, l);
    busy ||= s.busy;
    const g = groupOf(l, s);
    if (g === "you") you.push(await lessonCard(db, l, s));
    else if (g === "making") making.push(makingRow(l, s));
    else finished.push(finishedRow(l, s));
  }
  const devices = (await db.prepare("SELECT COUNT(*) AS n FROM devices WHERE teacher_id = ? AND revoked_at IS NULL")
    .bind(t.id).first<{ n: number }>())?.n ?? 0;
  const group = (cls: string, label: string, inner: Raw) => html`<section class="stack"><h2 class="label ${cls}">${label}</h2>${inner}</section>`;
  const body = html`<div class="row between"><h1>Lessons</h1><a class="button primary" href="/lessons/new">New lesson</a></div>
${results.length ? "" : firstVisit(devices > 0)}
${you.length ? group("you", "Waiting for you", html`<div class="lesson-cards">${you}</div>`) : ""}
${making.length ? group("making", "Being made", html`<div class="rows">${making}</div>`) : ""}
${finished.length ? group("", "Finished", html`<div class="rows">${finished}</div>`) : ""}`;
  return c.html(layout(c, "Lessons", body, { refresh: busy ? 30 : 0, current: "lessons" }));
});
```

`fileUrl` and `when` are module-level `const`s; move `fileUrl` above these helpers if TypeScript reports it is used
before its declaration.

- [ ] **Step 5: Run the gate**

Run: `npm run check && npm test`
Expected: PASS. Older list assertions that looked for a `<table>` row or `Lesson`/`Status` headers change to the
section helpers above; keep their intent (escaping, isolation, tombstones, Try again).

- [ ] **Step 6: Commit**

```bash
git add src test
git commit -m "slide2video: lessons list grouped by whose turn it is; first-visit steps; per-lesson Download all"
```

### Task B5: New lesson page and the script's helpers

**Files:**
- Modify: `src/pages.ts` (`/lessons/new`; export `ago` is already module-level), `src/client.ts` (`APP_JS` additions)
- Test: `test/pages.test.ts`

**Interfaces:**
- Consumes: classes `.drop`, `.file-row`, `.aside`, `ol.numbered`, `label.check`, `.notice.sun` (B3).
- Produces: in `APP_JS`, drop-zone highlighting, deck row and title fill (`[data-drop]`, `[data-file-row]`,
  `[data-title-hint]`, `[data-extra-list]`), copy buttons (`button[data-copy]`, used by B8), focusing an "Other" box
  (`input[data-other]`, used by B7).

- [ ] **Step 1: Write the failing test**

```ts
describe("new lesson page", () => {
  it("has the drop zones, the confirmation and what happens next, naming the home computer", async () => {
    const t = await seedTeacher();
    let page = await get(t.email, "/lessons/new");
    expect(page).toContain('<label class="drop" data-drop>');
    expect(page).toContain('name="deck" accept=".pptx,.pdf" required');
    expect(page).toContain('name="extra" multiple');
    expect(page).toContain('name="attest" required');
    expect(page).toContain("What happens next");
    expect(page).toContain("No computer connected yet.");
    await pairDevice(t.email, "Home iMac");
    page = await get(t.email, "/lessons/new");
    expect(page).toContain("Home computer: <strong>Home iMac</strong>");
    expectSafe(page);
  });
});
```

- [ ] **Step 2: Run it to see it fail**

Run: `npx vitest run test/pages.test.ts -t "new lesson page"`
Expected: FAIL.

- [ ] **Step 3: Implement the page** (replace the `/lessons/new` route)

```ts
const UPLOAD_ART = raw('<svg class="art small" viewBox="0 0 64 54" aria-hidden="true" focusable="false"><rect x="4" y="10" width="44" height="32" rx="5" fill="#E8F7F5" stroke="#137F7A" stroke-width="3"/><path d="M44 30 v-22 M36 16 l8 -8 l8 8" fill="none" stroke="#C2412D" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>');

pages.get("/lessons/new", async (c) => {
  const t = c.get("teacher");
  const d = await c.env.DB.prepare(
    "SELECT name, last_seen FROM devices WHERE teacher_id = ? AND revoked_at IS NULL ORDER BY last_seen DESC LIMIT 1",
  ).bind(t.id).first<{ name: string; last_seen: number | null }>();
  const body = html`<div class="title"><a class="back" href="/lessons">← All lessons</a><h1>New lesson</h1></div>
<div class="split"><form class="main stack" data-api="POST /api/lessons" data-kind="new-lesson" data-next="/lessons/:id">
<label class="drop" data-drop>${UPLOAD_ART}<strong>Drop your slide deck here</strong>
<span>or <span class="pick">choose a file</span> · PowerPoint (.pptx) or PDF · up to 100 MB</span>
<input type="file" name="deck" accept=".pptx,.pdf" required aria-label="Slide deck (.pptx or .pdf)"></label>
<div class="file-row" data-file-row hidden></div>
<label>Title <input name="title" required maxlength="200" autocomplete="off">
<span class="hint" data-title-hint hidden>Taken from the deck. Change it if you like.</span></label>
<label class="drop small" data-drop><span>Other files <span class="hint">(optional)</span>: worksheets, review sheets or
pictures (.pdf, .docx, .png, .jpg). Drop them here or <span class="pick">choose files</span></span>
<input type="file" name="extra" multiple accept=".pptx,.pdf,.docx,.png,.jpg,.jpeg" aria-label="Other files (optional)"></label>
<p class="small muted" data-extra-list hidden></p>
<label>Notes for Claude <span class="hint">(optional)</span>
<textarea name="instructions" maxlength="4000" rows="3" placeholder="For example: grade 10, keep each chapter short, end each one with a quick quiz."></textarea></label>
<label class="check notice sun"><input type="checkbox" name="attest" required><span><strong>These files contain no student
information</strong>: no student names, photos of students, student work or grades.</span></label>
<div class="actions"><button class="primary">Upload and start</button><a href="/lessons">Cancel</a></div></form>
<aside class="side aside"><h2>What happens next</h2><ol class="numbered">
<li><div>Your home computer picks up the deck the next time it checks in.</div></li>
<li><div>Claude reads it and asks you a few questions here: grade, length, voice.</div></li>
<li><div>You approve a plan with its cost, then watch each chapter as it's made.</div></li></ol>
${d ? html`<p class="small">Home computer: <strong>${d.name}</strong>, last seen ${ago(d.last_seen)}.</p>`
    : html`<p class="small"><strong>No computer connected yet.</strong> The lesson waits until you <a href="/devices">connect one</a>.</p>`}
</aside></div>`;
  return c.html(layout(c, "New lesson", body, { current: "lessons" }));
});
```

- [ ] **Step 4: Add to `APP_JS`** (append before the closing backtick)

```js
// New lesson: light up a drop zone while a file is over it, show the chosen deck, fill the title from its name
function fmtSize(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1e3)) + " KB"; }
for (const zone of document.querySelectorAll("[data-drop]")) {
  const input = zone.querySelector("input[type=file]");
  if (!input) continue;
  for (const ev of ["dragenter", "dragover"]) zone.addEventListener(ev, () => zone.classList.add("over"));
  for (const ev of ["dragleave", "drop"]) zone.addEventListener(ev, () => zone.classList.remove("over"));
  input.addEventListener("change", () => {
    const form = input.form;
    if (input.name === "deck") {
      const f = input.files[0], row = form.querySelector("[data-file-row]");
      if (!row) return;
      row.textContent = "";
      row.hidden = !f;
      if (!f) return;
      const what = document.createElement("span"); what.className = "what";
      const name = document.createElement("strong"); name.textContent = f.name;
      const size = document.createElement("span"); size.className = "small muted"; size.textContent = fmtSize(f.size) + " · ready";
      what.append(name, size); row.append(what);
      const title = form.elements.title;
      if (title && !title.value.trim()) {
        title.value = f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
        const hint = form.querySelector("[data-title-hint]");
        if (hint) hint.hidden = false;
      }
    } else {
      const list = form.querySelector("[data-extra-list]");
      if (list) { list.textContent = Array.from(input.files, (f) => f.name).join(", "); list.hidden = !input.files.length; }
    }
  });
}
// a Copy button copies the text of the element it names (shown only when this script runs)
for (const b of document.querySelectorAll("button[data-copy]")) {
  b.hidden = false;
  b.addEventListener("click", async () => {
    const src = document.querySelector(b.dataset.copy);
    if (!src) return;
    try { await navigator.clipboard.writeText(src.textContent.trim()); b.textContent = "Copied"; }
    catch { const r = document.createRange(); r.selectNodeContents(src); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); b.textContent = "Selected: copy it"; }
    setTimeout(() => { b.textContent = "Copy"; }, 2500);
  });
}
// choosing "Something else" puts the cursor in its box
document.addEventListener("change", (ev) => {
  const el = ev.target;
  if (!(el instanceof HTMLInputElement) || !el.hasAttribute("data-other") || !el.checked) return;
  const fs = el.closest("fieldset");
  const own = fs && fs.querySelector("input[data-own]");
  if (own) own.focus();
});
```

- [ ] **Step 5: Run the gate, and check the script parses**

Run: `npm run check && npm test`
Then: `node --experimental-strip-types -e "import('./src/client.ts').then((m) => { new Function(m.APP_JS); console.log('APP_JS parses') })"`
Expected: PASS, then "APP_JS parses" (the Workers test runtime can't compile strings, so Node checks the script).

- [ ] **Step 6: Commit**

```bash
git add src test
git commit -m "slide2video: new lesson page with drop zones, title from the deck, and what happens next"
```

### Task B6: Lesson page: header, step line, status panel, earlier steps

**Files:**
- Create: `src/steps.ts`
- Modify: `src/pages.ts` (`/lessons/:id`)
- Test: `test/steps.test.ts` (new), `test/pages.test.ts`

**Interfaces:**
- Consumes: `LessonState.working`, `Turn.progress_fraction`, `progressBar(s)` (B4), `lessons.slides` (B1).
- Produces: `lessonSteps(cards: { kind: string; body: string }[], turn: { kind: string; state: string } | null):
  { label: string; state: "done" | "now" | "todo" }[]` (cards newest first); `stepLine(steps): Raw` in `src/steps.ts`.

- [ ] **Step 1: Write the failing unit tests**

`test/steps.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { lessonSteps } from "../src/steps";

const card = (kind: string, body: object = {}) => ({ kind, body: JSON.stringify(body) });
const plan = (chapters: unknown) => card("plan", { estimate: { usd: 0, minutes: 3, chapters } });
const view = (cards: ReturnType<typeof card>[], turn: { kind: string; state: string } | null) =>
  lessonSteps(cards, turn).map((s) => `${s.label}:${s.state}`).join(" ");

describe("lessonSteps", () => {
  it("starts on Questions while the computer reads the deck, with one Chapters step before a plan", () => {
    expect(view([], { kind: "start", state: "running" }))
      .toBe("Uploaded:done Questions:now Plan:todo Chapters:todo Done:todo");
  });
  it("stays on Questions while they wait for answers", () => {
    expect(view([card("questions")], { kind: "start", state: "done" }))
      .toBe("Uploaded:done Questions:now Plan:todo Chapters:todo Done:todo");
  });
  it("lists the plan's chapters and marks the plan current", () => {
    expect(view([plan(3), card("questions")], { kind: "answer", state: "done" }))
      .toBe("Uploaded:done Questions:done Plan:now Chapter 1:todo Chapter 2:todo Chapter 3:todo Done:todo");
  });
  it("follows the newest plan after a change", () => {
    expect(view([plan(2), plan(3)], { kind: "change", state: "done" }))
      .toBe("Uploaded:done Questions:done Plan:now Chapter 1:todo Chapter 2:todo Done:todo");
  });
  it("marks the chapter under review, and the next one while it is made", () => {
    const cards = [card("review", { chapter: 2 }), card("review", { chapter: 1 }), plan(3)];
    expect(view(cards, { kind: "feedback", state: "done" })).toContain("Chapter 1:done Chapter 2:now Chapter 3:todo");
    expect(view(cards, { kind: "continue", state: "queued" })).toContain("Chapter 2:done Chapter 3:now Done:todo");
  });
  it("moves to Done while the last chapter is being finished, and shows everything done at the end", () => {
    const cards = [card("review", { chapter: 2 }), plan(2)];
    expect(view(cards, { kind: "continue", state: "running" })).toBe(
      "Uploaded:done Questions:done Plan:done Chapter 1:done Chapter 2:done Done:now");
    expect(view([card("done"), ...cards], { kind: "continue", state: "done" })).toBe(
      "Uploaded:done Questions:done Plan:done Chapter 1:done Chapter 2:done Done:done");
  });
  it("ignores an error card when placing the lesson", () => {
    expect(view([card("error"), card("review", { chapter: 1 }), plan(2)], { kind: "continue", state: "failed" }))
      .toContain("Chapter 1:now");
  });
  it("never shows zero or hundreds of chapter steps", () => {
    for (const n of [0, -1, "3", null]) expect(view([plan(n)], null)).toContain("Chapters:todo");
    expect(lessonSteps([plan(500)], null).filter((s) => s.label.startsWith("Chapter ")).length).toBe(20);
  });
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/steps.test.ts`
Expected: FAIL ("Cannot find module '../src/steps'").

- [ ] **Step 3: Write `src/steps.ts`**

```ts
import { html, raw, type Raw } from "./http";

export type Step = { label: string; state: "done" | "now" | "todo" };
type CardLite = { kind: string; body: string };
type TurnLite = { kind: string; state: string } | null;
const MAX_CHAPTERS = 20;

/** Where a lesson is, as the step line shows it: Uploaded, Questions, Plan, Chapter 1…N (one "Chapters" step
 * before a plan exists), Done. `cards` newest first; `turn` is the lesson's latest turn. */
export function lessonSteps(cards: CardLite[], turn: TurnLite): Step[] {
  const bodies = cards.map((c) => ({ kind: c.kind, b: JSON.parse(c.body) as Record<string, any> }));
  const chapters = bodies.find((c) => c.kind === "plan")?.b.estimate?.chapters;
  const n = Number.isInteger(chapters) && chapters > 0 ? Math.min(chapters, MAX_CHAPTERS) : 0;
  const labels = ["Uploaded", "Questions", "Plan", ...(n ? Array.from({ length: n }, (_, i) => `Chapter ${i + 1}`) : ["Chapters"]), "Done"];
  const done = labels.length - 1;
  const chapterAt = (k: number) => (n ? 2 + Math.min(Math.max(k, 1), n) : 3);
  const reviewed = Number(bodies.find((c) => c.kind === "review")?.b.chapter) || 0;

  const fromCards = (): number => {
    const c = bodies.find((x) => x.kind !== "error");
    if (!c || c.kind === "questions") return 1;
    if (c.kind === "plan") return 2;
    if (c.kind === "review") return chapterAt(Number(c.b.chapter) || 1);
    return done;
  };
  let at: number;
  if (bodies[0]?.kind === "done") at = done + 1; // all done, nothing current
  else if (turn && (turn.state === "queued" || turn.state === "running")) {
    const next: Record<string, number> = {
      start: 1, answer: 2, change: 2, approve: chapterAt(1), feedback: chapterAt(reviewed),
      continue: n && reviewed >= n ? done : chapterAt(reviewed + 1),
    };
    at = next[turn.kind] ?? fromCards();
  } else at = fromCards();
  return labels.map((label, i) => ({ label, state: i < at ? "done" : i === at ? "now" : "todo" }));
}

export const stepLine = (steps: Step[]): Raw => html`<div class="steps-line"><ol aria-label="Progress">${steps.map((s) =>
  html`<li class="${s.state}"${s.state === "now" ? raw(' aria-current="step"') : ""}><span class="dot" aria-hidden="true"></span>${s.label}<span class="sr-only">${s.state === "done" ? " (done)" : s.state === "now" ? " (current)" : ""}</span></li>`)}</ol></div>`;
```

- [ ] **Step 4: Run the unit tests**

Run: `npx vitest run test/steps.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing page tests** (in `test/pages.test.ts`)

```ts
describe("lesson page", () => {
  it("shows the file, the slide count once known, the step line and a working panel with a bar", async () => {
    const { t, mac, id, turn } = await homed("Water Cycle");
    let page = await get(t.email, `/lessons/${id}`);
    expect(page).toContain("water-cycle.pptx");
    expect(page).not.toContain(" slides");
    expect(page).toContain('<li class="now" aria-current="step">');
    expect(page).toContain("<h2>Your computer is working</h2>");
    await asDevice(mac.token, `/api/device/turns/${turn.turn.id}/heartbeat`, { method: "POST",
      body: JSON.stringify({ progress: "Reading the deck", fraction: 0.5 }) });
    page = await get(t.email, `/lessons/${id}`);
    expect(page).toContain('<progress max="100" value="50"');
    await finish(mac.token, turn.turn.id, { ...QUESTIONS, slides: 9 });
    page = await get(t.email, `/lessons/${id}`);
    expect(page).toContain("9 slides");
    expectSafe(page);
  });

  it("shows a waiting panel with the computer's last check-in and how to run it", async () => {
    const t = await seedTeacher();
    await pairDevice(t.email);
    const id = await newLesson(t.email);
    const page = text(await get(t.email, `/lessons/${id}`));
    expect(page).toContain("<h2>Waiting for your computer</h2>");
    expect(page).toContain("On that computer, run the line from setup in Terminal.");
  });

  it("puts answered steps under Earlier steps, collapsed", async () => {
    const { t, mac, id, turn } = await homed();
    await finish(mac.token, turn.turn.id, QUESTIONS);
    await post(t.email, `/api/lessons/${id}/answer`, { answers: [{ question: "grade", choice: "Grades 6–8", other: null }] });
    const next = await claim(mac.token);
    await finish(mac.token, next.turn.id, PLAN);
    const page = await get(t.email, `/lessons/${id}`);
    expect(page).toContain(">Earlier steps</h2>");
    expect(page).toContain('<details class="past"><summary>Questions');
  });
});
```

- [ ] **Step 6: Run them to see them fail**

Run: `npx vitest run test/pages.test.ts -t "lesson page"`
Expected: FAIL.

- [ ] **Step 7: Implement** (replace the `/lessons/:id` route body in `src/pages.ts`; import `lessonSteps, stepLine`
  from `./steps`)

```ts
const COMPUTER_ART = raw('<svg class="art small" viewBox="0 0 56 56" aria-hidden="true" focusable="false"><rect x="6" y="10" width="44" height="30" rx="4" fill="none" stroke="currentColor" stroke-width="3"/><path d="M20 48 h16 M28 40 v8" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="28" cy="25" r="6" fill="#FFC145"/></svg>');
const GUIDE = "https://github.com/DanielLandi/plugins/blob/main/lesson-videos/docs/install/slide2video.md";

/** One line naming an earlier card, for its collapsed summary. */
function pastLabel(cd: CardRow): string {
  const b = JSON.parse(cd.body);
  if (cd.kind === "questions") return `Questions · ${plural((b.questions ?? []).length, "question")}`;
  if (cd.kind === "plan") return `Plan · ${plural(Number(b.estimate?.chapters) || 0, "chapter")} · $${Number(b.estimate?.usd ?? 0).toFixed(2)}`;
  if (cd.kind === "review") return `Chapter ${b.chapter}${b.version ? ` · version ${b.version}` : ""}`;
  if (cd.kind === "done") return "Finished";
  return "Something went wrong";
}

pages.get("/lessons/:id", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const lesson = await db.prepare("SELECT * FROM lessons WHERE id = ? AND teacher_id = ? AND deleted_at IS NULL")
    .bind(c.req.param("id"), t.id).first<Lesson>();
  if (!lesson) return c.html(layout(c, "Not found", html`<h1>Not found</h1><p><a href="/lessons">Back to your lessons</a></p>`,
    { current: "lessons" }), 404);
  const s = await lessonState(db, lesson);
  const { results: cards } = await db.prepare("SELECT * FROM cards WHERE lesson_id = ? AND teacher_id = ? ORDER BY created_at DESC, rowid DESC")
    .bind(lesson.id, t.id).all<CardRow>();
  const { results: files } = await db.prepare(
    "SELECT name, path, kind FROM files WHERE lesson_id = ? AND teacher_id = ? AND (path LIKE 'in/%' OR kind = 'video') ORDER BY path",
  ).bind(lesson.id, t.id).all<{ name: string; path: string; kind: string }>();
  const inputs = files.filter((f) => f.path.startsWith("in/"));
  const videos = latestVideos(files.filter((f) => f.kind === "video"));
  const ctx = (open: boolean): CardCtx => ({ lessonId: lesson.id, open, turn: s.turn, videos });
  const paused = s.turn?.state === "queued" && !!s.turn.not_before && s.turn.not_before > now();
  const [current] = cards;
  // the newest card leads the page unless the computer is busy with what comes after it (then a panel does)
  const cardLeads = !!current && !s.revoked && (!s.busy || paused);
  const open = cardLeads && !s.busy && !current.answered_at;
  let lead: Raw;
  if (s.revoked) lead = html`<section class="card"><h2>This lesson can't continue</h2><p>${REVOKED}</p></section>`;
  else if (cardLeads) lead = cardView(current, ctx(open));
  else if (s.working) lead = html`<section class="card"><h2>Your computer is working</h2>
${s.turn?.progress ? html`<p>${s.turn.progress}</p>` : ""}${progressBar(s)}
<p class="muted small">You can close this page; it shows up here when it's ready.</p></section>`;
  else if (s.busy) lead = html`<section class="card"><div class="row">${COMPUTER_ART}<div class="grow stack">
<h2>Waiting for your computer</h2><p>${s.status}</p><p class="turn-note">On that computer, run the line from setup in Terminal.</p>
<a href="${GUIDE}" rel="noopener noreferrer">How to connect a computer</a></div></div></section>`;
  else lead = html`<section class="card"><p>${s.status}</p></section>`;
  const older = cardLeads ? cards.slice(1) : cards;
  const deck = inputs.find((f) => f.kind === "deck");
  const plan = cards.find((cd) => cd.kind === "plan");
  const chapters = plan ? Number(JSON.parse(plan.body).estimate?.chapters) || 0 : 0;
  const meta: Raw[] = [];
  if (deck) meta.push(html`${deck.name}`);
  if (lesson.slides) meta.push(html`${plural(lesson.slides, "slide")}`);
  if (chapters) meta.push(html`${plural(chapters, "chapter")}`);
  meta.push(html`started ${when(lesson.created_at)}`);
  const body = html`<div class="title"><a class="back" href="/lessons">← All lessons</a><h1>${lesson.title}</h1>
<p class="meta">${meta.map((m, i) => (i ? html` · ${m}` : m))}</p></div>
${stepLine(lessonSteps(cards, s.turn))}
${lead}
${older.length ? html`<section class="stack"><h2 class="label">Earlier steps</h2><div class="past-list">${older.map((cd) =>
    html`<details class="past"><summary>${pastLabel(cd)}</summary>${cardView(cd, ctx(false))}</details>`)}</div></section>` : ""}
<details><summary>Your files and notes for Claude</summary><div class="stack">
${inputs.length ? html`<ul>${inputs.map((f) => html`<li><a href="${fileUrl(lesson.id, f.path)}" download>${f.name}</a></li>`)}</ul>`
    : html`<p class="muted">No files.</p>`}
${lesson.instructions ? html`<h3>Notes for Claude</h3><p>${lesson.instructions}</p>` : ""}</div></details>
<form data-api="DELETE /api/lessons/${lesson.id}" data-kind="none" data-next="/lessons"
 data-confirm="Delete this lesson? It's removed from the website now and from your computer when it next checks in.">
<button class="danger">Delete this lesson</button></form>`;
  return c.html(layout(c, lesson.title, body, { refresh: s.busy ? (paused ? 60 : 15) : 0, current: "lessons" }));
});
```

`plural` was added in Task B4; keep one definition.

- [ ] **Step 8: Run the gate**

Run: `npm run check && npm test`
Expected: PASS. Earlier tests that asserted `<p class="status">…</p>` or the "Earlier steps (N)" summary now find the
same status text inside the panel or the past-card summaries; update them to the new markup without dropping what
they check (status texts, escaping, isolation).

- [ ] **Step 9: Commit**

```bash
git add src test
git commit -m "slide2video: lesson page with step line, status panel and earlier steps"
```

### Task B7: The cards: questions, plan, review, done, error

**Files:**
- Modify: `src/pages.ts` (`cardView`)
- Test: `test/pages.test.ts`

**Interfaces:**
- Consumes: `estimate.items`, option `recommended`, question ids `students`/`issue…` (Part A), classes (B3),
  `plural` (B4).

- [ ] **Step 1: Write the failing tests**

```ts
describe("cards", () => {
  async function asked(card: object) {
    const { t, mac, id, turn } = await homed();
    expect((await finish(mac.token, turn.turn.id, card)).status).toBe(204);
    return { t, id, page: await get(t.email, `/lessons/${id}`) };
  }

  it("shows Claude's suggestion on the first recommended option only, preselecting nothing", async () => {
    const { page } = await asked({ contract: 1, kind: "questions", message: "Q", questions: [{ id: "grade", text: "Grade?",
      options: [{ label: "9", recommended: true }, { label: "10", recommended: true }] }] });
    expect(page.match(/Claude suggests this/g)?.length).toBe(1);
    expect(page).not.toContain("checked");
    expect(page).toContain("Claude read your deck and has 1 question");
  });

  it("sets apart student-information and possible-issue questions", async () => {
    const { page } = await asked({ contract: 1, kind: "questions", message: "Q", questions: [
      { id: "issue-1", text: "Slide 7?", options: [{ label: "Redraw" }] },
      { id: "voice", text: "Voice?", options: [{ label: "Ava" }] }] });
    expect(page).toContain('<fieldset data-q="issue-1" class="issue">');
    expect(page).toContain('<fieldset data-q="voice">');
  });

  it("lists the plan's cost items, or only the total when there are none", async () => {
    const withItems = await asked({ ...PLAN, estimate: { usd: 0.84, minutes: 3, chapters: 3, items: [
      { label: "Narration (free voice)", usd: 0 }, { label: "Background music", usd: 0.24 }, { label: "2 short animated clips", usd: 0.6, detail: "8 seconds each" }] } });
    expect(withItems.page).toContain("<dt>Background music</dt><dd>$0.24</dd>");
    expect(withItems.page).toContain("<dd>free</dd>");
    expect(withItems.page).toContain('<span class="detail">8 seconds each</span>');
    expect(withItems.page).toContain('<p class="total">$0.84</p>');
    expect(withItems.page).toContain("Approve and start");
    const plain = await asked(PLAN);
    expect(plain.page).not.toContain("<dl>");
    expect(plain.page).toContain('<p class="total">$0.00</p>');
  });
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/pages.test.ts -t "cards"`
Expected: FAIL.

- [ ] **Step 3: Implement** (replace the bodies of `cardView`'s branches; keep `msg`, `id`, `fileUrl`, `mdLite`)

```ts
function cardView(card: CardRow, x: CardCtx): Raw {
  const b = JSON.parse(card.body);
  const msg = b.message ? html`<p>${b.message}</p>` : "";
  const id = x.lessonId;
  if (card.kind === "questions") {
    const qs = b.questions as any[];
    if (!x.open) return html`<div class="card"><h2>Questions</h2>${msg}<ul>${qs.map((q) => html`<li>${q.text}</li>`)}</ul></div>`;
    const fields = qs.map((q, i) => {
      const options = q.options as any[];
      const suggested = options.findIndex((o) => o.recommended === true);
      const issue = q.id === "students" || /^issue/.test(q.id);
      return html`<fieldset data-q="${q.id}"${issue ? raw(' class="issue"') : ""}><legend>${i + 1}. ${q.text}</legend><div class="choices">
${options.map((o, k) => html`<label class="choice"><input type="radio" name="q:${q.id}" value="${o.label}" required><span><strong>${o.label}</strong>${k === suggested ? html`<span class="tag">Claude suggests this</span>` : ""}${o.detail ? html`<span class="detail">${o.detail}</span>` : ""}</span></label>`)}
${q.other ? html`<label class="choice"><input type="radio" name="q:${q.id}" value="" required data-other><span><strong>Something else</strong><span class="detail">Type your own answer below.</span></span></label>` : ""}</div>
${q.other ? html`<input class="own" name="o:${q.id}" data-own maxlength="2000" aria-label="Your own answer to: ${q.text}" placeholder="Your own answer">` : ""}</fieldset>`;
    });
    return html`<div class="card"><p class="turn-note">Your turn: answer Claude's questions.</p>
<h2>Claude read your deck and has ${plural(qs.length, "question")}</h2>${msg}
<form class="stack" data-api="POST /api/lessons/${id}/answer" data-kind="answers">${fields}
<div class="actions"><button class="primary">Send answers</button><span class="muted small">Your computer writes the plan next. You can close this page meanwhile.</span></div></form></div>`;
  }
  if (card.kind === "plan") {
    const e = b.estimate;
    const items = Array.isArray(e.items) ? (e.items as any[]).slice(0, 8) : [];
    const money = (n: number) => (Number(n) === 0 ? "free" : `$${Number(n).toFixed(2)}`);
    const cost = html`<aside class="cost side"><h2>Estimated cost</h2><p class="total">$${Number(e.usd).toFixed(2)}</p>
${items.length ? html`<dl>${items.map((it) => html`<dt>${it.label}${it.detail ? html`<span class="detail">${it.detail}</span>` : ""}</dt><dd>${money(it.usd)}</dd>`)}</dl>` : ""}
<p class="small muted">Paid to the services on your own accounts. Claude's work is covered by your Claude plan.</p>
${x.open ? html`<form class="stack" data-api="POST /api/lessons/${id}/change">
<button class="primary" data-api="POST /api/lessons/${id}/approve" data-kind="none" formnovalidate>Approve and start</button>
<details><summary>Ask for changes</summary><div class="stack"><label>What should change?
<textarea name="feedback" rows="3" maxlength="4000" required placeholder="For example: no music, and two chapters instead of three."></textarea></label>
<button>Send changes</button></div></details></form>` : ""}</aside>`;
    return html`<div class="split"><section class="card main">${x.open ? html`<p class="turn-note">Your turn: approve the plan or ask for changes.</p>` : ""}
<h2>The plan: ${plural(Number(e.chapters), "chapter")}, about ${e.minutes} minutes each</h2>${msg}
<div class="plan-text">${mdLite(b.markdown)}</div>
<p class="muted">Every chapter gets captions and a picture for your slides.</p></section>${cost}</div>`;
  }
  if (card.kind === "review") {
    const downloads: Raw[] = [html`<a href="${fileUrl(id, b.video)}" download>Download video (MP4)</a>`];
    if (b.captions) downloads.push(html`<a href="${fileUrl(id, b.captions)}" download>Captions (.vtt)</a>`);
    if (b.stills) downloads.push(html`<a href="${fileUrl(id, b.stills)}" download>Picture for your slides</a>`);
    const resolved = Array.isArray(b.resolved) && b.resolved.length
      ? html`<h3>Your notes</h3><ul>${(b.resolved as any[]).map((r) => html`<li><strong>${r.note}</strong>: ${r.answer}</li>`)}</ul>` : "";
    return html`<div class="card"><div class="card-head"><h2>Chapter ${b.chapter}</h2>${b.version ? html`<span class="pill making">version ${b.version}</span>` : ""}</div>${msg}
<div class="split"><div class="main stack"><div class="video"><video controls preload="metadata" src="${fileUrl(id, b.video)}">${b.captions
      ? html`<track kind="captions" src="${fileUrl(id, b.captions)}" srclang="en" label="Captions" default>` : ""}</video></div>${resolved}</div>
<div class="side stack">${x.open ? html`<p class="turn-note">Your turn: watch it, then say if it's ready.</p>
<form class="stack" data-api="POST /api/lessons/${id}/feedback">
<button class="primary" data-api="POST /api/lessons/${id}/continue" data-kind="none" formnovalidate>Looks good, continue</button>
<details><summary>Suggest a change</summary><div class="stack"><label>What would you change?
<textarea name="feedback" rows="3" maxlength="4000" required></textarea></label><button>Send feedback</button></div></details></form>` : ""}
${b.cost_next ? html`<p class="small muted">Continuing makes chapter ${Number(b.chapter) + 1}: about $${Number(b.cost_next.usd).toFixed(2)}.</p>` : ""}
<div class="downloads">${downloads}</div></div></div></div>`;
  }
  if (card.kind === "error") {
    // the computer re-queued this card's turn for later (a plan limit): say when, and offer no Try again
    const waiting = !!x.turn && x.turn.id === card.turn_id && x.turn.state === "queued" && !!x.turn.not_before;
    const later = waiting
      ? html`<p>${x.turn!.not_before! > now() ? html`It continues by itself at ${when(x.turn!.not_before!)}.`
        : "It continues by itself as soon as your computer checks in."}</p>` : "";
    return html`<div class="card"><h2>${waiting || b.retry_after ? "Paused" : "Something went wrong"}</h2><p class="error">${b.message}</p>${later}
${b.log_tail ? html`<details><summary>Details</summary><pre>${b.log_tail}</pre></details>` : ""}
${x.open && !waiting ? html`<form data-api="POST /api/lessons/${id}/retry" data-kind="none"><button class="primary">Try again</button></form>` : ""}</div>`;
  }
  // done
  const chapters = Array.isArray(b.chapters) && b.chapters.length
    ? html`<ul class="list">${(b.chapters as any[]).map((ch) => html`<li>Chapter ${ch.chapter}: ${ch.title}</li>`)}</ul>` : "";
  const videos = x.videos.length
    ? html`<div class="downloads">${x.videos.map((v) => html`<a href="${fileUrl(id, v.path)}" download>${v.name} <span class="muted">(chapter ${v.chapter}, version ${v.version})</span></a>`)}</div>` : "";
  return html`<div class="card"><h2>Finished</h2>${msg}${chapters}${videos}
<p><a class="button primary" href="/api/lessons/${id}/export" download>Download all</a></p>
${b.readme ? html`<details><summary>Notes from Claude</summary><div class="plan-text">${mdLite(b.readme)}</div></details>` : ""}</div>`;
}
```

- [ ] **Step 4: Run the gate**

Run: `npm run check && npm test`
Expected: PASS. Update older assertions on the old card markup (`<h2>Done</h2>` → `<h2>Finished</h2>`, the review
heading's `<span class="muted">version`, `Other:` → `Something else`, the inline picture `<img>` now a download link)
and keep what each test checks (escaping, mdLite, error/paused texts).

- [ ] **Step 5: Commit**

```bash
git add src test
git commit -m "slide2video: new question, plan, review and finished cards (suggested answers, cost items)"
```

### Task B8: Devices, Account and Admin

**Files:**
- Modify: `src/pages.ts` (`/devices`, `/account`, `/admin`)
- Test: `test/pages.test.ts`, `test/admin.test.ts`

**Interfaces:**
- Consumes: `button[data-copy]` (B5), `COMPUTER_ART`, `GUIDE`, `plural` (B4/B6), classes (B3).

- [ ] **Step 1: Write the failing tests**

```ts
describe("devices and account", () => {
  it("lists devices with what they're making, and the four steps with the code box", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email, "Home iMac");
    await newLesson(t.email);
    await claim(mac.token);
    const page = await get(t.email, "/devices");
    expect(page).toContain("Home iMac");
    expect(page).toContain("making 1 lesson");
    expect(page).toContain('<pre class="code grow" id="plugin-lines">');
    expect(page).toContain('<button type="button" class="link" data-copy="#plugin-lines" hidden>Copy</button>');
    expect(page).toContain('class="code-box" name="user_code"');
    expect(page).toContain("Only type a code that your own computer is showing right now.");
    expectSafe(page);
  });

  it("shows the account's totals, the email and a separate delete section", async () => {
    const t = await seedTeacher();
    await pairDevice(t.email);
    await newLesson(t.email);
    const page = await get(t.email, "/account");
    expect(page).toContain(`Signed in as <strong>${t.email}</strong>`);
    expect(page).toContain("1 lesson · ");
    expect(page).toContain(" · 1 device");
    expect(page).toContain('<section class="danger-zone">');
    expect(page).toContain('<main class="page narrow">');
  });
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/pages.test.ts -t "devices and account"`
Expected: FAIL.

- [ ] **Step 3: Implement** (replace the three routes)

```ts
const INSTALL_GUIDE = "https://github.com/DanielLandi/plugins/blob/main/lesson-videos/docs/install/claude-code.md";

pages.get("/devices", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const { results } = await db.prepare(
    "SELECT id, name, last_seen FROM devices WHERE teacher_id = ? AND revoked_at IS NULL ORDER BY created_at",
  ).bind(t.id).all<{ id: string; name: string; last_seen: number | null }>();
  const { results: busy } = await db.prepare(
    `SELECT l.home_device_id AS id, COUNT(DISTINCT l.id) AS n FROM lessons l JOIN turns tr ON tr.lesson_id = l.id
     WHERE l.teacher_id = ? AND l.deleted_at IS NULL AND tr.state IN ('queued', 'running') GROUP BY l.home_device_id`,
  ).bind(t.id).all<{ id: string | null; n: number }>();
  const making = new Map(busy.map((r) => [r.id, r.n]));
  const list = results.length ? html`<div class="rows">${results.map((d) => {
    const n = making.get(d.id) ?? 0;
    return html`<div class="item">${COMPUTER_ART}<span class="name">${d.name}<span class="meta">${d.last_seen ? `Last seen ${ago(d.last_seen)}` : "Not seen yet"}${n ? ` · making ${plural(n, "lesson")}` : ""}</span></span>
<form class="inline" data-api="DELETE /api/devices/${d.id}" data-kind="none" data-confirm="Remove ${d.name}? Its lessons can't continue on another device."><button class="danger">Remove</button></form></div>`;
  })}</div>` : html`<p class="muted">No device connected yet.</p>`;
  const body = html`<div class="title"><h1>Your devices</h1>
<p class="prose">A device is a computer of yours, usually at home, that makes the videos for the lessons you upload here.
It uses Claude Code signed in to <strong>your own</strong> Claude account (see the <a href="/terms">Terms</a>).</p></div>
<section class="stack"><h2 class="label making">Connected</h2>${list}</section>
<section class="card"><div class="card-head"><h2>Add a device</h2><span class="muted small">About 15 minutes, once per computer · Mac today, Windows soon</span></div>
<ol class="numbered ruled">
<li><div><strong>Install Claude Code on that computer</strong><span>Sign in with your own Claude account (any paid plan).
<a href="${INSTALL_GUIDE}" rel="noopener noreferrer">Install guide</a></span></div></li>
<li><div><strong>Add the lesson-videos plugin</strong><span>In Claude Code, type these two lines:</span>
<div class="row"><pre class="code grow" id="plugin-lines"><code>/plugin marketplace add DanielLandi/plugins
/plugin install lesson-videos@daniellandi</code></pre><button type="button" class="link" data-copy="#plugin-lines" hidden>Copy</button></div></div></li>
<li><div><strong>Run setup</strong><span>Type <code>/lesson-videos:setup</code>. It installs free tools (about 10 minutes), then
asks to connect to slide2video. Say yes: it shows a short code.</span></div></li>
<li><div><form class="stack" data-api="POST /api/devices/pair" data-done="Connected {name}. It shows up here in a moment.">
<label for="code">Type the code it shows</label>
<div class="row"><input id="code" class="code-box" name="user_code" required placeholder="KQ7-4M2" maxlength="9" autocomplete="off" autocapitalize="characters">
<button class="primary">Connect</button></div>
<p class="warn small">Only type a code that your own computer is showing right now. Codes last 10 minutes.</p></form></div></li>
</ol>
<p class="notice">After connecting, setup gives you one line to paste into Terminal on that computer. Run it whenever a
lesson says it's waiting for your computer. <a href="${GUIDE}" rel="noopener noreferrer">Full guide with troubleshooting</a></p></section>`;
  return c.html(layout(c, "Your devices", body, { current: "devices" }));
});

pages.get("/account", async (c) => {
  const t = c.get("teacher");
  const n = await c.env.DB.prepare(
    `SELECT (SELECT COUNT(*) FROM lessons WHERE teacher_id = ?1 AND deleted_at IS NULL) AS lessons,
            (SELECT COALESCE(SUM(size), 0) FROM files WHERE teacher_id = ?1) AS bytes,
            (SELECT COUNT(*) FROM devices WHERE teacher_id = ?1 AND revoked_at IS NULL) AS devices`,
  ).bind(t.id).first<{ lessons: number; bytes: number; devices: number }>();
  const body = html`<div class="title"><h1>Account</h1><p>Signed in as <strong>${t.email}</strong></p></div>
<section class="card"><h2>Your data</h2>
<p>${plural(n?.lessons ?? 0, "lesson")} · ${((n?.bytes ?? 0) / 1e6).toFixed(1)} MB of files and videos · ${plural(n?.devices ?? 0, "device")}</p>
<p><a class="button" href="/api/account/export">Download everything (.zip)</a></p>
<p class="muted small">Every lesson's files, answers, plans and videos, in one zip.</p></section>
<section class="card"><h2>Good to know</h2><p>slide2video never runs Claude itself, and never sends your lessons to anyone
else's computer. <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a></p></section>
<section class="danger-zone"><h2>Delete my account</h2>
<p>Deletes every lesson and file from the website now, and from your computers the next time they check in. This can't be undone.</p>
<form class="stack" data-api="DELETE /api/account" data-done="Your account is deleted. You can close this page." data-stay
 data-confirm="Delete your account and every lesson? This can't be undone.">
<label>Type your email address to confirm <input name="confirm" required autocomplete="off"></label>
<div class="actions"><button class="danger solid">Delete my account</button></div></form></section>`;
  return c.html(layout(c, "Account", body, { current: "account", narrow: true }));
});
```

`/admin`: keep its queries and texts; wrap the table in `<section class="card"><div class="scroll"><table>…</table></div></section>`,
the invite form in `<section class="card"><h2>Invite a teacher</h2><form class="stack" …>…</form></section>`, pass
`{ current: "admin" }` to both `layout` calls.

- [ ] **Step 4: Run the gate**

Run: `npm run check && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src test
git commit -m "slide2video: Devices with four setup steps and the code box; Account totals; Admin in cards"
```

### Task B9: Landing page at `/`

**Files:**
- Create: `src/landing.ts`
- Modify: `src/auth.ts` (`sessionEmail`), `src/index.ts` (`/` before `teacherAuth`), `src/pages.ts` (drop the `/`
  redirect from B3), `src/client.ts` (landing styles appended to `APP_CSS`)
- Test: `test/landing.test.ts` (new), `test/pages.test.ts` (remove "sends the old home address to /lessons")

**Interfaces:**
- Consumes: `shell`, `SIGN_IN` (B3), `/img/*` (B2), `accessToken(email)` test helper.
- Produces: `landingPage(): string`; `sessionEmail(req: Request, env: Env): Promise<string | null>` (verifies the
  `CF_Authorization` cookie with the same keys, issuer and audience as the header; never used to grant access).

- [ ] **Step 1: Write the failing tests**

`test/landing.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { exports } from "cloudflare:workers";
import { BASE, accessToken, seedTeacher } from "./helpers";

const home = (cookie?: string) =>
  exports.default.fetch(new Request(BASE + "/", { headers: cookie ? { Cookie: cookie } : {}, redirect: "manual" }));

describe("landing page", () => {
  it("tells a visitor what the site is for and how it works, with no script, no inline style and no teacher data", async () => {
    const r = await home();
    expect(r.status).toBe(200);
    const page = await r.text();
    expect(page).toContain("Turn your slide decks into narrated study videos.");
    expect(page).toContain('<a class="button primary" href="/lessons">Sign in</a>');
    expect(page).toContain('<svg class="trip" viewBox="0 0 1000 300" role="img" aria-label="A slide deck goes from a school laptop');
    expect(page).toContain("5. Your notes go back, and the next round starts");
    expect(page).toContain('src="/img/sample-2-diagram.webp"');
    expect(page).toContain('id="how"');
    expect(page).toContain('id="need"');
    expect(page).not.toMatch(/<script/i);
    expect(page).not.toMatch(/<style/i);
    expect(page).not.toMatch(/\sstyle=/i);
    expect(r.headers.get("Content-Security-Policy")).toContain("script-src 'self'");
  });

  it("sends a signed-in, invited teacher on to their lessons", async () => {
    const t = await seedTeacher();
    const r = await home(`other=1; CF_Authorization=${await accessToken(t.email)}`);
    expect(r.status).toBe(302);
    expect(r.headers.get("Location")).toBe("/lessons");
  });

  it("shows the landing page for an uninvited, expired, forged or foreign session", async () => {
    const cookies = [
      `CF_Authorization=${await accessToken("nobody@example.org")}`,
      `CF_Authorization=${await accessToken((await seedTeacher()).email, { exp: Math.floor(Date.now() / 1000) - 60 })}`,
      `CF_Authorization=${await accessToken((await seedTeacher()).email, { aud: "another-app" })}`,
      "CF_Authorization=not-a-token",
    ];
    for (const c of cookies) {
      const r = await home(c);
      expect(r.status, c.slice(0, 40)).toBe(200);
      expect(await r.text()).toContain("Turn your slide decks into narrated study videos.");
    }
  });
});
```

Remove the B3 test "sends the old home address to /lessons" from `test/pages.test.ts`.

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/landing.test.ts`
Expected: FAIL (401 from `teacherAuth`).

- [ ] **Step 3: `sessionEmail` in `src/auth.ts`**

Refactor `accessEmail` so the verification is shared:

```ts
async function verifiedEmail(token: string | null | undefined, env: Env): Promise<string | null> {
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return null;
  try {
    const { payload } = await jwtVerify(token, keySet(env), {
      issuer: env.ACCESS_TEAM_DOMAIN, audience: env.ACCESS_AUD, algorithms: ["RS256"],
    });
    return typeof payload.email === "string" ? payload.email.toLowerCase() : null;
  } catch {
    return null;
  }
}

/** The signed-in email, verified against Cloudflare Access (signature, issuer, audience, expiry). */
export async function accessEmail(req: Request, env: Env): Promise<string | null> {
  const host = new URL(req.url).hostname;
  if (env.DEV_EMAIL && (host === "localhost" || host === "127.0.0.1")) return env.DEV_EMAIL.toLowerCase();
  return verifiedEmail(req.headers.get("Cf-Access-Jwt-Assertion"), env);
}

/** The email in a still-valid Access session cookie. Only the public home page reads it, to send a signed-in teacher
 * on to their lessons; it never grants access to anything. */
export async function sessionEmail(req: Request, env: Env): Promise<string | null> {
  const m = (req.headers.get("Cookie") ?? "").match(/(?:^|;\s*)CF_Authorization=([^;]+)/);
  return verifiedEmail(m?.[1], env);
}
```

- [ ] **Step 4: Write `src/landing.ts`**

```ts
import { html, raw } from "./http";
import { SIGN_IN, shell } from "./ui";

const TRIP = "A slide deck goes from a school laptop to slide2video.com, then to your computer at home, where Claude " +
  "makes the video. The video comes back to the laptop to be reviewed, and your notes go back to the home computer.";

const DIAGRAM = raw(`<svg class="trip" viewBox="0 0 1000 300" role="img" aria-label="${TRIP}">
<line class="lane" x1="285" y1="128" x2="415" y2="128"/><line class="lane" x1="590" y1="128" x2="715" y2="128"/>
<rect class="screen" x="60" y="62" width="200" height="132" rx="10"/><path class="navy" d="M36 194 h248 l-14 16 h-220 z"/>
<g class="up"><path class="arrow" d="M160 150 v-46 M142 120 l18 -18 l18 18"/><path class="rule" d="M126 162 h68"/></g>
<g class="rv"><rect class="vid" x="78" y="78" width="110" height="64" rx="6"/><path class="white" d="M124 98 L144 110 L124 122 Z"/><rect class="sun" x="150" y="128" width="98" height="40" rx="8"/><path class="sun" d="M162 168 l-6 12 l16 -12 z"/><text class="note-text" x="199" y="153" text-anchor="middle">Slower here</text></g>
<text class="st" x="160" y="248" text-anchor="middle">At school</text><text class="sub" x="160" y="276" text-anchor="middle">any computer, a browser</text>
<circle class="cloud" cx="462" cy="134" r="42"/><circle class="cloud" cx="510" cy="112" r="54"/><circle class="cloud" cx="558" cy="138" r="38"/><rect class="cloud" x="440" y="130" width="130" height="46" rx="20"/>
<g transform="translate(486 112)"><rect class="teal" x="6" y="0" width="34" height="24" rx="4"/><rect class="navy" x="0" y="7" width="34" height="26" rx="4"/><path class="sun" d="M12 13 L23 20 L12 27 Z"/></g>
<text class="st" x="505" y="248" text-anchor="middle">slide2video.com</text><text class="sub" x="505" y="276" text-anchor="middle">keeps your lesson</text>
<rect class="navy" x="740" y="62" width="200" height="132" rx="10"/><rect class="navy" x="826" y="194" width="28" height="18"/><rect class="navy" x="796" y="210" width="88" height="8" rx="3"/>
<g class="spark"><path class="spark-lines" d="M840 100 v40 M820 120 h40 M826 106 l28 28 M854 106 l-28 28"/></g>
<rect class="track" x="790" y="160" width="100" height="10" rx="5"/><rect class="fill" x="790" y="160" width="100" height="10" rx="5"/>
<text class="st" x="840" y="248" text-anchor="middle">At home</text><text class="sub" x="840" y="276" text-anchor="middle">your computer, with Claude</text>
<g class="tk tk-slide"><rect class="slide-card" x="-28" y="-20" width="56" height="40" rx="5"/><path class="slide-lines" d="M-18 -8 h28 M-18 2 h36 M-18 11 h22"/></g>
<g class="tk tk-video"><rect class="vid-card" x="-28" y="-20" width="56" height="40" rx="5"/><path class="sun" d="M-7 -10 L11 0 L-7 10 Z"/></g>
<g class="tk tk-note"><rect class="sun" x="-22" y="-22" width="44" height="44" rx="4"/><path class="note-lines" d="M-12 -8 h24 M-12 2 h24 M-12 12 h14"/></g>
</svg>`);

const SAMPLES: [string, string, string][] = [
  ["sample-1-hook", "A chapter's opening question about the water cycle", "An opening question to hook the class"],
  ["sample-2-diagram", "A diagram of condensation with a common-mistake warning", "Diagrams that build step by step, with captions"],
  ["sample-3-quiz", "A quiz question at the end of a chapter", "A quick quiz to end each chapter"],
];

/** slide2video.com for anyone: what it's for, how a lesson travels, and a way to sign in. No script. */
export function landingPage(): string {
  const body = html`<section class="hero"><p class="label making">For teachers</p>
<h1 class="hero-title">Turn your slide decks into narrated study videos.</h1>
<p class="lead">Upload a deck from any school computer. Your own computer at home, with your Claude account, turns it
into short chapters with narration, captions and a quick quiz. You approve the plan and review every chapter before it's done.</p>
<div class="actions"><a class="button primary" href="/lessons">Sign in</a><a class="button" href="#how">See how it works</a>
<span class="muted small">Invite-only for now.</span></div></section>
<section class="trip-panel" aria-label="How a lesson travels">${DIAGRAM}<ol class="trip-steps">
<li class="hi1">1. You upload the deck</li><li class="hi2">2. Your computer picks it up and Claude makes the chapter</li>
<li class="hi3">3. The video comes back to the site</li><li class="hi4">4. You watch it and note what to change</li>
<li class="hi5">5. Your notes go back, and the next round starts</li></ol></section>
<section id="how" class="stack"><h2 class="section-title">How it works</h2><ol class="how">
<li><strong>Upload at school</strong><span>Drop a PowerPoint or PDF, plus any worksheets. Nothing to install on the school computer.</span></li>
<li><strong>Answer a few questions</strong><span>Your home computer reads every slide with Claude, then asks about grade, length and voice, and flags anything unclear.</span></li>
<li><strong>Approve the plan</strong><span>See the chapters and what any paid extras would cost before anything is made.</span></li>
<li><strong>Review each chapter</strong><span>Watch it, say what to change, and approve it. Then download the videos, captions and pictures.</span></li>
</ol></section>
<section class="stack" aria-labelledby="looks"><h2 id="looks" class="section-title">What the videos look like</h2><div class="samples">
${SAMPLES.map(([f, alt, cap]) => html`<figure><img src="/img/${f}.webp" alt="${alt}" width="1280" height="720" loading="lazy"><figcaption>${cap}</figcaption></figure>`)}
</div></section>
<section id="need" class="split"><div class="main stack"><h2 class="section-title">What you need</h2><ul class="list">
<li>An invitation to slide2video.com.</li>
<li>A computer at home with Claude Code and a paid Claude plan. A Mac today; Windows is on the way.</li>
<li>Optional: a more natural voice (ElevenLabs), music and short animated clips (Google), on your own accounts.</li></ul></div>
<div class="side aside"><h2>Your material stays yours</h2><ul class="list">
<li>No student information goes in: no names, photos or student work.</li>
<li>The website never runs Claude. Your lessons only go to your own computers.</li>
<li>Download or delete everything at any time.</li></ul>
<p><a href="/terms">Terms</a> · <a href="/privacy">Privacy</a></p></div></section>`;
  return shell({ title: "slide2video: narrated study videos from your slides", home: "/", body,
    description: "Turn your slide decks into narrated study videos, made on your own computer with your Claude account.",
    nav: [{ href: "#how", label: "How it works" }, { href: "#need", label: "What you need" }, SIGN_IN] });
}
```

- [ ] **Step 5: Route `/` in `src/index.ts`** (above the `teacherAuth` line; remove `pages.get("/", …)` from
  `src/pages.ts`)

```ts
app.get("/", async (c) => {
  const email = await sessionEmail(c.req.raw, c.env);
  if (email && await c.env.DB.prepare("SELECT 1 FROM teachers WHERE email = ? AND deleted_at IS NULL").bind(email).first()) {
    return c.redirect("/lessons", 302);
  }
  return c.html(landingPage(), 200, { "Cache-Control": "no-cache", Vary: "Cookie" });
});
```

- [ ] **Step 6: Landing styles** (append inside `APP_CSS`, before the `@media (max-width:600px)` line)

```css
.hero{padding-top:28px;display:flex;flex-direction:column;gap:18px}
.hero-title{font-size:3.5rem;line-height:1.05;letter-spacing:-.02em;max-width:16ch}
.lead{font-size:1.2rem;max-width:60ch}
.section-title{font-size:2.2rem}
.trip-panel{background:#FFFFFF;color:#16212E;border:1px solid #E7DFCF;border-radius:20px;box-shadow:0 3px 0 #E7DFCF;padding:24px 16px 8px}
.trip{display:block;width:100%;height:auto;font-family:var(--font)}
.trip .lane{stroke:#CFC5B0;stroke-width:3;stroke-dasharray:8 8}
.trip .screen{fill:#FBF8F1;stroke:#0B2545;stroke-width:4}
.trip .navy{fill:#0B2545}.trip .teal{fill:#1FA7A0}.trip .sun{fill:#FFC145}.trip .white{fill:#FFFFFF}.trip .vid{fill:#0F4C75}
.trip .cloud{fill:#E8F7F5}.trip .track{fill:#16355C}.trip .fill{fill:#1FA7A0}
.trip .arrow{fill:none;stroke:#137F7A;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}
.trip .rule{stroke:#CFC5B0;stroke-width:6;stroke-linecap:round}
.trip .spark-lines{stroke:#FFC145;stroke-width:6;stroke-linecap:round}
.trip .slide-card{fill:#FFFFFF;stroke:#0B2545;stroke-width:3}.trip .slide-lines{stroke:#C2412D;stroke-width:4;stroke-linecap:round}
.trip .vid-card{fill:#0F4C75;stroke:#FFFFFF;stroke-width:3}.trip .note-lines{stroke:#0B2545;stroke-width:4;stroke-linecap:round}
.trip .st{font-size:22px;font-weight:800;fill:#0B2545}.trip .sub{font-size:17px;fill:#5E6875}.trip .note-text{font-size:14px;font-weight:800;fill:#0B2545}
.trip .tk{opacity:0;animation-duration:14s;animation-timing-function:ease-in-out;animation-iteration-count:infinite}
.trip .tk-slide{animation-name:s2vSlide}.trip .tk-video{animation-name:s2vVideo}.trip .tk-note{animation-name:s2vNote}
.trip .spark{animation:s2vWork 14s linear infinite}
.trip .fill{transform-box:fill-box;transform-origin:left center;animation:s2vFill 14s linear infinite}
.trip .rv{opacity:0;animation:s2vReview 14s linear infinite}
.trip .up{animation:s2vUpload 14s linear infinite}
@keyframes s2vSlide{0%{transform:translate(160px,128px);opacity:0}3%{opacity:1}14%{transform:translate(500px,128px)}17%{transform:translate(500px,128px)}28%{transform:translate(840px,128px);opacity:1}31%,100%{transform:translate(840px,128px);opacity:0}}
@keyframes s2vVideo{0%,44%{transform:translate(840px,128px);opacity:0}47%{opacity:1}56%{transform:translate(500px,128px)}59%{transform:translate(500px,128px)}68%{transform:translate(160px,128px);opacity:1}71%,100%{transform:translate(160px,128px);opacity:0}}
@keyframes s2vNote{0%,84%{transform:translate(160px,128px);opacity:0}86%{opacity:1}92%{transform:translate(500px,128px)}98%{transform:translate(840px,128px);opacity:1}100%{transform:translate(840px,128px);opacity:0}}
@keyframes s2vWork{0%,29%{opacity:.25}31%{opacity:1}34%{opacity:.45}37%{opacity:1}40%{opacity:.45}43%{opacity:1}46%,100%{opacity:.25}}
@keyframes s2vFill{0%,29%{transform:scaleX(0)}45%{transform:scaleX(1)}47%,100%{transform:scaleX(0)}}
@keyframes s2vReview{0%,70%{opacity:0}72%,88%{opacity:1}90%,100%{opacity:0}}
@keyframes s2vUpload{0%,70%{opacity:1}72%,88%{opacity:0}90%,100%{opacity:1}}
.trip-steps{list-style:none;margin:8px 0 16px;padding:0;display:flex;flex-wrap:wrap;gap:8px;font-size:.95rem;font-weight:700}
.trip-steps li{flex:1 1 170px;padding:8px 12px;border:2px solid #E7DFCF;border-radius:12px;background:#FFFFFF}
.trip-steps li{animation-duration:14s;animation-timing-function:step-end;animation-iteration-count:infinite}
.trip-steps .hi1{animation-name:s2vH1}.trip-steps .hi2{animation-name:s2vH2}.trip-steps .hi3{animation-name:s2vH3}.trip-steps .hi4{animation-name:s2vH4}.trip-steps .hi5{animation-name:s2vH5}
@keyframes s2vH1{0%{background:#FFF4E0;border-color:#FFC145}14%,100%{background:#FFFFFF;border-color:#E7DFCF}}
@keyframes s2vH2{0%{background:#FFFFFF;border-color:#E7DFCF}14%{background:#FFF4E0;border-color:#FFC145}46%,100%{background:#FFFFFF;border-color:#E7DFCF}}
@keyframes s2vH3{0%{background:#FFFFFF;border-color:#E7DFCF}46%{background:#FFF4E0;border-color:#FFC145}70%,100%{background:#FFFFFF;border-color:#E7DFCF}}
@keyframes s2vH4{0%{background:#FFFFFF;border-color:#E7DFCF}70%{background:#FFF4E0;border-color:#FFC145}86%,100%{background:#FFFFFF;border-color:#E7DFCF}}
@keyframes s2vH5{0%{background:#FFFFFF;border-color:#E7DFCF}86%{background:#FFF4E0;border-color:#FFC145}100%{background:#FFFFFF;border-color:#E7DFCF}}
@media (prefers-reduced-motion:reduce){.trip .rv{opacity:1}.trip .up{opacity:0}}
.how{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;counter-reset:n}
.how li{counter-increment:n;display:flex;flex-direction:column;gap:8px;padding:20px;background:var(--card);border:1px solid var(--line);border-radius:16px}
.how li::before{content:counter(n);width:36px;height:36px;border-radius:50%;background:var(--sun);color:#0B2545;font-weight:800;text-align:center;line-height:36px}
.how strong{color:var(--heading)}.how span{font-size:.95rem}
.samples{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.samples figure{margin:0;display:flex;flex-direction:column;gap:8px}
.samples img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:12px;border:1px solid var(--line)}
.samples figcaption{font-size:.9rem;color:var(--muted)}
```

and inside the existing `@media (max-width:600px){…}` add `.hero-title{font-size:2.4rem}.section-title{font-size:1.7rem}`.

(The diagram panel keeps fixed light colours in both themes on purpose: it is an illustration.)

- [ ] **Step 7: Run the gate**

Run: `npm run check && npm test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src test
git commit -m "slide2video: public landing page with the animated round-trip diagram"
```

### Task B10: Usage numbers: recording

**Files:**
- Create: `migrations/0003_usage.sql`, `src/usage.ts`
- Modify: `src/turns.ts` (claim sets `started_at`; `TurnRow` gains `started_at: number | null`), `src/device.ts`
  (finish records usage), `src/teacher-api.ts` (start and teacher actions record usage), `src/deletion.ts`
  (`closeAccount` drops the ids), `src/export.ts` (`data.json` gains `usage`), `src/legal.ts` (Privacy line)
- Test: `test/usage.test.ts` (new), `test/pages.test.ts` (Privacy line)

**Interfaces:**
- Produces (`src/usage.ts`): `type Metric = "deck" | "slides" | "video" | "video_seconds" | "turn_seconds" | "error" |
  "limit_pause" | "lesson_done" | "answer" | "plan_change" | "approve" | "feedback" | "continue" | "wait_seconds"`;
  `type UsageRow = { metric: Metric; value?: number; detail?: string | null }`;
  `usageRow(db, teacherId, lessonId, row: UsageRow): D1PreparedStatement`;
  `usageIfHeld(db, turnId, deviceId, teacherId, lessonId, row: UsageRow, at: number): D1PreparedStatement`.
  Task B11 reads the `usage` table.

- [ ] **Step 1: Write the failing tests**

`test/usage.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { unzipSync } from "fflate";
import { PLAN, QUESTIONS, asTeacher, claim, finish, newLesson, pairDevice, seedTeacher, upload } from "./helpers";

type Row = { metric: string; value: number; detail: string | null };
const rows = (lessonId: string) => env.DB.prepare("SELECT metric, value, detail FROM usage WHERE lesson_id = ? ORDER BY id")
  .bind(lessonId).all<Row>().then((r) => r.results);
const pick = (r: Row[], metric: string) => r.filter((x) => x.metric === metric);
const post = (email: string, path: string, body: object = {}) => asTeacher(email, path, { method: "POST", body: JSON.stringify(body) });
const enc = (s: string) => new TextEncoder().encode(s);

/** One lesson through every step: questions, plan, a chapter, a change, the changed chapter, done. */
export async function fullLesson() {
  const t = await seedTeacher();
  const mac = await pairDevice(t.email);
  const id = await newLesson(t.email);
  let turn = await claim(mac.token);
  await finish(mac.token, turn.turn.id, { ...QUESTIONS, slides: 9 });
  await post(t.email, `/api/lessons/${id}/answer`, { answers: [{ question: "grade", choice: "Grades 6–8", other: null }] });
  turn = await claim(mac.token);
  await finish(mac.token, turn.turn.id, { ...PLAN, slides: 9, estimate: { usd: 0.84, minutes: 3, chapters: 1 } });
  await post(t.email, `/api/lessons/${id}/approve`);
  turn = await claim(mac.token);
  await upload(mac.token, turn.turn.id, "out/ch1/v1/a.mp4", enc("video"));
  await upload(mac.token, turn.turn.id, "out/ch1/v1/timing.json", enc(JSON.stringify({ duration: 192.5, scenes: [] })), "application/json");
  await finish(mac.token, turn.turn.id, { contract: 1, kind: "review", message: "Chapter 1", chapter: 1, version: 1,
    video: "out/ch1/v1/a.mp4", timing: "out/ch1/v1/timing.json" });
  await post(t.email, `/api/lessons/${id}/feedback`, { feedback: "Slower, please" });
  turn = await claim(mac.token);
  await upload(mac.token, turn.turn.id, "out/ch1/v2/a.mp4", enc("video 2"));
  await finish(mac.token, turn.turn.id, { contract: 1, kind: "review", message: "Chapter 1 again", chapter: 1, version: 2,
    video: "out/ch1/v2/a.mp4" });
  await post(t.email, `/api/lessons/${id}/continue`);
  turn = await claim(mac.token);
  await finish(mac.token, turn.turn.id, { contract: 1, kind: "done", message: "Done", chapters: [{ chapter: 1, title: "One" }] });
  return { t, mac, id };
}

describe("usage recording", () => {
  it("records each step of a lesson once, as numbers only", async () => {
    const { id } = await fullLesson();
    const r = await rows(id);
    expect(pick(r, "deck").length).toBe(1);
    expect(pick(r, "slides").map((x) => x.value)).toEqual([9]); // the first card's count only
    expect(pick(r, "video").map((x) => x.detail)).toEqual(["ch1v1", "ch1v2"]);
    expect(pick(r, "video_seconds").map((x) => [x.value, x.detail])).toEqual([[192.5, "ch1v1"]]); // v2 had no timing file
    expect(pick(r, "turn_seconds").map((x) => x.detail)).toEqual(["start", "answer", "approve", "feedback", "continue"]);
    for (const m of ["answer", "feedback", "continue", "lesson_done"]) expect(pick(r, m).length, m).toBe(1);
    expect(pick(r, "approve").map((x) => x.value)).toEqual([0.84]);
    expect(pick(r, "wait_seconds").map((x) => x.detail)).toEqual(["answer", "approve", "feedback", "continue"]);
  });

  it("counts errors and plan-limit pauses with the step they ended", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    let turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, { contract: 1, kind: "error", message: "Limit",
      retry_after: new Date(Date.now() + 3600e3).toISOString() });
    await env.DB.prepare("UPDATE turns SET not_before = 0 WHERE lesson_id = ?").bind(id).run();
    turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, { contract: 1, kind: "error", message: "Broke" });
    const r = await rows(id);
    expect(pick(r, "limit_pause").map((x) => x.detail)).toEqual(["start"]);
    expect(pick(r, "error").map((x) => x.detail)).toEqual(["start"]);
  });

  it("times a step from its last claim", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    const turn = await claim(mac.token);
    await env.DB.prepare("UPDATE turns SET started_at = 1000, lease_until = 0 WHERE id = ?").bind(turn.turn.id).run();
    expect((await claim(mac.token)).turn.id).toBe(turn.turn.id);
    await finish(mac.token, turn.turn.id, QUESTIONS);
    expect(pick(await rows(id), "turn_seconds")[0].value).toBeLessThan(60);
  });

  it("keeps a deleted lesson's numbers, and drops both ids when the account is deleted", async () => {
    const { t, id } = await fullLesson();
    await asTeacher(t.email, `/api/lessons/${id}`, { method: "DELETE" });
    expect((await rows(id)).length).toBeGreaterThan(10);
    await asTeacher(t.email, "/api/account", { method: "DELETE", body: JSON.stringify({ confirm: t.email }) });
    expect((await rows(id)).length).toBe(0);
    const anon = await env.DB.prepare("SELECT COUNT(*) AS n FROM usage WHERE teacher_id IS NULL AND lesson_id IS NULL AND metric = 'deck'")
      .first<{ n: number }>();
    expect(anon!.n).toBeGreaterThan(0);
  });

  it("puts the teacher's own usage rows in the export, without ids", async () => {
    const { t } = await fullLesson();
    const zip = unzipSync(new Uint8Array(await (await asTeacher(t.email, "/api/account/export")).arrayBuffer()));
    const data = JSON.parse(new TextDecoder().decode(zip["data.json"]));
    expect(data.usage.some((u: any) => u.metric === "video_seconds" && u.value === 192.5)).toBe(true);
    expect(Object.keys(data.usage[0]).sort()).toEqual(["created_at", "detail", "metric", "value"]);
  });
});
```

In `test/pages.test.ts`'s public-pages test add
`expect(privacy).toContain("Usage numbers: how many decks, slides and videos");`.

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/usage.test.ts`
Expected: FAIL (`no such table: usage`).

- [ ] **Step 3: Migration and `src/usage.ts`**

`migrations/0003_usage.sql`:

```sql
-- usage numbers (spec §4.13): numbers only, kept when a lesson is deleted, ids dropped when the account is
CREATE TABLE usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id TEXT, lesson_id TEXT, metric TEXT NOT NULL,
  value REAL NOT NULL DEFAULT 1, detail TEXT, created_at INTEGER NOT NULL
);
CREATE INDEX usage_metric_time ON usage(metric, created_at);
CREATE INDEX usage_teacher ON usage(teacher_id, created_at);
CREATE INDEX usage_lesson ON usage(lesson_id);
ALTER TABLE turns ADD COLUMN started_at INTEGER;
```

`src/usage.ts`:

```ts
import { now } from "./util";

export type Metric = "deck" | "slides" | "video" | "video_seconds" | "turn_seconds" | "error" | "limit_pause" | "lesson_done"
  | "answer" | "plan_change" | "approve" | "feedback" | "continue" | "wait_seconds";
export type UsageRow = { metric: Metric; value?: number; detail?: string | null };

const INSERT = "INSERT INTO usage (teacher_id, lesson_id, metric, value, detail, created_at)";

/** One usage row: numbers only, never titles or content. */
export const usageRow = (db: D1Database, teacherId: string, lessonId: string, u: UsageRow) =>
  db.prepare(`${INSERT} VALUES (?, ?, ?, ?, ?, ?)`).bind(teacherId, lessonId, u.metric, u.value ?? 1, u.detail ?? null, now());

/** A usage row for a computer's result, written in the same batch and only while that computer still holds the turn. */
export const usageIfHeld = (db: D1Database, turnId: string, deviceId: string, teacherId: string, lessonId: string,
  u: UsageRow, at: number) =>
  db.prepare(`${INSERT} SELECT ?3, ?4, ?5, ?6, ?7, ?8
              WHERE EXISTS (SELECT 1 FROM turns WHERE id = ?1 AND device_id = ?2 AND state = 'running')`)
    .bind(turnId, deviceId, teacherId, lessonId, u.metric, u.value ?? 1, u.detail ?? null, at);
```

- [ ] **Step 4: Record**

`src/turns.ts`: in the claim's first `UPDATE turns SET state = 'running', …` add `, started_at = ?4` (the claim binds
`?4` to the current time); add `started_at: number | null` to `TurnRow`.

`src/device.ts`: import `{ usageIfHeld, type UsageRow }` from `./usage` and `Env` from `./env`; add:

```ts
/** A review's video length, from the timing file the computer uploaded with it (0.5.x plugins upload it too). */
async function videoSeconds(env: Env, lessonId: string, timingPath: unknown): Promise<number | null> {
  if (typeof timingPath !== "string" || !timingPath) return null;
  const f = await env.DB.prepare("SELECT r2_key FROM files WHERE lesson_id = ? AND path = ? AND kind = 'timing'")
    .bind(lessonId, timingPath).first<{ r2_key: string }>();
  const obj = f ? await env.FILES.get(f.r2_key) : null;
  if (!obj) return null;
  try {
    const d = (JSON.parse(await obj.text()) as { duration?: unknown }).duration;
    return typeof d === "number" && Number.isFinite(d) && d > 0 && d <= 7200 ? d : null;
  } catch {
    return null;
  }
}

/** What a computer's result adds to the usage numbers: the step's time, and what its card brings. */
async function finishUsage(env: Env, turn: TurnRow, card: Record<string, any>, paused: boolean, at: number): Promise<UsageRow[]> {
  const rows: UsageRow[] = [];
  if (turn.started_at) rows.push({ metric: "turn_seconds", value: Math.max(0, at - turn.started_at), detail: turn.kind });
  if (card.kind === "error") rows.push({ metric: paused ? "limit_pause" : "error", detail: turn.kind });
  if (typeof card.slides === "number") {
    const l = await env.DB.prepare("SELECT slides FROM lessons WHERE id = ?").bind(turn.lesson_id).first<{ slides: number | null }>();
    if (l && l.slides === null) rows.push({ metric: "slides", value: card.slides });
  }
  if (card.kind === "review") {
    const detail = `ch${card.chapter}v${card.version ?? 1}`;
    rows.push({ metric: "video", detail });
    const secs = await videoSeconds(env, turn.lesson_id, card.timing);
    if (secs !== null) rows.push({ metric: "video_seconds", value: secs, detail });
  }
  if (card.kind === "done") rows.push({ metric: "lesson_done" });
  return rows;
}
```

In the finish handler, just before the batch:

```ts
  const usage = turn.kind === "delete" ? [] : await finishUsage(c.env, turn, card, retryAt !== null, t);
```

and the batch becomes (the card insert first, the usage rows next, both still guarded by the held turn, then the
turn update and the lesson update):

```ts
  const results = await db.batch([
    db.prepare(`INSERT INTO cards (id, teacher_id, lesson_id, turn_id, kind, body, created_at)
                SELECT ?3, ?4, ?5, ?1, ?6, ?7, ?8 WHERE EXISTS (SELECT 1 FROM turns WHERE ${HELD})`)
      .bind(turn.id, d.id, newId("crd"), turn.teacher_id, turn.lesson_id, card.kind, JSON.stringify(stored), t),
    ...usage.map((u) => usageIfHeld(db, turn.id, d.id, turn.teacher_id, turn.lesson_id, u, t)),
    update,
    db.prepare("UPDATE lessons SET updated_at = ?1, slides = COALESCE(?2, slides) WHERE id = ?3")
      .bind(t, typeof card.slides === "number" ? card.slides : null, turn.lesson_id),
  ]);
  const done = results[1 + usage.length];
```

`src/teacher-api.ts`: import `{ usageRow }` from `./usage` and `now` from `./util`. In `/lessons/:id/start`, after the
`queueTurn` check and before `return c.body(null, 204)`:

```ts
  await usageRow(c.env.DB, t.id, lesson.id, { metric: "deck" }).run();
```

In the action route, after a successful `answerCard` and before `return c.body(null, 204)`:

```ts
  const metric = ({ answer: "answer", approve: "approve", change: "plan_change", continue: "continue", feedback: "feedback" } as const)[
    c.req.param("action") as "answer" | "approve" | "change" | "continue" | "feedback"];
  const value = metric === "approve" ? Number(JSON.parse(card.body).estimate?.usd) || 0 : 1;
  await db.batch([
    usageRow(db, t.id, lesson.id, { metric, value }),
    usageRow(db, t.id, lesson.id, { metric: "wait_seconds", value: Math.max(0, now() - card.created_at), detail: action.turn }),
  ]);
```

`src/deletion.ts` `closeAccount`: add to its batch
`db.prepare("UPDATE usage SET teacher_id = NULL, lesson_id = NULL WHERE teacher_id = ?").bind(teacherId),`.

`src/export.ts` `exportZip`: add
`const usage = await q("SELECT metric, value, detail, created_at FROM usage WHERE teacher_id = ?1 ORDER BY id");` and
`usage` to `data`.

`src/legal.ts`, Privacy, "What is stored" list: add before the action-log item:

```html
<li>Usage numbers: how many decks, slides and videos, how many minutes of video, and how long each step took. They hold
no titles or content. They stay when you delete a lesson; when you delete your account they are kept without your name.</li>
```

- [ ] **Step 5: Run the gate**

Run: `npm run check && npm test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add migrations/0003_usage.sql src test
git commit -m "slide2video: record usage numbers (decks, slides, videos, minutes, step times, teacher actions)"
```

### Task B11: Usage numbers: Account and Admin

**Files:**
- Modify: `src/usage.ts` (summaries), `src/pages.ts` (`/account` "Your numbers", `/admin` "Usage"), `src/client.ts`
  (`.stats`, `.num` styles)
- Test: `test/usage.test.ts`

**Interfaces:**
- Consumes: the `usage` table (B10), `fullLesson()` (B10's test helper, same file).
- Produces: `usageSummary(db, opts?: { teacherId?: string; since?: number }): Promise<Summary>`,
  `usageByTeacher(db)`, `usageByMonth(db)`, `fmtSeconds(s: number | null): string`, `ratio(a, b): number | null`.

- [ ] **Step 1: Write the failing tests** (append to `test/usage.test.ts`)

```ts
describe("usage numbers on the pages", () => {
  it("shows a teacher their own numbers only", async () => {
    const { t } = await fullLesson();
    const other = await seedTeacher();
    const page = await (await asTeacher(t.email, "/account")).text();
    expect(page).toContain("<h2>Your numbers</h2>");
    expect(page).toContain("<dt>Decks</dt><dd>1</dd>");
    expect(page).toContain("<dt>Slides</dt><dd>9</dd>");
    expect(page).toContain("<dt>Chapter videos</dt><dd>1</dd>");
    expect(page).toContain("<dt>Minutes of video</dt><dd>3.2</dd>");
    expect(page).toContain("<dt>Changes you asked for</dt><dd>1</dd>");
    const theirs = await (await asTeacher(other.email, "/account")).text();
    expect(theirs).toContain("<dt>Decks</dt><dd>0</dd>");
    expect(theirs).toContain("<dt>Computer time per minute of video</dt><dd>—</dd>");
  });

  it("shows the admin the measures, each teacher and each month; nobody else", async () => {
    const { t } = await fullLesson();
    const page = await (await asTeacher("admin@example.org", "/admin")).text();
    expect(page).toContain("<h2>Usage</h2>");
    expect(page).toContain("<td>Computer time per minute of video</td>");
    expect(page).toContain("<th>Last 30 days</th><th>All time</th>");
    expect(page).toContain(`<td>${t.email}</td>`);
    expect(page).toContain(`<td>${new Date().toISOString().slice(0, 7)}</td>`);
    expect(await (await asTeacher(t.email, "/admin")).text()).not.toContain("<h2>Usage</h2>");
  });
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run test/usage.test.ts -t "on the pages"`
Expected: FAIL.

- [ ] **Step 3: Summaries** (append to `src/usage.ts`)

```ts
export type Summary = { decks: number; slides: number; chapters: number; videos: number; videoSeconds: number;
  readSeconds: number; makeSeconds: number; feedback: number; approvedUsd: number; finished: number; errors: number;
  pauses: number; waitAvg: number | null; teachers: number };

const MEASURES = `SUM(metric = 'deck') AS decks,
  COALESCE(SUM(CASE WHEN metric = 'slides' THEN value END), 0) AS slides,
  SUM(metric = 'video' AND detail LIKE '%v1') AS chapters,
  SUM(metric = 'video') AS videos,
  COALESCE(SUM(CASE WHEN metric = 'video_seconds' THEN value END), 0) AS videoSeconds`;

/** Totals over every teacher, or one (`teacherId`), from `since` (unix seconds) on. */
export async function usageSummary(db: D1Database, opts: { teacherId?: string; since?: number } = {}): Promise<Summary> {
  const where: string[] = [];
  const binds: unknown[] = [];
  if (opts.teacherId) { where.push("teacher_id = ?"); binds.push(opts.teacherId); }
  if (opts.since) { where.push("created_at >= ?"); binds.push(opts.since); }
  const r = await db.prepare(`SELECT ${MEASURES},
    COALESCE(SUM(CASE WHEN metric = 'turn_seconds' AND detail = 'start' THEN value END), 0) AS readSeconds,
    COALESCE(SUM(CASE WHEN metric = 'turn_seconds' AND detail IN ('approve', 'continue', 'feedback') THEN value END), 0) AS makeSeconds,
    SUM(metric = 'feedback') AS feedback,
    COALESCE(SUM(CASE WHEN metric = 'approve' THEN value END), 0) AS approvedUsd,
    SUM(metric = 'lesson_done') AS finished, SUM(metric = 'error') AS errors, SUM(metric = 'limit_pause') AS pauses,
    AVG(CASE WHEN metric = 'wait_seconds' THEN value END) AS waitAvg,
    COUNT(DISTINCT teacher_id) AS teachers
    FROM usage${where.length ? ` WHERE ${where.join(" AND ")}` : ""}`).bind(...binds).first<Record<string, number | null>>();
  const n = (k: string) => Number(r?.[k] ?? 0);
  return { decks: n("decks"), slides: n("slides"), chapters: n("chapters"), videos: n("videos"), videoSeconds: n("videoSeconds"),
    readSeconds: n("readSeconds"), makeSeconds: n("makeSeconds"), feedback: n("feedback"), approvedUsd: n("approvedUsd"),
    finished: n("finished"), errors: n("errors"), pauses: n("pauses"), waitAvg: r?.waitAvg ?? null, teachers: n("teachers") };
}

export type TeacherUsage = { email: string | null; decks: number; slides: number; chapters: number; videoSeconds: number; last: number };

/** One row per teacher (deleted accounts together, with no email), most recently active first. */
export const usageByTeacher = (db: D1Database) => db.prepare(`SELECT t.email AS email, ${MEASURES}, MAX(u.created_at) AS last
  FROM usage u LEFT JOIN teachers t ON t.id = u.teacher_id AND t.deleted_at IS NULL
  GROUP BY u.teacher_id ORDER BY last DESC`).all<TeacherUsage>().then((r) => r.results);

export type MonthUsage = { month: string; decks: number; chapters: number; videoSeconds: number };

/** The last 12 months with any usage, newest first. */
export const usageByMonth = (db: D1Database) => db.prepare(`SELECT strftime('%Y-%m', created_at, 'unixepoch') AS month,
  SUM(metric = 'deck') AS decks, SUM(metric = 'video' AND detail LIKE '%v1') AS chapters,
  COALESCE(SUM(CASE WHEN metric = 'video_seconds' THEN value END), 0) AS videoSeconds
  FROM usage GROUP BY month ORDER BY month DESC LIMIT 12`).all<MonthUsage>().then((r) => r.results);

export const ratio = (a: number, b: number): number | null => (b > 0 ? a / b : null);
export const fmtSeconds = (s: number | null): string => s === null || !Number.isFinite(s) ? "—"
  : s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`;
export const fmtMinutes = (s: number) => (s / 60).toFixed(1);
```

- [ ] **Step 4: Show them** (`src/pages.ts`; import the new names from `./usage`)

`/account`: after the "Your data" section add

```ts
  const u = await usageSummary(c.env.DB, { teacherId: t.id });
  const tile = (label: string, value: string | number) => html`<div><dt>${label}</dt><dd>${value}</dd></div>`;
  const numbers = html`<section class="card"><h2>Your numbers</h2><dl class="stats">
${tile("Decks", u.decks)}${tile("Slides", u.slides)}${tile("Chapter videos", u.chapters)}${tile("Minutes of video", fmtMinutes(u.videoSeconds))}
${tile("Changes you asked for", u.feedback)}${tile("Computer time per minute of video", fmtSeconds(ratio(u.makeSeconds, u.videoSeconds / 60)))}</dl></section>`;
```

and put `${numbers}` between the "Your data" and "Good to know" sections.

`/admin`: after the teachers table and before the invite form, add `${usageSection}`:

```ts
  const since = now() - 30 * 86400;
  const [all, recent, people, months] = await Promise.all([
    usageSummary(c.env.DB), usageSummary(c.env.DB, { since }), usageByTeacher(c.env.DB), usageByMonth(c.env.DB)]);
  const measures: [string, (s: Summary) => string][] = [
    ["Teachers active", (s) => String(s.teachers)],
    ["Decks", (s) => String(s.decks)],
    ["Slides", (s) => String(s.slides)],
    ["Chapter videos", (s) => String(s.chapters)],
    ["Video versions (with changes)", (s) => String(s.videos)],
    ["Minutes of video", (s) => fmtMinutes(s.videoSeconds)],
    ["Lessons finished", (s) => String(s.finished)],
    ["Changes asked per chapter", (s) => { const r = ratio(s.feedback, s.chapters); return r === null ? "—" : r.toFixed(1); }],
    ["Computer time reading per slide", (s) => fmtSeconds(ratio(s.readSeconds, s.slides))],
    ["Computer time per minute of video", (s) => fmtSeconds(ratio(s.makeSeconds, s.videoSeconds / 60))],
    ["Average time teachers take to answer", (s) => fmtSeconds(s.waitAvg)],
    ["Paid extras approved", (s) => `$${s.approvedUsd.toFixed(2)}`],
    ["Errors", (s) => String(s.errors)],
    ["Plan-limit pauses", (s) => String(s.pauses)],
  ];
  const usageSection = html`<section class="card"><h2>Usage</h2>
<div class="scroll"><table><tr><th>Measure</th><th>Last 30 days</th><th>All time</th></tr>
${measures.map(([label, f]) => html`<tr><td>${label}</td><td class="num">${f(recent)}</td><td class="num">${f(all)}</td></tr>`)}</table></div>
<h3>By teacher</h3><div class="scroll"><table><tr><th>Teacher</th><th>Decks</th><th>Slides</th><th>Chapter videos</th><th>Minutes of video</th><th>Last active</th></tr>
${people.map((p) => html`<tr><td>${p.email ?? "Deleted accounts"}</td><td class="num">${p.decks}</td><td class="num">${p.slides}</td>
<td class="num">${p.chapters}</td><td class="num">${fmtMinutes(p.videoSeconds)}</td><td>${when(p.last)}</td></tr>`)}</table></div>
<h3>By month</h3><div class="scroll"><table><tr><th>Month</th><th>Decks</th><th>Chapter videos</th><th>Minutes of video</th></tr>
${months.map((m) => html`<tr><td>${m.month}</td><td class="num">${m.decks}</td><td class="num">${m.chapters}</td><td class="num">${fmtMinutes(m.videoSeconds)}</td></tr>`)}</table></div></section>`;
```

(`/admin` keeps its "Admins only" 403 for anyone else, before any of this runs.)

`src/client.ts`, append inside `APP_CSS` before the `@media (max-width:600px)` line:

```css
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:0}
.stats div{background:var(--paper);border-radius:12px;padding:12px 14px}
.stats dt{font-size:.85rem;font-weight:700;color:var(--muted)}
.stats dd{margin:0;font-size:1.6rem;font-weight:800;color:var(--heading);font-variant-numeric:tabular-nums}
.num{text-align:right;font-variant-numeric:tabular-nums}
```

- [ ] **Step 5: Run the gate**

Run: `npm run check && npm test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src test
git commit -m "slide2video: usage numbers on Account (your numbers) and Admin (measures, by teacher, by month)"
```

### Task B12: Whole-site check in a browser (local)

**Files:** none (fixes found go into the task that owns the code, as a follow-up commit)

- [ ] **Step 1: Run the site locally with a dev sign-in**

```bash
npm run db:local
git check-ignore -q .dev.vars || echo ".dev.vars is NOT ignored: stop and add it to .gitignore first"
printf 'DEV_EMAIL=%s\n' "$(git config user.email)" > .dev.vars   # read by wrangler dev; the Worker trusts it only on localhost
npx wrangler dev --port 8787
```

- [ ] **Step 2: Look at every page** at 1280px and 400px wide, light and dark (`prefers-color-scheme`), with Chrome:
  `/` (watch one full 14 s loop; then turn on "reduce motion" in the OS and reload: nothing moves, the laptop shows
  "Slower here"), `/lessons` (empty), `/lessons/new` (pick a file: the row appears and the title fills), `/devices`
  (Copy copies), `/account` (Your numbers), `/admin` (Usage), `/terms`, `/privacy`. Check the browser console shows no CSP violations.

- [ ] **Step 3: Fix what's off** in the owning file, run the gate, commit
  (`git commit -m "slide2video: design pass fixes from the browser check"`), and delete `.dev.vars`.

### Task B13: Deploy, switch Access, smoke test

**Files:** none in the repo (Cloudflare configuration); the ledger records the before/after.

- [ ] **Step 1: Push and deploy**

```bash
git push origin main
npx wrangler d1 migrations apply slide2video --remote
npx wrangler deploy
```

Expected: migrations `0002_design_pass.sql` and `0003_usage.sql` applied; a new Worker version on slide2video.com. The site still sits
entirely behind Access at this point, which is harmless.

- [ ] **Step 2: Record the current Access setup** (Zero Trust dashboard → Access → Applications, team
  `fancy-math-8d8a`): write into the ledger the destinations of "slide2video.com" (today: `slide2video.com`, whole
  domain) and of "slide2video.com public paths (bypass)" (today: `api/device/*`, `terms`, `privacy`, `app.css`,
  `health`). This is the rollback.

- [ ] **Step 3: Ask Daniel before changing account settings**, then edit in the dashboard (Chrome):
  - "slide2video.com public paths (bypass)": destinations become `slide2video.com` (empty path) and
    `slide2video.com/api/device/*`. Policy unchanged (Bypass, Everyone).
  - "slide2video.com": destinations become `slide2video.com/lessons`, `slide2video.com/lessons/*`,
    `slide2video.com/devices`, `slide2video.com/account`, `slide2video.com/admin`, `slide2video.com/api/*`. Policy
    unchanged (Allow, group "slide2video teachers"), session 1 month.

- [ ] **Step 4: Smoke test** (the Mac's DNS cache may need `--resolve slide2video.com:443:104.21.2.200`)

```bash
for p in / /terms /privacy /app.css /app.js /fonts/nunito-v1.woff2 /img/sample-1-hook.webp /logo.svg /favicon.svg /health; do
  printf '%-28s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' https://slide2video.com$p)"; done   # all 200
for p in /lessons /lessons/new /devices /account /admin /api/lessons; do
  printf '%-28s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' https://slide2video.com$p)"; done   # 302 to the Access sign-in
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'X-LV-Contract: 1' -H 'Content-Type: application/json' \
  -d '{"name":"smoke"}' https://slide2video.com/api/device/pair/start   # 200 (reaches the Worker)
curl -s https://slide2video.com/ | grep -c "Turn your slide decks into narrated study videos."   # 1
```

Then, signed in as Daniel in Chrome: `slide2video.com` goes to `/lessons`; Lessons, a lesson page, Devices and Account
load with the font and logo.

If any protected path answers 200 without sign-in, or a public one redirects, put back the Step 2 destinations and
stop.

- [ ] **Step 5: Close the design issue**

```bash
gh issue close 11 -R DanielLandi/slide2video -c "Shipped: Study notebook identity, new screens, landing page (deploy <version id>)."
```

---

# Part C: plugin 0.6.0 (plugins repo, branch `slide2video-design-pass`)

### Task C1: `estimate --json`

**Files:**
- Modify: `lesson-videos/scripts/lv/estimate.py`, `lesson-videos/scripts/lv/cli.py`
- Test: `tests/test_estimate_status.py`

**Interfaces:**
- Produces: `estimate.breakdown(chars: int, clips: int, music: bool, paid_voice: bool = True) -> dict` returning
  `{"usd": float, "items": [{"label": str, "usd": float, "detail"?: str}]}`; CLI `LV estimate … --json`.

- [ ] **Step 1: Write the failing tests** (append; add `import json` and `from lv import cli, contract, keys` as needed)

```python
def test_breakdown_lists_what_report_says():
    b = estimate.breakdown(22500, 2, True)
    assert b["usd"] == estimate.gemini_usd(2, True) == 0.88
    assert [i["label"] for i in b["items"]] == ["Narration (ElevenLabs)", "Background music", "2 short animated clips"]
    assert round(sum(i["usd"] for i in b["items"]), 2) == b["usd"]
    assert "22,500 characters" in b["items"][0]["detail"]
    assert estimate.breakdown(1000, 0, False, paid_voice=False) == {"usd": 0, "items": [{"label": "Narration (free voice)", "usd": 0}]}
    assert estimate.breakdown(1000, 1, False, paid_voice=False)["items"][1]["label"] == "1 short animated clip"


def test_breakdown_fits_the_plan_card():
    card = {"contract": 1, "kind": "plan", "message": "m", "markdown": "x",
            "estimate": {**estimate.breakdown(9000, 3, True), "minutes": 3, "chapters": 2}}
    assert contract.problems("card", card) == []


def test_estimate_json_command(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(keys, "get", lambda *a, **k: None)
    assert cli.main(["estimate", str(tmp_path), "--chapters", "2", "--minutes", "3", "--clips", "1", "--music", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["usd"] == estimate.gemini_usd(1, True)
    assert out["items"][0] == {"label": "Narration (free voice)", "usd": 0}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_estimate_status.py`
Expected: FAIL (`AttributeError: ... 'breakdown'`).

- [ ] **Step 3: Implement**

`estimate.py`, append:

```python
def breakdown(chars: int, clips: int, music: bool, paid_voice: bool = True) -> dict:
    """The plan card's estimate as data: the dollar total and one line per part (the same numbers as `report`)."""
    clip_usd = config.VEO_SECONDS * config.VEO_PRICE_PER_SECOND
    items = [{"label": "Narration (ElevenLabs)", "usd": 0, "detail": f"about {chars:,} characters of your ElevenLabs plan"}
             if paid_voice else {"label": "Narration (free voice)", "usd": 0}]
    if music:
        items.append({"label": "Background music", "usd": round(config.LYRIA_PRICE, 2)})
    if clips:
        items.append({"label": f"{clips} short animated clip{'' if clips == 1 else 's'}", "usd": round(clips * clip_usd, 2),
                      "detail": f"{config.VEO_SECONDS:g} seconds each"})
    return {"usd": gemini_usd(clips, music), "items": items}
```

`cli.py`: after the `--music` argument add
`e.add_argument("--json", action="store_true", help="print the plan card's estimate (total and parts) as JSON")`,
and the handler becomes:

```python
    if args.cmd == "estimate":
        chars = estimate.plan_chars(args.chapters, args.minutes) if args.chapters else estimate.chars_in_scripts(args.work)
        paid = bool(keys.get("ELEVENLABS_API_KEY", required=False))
        if args.json:
            import json
            print(json.dumps(estimate.breakdown(chars, args.clips, args.music, paid_voice=paid)))
        else:
            print(estimate.report(chars, args.clips, args.music, paid_voice=paid))
        return 0
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/estimate.py lesson-videos/scripts/lv/cli.py tests/test_estimate_status.py
git commit -m "lesson-videos: estimate --json gives the plan card its cost items"
```

### Task C2: Slide count from `ingest` to every card

**Files:**
- Modify: `lesson-videos/scripts/lv/ingest.py`, `lesson-videos/scripts/lv/worker.py`
- Test: `tests/test_ingest.py`, `tests/test_worker.py`

**Interfaces:**
- Produces: `<WORK>/deck/deck.json` = `{"slides": N}`; `worker._with_slides(card: dict, folder: Path) -> dict`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ingest.py` (append; import `read_json` from `lv.util`):

```python
def test_ingest_writes_the_slide_count(tmp_path):
    deck = tmp_path / "deck.pptx"
    make_pptx(deck)
    out = ingest.ingest(deck, tmp_path / "work")
    assert read_json(out / "deck.json") == {"slides": 2}
```

`tests/test_worker.py` (append):

```python
def _with_deck_json(slides):
    def write(cwd):
        f = cwd / "lesson-videos" / "_work" / "deck" / "deck.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        write_json(f, {"slides": slides})
    return write


def test_worker_adds_the_slide_count_to_the_card(paired, lessons):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(QUESTIONS, also=_with_deck_json(9))) == 0
    assert paired.finished == [("trn_0123456789abcdefghijkl", {**QUESTIONS, "slides": 9})]


@pytest.mark.parametrize("slides", [0, 501, "9", None])
def test_worker_skips_a_slide_count_that_doesnt_fit(paired, lessons, slides):
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK
    assert worker.run_once(claude=_claude_writing(QUESTIONS, also=_with_deck_json(slides))) == 0
    assert paired.finished == [("trn_0123456789abcdefghijkl", QUESTIONS)]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_ingest.py tests/test_worker.py`
Expected: FAIL.

- [ ] **Step 3: Implement**

`ingest.py`: import `write_json` from `.util` (beside `write_text`), and after `write_text(out / "slides.md", …)` add
`write_json(out / "deck.json", {"slides": len(slides)})`.

`worker.py`, add near `_publish`:

```python
def _with_slides(card: dict, folder: Path) -> dict:
    """Add the deck's slide count (written by ingest) to a card that has none, for the website's lesson header."""
    f = folder / "lesson-videos" / "_work" / "deck" / "deck.json"
    if "slides" in card or not f.is_file():
        return card
    try:
        n = read_json(f).get("slides")
    except (OSError, ValueError, AttributeError):
        return card
    return {**card, "slides": n} if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 500 else card
```

In `_run_turn`, in the `else:` branch after `card = _claude_turn(turn, folder, sitedir, log, claude)`, add
`card = _with_slides(card, folder)`. (`read_json` is already imported in `worker.py`; add it to the
`from .util import …` line if not.)

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/ingest.py lesson-videos/scripts/lv/worker.py tests/test_ingest.py tests/test_worker.py
git commit -m "lesson-videos: ingest records the slide count; the worker adds it to each card"
```

### Task C3: Progress fraction from `[a/b]`

**Files:**
- Modify: `lesson-videos/scripts/lv/worker.py`, `tests/site_fake.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Produces: `worker._progress(f: Path) -> tuple[str, float | None]`; heartbeat body `{"progress": str}` plus
  `"fraction": float` when the line ends with a valid ` [a/b]`.

- [ ] **Step 1: Write the failing tests**

In `tests/site_fake.py`, record whole heartbeat bodies: add `self.heartbeat_bodies = []` in `__init__`, and in the
heartbeat branch:

```python
                    if action == "heartbeat":
                        body = json.loads(self._body())
                        site.heartbeats.append((tid, body["progress"]))
                        site.heartbeat_bodies.append(body)
                        return self._send(204)
```

`tests/test_worker.py` (append):

```python
@pytest.mark.parametrize("line,text,fraction", [
    ("Narrating scenes [3/12]", "Narrating scenes", 0.25),
    ("Rendering chapter 1 [1/1]", "Rendering chapter 1", 1.0),
    ("Starting [0/4]", "Starting", 0.0),
    ("Narrating [5/3]", "Narrating [5/3]", None),
    ("Narrating [0/0]", "Narrating [0/0]", None),
    ("Narrating [a/b]", "Narrating [a/b]", None),
    ("Reading the deck", "Reading the deck", None),
])
def test_progress_line_and_fraction(tmp_path, line, text, fraction):
    f = tmp_path / "progress.txt"
    write_text(f, f"Starting\n{line}\n")
    assert worker._progress(f) == (text, fraction)


def test_heartbeat_sends_the_fraction(paired, lessons, monkeypatch):
    monkeypatch.setattr(worker, "HEARTBEAT", 0.05)
    paired.turns.append(_turn())
    paired.files["fil_0123456789abcdefghijkl"] = DECK

    def slow(cwd):
        import time
        write_text(cwd / "site" / "progress.txt", "Reading the deck\nNarrating scenes [3/12]\n")
        time.sleep(0.3)
    assert worker.run_once(claude=_claude_writing(QUESTIONS, also=slow)) == 0
    assert {"progress": "Narrating scenes", "fraction": 0.25} in paired.heartbeat_bodies
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_worker.py`
Expected: FAIL (`AttributeError: ... '_progress'`).

- [ ] **Step 3: Implement** (`worker.py`; add `import re` at the top if missing)

```python
_COUNT = re.compile(r"^(.*?)\s*\[(\d+)/(\d+)\]\s*$")


def _progress(f: Path) -> tuple[str, float | None]:
    """The last progress line for the website, and its share done when it ends with ` [done/total]`."""
    line = _last_line(f)
    m = _COUNT.match(line)
    if m and int(m.group(3)) > 0 and int(m.group(2)) <= int(m.group(3)) and m.group(1).strip():
        return m.group(1).strip(), int(m.group(2)) / int(m.group(3))
    return line, None
```

`_Heartbeat.run` sends:

```python
                text, fraction = _progress(self.progress)
                body = {"progress": text} if fraction is None else {"progress": text, "fraction": fraction}
                site.call(f"/api/device/turns/{self.turn_id}/heartbeat", body)
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS (including the old `test_heartbeat_sends_the_progress_line`).

- [ ] **Step 5: Commit**

```bash
git add lesson-videos/scripts/lv/worker.py tests/site_fake.py tests/test_worker.py
git commit -m "lesson-videos: a progress line ending in [done/total] becomes the website's progress bar"
```

### Task C4: Make skill site mode, version 0.6.0, merge and publish

**Files:**
- Modify: `lesson-videos/skills/make/SKILL.md` (Site mode)
- Modify: `lesson-videos/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `lesson-videos/scripts/lv/__init__.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_skills.py`, reading the make skill the way the
  neighbouring site-mode tests do)

```python
def test_site_mode_sends_the_new_card_details():
    text = (PLUGIN / "skills" / "make" / "SKILL.md").read_text(encoding="utf-8")
    site = text.split("## Site mode (slide2video.com)", 1)[1]
    assert '--json' in site and '"items"' in site          # cost items from estimate --json
    assert '"recommended": true' in site                   # Claude's suggested option
    assert "issue-1" in site                               # possible-issue question ids
    assert "[3/12]" in site                                # counted progress lines
```

(If `PLUGIN` isn't imported in `test_skills.py`, add `from conftest import PLUGIN`.)

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest -q tests/test_skills.py -k new_card_details`
Expected: FAIL.

- [ ] **Step 3: Edit the skill's Site mode section**

- **Progress** rule: append the sentence: "When a step counts through items (scenes narrated, chapters rendered),
  end the line with ` [done/total]`, for example `Narrating scenes [3/12]`; the website shows it as a progress bar."
- In the `answer` row's card column, replace ``estimate` = `{"usd": <total>, "minutes": <per video>, "chapters": <N>}``
  with: ``estimate` = the JSON that `LV estimate "WORK" --chapters <N> --minutes <M> --clips <K> [--music] --json`
  prints (`"usd"` and `"items"`), plus `"minutes": <per video>` and `"chapters": <N>``. Make the same change where the
  `change` turn re-runs `estimate`.
- In the `start` row's card column, after "plus one question per possible issue in the slides (follow the slide /
  follow the correction / leave it out)", add: "Give the possible-issue questions the ids `issue-1`, `issue-2`, …".
- In the `"questions"` bullet under "Card formats", append: "Mark the option you'd choose by default with
  `"recommended": true` (at most one per question); the website shows it as Claude's suggestion and never picks it for
  the teacher."
- In the example questions card, add `, "recommended": true` to the `"Grades 6–8"` option.

- [ ] **Step 4: Bump the version to 0.6.0** in `lesson-videos/.claude-plugin/plugin.json`, the `lesson-videos` entry of
  `.claude-plugin/marketplace.json`, and `lesson-videos/scripts/lv/__init__.py`.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest -q`
Expected: PASS (including `tests/test_packaging.py`).

- [ ] **Step 6: Commit, merge and publish** (only after Task B13 is done: the site must already accept the fields)

```bash
git add lesson-videos .claude-plugin tests/test_skills.py
git commit -m "lesson-videos 0.6.0: site mode sends cost items, suggested answers, counted progress and slide count"
git checkout main && git pull --ff-only && git merge --no-ff slide2video-design-pass -m "Merge lesson-videos 0.6.0 (slide2video design pass: four details for the website)"
uv run pytest -q
git push origin main && git branch -d slide2video-design-pass
```

Expected: tests pass on `main`; push succeeds.
