# slide2video M1-B (the website) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy slide2video.com for M1: invited teachers sign in with an emailed code, upload a deck,
answer Claude's cards, and watch and download the chapters their own Mac made (the Mac runs `worker --once` by
hand in M1).

**Architecture:** One Cloudflare Worker (Hono) serves server-rendered pages, a teacher JSON API and the device
API. Cloudflare Access sits in front of everything except `/api/device/*`, `/terms`, `/privacy`, `/app.css`;
the Worker verifies the Access JWT itself. D1 holds teachers, devices, lessons, files, turns, cards and events;
R2 holds files under `t/<teacher>/<lesson>/…`. The job contract (JSON Schemas) is a pinned copy of
`plugins/lesson-videos/site-contract/`.

**Tech Stack:** TypeScript, Hono, jose (JWT), @cfworker/json-schema (validation without eval), fflate (export
zip), Wrangler 4, Vitest 4.1 + @cloudflare/vitest-plugin (local D1/R2).

**Spec:** `plugins/docs/superpowers/specs/2026-10-13-lesson-videos-site-design.md` (§4, §5, §7, §9, §10, §11 M1).
The plugin side is `plugins/docs/superpowers/plans/2026-10-13-slide2video-m1a-plugin.md`; its Global
Constraints table "Device API this plan calls" is the contract this plan must serve exactly.

## Global Constraints

- New repo `~/Projects/slide2video` (GitHub `DanielLandi/slide2video`, **private**). Creating the GitHub repo,
  Cloudflare resources and deploying are outside the worktree: **stop and ask Daniel before each of them**
  (Task 1 step 1, Task 9).
- The repo's `AGENTS.md` declares **Tier B** (branch, `npm test` gate, merge to `main`, push), the same as
  `plugins`, unless Daniel picks another tier when the repo is created.
- Gate: `npm test` (Vitest). `npm run check` (tsc) must also pass before each commit.
- Contract version **1**: device calls must send `X-LV-Contract: 1`; anything else → **426**
  `{"error": "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos"}`.
- Ids: `tch_`, `dev_`, `les_`, `fil_`, `trn_`, `crd_` + 22 base62 chars. Device tokens: `s2v_` + base64url of 32
  random bytes, stored only as SHA-256 hex.
- Every teacher query is scoped by `teacher_id`; every device query by the device's `teacher_id`.
- State-changing teacher API calls (`POST`/`PUT`/`DELETE` under `/api/`, not `/api/device/`) require header
  `X-S2V: 1` (CSRF guard; cross-site forms can't set it).
- Uploads: `.pptx`, `.pdf` (deck); `.pptx`, `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg` (extra); ≤ 100 MB; names
  cleaned. Device uploads: `out/ch<N>/v<K>/<name>` with `.mp4`, `.vtt`, `.jpg`, `.jpeg`, `.png`, `.json`.
- Only video is served `inline`; everything else `attachment`. Headers on every response: CSP
  `default-src 'self'; img-src 'self' data: blob:; media-src 'self'; script-src 'self'; style-src 'self';
  frame-ancestors 'none'; base-uri 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`.
- Lease 1800 s. Pairing codes `XXX-XXX` from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, valid 600 s; 5 wrong entries per
  teacher per hour; 10 `pair/start` per IP per hour.
- No secrets in the repo: `CF_API_TOKEN` is a Worker secret; local dev uses `.dev.vars` (gitignored) with
  `DEV_EMAIL`, honoured only on `localhost`/`127.0.0.1`.

## Review Focus

1. **Cross-teacher access** through any id in a URL or body (lesson, file path, device, card action, admin
   route by a non-admin) must answer 404/403 and change nothing; Task 4/5/6/7 tests try each route as teacher B.
2. **A turn claimed by one Mac, finished by another** (or by a device of another teacher) must get 409 and leave
   the turn untouched (Task 5).
3. **A lease that ran out** (Mac asleep) must make the turn claimable again by the home Mac, and the late
   heartbeat/finish from the old claim must be refused once someone else holds it (Task 5).
4. **HTML injection** through a lesson title, card message, question text/option, plan markdown or file name must
   render as text (Task 8 test with `<script>` and `"><img onerror>`).
5. **Account deletion with lessons on a Mac** must still let that Mac pick up the delete turns (retiring device),
   then remove the teacher completely (Task 6).

---

## File Structure (`~/Projects/slide2video`)

| File | Responsibility |
|---|---|
| `package.json`, `tsconfig.json`, `wrangler.jsonc`, `vitest.config.ts`, `.gitignore`, `.dev.vars.example` | project setup |
| `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md`), `README.md` | repo docs |
| `migrations/0001_init.sql` | D1 schema |
| `contract/` | pinned copy of `plugins/lesson-videos/site-contract/` (`contract.json`, `schemas/`, `examples/`) |
| `src/env.ts` | `Env`, `Teacher`, `Device`, `AppEnv` types |
| `src/util.ts` | ids, tokens, hashing, time |
| `src/http.ts` | security headers, `html` escaping template, `cleanName` |
| `src/contract.ts` | `CONTRACT_VERSION`, `cardProblems`, `turnProblems` |
| `src/auth.ts` | Access JWT verification, `teacherAuth`, `isAdmin` |
| `src/files.ts` | streaming uploads to R2 with SHA-256, range downloads |
| `src/turns.ts` | queue, claim, lease, turn JSON, lesson state |
| `src/device.ts` | `/api/device/*` |
| `src/teacher-api.ts` | `/api/lessons/*`, `/api/devices/*`, `/api/account/*`, `/api/admin/*` |
| `src/deletion.ts` | lesson/account deletion, tombstones, R2 purge |
| `src/access.ts` | Access group sync (admin invites) |
| `src/export.ts` | account export zip |
| `src/pages.ts`, `src/client.ts`, `src/legal.ts` | HTML pages, `/app.js` + `/app.css`, Terms/Privacy text |
| `src/index.ts` | the Hono app |
| `test/…` | helpers, keys, migrations setup, one test file per area |

---

### Task 1: Repo, scaffold, schema, test harness, security headers

**Files:**
- Create: everything in the "project setup" and "repo docs" rows, `migrations/0001_init.sql`, `contract/…`,
  `src/env.ts`, `src/util.ts`, `src/http.ts`, `src/contract.ts`, `src/index.ts` (minimal),
  `test/apply-migrations.ts`, `test/env.d.ts`, `test/keys/private.json`, `test/keys/public-jwks.json`,
  `test/helpers.ts`, `test/scaffold.test.ts`

**Interfaces:**
- Produces: `newId(prefix)`, `randomToken()`, `sha256Hex(data)`, `hex(buf)`, `now()` (seconds);
  `securityHeaders` middleware; `html` tagged template + `raw()`; `cleanName(name) -> string | null`;
  `CONTRACT_VERSION`, `UPDATE_PLUGIN`, `cardProblems(card) -> string[]`, `turnProblems(turn) -> string[]`;
  test helpers `BASE`, `accessToken(email, opts?)`, `asTeacher(email, path, init?)`, `seedTeacher(email?)`,
  `asDevice(token, path, init?, contract?)`, `uniqueEmail()`.

- [ ] **Step 1: Create the repo folder (ask before GitHub)**

```bash
mkdir -p ~/Projects/slide2video && cd ~/Projects/slide2video && git init -b main
```

Ask Daniel: "Create the private GitHub repo DanielLandi/slide2video now?" Only on yes:
`gh repo create DanielLandi/slide2video --private --source . --remote origin`.

- [ ] **Step 2: Install the toolchain**

```bash
npm init -y
npm install hono jose @cfworker/json-schema fflate
npm install -D wrangler typescript @cloudflare/workers-types vitest@^4.1 @cloudflare/vitest-plugin
```

Then set `package.json` fields (keep the installed versions it wrote):

```json
{
  "name": "slide2video",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "wrangler dev",
    "test": "vitest run",
    "check": "tsc --noEmit",
    "deploy": "wrangler deploy",
    "db:local": "wrangler d1 migrations apply slide2video --local"
  }
}
```

- [ ] **Step 3: Config files**

`wrangler.jsonc`:

```jsonc
{
  "name": "slide2video",
  "main": "src/index.ts",
  "compatibility_date": "2026-10-01",
  "compatibility_flags": ["nodejs_compat"],
  "routes": [{ "pattern": "slide2video.com", "custom_domain": true }],
  "d1_databases": [
    // database_id is set in Task 9 from `wrangler d1 create`; this all-zero id only serves local dev and tests.
    { "binding": "DB", "database_name": "slide2video", "database_id": "00000000-0000-0000-0000-000000000000",
      "migrations_dir": "migrations" }
  ],
  "r2_buckets": [{ "binding": "FILES", "bucket_name": "slide2video-files" }],
  "vars": {
    "SITE_URL": "https://slide2video.com",
    "ACCESS_TEAM_DOMAIN": "",
    "ACCESS_AUD": "",
    "ADMIN_EMAIL": "",
    "CF_ACCOUNT_ID": "",
    "ACCESS_GROUP_ID": ""
  }
}
```

`tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "es2022", "module": "es2022", "moduleResolution": "bundler", "strict": true,
    "resolveJsonModule": true, "noEmit": true, "skipLibCheck": true,
    "lib": ["es2022", "webworker"],
    "types": ["@cloudflare/workers-types", "@cloudflare/vitest-plugin"]
  },
  "include": ["src", "test"]
}
```

`vitest.config.ts`:

```ts
import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vitest/config";
import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { readD1Migrations } from "@cloudflare/vitest-plugin/config";

export default defineConfig(async () => {
  const migrations = await readD1Migrations(path.join(__dirname, "migrations"));
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.jsonc" },
        miniflare: {
          bindings: {
            TEST_MIGRATIONS: migrations,
            ACCESS_JWKS: fs.readFileSync(path.join(__dirname, "test/keys/public-jwks.json"), "utf8"),
            ACCESS_TEAM_DOMAIN: "https://test.cloudflareaccess.com",
            ACCESS_AUD: "test-aud",
            ADMIN_EMAIL: "admin@example.org",
            SITE_URL: "https://slide2video.test",
          },
        },
      }),
    ],
    test: { setupFiles: ["./test/apply-migrations.ts"] },
  };
});
```

If the installed `@cloudflare/vitest-plugin` exposes these under different names, follow its README for the
same three things (wrangler config path, extra bindings, a setup file) and note the change in the ledger.

`.gitignore`: `node_modules/`, `.wrangler/`, `.dev.vars`, `coverage/`.
`.dev.vars.example`: `DEV_EMAIL=you@example.org` (with a comment: copy to `.dev.vars`; only honoured on
localhost).

- [ ] **Step 4: Repo docs**

`AGENTS.md`:

```markdown
# slide2video

The website at https://slide2video.com for the `lesson-videos` plugin (repo `DanielLandi/plugins`): invited
teachers upload slide decks, answer Claude's questions and watch the videos their **own Mac** made. The site never
runs Claude. Design: `plugins/docs/superpowers/specs/2026-10-13-lesson-videos-site-design.md`.

## Contribution flow

**Tier B**: short-lived branch off `main`, `npm run check && npm test`, merge to `main`, push. Deploy with
`npm run deploy` only when Daniel asks.

## Paired repo: plugins

`contract/` is a pinned copy of `plugins/lesson-videos/site-contract/`. Change the contract there first, bump its
version if the change isn't backwards compatible, then copy it here (`contract/contract.json` records the plugin
version it came from). Device calls carry `X-LV-Contract`; a mismatch answers 426.

## Rules

- Teacher-made material only: never student information. Never log file contents or tokens.
- Every query is scoped to the signed-in teacher (or the device's teacher). Add a cross-teacher test for every
  new route.
- Secrets live in Wrangler secrets / `.dev.vars` (gitignored), never in the repo.
- Terms and Privacy (`src/legal.ts`) are drafts until reviewed by the district or a lawyer.

## Build & test

npm install · npm run check · npm test · npm run dev (local, uses .dev.vars and a local D1: npm run db:local)
```

`CLAUDE.md`: `@AGENTS.md`. `README.md`: two lines (what it is, see AGENTS.md).

- [ ] **Step 5: Schema**

`migrations/0001_init.sql`:

```sql
CREATE TABLE teachers (
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, deleted_at INTEGER
);
CREATE TABLE devices (
  id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL REFERENCES teachers(id), name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, last_seen INTEGER, revoked_at INTEGER,
  retiring INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE pair_codes (
  device_code TEXT PRIMARY KEY, user_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, ip TEXT,
  created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, teacher_id TEXT, confirmed_at INTEGER
);
CREATE TABLE lessons (
  id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL REFERENCES teachers(id), title TEXT NOT NULL,
  instructions TEXT, attested_at INTEGER, home_device_id TEXT, created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL, deleted_at INTEGER
);
CREATE INDEX lessons_teacher ON lessons(teacher_id);
CREATE TABLE files (
  id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL, lesson_id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
  path TEXT NOT NULL, r2_key TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
  content_type TEXT NOT NULL, created_at INTEGER NOT NULL, UNIQUE (lesson_id, path)
);
CREATE TABLE turns (
  id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL, lesson_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL,
  input TEXT NOT NULL DEFAULT '{}', state TEXT NOT NULL DEFAULT 'queued', device_id TEXT, lease_until INTEGER,
  not_before INTEGER, progress TEXT, created_at INTEGER NOT NULL, finished_at INTEGER
);
CREATE INDEX turns_queue ON turns(teacher_id, state, created_at);
CREATE TABLE cards (
  id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL, lesson_id TEXT NOT NULL, turn_id TEXT NOT NULL, kind TEXT NOT NULL,
  body TEXT NOT NULL, created_at INTEGER NOT NULL, answered_at INTEGER
);
CREATE INDEX cards_lesson ON cards(lesson_id, created_at);
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id TEXT, kind TEXT NOT NULL, detail TEXT, created_at INTEGER NOT NULL
);
```

- [ ] **Step 6: Contract copy**

Requires M1-A Task 1 merged or on its branch in `~/Projects/plugins`:

```bash
mkdir -p contract && cp -R ~/Projects/plugins/lesson-videos/site-contract/{contract.json,schemas,examples} contract/
```

Then edit `contract/contract.json` to `{"version": 1, "from": "lesson-videos 0.5.0"}`.

- [ ] **Step 7: Test keys**

Generate an RSA key pair for signing fake Access tokens in tests (test-only, safe to commit):

```bash
node --input-type=module -e '
import { generateKeyPair, exportJWK } from "jose"; import fs from "node:fs";
const { publicKey, privateKey } = await generateKeyPair("RS256", { extractable: true });
const kid = "test-key-1";
fs.mkdirSync("test/keys", { recursive: true });
fs.writeFileSync("test/keys/private.json", JSON.stringify({ ...(await exportJWK(privateKey)), kid, alg: "RS256" }));
fs.writeFileSync("test/keys/public-jwks.json", JSON.stringify({ keys: [{ ...(await exportJWK(publicKey)), kid, alg: "RS256", use: "sig" }] }));'
```

- [ ] **Step 8: Core modules**

`src/env.ts`:

```ts
export interface Env {
  DB: D1Database;
  FILES: R2Bucket;
  SITE_URL: string;
  ACCESS_TEAM_DOMAIN: string;
  ACCESS_AUD: string;
  ACCESS_JWKS?: string; // tests only: a local key set instead of the team's certs
  ADMIN_EMAIL: string;
  CF_API_TOKEN?: string;
  CF_ACCOUNT_ID?: string;
  ACCESS_GROUP_ID?: string;
  DEV_EMAIL?: string; // local dev only, honoured on localhost
}
export type Teacher = { id: string; email: string };
export type Device = { id: string; teacher_id: string; name: string; retiring: number };
export type AppEnv = { Bindings: Env; Variables: { teacher: Teacher; device: Device } };
```

`src/util.ts`:

```ts
const B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

export function newId(prefix: string): string {
  let s = "";
  for (const b of crypto.getRandomValues(new Uint8Array(22))) s += B62[b % 62];
  return `${prefix}_${s}`;
}

export function randomToken(): string {
  const b = crypto.getRandomValues(new Uint8Array(32));
  return "s2v_" + btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function hex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(data: string | ArrayBuffer | Uint8Array): Promise<string> {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  return hex(await crypto.subtle.digest("SHA-256", bytes));
}

export const now = (): number => Math.floor(Date.now() / 1000);
```

`src/http.ts`:

```ts
import type { MiddlewareHandler } from "hono";
import type { AppEnv } from "./env";

export const CSP =
  "default-src 'self'; img-src 'self' data: blob:; media-src 'self'; script-src 'self'; style-src 'self'; " +
  "frame-ancestors 'none'; base-uri 'none'; form-action 'self'";

export const securityHeaders: MiddlewareHandler<AppEnv> = async (c, next) => {
  await next();
  const h = c.res.headers;
  h.set("Content-Security-Policy", CSP);
  h.set("X-Content-Type-Options", "nosniff");
  h.set("Referrer-Policy", "no-referrer");
  h.set("X-Frame-Options", "DENY");
};

export class Raw {
  constructor(public readonly s: string) {}
  toString() { return this.s; }
}
export const raw = (s: string) => new Raw(s);

const ESC: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v: unknown): string => String(v ?? "").replace(/[&<>"']/g, (ch) => ESC[ch]);

/** Template that escapes every interpolation unless it is Raw (or an array of Raw). */
export function html(strings: TemplateStringsArray, ...vals: unknown[]): Raw {
  let out = strings[0];
  vals.forEach((v, i) => {
    const part = Array.isArray(v) ? v.map((x) => (x instanceof Raw ? x.s : esc(x))).join("") : v instanceof Raw ? v.s : esc(v);
    out += part + strings[i + 1];
  });
  return new Raw(out);
}

/** A safe file name: no folders, no control or reserved characters, no leading dots, at most 200 chars. */
export function cleanName(name: string): string | null {
  const base = (name.split(/[\\/]/).pop() ?? "").normalize("NFC")
    .replace(/[\x00-\x1f<>:"|?*]/g, "-").trim().replace(/^\.+/, "").slice(0, 200);
  return base || null;
}
```

`src/contract.ts`:

```ts
import { Validator } from "@cfworker/json-schema";
import cardSchema from "../contract/schemas/card.schema.json";
import turnSchema from "../contract/schemas/turn.schema.json";
import contract from "../contract/contract.json";

export const CONTRACT_VERSION: number = contract.version;
export const UPDATE_PLUGIN = "Update the lesson-videos plugin on this Mac: run /plugin update lesson-videos";

const card = new Validator(cardSchema as object, "2020-12", false);
const turn = new Validator(turnSchema as object, "2020-12", false);

const problems = (v: Validator, obj: unknown): string[] => {
  const r = v.validate(obj);
  return r.valid ? [] : r.errors.map((e) => `${e.instanceLocation}: ${e.error}`);
};
export const cardProblems = (obj: unknown) => problems(card, obj);
export const turnProblems = (obj: unknown) => problems(turn, obj);
```

`src/index.ts` (minimal; later tasks grow it):

```ts
import { Hono } from "hono";
import type { AppEnv } from "./env";
import { securityHeaders } from "./http";

const app = new Hono<AppEnv>();
app.use("*", securityHeaders);
app.get("/health", (c) => c.text("ok"));
export default app;
```

- [ ] **Step 9: Test harness**

`test/apply-migrations.ts`:

```ts
import { applyD1Migrations } from "cloudflare:test";
import { env } from "cloudflare:workers";

await applyD1Migrations(env.DB, env.TEST_MIGRATIONS);
```

`test/env.d.ts`:

```ts
import type { D1Migration } from "cloudflare:test";
import type { Env as AppBindings } from "../src/env";

declare global {
  namespace Cloudflare {
    interface Env extends AppBindings {
      TEST_MIGRATIONS: D1Migration[];
    }
  }
}
```

`test/helpers.ts`:

```ts
import { SignJWT, importJWK, type JWK } from "jose";
import { env, exports } from "cloudflare:workers";
import privateJwk from "./keys/private.json";

export const BASE = "https://slide2video.test";

export const uniqueEmail = () => `t-${crypto.randomUUID().slice(0, 8)}@example.org`;

export async function accessToken(email: string, opts: { aud?: string; iss?: string; exp?: string | number } = {}) {
  const key = await importJWK(privateJwk as JWK, "RS256");
  return new SignJWT({ email })
    .setProtectedHeader({ alg: "RS256", kid: (privateJwk as JWK).kid })
    .setIssuer(opts.iss ?? env.ACCESS_TEAM_DOMAIN)
    .setAudience(opts.aud ?? env.ACCESS_AUD)
    .setIssuedAt()
    .setExpirationTime(opts.exp ?? "1h")
    .sign(key);
}

export async function seedTeacher(email = uniqueEmail()): Promise<{ id: string; email: string }> {
  const id = "tch_" + crypto.randomUUID().replace(/-/g, "").slice(0, 22);
  await env.DB.prepare("INSERT INTO teachers (id, email, created_at) VALUES (?, ?, 0)").bind(id, email).run();
  return { id, email };
}

export async function asTeacher(email: string, path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Cf-Access-Jwt-Assertion", await accessToken(email));
  if (init.method && init.method !== "GET") headers.set("X-S2V", "1");
  if (typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init.body instanceof Uint8Array) headers.set("Content-Length", String(init.body.byteLength));
  return exports.default.fetch(new Request(BASE + path, { ...init, headers }));
}

export function asDevice(token: string | null, path: string, init: RequestInit = {}, contract = "1"): Promise<Response> {
  const headers = new Headers(init.headers);
  if (contract) headers.set("X-LV-Contract", contract);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init.body instanceof Uint8Array) headers.set("Content-Length", String(init.body.byteLength));
  return exports.default.fetch(new Request(BASE + path, { ...init, headers }));
}
```

- [ ] **Step 10: Write the failing scaffold tests**

`test/scaffold.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env, exports } from "cloudflare:workers";
import { cardProblems, turnProblems, CONTRACT_VERSION } from "../src/contract";
import { cleanName, html } from "../src/http";
import { newId, randomToken } from "../src/util";
import contract from "../contract/contract.json";

const examples = import.meta.glob("../contract/examples/*.json", { eager: true, import: "default" });

describe("scaffold", () => {
  it("serves health with security headers", async () => {
    const r = await exports.default.fetch("https://slide2video.test/health");
    expect(await r.text()).toBe("ok");
    expect(r.headers.get("Content-Security-Policy")).toContain("frame-ancestors 'none'");
    expect(r.headers.get("X-Content-Type-Options")).toBe("nosniff");
  });

  it("has the schema", async () => {
    const t = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='turns'").first();
    expect(t).toBeTruthy();
  });

  it("validates the pinned contract examples", () => {
    expect(CONTRACT_VERSION).toBe(contract.version);
    for (const [path, ex] of Object.entries(examples)) {
      const name = path.split("/").pop()!;
      if (name.startsWith("card-")) expect(cardProblems(ex), name).toEqual([]);
      if (name.startsWith("turn-")) expect(turnProblems(ex), name).toEqual([]);
    }
    expect(cardProblems({ contract: 1, kind: "plan", message: "x" }).length).toBeGreaterThan(0);
  });

  it("makes ids and tokens", () => {
    expect(newId("les")).toMatch(/^les_[0-9A-Za-z]{22}$/);
    expect(randomToken()).toMatch(/^s2v_[A-Za-z0-9_-]{43}$/);
  });

  it("escapes html and cleans names", () => {
    expect(html`<p>${'<script>"x"</script>'}</p>`.s).toBe("<p>&lt;script&gt;&quot;x&quot;&lt;/script&gt;</p>");
    expect(cleanName("../../etc/passwd")).toBe("passwd");
    expect(cleanName("..hidden.pptx")).toBe("hidden.pptx");
    expect(cleanName("a:b?.pdf")).toBe("a-b-.pdf");
    expect(cleanName("///")).toBeNull();
  });
});
```

Run before Step 8's files exist to see it fail (e.g. by running this step first in practice): `npm test` —
Expected: FAIL (`Cannot find module '../src/contract'`). Then with Step 8 in place: `npm test` — Expected: PASS;
`npm run check` — Expected: no errors (fix `test/env.d.ts` to the plugin's declared env type if tsc disagrees).

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "slide2video: scaffold (Worker, D1 schema, R2, contract copy, test harness, security headers)"
```

---

### Task 2: Sign-in (Access JWT), teachers, admin bootstrap, CSRF guard

**Files:**
- Create: `src/auth.ts`, `test/auth.test.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: `Env`, `AppEnv`, `Teacher`, `newId`, `now`, `html`.
- Produces: `accessEmail(req, env) -> Promise<string | null>`; `teacherAuth` middleware (sets `c.var.teacher`,
  401 without a valid token, 403 page when not invited, 403 JSON when `X-S2V` is missing on a state change);
  `isAdmin(c) -> boolean`; `logEvent(db, teacherId, kind, detail?)`.

- [ ] **Step 1: Write the failing tests**

`test/auth.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env, exports } from "cloudflare:workers";
import { BASE, accessToken, asTeacher, seedTeacher, uniqueEmail } from "./helpers";

const get = (path: string, headers: Record<string, string> = {}) =>
  exports.default.fetch(new Request(BASE + path, { headers }));

describe("sign-in", () => {
  it("refuses requests without an Access token", async () => {
    expect((await get("/")).status).toBe(401);
  });

  it("refuses tokens with the wrong audience, issuer or expiry", async () => {
    const t = await seedTeacher();
    for (const opts of [{ aud: "other" }, { iss: "https://evil.cloudflareaccess.com" }, { exp: Math.floor(Date.now() / 1000) - 60 }]) {
      const r = await get("/", { "Cf-Access-Jwt-Assertion": await accessToken(t.email, opts) });
      expect(r.status).toBe(401);
    }
  });

  it("shows a not-invited page to unknown emails", async () => {
    const r = await asTeacher(uniqueEmail(), "/");
    expect(r.status).toBe(403);
    expect(await r.text()).toContain("invited");
  });

  it("lets an invited teacher in", async () => {
    const t = await seedTeacher();
    expect((await asTeacher(t.email, "/")).status).toBe(200);
  });

  it("creates the admin on first sign-in", async () => {
    expect((await asTeacher("admin@example.org", "/")).status).toBe(200);
    const row = await env.DB.prepare("SELECT id FROM teachers WHERE email = 'admin@example.org'").first();
    expect(row).toBeTruthy();
  });

  it("treats a deleted teacher as not invited", async () => {
    const t = await seedTeacher();
    await env.DB.prepare("UPDATE teachers SET deleted_at = 1 WHERE id = ?").bind(t.id).run();
    expect((await asTeacher(t.email, "/")).status).toBe(403);
  });

  it("requires X-S2V on state changes", async () => {
    const t = await seedTeacher();
    const r = await exports.default.fetch(new Request(BASE + "/api/lessons", {
      method: "POST", body: "{}", headers: { "Cf-Access-Jwt-Assertion": await accessToken(t.email), "Content-Type": "application/json" },
    }));
    expect(r.status).toBe(403);
  });

  it("ignores DEV_EMAIL away from localhost", async () => {
    // DEV_EMAIL is not bound in tests; the code path is covered by checking the host rule in accessEmail
    const { accessEmail } = await import("../src/auth");
    const req = new Request("https://slide2video.com/");
    expect(await accessEmail(req, { ...env, DEV_EMAIL: "dev@example.org" })).toBeNull();
    expect(await accessEmail(new Request("http://localhost:8787/"), { ...env, DEV_EMAIL: "Dev@Example.org" })).toBe("dev@example.org");
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm test -- test/auth.test.ts` — Expected: FAIL (404s / module not found for `../src/auth`).

- [ ] **Step 3: Implement `src/auth.ts`**

```ts
import { createLocalJWKSet, createRemoteJWKSet, jwtVerify, type JWTVerifyGetKey } from "jose";
import type { Context, MiddlewareHandler } from "hono";
import type { AppEnv, Env, Teacher } from "./env";
import { html } from "./http";
import { newId, now } from "./util";

const remote = new Map<string, JWTVerifyGetKey>();

function keySet(env: Env): JWTVerifyGetKey {
  if (env.ACCESS_JWKS) return createLocalJWKSet(JSON.parse(env.ACCESS_JWKS));
  let ks = remote.get(env.ACCESS_TEAM_DOMAIN);
  if (!ks) {
    ks = createRemoteJWKSet(new URL(`${env.ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`));
    remote.set(env.ACCESS_TEAM_DOMAIN, ks);
  }
  return ks;
}

/** The signed-in email, verified against Cloudflare Access (signature, issuer, audience, expiry). */
export async function accessEmail(req: Request, env: Env): Promise<string | null> {
  const host = new URL(req.url).hostname;
  if (env.DEV_EMAIL && (host === "localhost" || host === "127.0.0.1")) return env.DEV_EMAIL.toLowerCase();
  const token = req.headers.get("Cf-Access-Jwt-Assertion");
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

export async function logEvent(db: D1Database, teacherId: string | null, kind: string, detail?: string) {
  await db.prepare("INSERT INTO events (teacher_id, kind, detail, created_at) VALUES (?, ?, ?, ?)")
    .bind(teacherId, kind, detail ?? null, now()).run();
}

const notInvited = (email: string) => html`<!doctype html><meta charset="utf-8"><title>Not invited</title>
<link rel="stylesheet" href="/app.css"><main><h1>slide2video</h1>
<p>${email} hasn't been invited yet. Ask the person who told you about slide2video to invite this address.</p></main>`;

export const teacherAuth: MiddlewareHandler<AppEnv> = async (c, next) => {
  const email = await accessEmail(c.req.raw, c.env);
  if (!email) return c.text("Sign in at slide2video.com.", 401);
  const db = c.env.DB;
  let t = await db.prepare("SELECT id, email FROM teachers WHERE email = ? AND deleted_at IS NULL").bind(email).first<Teacher>();
  if (!t && c.env.ADMIN_EMAIL && email === c.env.ADMIN_EMAIL.toLowerCase()) {
    t = { id: newId("tch"), email };
    await db.prepare("INSERT INTO teachers (id, email, created_at) VALUES (?, ?, ?)").bind(t.id, email, now()).run();
  }
  if (!t) return c.html(notInvited(email).s, 403);
  c.set("teacher", t);
  if (!["GET", "HEAD"].includes(c.req.method) && c.req.header("X-S2V") !== "1") {
    return c.json({ error: "Missing X-S2V header" }, 403);
  }
  await next();
};

export const isAdmin = (c: Context<AppEnv>) =>
  !!c.env.ADMIN_EMAIL && c.get("teacher").email === c.env.ADMIN_EMAIL.toLowerCase();
```

In `src/index.ts`, after the `/health` route:

```ts
import { teacherAuth } from "./auth";
// … public routes stay above this line …
app.use("*", teacherAuth);
app.get("/", (c) => c.html("<!doctype html><title>slide2video</title><p>Lessons</p>"));
```

(Task 8 replaces the `/` placeholder with the real page.)

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "slide2video: Access sign-in, invited teachers, admin bootstrap, CSRF guard"`

---

### Task 3: Pairing a Mac, device auth, contract check, teacher's Devices API

**Files:**
- Create: `src/device.ts`, `src/teacher-api.ts`, `test/pairing.test.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: `CONTRACT_VERSION`, `UPDATE_PLUGIN`, `randomToken`, `sha256Hex`, `newId`, `now`, `logEvent`,
  `teacherAuth`.
- Produces: Hono apps `device` (mounted at `/api/device`) and `teacherApi` (mounted at `/api`); device middleware
  sets `c.var.device`; routes `POST /api/device/pair/start`, `POST /api/device/pair/poll`,
  `GET /api/device/status`; `GET /api/devices`, `POST /api/devices/pair`, `DELETE /api/devices/:id`. Test
  helper added to `test/helpers.ts`: `pairDevice(email, name?) -> Promise<{ token: string; id: string }>`.

- [ ] **Step 1: Write the failing tests**

Append to `test/helpers.ts`:

```ts
export async function pairDevice(email: string, name = "Test Mac"): Promise<{ token: string; id: string }> {
  const start = await (await asDevice(null, "/api/device/pair/start", { method: "POST", body: JSON.stringify({ name }) })).json<any>();
  const ok = await asTeacher(email, "/api/devices/pair", { method: "POST", body: JSON.stringify({ user_code: start.user_code }) });
  if (ok.status !== 200) throw new Error(`pair failed ${ok.status}`);
  const got = await (await asDevice(null, "/api/device/pair/poll", { method: "POST", body: JSON.stringify({ device_code: start.device_code }) })).json<any>();
  const list = await (await asTeacher(email, "/api/devices")).json<any>();
  return { token: got.token, id: list.devices.find((d: any) => d.name === name).id };
}
```

`test/pairing.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { asDevice, asTeacher, pairDevice, seedTeacher } from "./helpers";

const post = (path: string, body: object, token: string | null = null, contract = "1") =>
  asDevice(token, path, { method: "POST", body: JSON.stringify(body) }, contract);

describe("pairing", () => {
  it("needs the contract header", async () => {
    const r = await post("/api/device/pair/start", { name: "Mac" }, null, "2");
    expect(r.status).toBe(426);
    expect((await r.json<any>()).error).toContain("/plugin update lesson-videos");
  });

  it("pairs: code → teacher enters it → token once", async () => {
    const t = await seedTeacher();
    const start = await (await post("/api/device/pair/start", { name: "Home iMac" })).json<any>();
    expect(start.user_code).toMatch(/^[A-HJ-NP-Z2-9]{3}-[A-HJ-NP-Z2-9]{3}$/);
    expect(start.expires_in).toBe(600);
    expect(start.verify_url).toBe("https://slide2video.test/devices");
    expect((await post("/api/device/pair/poll", { device_code: start.device_code })).status).toBe(428);
    const entered = await asTeacher(t.email, "/api/devices/pair", { method: "POST", body: JSON.stringify({ user_code: start.user_code.toLowerCase().replace("-", " ") }) });
    expect(entered.status).toBe(200);
    const got = await (await post("/api/device/pair/poll", { device_code: start.device_code })).json<any>();
    expect(got.teacher_email).toBe(t.email);
    expect(got.token).toMatch(/^s2v_/);
    expect((await post("/api/device/pair/poll", { device_code: start.device_code })).status).toBe(410);
    const row = await env.DB.prepare("SELECT token_hash FROM devices WHERE teacher_id = ?").bind(t.id).first<any>();
    expect(row.token_hash).not.toContain(got.token);
    const status = await (await asDevice(got.token, "/api/device/status")).json<any>();
    expect(status).toEqual({ teacher_email: t.email, device_name: "Home iMac", contract: 1 });
  });

  it("expires codes", async () => {
    const start = await (await post("/api/device/pair/start", { name: "Mac" })).json<any>();
    await env.DB.prepare("UPDATE pair_codes SET expires_at = 1 WHERE device_code = ?").bind(start.device_code).run();
    expect((await post("/api/device/pair/poll", { device_code: start.device_code })).status).toBe(410);
  });

  it("limits wrong code entries to 5 an hour", async () => {
    const t = await seedTeacher();
    for (let i = 0; i < 5; i++) {
      const r = await asTeacher(t.email, "/api/devices/pair", { method: "POST", body: JSON.stringify({ user_code: "AAA-AAA" }) });
      expect(r.status).toBe(404);
    }
    const r = await asTeacher(t.email, "/api/devices/pair", { method: "POST", body: JSON.stringify({ user_code: "AAA-AAA" }) });
    expect(r.status).toBe(429);
  });

  it("rejects bad and revoked tokens; revocation is per teacher", async () => {
    const a = await seedTeacher();
    const b = await seedTeacher();
    const dev = await pairDevice(a.email);
    expect((await asDevice("s2v_" + "x".repeat(43), "/api/device/status")).status).toBe(401);
    expect((await asTeacher(b.email, `/api/devices/${dev.id}`, { method: "DELETE" })).status).toBe(404);
    expect((await asDevice(dev.token, "/api/device/status")).status).toBe(200);
    expect((await asTeacher(a.email, `/api/devices/${dev.id}`, { method: "DELETE" })).status).toBe(204);
    expect((await asDevice(dev.token, "/api/device/status")).status).toBe(401);
  });

  it("lists only my devices, with last seen", async () => {
    const a = await seedTeacher();
    const b = await seedTeacher();
    await pairDevice(a.email, "A's Mac");
    await pairDevice(b.email, "B's Mac");
    const list = await (await asTeacher(a.email, "/api/devices")).json<any>();
    expect(list.devices.map((d: any) => d.name)).toEqual(["A's Mac"]);
  });
});
```

- [ ] **Step 2: Run to see it fail** — `npm test -- test/pairing.test.ts` — Expected: FAIL (404s).

- [ ] **Step 3: Implement**

`src/device.ts`:

```ts
import { Hono, type MiddlewareHandler } from "hono";
import type { AppEnv, Device } from "./env";
import { CONTRACT_VERSION, UPDATE_PLUGIN } from "./contract";
import { logEvent } from "./auth";
import { newId, now, randomToken, sha256Hex } from "./util";

export const device = new Hono<AppEnv>();
const CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
export const PAIR_SECONDS = 600;

const userCode = () => {
  const b = crypto.getRandomValues(new Uint8Array(6));
  const s = [...b].map((x) => CODE_CHARS[x % CODE_CHARS.length]).join("");
  return `${s.slice(0, 3)}-${s.slice(3)}`;
};

device.use("*", async (c, next) => {
  if (c.req.header("X-LV-Contract") !== String(CONTRACT_VERSION)) return c.json({ error: UPDATE_PLUGIN }, 426);
  await next();
});

device.post("/pair/start", async (c) => {
  const body = await c.req.json<{ name?: unknown }>().catch(() => ({}) as { name?: unknown });
  const name = typeof body.name === "string" && body.name.trim() ? body.name.trim().slice(0, 60) : "Mac";
  const ip = c.req.header("CF-Connecting-IP") ?? "local";
  const recent = await c.env.DB.prepare("SELECT COUNT(*) AS n FROM pair_codes WHERE ip = ? AND created_at > ?")
    .bind(ip, now() - 3600).first<{ n: number }>();
  if ((recent?.n ?? 0) >= 10) return c.json({ error: "Too many pairing attempts; try again in an hour." }, 429);
  const device_code = "dc_" + randomToken().slice(4);
  const user_code = userCode();
  await c.env.DB.prepare("INSERT INTO pair_codes (device_code, user_code, name, ip, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(device_code, user_code, name, ip, now(), now() + PAIR_SECONDS).run();
  return c.json({ user_code, device_code, expires_in: PAIR_SECONDS, verify_url: `${c.env.SITE_URL}/devices` });
});

device.post("/pair/poll", async (c) => {
  const { device_code } = await c.req.json<{ device_code?: string }>().catch(() => ({ device_code: undefined }));
  const db = c.env.DB;
  const row = await db.prepare("SELECT * FROM pair_codes WHERE device_code = ?").bind(device_code ?? "").first<any>();
  if (!row || row.expires_at < now()) {
    if (row) await db.prepare("DELETE FROM pair_codes WHERE device_code = ?").bind(row.device_code).run();
    return c.json({ error: "expired" }, 410);
  }
  if (!row.teacher_id) return c.json({ error: "pending" }, 428);
  const token = randomToken();
  const id = newId("dev");
  await db.batch([
    db.prepare("INSERT INTO devices (id, teacher_id, name, token_hash, created_at, last_seen) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(id, row.teacher_id, row.name, await sha256Hex(token), now(), now()),
    db.prepare("DELETE FROM pair_codes WHERE device_code = ?").bind(row.device_code),
  ]);
  const t = await db.prepare("SELECT email FROM teachers WHERE id = ?").bind(row.teacher_id).first<{ email: string }>();
  await logEvent(db, row.teacher_id, "device_paired", id);
  return c.json({ token, teacher_email: t!.email });
});

export const deviceAuth: MiddlewareHandler<AppEnv> = async (c, next) => {
  const m = (c.req.header("Authorization") ?? "").match(/^Bearer (s2v_[A-Za-z0-9_-]{20,})$/);
  if (!m) return c.json({ error: "unauthorized" }, 401);
  const d = await c.env.DB.prepare("SELECT id, teacher_id, name, retiring FROM devices WHERE token_hash = ? AND revoked_at IS NULL")
    .bind(await sha256Hex(m[1])).first<Device>();
  if (!d) return c.json({ error: "unauthorized" }, 401);
  await c.env.DB.prepare("UPDATE devices SET last_seen = ? WHERE id = ?").bind(now(), d.id).run();
  c.set("device", d);
  await next();
};
device.use("*", deviceAuth);

device.get("/status", async (c) => {
  const d = c.get("device");
  const t = await c.env.DB.prepare("SELECT email FROM teachers WHERE id = ?").bind(d.teacher_id).first<{ email: string }>();
  return c.json({ teacher_email: t!.email, device_name: d.name, contract: CONTRACT_VERSION });
});
```

`src/teacher-api.ts` (this task adds the devices routes; later tasks append):

```ts
import { Hono } from "hono";
import type { AppEnv } from "./env";
import { logEvent } from "./auth";
import { now } from "./util";

export const teacherApi = new Hono<AppEnv>();

teacherApi.get("/devices", async (c) => {
  const t = c.get("teacher");
  const { results } = await c.env.DB.prepare(
    "SELECT id, name, created_at, last_seen FROM devices WHERE teacher_id = ? AND revoked_at IS NULL ORDER BY created_at",
  ).bind(t.id).all();
  return c.json({ devices: results });
});

teacherApi.post("/devices/pair", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const fails = await db.prepare("SELECT COUNT(*) AS n FROM events WHERE teacher_id = ? AND kind = 'pair_fail' AND created_at > ?")
    .bind(t.id, now() - 3600).first<{ n: number }>();
  if ((fails?.n ?? 0) >= 5) return c.json({ error: "Too many wrong codes. Try again in an hour." }, 429);
  const { user_code } = await c.req.json<{ user_code?: string }>().catch(() => ({ user_code: "" }));
  const code = String(user_code ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  const formatted = code.length === 6 ? `${code.slice(0, 3)}-${code.slice(3)}` : "";
  const row = await db.prepare("SELECT device_code, name FROM pair_codes WHERE user_code = ? AND teacher_id IS NULL AND expires_at > ?")
    .bind(formatted, now()).first<{ device_code: string; name: string }>();
  if (!row) {
    await logEvent(db, t.id, "pair_fail");
    return c.json({ error: "That code doesn't match. Check the code your Mac shows; it works for 10 minutes." }, 404);
  }
  await db.prepare("UPDATE pair_codes SET teacher_id = ?, confirmed_at = ? WHERE device_code = ?").bind(t.id, now(), row.device_code).run();
  return c.json({ name: row.name });
});

teacherApi.delete("/devices/:id", async (c) => {
  const t = c.get("teacher");
  const r = await c.env.DB.prepare("UPDATE devices SET revoked_at = ? WHERE id = ? AND teacher_id = ? AND revoked_at IS NULL")
    .bind(now(), c.req.param("id"), t.id).run();
  if (!r.meta.changes) return c.json({ error: "not found" }, 404);
  await logEvent(c.env.DB, t.id, "device_revoked", c.req.param("id"));
  return c.body(null, 204);
});
```

`src/index.ts` becomes:

```ts
import { Hono } from "hono";
import type { AppEnv } from "./env";
import { securityHeaders } from "./http";
import { teacherAuth } from "./auth";
import { device } from "./device";
import { teacherApi } from "./teacher-api";

const app = new Hono<AppEnv>();
app.use("*", securityHeaders);
app.get("/health", (c) => c.text("ok"));
app.route("/api/device", device);
app.use("*", teacherAuth);
app.route("/api", teacherApi);
app.get("/", (c) => c.html("<!doctype html><title>slide2video</title><p>Lessons</p>"));
export default app;
```

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "slide2video: pair a Mac with a code, device tokens, contract check"`

---

### Task 4: Lessons, uploads, start, downloads

**Files:**
- Create: `src/files.ts`, `src/turns.ts` (queue part), `test/lessons.test.ts`
- Modify: `src/teacher-api.ts`

**Interfaces:**
- Consumes: `cleanName`, `newId`, `now`, `logEvent`, `hex`.
- Produces:
  - `files.ts`: `MAX_BYTES`, `UPLOAD_TYPES`, `OUT_TYPES`, `ext(name)`, `storeStream(env, req, row) -> Promise<{ id } | { error, status }>`,
    `serveFile(env, req, fileRow) -> Promise<Response>`, type `FileRow`.
  - `turns.ts`: `LEASE = 1800`, `queueTurn(db, teacherId, lessonId, kind, input) -> Promise<string>`,
    `busy(db, lessonId) -> Promise<boolean>`.
  - Routes: `POST /api/lessons` `{title, instructions?, attest}` → 201 `{id}`;
    `PUT /api/lessons/:id/files?name=&kind=deck|extra` (raw body) → 201 `{id}`;
    `POST /api/lessons/:id/start` → 204; `GET /api/lessons/:id/file?path=` → bytes (Range supported).
  - Test helper `newLesson(email, deck?) -> Promise<string>` (creates, uploads a deck, starts).

- [ ] **Step 1: Write the failing tests**

Append to `test/helpers.ts`:

```ts
export const DECK = new TextEncoder().encode("pretend pptx bytes");

export async function newLesson(email: string, opts: { start?: boolean; title?: string } = {}): Promise<string> {
  const created = await asTeacher(email, "/api/lessons", { method: "POST", body: JSON.stringify({ title: opts.title ?? "Water Cycle", attest: true }) });
  const { id } = await created.json<any>();
  await asTeacher(email, `/api/lessons/${id}/files?name=water-cycle.pptx&kind=deck`, { method: "PUT", body: DECK });
  if (opts.start !== false) await asTeacher(email, `/api/lessons/${id}/start`, { method: "POST" });
  return id;
}
```

`test/lessons.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { DECK, asTeacher, newLesson, seedTeacher } from "./helpers";

const body = (o: object) => ({ method: "POST", body: JSON.stringify(o) });

describe("lessons", () => {
  it("requires the no-student-information box", async () => {
    const t = await seedTeacher();
    const r = await asTeacher(t.email, "/api/lessons", body({ title: "X", attest: false }));
    expect(r.status).toBe(400);
    expect((await r.json<any>()).error).toContain("student");
  });

  it("uploads a deck with its sha256 and starts a turn", async () => {
    const t = await seedTeacher();
    const id = await newLesson(t.email, { start: false });
    const f = await env.DB.prepare("SELECT * FROM files WHERE lesson_id = ?").bind(id).first<any>();
    expect(f.path).toBe("in/water-cycle.pptx");
    expect(f.size).toBe(DECK.byteLength);
    expect(f.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(f.r2_key).toBe(`t/${t.id}/${id}/in/water-cycle.pptx`);
    expect((await asTeacher(t.email, `/api/lessons/${id}/start`, { method: "POST" })).status).toBe(204);
    const turn = await env.DB.prepare("SELECT kind, state, input FROM turns WHERE lesson_id = ?").bind(id).first<any>();
    expect(turn).toMatchObject({ kind: "start", state: "queued" });
    expect((await asTeacher(t.email, `/api/lessons/${id}/start`, { method: "POST" })).status).toBe(409);
  });

  it("won't start without a deck", async () => {
    const t = await seedTeacher();
    const { id } = await (await asTeacher(t.email, "/api/lessons", body({ title: "X", attest: true }))).json<any>();
    expect((await asTeacher(t.email, `/api/lessons/${id}/start`, { method: "POST" })).status).toBe(400);
  });

  it("rejects wrong file types and cleans names", async () => {
    const t = await seedTeacher();
    const { id } = await (await asTeacher(t.email, "/api/lessons", body({ title: "X", attest: true }))).json<any>();
    const bad = await asTeacher(t.email, `/api/lessons/${id}/files?name=run.exe&kind=extra`, { method: "PUT", body: DECK });
    expect(bad.status).toBe(415);
    const docx = await asTeacher(t.email, `/api/lessons/${id}/files?name=notes.docx&kind=deck`, { method: "PUT", body: DECK });
    expect(docx.status).toBe(415);
    await asTeacher(t.email, `/api/lessons/${id}/files?name=${encodeURIComponent("../../evil.pdf")}&kind=deck`, { method: "PUT", body: DECK });
    const f = await env.DB.prepare("SELECT path FROM files WHERE lesson_id = ?").bind(id).first<any>();
    expect(f.path).toBe("in/evil.pdf");
  });

  it("serves byte ranges", async () => {
    const t = await seedTeacher();
    const id = await newLesson(t.email);
    const r = await asTeacher(t.email, `/api/lessons/${id}/file?path=in/water-cycle.pptx`, { headers: { Range: "bytes=0-6" } });
    expect(r.status).toBe(206);
    expect(r.headers.get("Content-Range")).toBe(`bytes 0-6/${DECK.byteLength}`);
    expect(await r.text()).toBe("pretend");
    const full = await asTeacher(t.email, `/api/lessons/${id}/file?path=in/water-cycle.pptx`);
    expect(full.headers.get("Content-Disposition")).toContain("attachment");
  });

  it("keeps teachers apart", async () => {
    const a = await seedTeacher();
    const b = await seedTeacher();
    const id = await newLesson(a.email, { start: false });
    expect((await asTeacher(b.email, `/api/lessons/${id}/file?path=in/water-cycle.pptx`)).status).toBe(404);
    expect((await asTeacher(b.email, `/api/lessons/${id}/files?name=x.pdf&kind=deck`, { method: "PUT", body: DECK })).status).toBe(404);
    expect((await asTeacher(b.email, `/api/lessons/${id}/start`, { method: "POST" })).status).toBe(404);
  });
});
```

- [ ] **Step 2: Run to see it fail** — `npm test -- test/lessons.test.ts` — Expected: FAIL (404s).

- [ ] **Step 3: Implement `src/files.ts`**

```ts
import type { Env } from "./env";
import { hex, newId, now } from "./util";

export const MAX_BYTES = 100 * 1024 * 1024;
export const UPLOAD_TYPES: Record<string, string> = {
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
};
export const DECK_TYPES = [".pptx", ".pdf"];
export const OUT_TYPES: Record<string, { type: string; kind: string }> = {
  ".mp4": { type: "video/mp4", kind: "video" }, ".vtt": { type: "text/vtt", kind: "captions" },
  ".jpg": { type: "image/jpeg", kind: "stills" }, ".jpeg": { type: "image/jpeg", kind: "stills" },
  ".png": { type: "image/png", kind: "stills" }, ".json": { type: "application/json", kind: "timing" },
};
export type FileRow = { id: string; kind: string; name: string; path: string; r2_key: string; size: number; content_type: string };

export const ext = (name: string) => (name.toLowerCase().match(/\.[a-z0-9]+$/) ?? [""])[0];

type NewFile = { teacherId: string; lessonId: string; kind: string; name: string; path: string; contentType: string };

/** Streams the request body to R2 (known length) while hashing it; upserts the files row. Without a
 * Content-Length header (some runtimes drop it) the body is buffered instead; Workers cap bodies at 100 MB. */
export async function storeStream(env: Env, req: Request, f: NewFile): Promise<{ id: string } | { error: string; status: 400 | 411 | 413 }> {
  const key = `t/${f.teacherId}/${f.lessonId}/${f.path}`;
  const meta = { httpMetadata: { contentType: f.contentType } };
  let length = Number(req.headers.get("Content-Length"));
  let sha256: string;
  if (Number.isFinite(length) && length > 0 && req.body) {
    if (length > MAX_BYTES) return { error: "Files can be at most 100 MB.", status: 413 };
    const [toR2, toHash] = req.body.tee();
    const digest = new crypto.DigestStream("SHA-256");
    const hashed = toHash.pipeTo(digest).then(async () => hex(await digest.digest));
    await env.FILES.put(key, toR2.pipeThrough(new FixedLengthStream(length)), meta);
    sha256 = await hashed;
  } else {
    const buf = await req.arrayBuffer();
    length = buf.byteLength;
    if (!length) return { error: "Empty upload.", status: 411 };
    if (length > MAX_BYTES) return { error: "Files can be at most 100 MB.", status: 413 };
    sha256 = hex(await crypto.subtle.digest("SHA-256", buf));
    await env.FILES.put(key, buf, meta);
  }
  await env.DB.prepare(
    `INSERT INTO files (id, teacher_id, lesson_id, kind, name, path, r2_key, size, sha256, content_type, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT (lesson_id, path) DO UPDATE SET kind = excluded.kind, name = excluded.name, size = excluded.size,
       sha256 = excluded.sha256, content_type = excluded.content_type, created_at = excluded.created_at`,
  ).bind(newId("fil"), f.teacherId, f.lessonId, f.kind, f.name, f.path, key, length, sha256, f.contentType, now()).run();
  const row = await env.DB.prepare("SELECT id FROM files WHERE lesson_id = ? AND path = ?").bind(f.lessonId, f.path).first<{ id: string }>();
  return { id: row!.id };
}

export async function serveFile(env: Env, req: Request, f: FileRow): Promise<Response> {
  const obj = await env.FILES.get(f.r2_key, { range: req.headers });
  if (!obj) return new Response("Not found", { status: 404 });
  const h = new Headers({ "Content-Type": f.content_type, "Accept-Ranges": "bytes", "Cache-Control": "private, no-store" });
  h.set("Content-Disposition", f.kind === "video" ? "inline" : `attachment; filename*=UTF-8''${encodeURIComponent(f.name)}`);
  const r = obj.range as { offset?: number; length?: number; suffix?: number } | undefined;
  if (req.headers.has("Range") && r) {
    const offset = r.suffix !== undefined ? obj.size - r.suffix : r.offset ?? 0;
    const length = r.suffix !== undefined ? r.suffix : r.length ?? obj.size - offset;
    h.set("Content-Range", `bytes ${offset}-${offset + length - 1}/${obj.size}`);
    h.set("Content-Length", String(length));
    return new Response(obj.body, { status: 206, headers: h });
  }
  h.set("Content-Length", String(obj.size));
  return new Response(obj.body, { headers: h });
}
```

`src/turns.ts` (queue part; Task 5 adds the rest):

```ts
import { newId, now } from "./util";

export const LEASE = 1800;
export type TurnKind = "start" | "answer" | "approve" | "change" | "continue" | "feedback" | "revise" | "delete";

export async function queueTurn(db: D1Database, teacherId: string, lessonId: string, kind: TurnKind, input: object): Promise<string> {
  const n = await db.prepare("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM turns WHERE lesson_id = ?").bind(lessonId).first<{ n: number }>();
  const id = newId("trn");
  await db.prepare("INSERT INTO turns (id, teacher_id, lesson_id, seq, kind, input, state, created_at) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?)")
    .bind(id, teacherId, lessonId, n!.n, kind, JSON.stringify(input), now()).run();
  await db.prepare("UPDATE lessons SET updated_at = ? WHERE id = ?").bind(now(), lessonId).run();
  return id;
}

export async function busy(db: D1Database, lessonId: string): Promise<boolean> {
  return !!(await db.prepare("SELECT 1 FROM turns WHERE lesson_id = ? AND state IN ('queued', 'running') LIMIT 1").bind(lessonId).first());
}
```

Append to `src/teacher-api.ts`:

```ts
import { cleanName } from "./http";
import { DECK_TYPES, UPLOAD_TYPES, ext, serveFile, storeStream, type FileRow } from "./files";
import { queueTurn } from "./turns";
import { newId } from "./util";

const ownLesson = (db: D1Database, teacherId: string, id: string) =>
  db.prepare("SELECT * FROM lessons WHERE id = ? AND teacher_id = ? AND deleted_at IS NULL").bind(id, teacherId).first<any>();

teacherApi.post("/lessons", async (c) => {
  const t = c.get("teacher");
  const b = await c.req.json<{ title?: string; instructions?: string; attest?: boolean }>().catch(() => ({}) as any);
  const title = String(b.title ?? "").trim().slice(0, 200);
  if (!title) return c.json({ error: "Give the lesson a title." }, 400);
  if (b.attest !== true) return c.json({ error: "Confirm the files contain no student names, photos or work." }, 400);
  const id = newId("les");
  const instructions = b.instructions ? String(b.instructions).slice(0, 4000) : null;
  await c.env.DB.prepare("INSERT INTO lessons (id, teacher_id, title, instructions, attested_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .bind(id, t.id, title, instructions, now(), now(), now()).run();
  await logEvent(c.env.DB, t.id, "lesson_created", id);
  return c.json({ id }, 201);
});

teacherApi.put("/lessons/:id/files", async (c) => {
  const t = c.get("teacher");
  const lesson = await ownLesson(c.env.DB, t.id, c.req.param("id"));
  if (!lesson) return c.json({ error: "not found" }, 404);
  if (await c.env.DB.prepare("SELECT 1 FROM turns WHERE lesson_id = ? LIMIT 1").bind(lesson.id).first())
    return c.json({ error: "Files can only be added before the lesson starts." }, 409);
  const name = cleanName(c.req.query("name") ?? "");
  const kind = c.req.query("kind") === "deck" ? "deck" : "extra";
  const e = name ? ext(name) : "";
  if (!name || !UPLOAD_TYPES[e] || (kind === "deck" && !DECK_TYPES.includes(e)))
    return c.json({ error: "Decks can be .pptx or .pdf; other files .pptx, .pdf, .docx, .png or .jpg." }, 415);
  const r = await storeStream(c.env, c.req.raw, { teacherId: t.id, lessonId: lesson.id, kind, name, path: `in/${name}`, contentType: UPLOAD_TYPES[e] });
  if ("error" in r) return c.json({ error: r.error }, r.status);
  await logEvent(c.env.DB, t.id, "upload", `${lesson.id} in/${name}`);
  return c.json(r, 201);
});

teacherApi.post("/lessons/:id/start", async (c) => {
  const t = c.get("teacher");
  const lesson = await ownLesson(c.env.DB, t.id, c.req.param("id"));
  if (!lesson) return c.json({ error: "not found" }, 404);
  if (await c.env.DB.prepare("SELECT 1 FROM turns WHERE lesson_id = ? LIMIT 1").bind(lesson.id).first())
    return c.json({ error: "This lesson has already started." }, 409);
  if (!(await c.env.DB.prepare("SELECT 1 FROM files WHERE lesson_id = ? AND kind = 'deck'").bind(lesson.id).first()))
    return c.json({ error: "Add a deck (.pptx or .pdf) first." }, 400);
  await queueTurn(c.env.DB, t.id, lesson.id, "start", { instructions: lesson.instructions });
  return c.body(null, 204);
});

teacherApi.get("/lessons/:id/file", async (c) => {
  const t = c.get("teacher");
  const f = await c.env.DB.prepare("SELECT id, kind, name, path, r2_key, size, content_type FROM files WHERE lesson_id = ? AND teacher_id = ? AND path = ?")
    .bind(c.req.param("id"), t.id, c.req.query("path") ?? "").first<FileRow>();
  if (!f) return c.json({ error: "not found" }, 404);
  return serveFile(c.env, c.req.raw, f);
});
```

(Merge the new imports into the top of `src/teacher-api.ts`; keep one import line per module.)

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "slide2video: lessons, streaming uploads with sha256, start, range downloads"`

---

### Task 5: Turns on the device side, cards, and answering cards

**Files:**
- Modify: `src/turns.ts`, `src/device.ts`, `src/teacher-api.ts`
- Test: `test/turns.test.ts`

**Interfaces:**
- Consumes: `queueTurn`, `busy`, `LEASE`, `storeStream`, `OUT_TYPES`, `ext`, `cardProblems`, `CONTRACT_VERSION`,
  `deviceAuth` (`c.var.device`).
- Produces:
  - `turns.ts`: `claimNext(db, device) -> Promise<TurnRow | null>`, `turnJson(db, turn) -> Promise<object>`,
    `latestCard(db, lessonId) -> Promise<CardRow | null>`, types `TurnRow`, `CardRow`.
  - Device routes: `GET /next` (200 turn JSON | 204), `POST /turns/:id/heartbeat`, `GET /files/:id`,
    `PUT /turns/:id/files?path=`, `POST /turns/:id/finish`.
  - Teacher routes: `POST /api/lessons/:id/answer|approve|change|continue|feedback|retry`.
  - `onDeleteFinished(env, lessonId, teacherId)` hook is called from `finish` for `delete` turns; Task 6 defines
    it in `src/deletion.ts` (this task imports it, so create `src/deletion.ts` now with
    `export async function onDeleteFinished(env: Env, lessonId: string, teacherId: string) {}` and fill it in
    Task 6).
  - Test helpers: `claim(token) -> Promise<any>`, `finish(token, turnId, card) -> Promise<Response>`.

- [ ] **Step 1: Write the failing tests**

Append to `test/helpers.ts`:

```ts
export async function claim(token: string): Promise<any> {
  const r = await asDevice(token, "/api/device/next");
  return r.status === 204 ? null : r.json();
}
export const finish = (token: string, turnId: string, card: object) =>
  asDevice(token, `/api/device/turns/${turnId}/finish`, { method: "POST", body: JSON.stringify(card) });
export const QUESTIONS = { contract: 1, kind: "questions", message: "Questions",
  questions: [{ id: "grade", text: "Grade?", options: [{ label: "Grades 6–8" }, { label: "Grades 9–10" }], other: true }] };
export const PLAN = { contract: 1, kind: "plan", message: "Plan", markdown: "## Chapter 1", estimate: { usd: 0, minutes: 3, chapters: 1 } };
```

`test/turns.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { PLAN, QUESTIONS, asDevice, asTeacher, claim, finish, newLesson, pairDevice, seedTeacher } from "./helpers";
import { turnProblems } from "../src/contract";

const post = (email: string, path: string, body: object = {}) => asTeacher(email, path, { method: "POST", body: JSON.stringify(body) });

async function setup() {
  const t = await seedTeacher();
  const mac = await pairDevice(t.email);
  const lesson = await newLesson(t.email);
  return { t, mac, lesson };
}

describe("turns", () => {
  it("hands out a valid turn with its deck, and only once", async () => {
    const { mac, lesson } = await setup();
    const turn = await claim(mac.token);
    expect(turnProblems(turn)).toEqual([]);
    expect(turn.lesson.id).toBe(lesson);
    expect(turn.turn).toMatchObject({ kind: "start", seq: 1, lease_seconds: 1800 });
    expect(turn.files[0]).toMatchObject({ name: "water-cycle.pptx", kind: "deck", path: "in/water-cycle.pptx" });
    expect(await claim(mac.token)).toBeNull();
    const file = await asDevice(mac.token, `/api/device/files/${turn.files[0].id}`);
    expect(await file.text()).toBe("pretend pptx bytes");
  });

  it("never hands one teacher's turn to another teacher's Mac", async () => {
    await setup();
    const other = await seedTeacher();
    const otherMac = await pairDevice(other.email);
    expect(await claim(otherMac.token)).toBeNull();
  });

  it("keeps a lesson on its home Mac", async () => {
    const { t, mac, lesson } = await setup();
    const second = await pairDevice(t.email, "Second Mac");
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, QUESTIONS);
    await post(t.email, `/api/lessons/${lesson}/answer`, { answers: [{ question: "grade", choice: "Grades 6–8", other: null }] });
    expect(await claim(second.token)).toBeNull();
    expect((await claim(mac.token)).turn.kind).toBe("answer");
  });

  it("re-queues a turn whose lease ran out, and refuses the stale claim", async () => {
    const { t, mac } = await setup();
    const turn = await claim(mac.token);
    await env.DB.prepare("UPDATE turns SET lease_until = 1 WHERE id = ?").bind(turn.turn.id).run();
    const again = await claim(mac.token);
    expect(again.turn.id).toBe(turn.turn.id);
    const other = await pairDevice(t.email, "Other");
    expect((await finish(other.token, turn.turn.id, QUESTIONS)).status).toBe(409);
  });

  it("renews the lease and records progress on heartbeat", async () => {
    const { mac } = await setup();
    const turn = await claim(mac.token);
    const r = await asDevice(mac.token, `/api/device/turns/${turn.turn.id}/heartbeat`, { method: "POST", body: JSON.stringify({ progress: "Narrating 3 of 12 scenes" }) });
    expect(r.status).toBe(204);
    const row = await env.DB.prepare("SELECT progress, lease_until FROM turns WHERE id = ?").bind(turn.turn.id).first<any>();
    expect(row.progress).toBe("Narrating 3 of 12 scenes");
    expect(row.lease_until).toBeGreaterThan(Date.now() / 1000 + 1700);
  });

  it("rejects invalid cards", async () => {
    const { mac } = await setup();
    const turn = await claim(mac.token);
    const r = await finish(mac.token, turn.turn.id, { contract: 1, kind: "plan", message: "x" });
    expect(r.status).toBe(422);
  });

  it("walks questions → answer → plan → approve → review → continue", async () => {
    const { t, mac, lesson } = await setup();
    let turn = await claim(mac.token);
    expect((await finish(mac.token, turn.turn.id, QUESTIONS)).status).toBe(204);
    // answers must match the card
    expect((await post(t.email, `/api/lessons/${lesson}/answer`, { answers: [{ question: "nope", choice: "x" }] })).status).toBe(400);
    expect((await post(t.email, `/api/lessons/${lesson}/approve`)).status).toBe(409);
    expect((await post(t.email, `/api/lessons/${lesson}/answer`, { answers: [{ question: "grade", choice: null, other: "Grade 7" }] })).status).toBe(204);
    expect((await post(t.email, `/api/lessons/${lesson}/answer`, { answers: [] })).status).toBe(409); // already answered
    turn = await claim(mac.token);
    expect(turn.answers).toEqual([{ question: "grade", choice: null, other: "Grade 7" }]);
    await finish(mac.token, turn.turn.id, PLAN);
    expect((await post(t.email, `/api/lessons/${lesson}/approve`)).status).toBe(204);
    turn = await claim(mac.token);
    expect(turn.turn.kind).toBe("approve");
    // a review must name a video uploaded in this turn
    const missing = { contract: 1, kind: "review", message: "Ready", chapter: 1, version: 1, video: "out/ch1/v1/c.mp4" };
    expect((await finish(mac.token, turn.turn.id, missing)).status).toBe(422);
    const mp4 = new TextEncoder().encode("mp4 bytes");
    const up = await asDevice(mac.token, `/api/device/turns/${turn.turn.id}/files?path=${encodeURIComponent("out/ch1/v1/c.mp4")}`, { method: "PUT", body: mp4, headers: { "Content-Type": "video/mp4" } });
    expect(up.status).toBe(201);
    expect((await finish(mac.token, turn.turn.id, missing)).status).toBe(204);
    const video = await asTeacher(t.email, `/api/lessons/${lesson}/file?path=out/ch1/v1/c.mp4`);
    expect(video.headers.get("Content-Disposition")).toBe("inline");
    expect((await post(t.email, `/api/lessons/${lesson}/feedback`, { feedback: "" })).status).toBe(400);
    expect((await post(t.email, `/api/lessons/${lesson}/continue`)).status).toBe(204);
    expect((await claim(mac.token)).turn.kind).toBe("continue");
  });

  it("refuses device uploads outside out/chN/vK/ and for turns it doesn't hold", async () => {
    const { t, mac } = await setup();
    const turn = await claim(mac.token);
    const bytes = new TextEncoder().encode("x");
    for (const p of ["in/x.pptx", "out/ch1/x.mp4", "out/ch1/v1/../../x.mp4", "out/ch1/v1/.x.mp4", "out/ch1/v1/x.exe"]) {
      const r = await asDevice(mac.token, `/api/device/turns/${turn.turn.id}/files?path=${encodeURIComponent(p)}`, { method: "PUT", body: bytes });
      expect(r.status, p).toBe(400);
    }
    const other = await pairDevice(t.email, "Other");
    const r = await asDevice(other.token, `/api/device/turns/${turn.turn.id}/files?path=out/ch1/v1/x.mp4`, { method: "PUT", body: bytes });
    expect(r.status).toBe(409);
  });

  it("error cards: retry_after re-queues later; others fail with Try again", async () => {
    const { t, mac, lesson } = await setup();
    let turn = await claim(mac.token);
    const later = new Date(Date.now() + 3600_000).toISOString();
    await finish(mac.token, turn.turn.id, { contract: 1, kind: "error", message: "limit", log_tail: "", retry_after: later });
    expect(await claim(mac.token)).toBeNull();
    await env.DB.prepare("UPDATE turns SET not_before = 1 WHERE id = ?").bind(turn.turn.id).run();
    turn = await claim(mac.token);
    expect(turn.turn.kind).toBe("start");
    await finish(mac.token, turn.turn.id, { contract: 1, kind: "error", message: "crashed", log_tail: "x", retry_after: null });
    expect(await claim(mac.token)).toBeNull();
    expect((await post(t.email, `/api/lessons/${lesson}/retry`)).status).toBe(204);
    expect((await claim(mac.token)).turn.kind).toBe("start");
  });

  it("keeps teachers apart on card actions and device files", async () => {
    const { mac, lesson } = await setup();
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, QUESTIONS);
    const b = await seedTeacher();
    expect((await post(b.email, `/api/lessons/${lesson}/answer`, { answers: [] })).status).toBe(404);
    const bMac = await pairDevice(b.email);
    expect((await asDevice(bMac.token, `/api/device/files/${turn.files[0].id}`)).status).toBe(404);
  });
});
```

- [ ] **Step 2: Run to see it fail** — `npm test -- test/turns.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `src/turns.ts`:

```ts
import { CONTRACT_VERSION } from "./contract";
import type { Device } from "./env";

export type TurnRow = { id: string; teacher_id: string; lesson_id: string; seq: number; kind: TurnKind; input: string;
  state: string; device_id: string | null; lease_until: number | null; not_before: number | null };
export type CardRow = { id: string; lesson_id: string; turn_id: string; kind: string; body: string; created_at: number; answered_at: number | null };

/** The oldest claimable turn for this Mac's teacher (new lessons, or lessons homed on this Mac), claimed atomically. */
export async function claimNext(db: D1Database, d: Device): Promise<TurnRow | null> {
  const t = now();
  const candidates = await db.prepare(
    `SELECT t.* FROM turns t JOIN lessons l ON l.id = t.lesson_id
     WHERE t.teacher_id = ?1 AND (l.home_device_id IS NULL OR l.home_device_id = ?2)
       AND (?4 = 0 OR t.kind = 'delete')
       AND ((t.state = 'queued' AND (t.not_before IS NULL OR t.not_before <= ?3))
            OR (t.state = 'running' AND t.lease_until < ?3))
     ORDER BY t.created_at, t.seq LIMIT 5`,
  ).bind(d.teacher_id, d.id, t, d.retiring).all<TurnRow>();
  for (const row of candidates.results) {
    const r = await db.prepare(
      `UPDATE turns SET state = 'running', device_id = ?, lease_until = ?
       WHERE id = ? AND (state = 'queued' OR (state = 'running' AND lease_until < ?))`,
    ).bind(d.id, t + LEASE, row.id, t).run();
    if (r.meta.changes === 1) {
      await db.prepare("UPDATE lessons SET home_device_id = ? WHERE id = ? AND home_device_id IS NULL").bind(d.id, row.lesson_id).run();
      return { ...row, state: "running", device_id: d.id, lease_until: t + LEASE };
    }
  }
  return null;
}

export async function turnJson(db: D1Database, turn: TurnRow): Promise<object> {
  const lesson = await db.prepare("SELECT id, title FROM lessons WHERE id = ?").bind(turn.lesson_id).first<{ id: string; title: string }>();
  const { results: files } = await db.prepare(
    "SELECT id, name, kind, sha256, size, path FROM files WHERE lesson_id = ? AND path LIKE 'in/%' ORDER BY created_at",
  ).bind(turn.lesson_id).all();
  return {
    contract: CONTRACT_VERSION,
    lesson: { id: turn.lesson_id, title: lesson?.title || "(deleted)" },
    turn: { id: turn.id, seq: turn.seq, kind: turn.kind, lease_seconds: LEASE },
    files,
    ...JSON.parse(turn.input),
  };
}

export const latestCard = (db: D1Database, lessonId: string) =>
  db.prepare("SELECT * FROM cards WHERE lesson_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1").bind(lessonId).first<CardRow>();
```

Merge `import { newId, now } from "./util";` with the existing import at the top.

Append to `src/device.ts`:

```ts
import { cardProblems } from "./contract";
import { OUT_TYPES, ext, serveFile, storeStream, type FileRow } from "./files";
import { LEASE, claimNext, turnJson, type TurnRow } from "./turns";
import { onDeleteFinished } from "./deletion";

const OUT_PATH = /^out\/ch[0-9]{1,3}\/v[0-9]{1,3}\/[^/\\.][^/\\]{0,199}$/;

const heldTurn = (db: D1Database, id: string, deviceId: string) =>
  db.prepare("SELECT * FROM turns WHERE id = ? AND device_id = ? AND state = 'running'").bind(id, deviceId).first<TurnRow>();

device.get("/next", async (c) => {
  const turn = await claimNext(c.env.DB, c.get("device"));
  return turn ? c.json(await turnJson(c.env.DB, turn)) : c.body(null, 204);
});

device.post("/turns/:id/heartbeat", async (c) => {
  const { progress } = await c.req.json<{ progress?: string }>().catch(() => ({ progress: "" }));
  const r = await c.env.DB.prepare("UPDATE turns SET lease_until = ?, progress = ? WHERE id = ? AND device_id = ? AND state = 'running'")
    .bind(now() + LEASE, String(progress ?? "").slice(0, 200), c.req.param("id"), c.get("device").id).run();
  return r.meta.changes ? c.body(null, 204) : c.json({ error: "This Mac doesn't hold that turn." }, 409);
});

device.get("/files/:id", async (c) => {
  const f = await c.env.DB.prepare("SELECT id, kind, name, path, r2_key, size, content_type FROM files WHERE id = ? AND teacher_id = ?")
    .bind(c.req.param("id"), c.get("device").teacher_id).first<FileRow>();
  return f ? serveFile(c.env, c.req.raw, f) : c.json({ error: "not found" }, 404);
});

device.put("/turns/:id/files", async (c) => {
  const path = c.req.query("path") ?? "";
  const type = OUT_TYPES[ext(path)];
  if (!OUT_PATH.test(path) || !type) return c.json({ error: "Uploads go to out/ch<N>/v<K>/<name> (.mp4, .vtt, .jpg, .png, .json)." }, 400);
  const turn = await heldTurn(c.env.DB, c.req.param("id"), c.get("device").id);
  if (!turn) return c.json({ error: "This Mac doesn't hold that turn." }, 409);
  const r = await storeStream(c.env, c.req.raw, { teacherId: turn.teacher_id, lessonId: turn.lesson_id, kind: type.kind,
    name: path.split("/").pop()!, path, contentType: type.type });
  return "error" in r ? c.json({ error: r.error }, r.status) : c.json(r, 201);
});

device.post("/turns/:id/finish", async (c) => {
  const db = c.env.DB;
  const card = await c.req.json<any>().catch(() => null);
  const bad = cardProblems(card);
  if (bad.length) return c.json({ error: "invalid card", problems: bad.slice(0, 10) }, 422);
  const turn = await heldTurn(db, c.req.param("id"), c.get("device").id);
  if (!turn) return c.json({ error: "This Mac doesn't hold that turn." }, 409);
  if (turn.kind === "delete") {
    await onDeleteFinished(c.env, turn.lesson_id, turn.teacher_id);
    return c.body(null, 204);
  }
  if (card.kind === "review") {
    for (const field of ["video", "captions", "stills", "timing"]) {
      if (card[field] && !(await db.prepare("SELECT 1 FROM files WHERE lesson_id = ? AND path = ?").bind(turn.lesson_id, card[field]).first()))
        return c.json({ error: `The review card's ${field} (${card[field]}) wasn't uploaded.` }, 422);
    }
  }
  const t = now();
  const retryAt = card.kind === "error" && card.retry_after ? Math.floor(Date.parse(card.retry_after) / 1000) : null;
  const update = retryAt
    ? db.prepare("UPDATE turns SET state = 'queued', not_before = ?, lease_until = NULL, device_id = NULL WHERE id = ?").bind(retryAt, turn.id)
    : db.prepare("UPDATE turns SET state = ?, finished_at = ?, lease_until = NULL WHERE id = ?").bind(card.kind === "error" ? "failed" : "done", t, turn.id);
  await db.batch([
    update,
    db.prepare("INSERT INTO cards (id, teacher_id, lesson_id, turn_id, kind, body, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)")
      .bind(newId("crd"), turn.teacher_id, turn.lesson_id, turn.id, card.kind, JSON.stringify(card), t),
    db.prepare("UPDATE lessons SET updated_at = ? WHERE id = ?").bind(t, turn.lesson_id),
  ]);
  return c.body(null, 204);
});
```

Merge imports (`newId`, `now` from `./util`) at the top of `src/device.ts`. Create `src/deletion.ts` with the empty
`onDeleteFinished` stub named in Interfaces.

Append to `src/teacher-api.ts`:

```ts
import { busy, latestCard, queueTurn, type TurnKind } from "./turns";

const ACTIONS: Record<string, { card: string; turn: TurnKind }> = {
  answer: { card: "questions", turn: "answer" }, approve: { card: "plan", turn: "approve" },
  change: { card: "plan", turn: "change" }, continue: { card: "review", turn: "continue" },
  feedback: { card: "review", turn: "feedback" },
};

function answersInput(card: any, body: any): { answers: object[] } | string {
  if (!Array.isArray(body.answers) || body.answers.length > 8) return "Answer the questions on the card.";
  const qs = new Map<string, any>(card.questions.map((q: any) => [q.id, q]));
  const out = [];
  for (const a of body.answers) {
    const q = qs.get(String(a?.question));
    if (!q) return "That answer doesn't match a question on the card.";
    const choice = a.choice == null ? null : String(a.choice);
    const other = a.other == null ? null : String(a.other).slice(0, 2000);
    if (choice !== null && !q.options.some((o: any) => o.label === choice)) return "That choice isn't one of the options.";
    if (choice === null && !(q.other && other?.trim())) return "Pick an option or type your own answer.";
    out.push({ question: q.id, choice, other });
  }
  return { answers: out };
}

teacherApi.post("/lessons/:id/:action{answer|approve|change|continue|feedback}", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const lesson = await ownLesson(db, t.id, c.req.param("id"));
  if (!lesson) return c.json({ error: "not found" }, 404);
  const action = ACTIONS[c.req.param("action")];
  const card = await latestCard(db, lesson.id);
  if (!card || card.kind !== action.card || card.answered_at || (await busy(db, lesson.id)))
    return c.json({ error: "There's nothing to answer right now." }, 409);
  const body = await c.req.json<any>().catch(() => ({}));
  let input: object = {};
  if (action.turn === "answer") {
    const r = answersInput(JSON.parse(card.body), body);
    if (typeof r === "string") return c.json({ error: r }, 400);
    input = r;
  } else if (action.turn === "change" || action.turn === "feedback") {
    const feedback = String(body.feedback ?? "").trim().slice(0, 4000);
    if (!feedback) return c.json({ error: "Say what you'd like changed." }, 400);
    input = { feedback };
  }
  await db.prepare("UPDATE cards SET answered_at = ? WHERE id = ?").bind(now(), card.id).run();
  await queueTurn(db, t.id, lesson.id, action.turn, input);
  return c.body(null, 204);
});

teacherApi.post("/lessons/:id/retry", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const lesson = await ownLesson(db, t.id, c.req.param("id"));
  if (!lesson) return c.json({ error: "not found" }, 404);
  const card = await latestCard(db, lesson.id);
  if (!card || card.kind !== "error" || card.answered_at || (await busy(db, lesson.id)))
    return c.json({ error: "There's nothing to retry." }, 409);
  const failed = await db.prepare("SELECT kind, input FROM turns WHERE id = ?").bind(card.turn_id).first<{ kind: TurnKind; input: string }>();
  await db.prepare("UPDATE cards SET answered_at = ? WHERE id = ?").bind(now(), card.id).run();
  await queueTurn(db, t.id, lesson.id, failed!.kind, JSON.parse(failed!.input));
  return c.body(null, 204);
});
```

Note: for an error card with `retry_after`, the turn is already re-queued, so `busy` is true and retry answers
409, as the test expects.

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "slide2video: device turns (claim, lease, uploads, finish), cards and answers"`

---

### Task 6: Deletion, account export and account deletion

**Files:**
- Create: `src/export.ts`, `src/access.ts` (stub `syncAccessGroup` returning `"skipped"`; Task 7 fills it),
  `test/deletion.test.ts`
- Modify: `src/deletion.ts`, `src/teacher-api.ts`

**Interfaces:**
- Consumes: `queueTurn`, `logEvent`, `claimNext` behaviour for `retiring` devices.
- Produces: `deleteLesson(env, teacherId, lessonId) -> Promise<boolean>`, `deleteAccount(env, teacherId) -> Promise<void>`,
  `onDeleteFinished(env, lessonId, teacherId)`, `exportZip(c) -> Promise<Response>`; routes
  `DELETE /api/lessons/:id` → 204, `GET /api/account/export` → zip, `DELETE /api/account` `{confirm: <email>}` →
  204; `syncAccessGroup(env) -> Promise<"synced" | "skipped">` (stub here).

- [ ] **Step 1: Write the failing tests**

`test/deletion.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { env } from "cloudflare:workers";
import { unzipSync, strFromU8 } from "fflate";
import { QUESTIONS, asDevice, asTeacher, claim, finish, newLesson, pairDevice, seedTeacher } from "./helpers";

const del = (email: string, path: string, body?: object) =>
  asTeacher(email, path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined });

describe("deletion and export", () => {
  it("deletes a lesson never picked up by a Mac completely", async () => {
    const t = await seedTeacher();
    const id = await newLesson(t.email);
    expect((await del(t.email, `/api/lessons/${id}`)).status).toBe(204);
    expect(await env.DB.prepare("SELECT 1 FROM lessons WHERE id = ?").bind(id).first()).toBeNull();
    expect((await env.FILES.list({ prefix: `t/${t.id}/${id}/` })).objects).toEqual([]);
  });

  it("leaves a tombstone with a delete turn for the home Mac, then removes it", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email, { title: "Secret title" });
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, QUESTIONS);
    expect((await del(t.email, `/api/lessons/${id}`)).status).toBe(204);
    const tomb = await env.DB.prepare("SELECT title, instructions, deleted_at FROM lessons WHERE id = ?").bind(id).first<any>();
    expect(tomb.title).toBe("");
    expect(tomb.deleted_at).toBeTruthy();
    expect(await env.DB.prepare("SELECT 1 FROM files WHERE lesson_id = ?").bind(id).first()).toBeNull();
    const d = await claim(mac.token);
    expect(d).toMatchObject({ turn: { kind: "delete" }, delete: true, files: [] });
    expect((await finish(mac.token, d.turn.id, { contract: 1, kind: "done", message: "Removed from this Mac." })).status).toBe(204);
    expect(await env.DB.prepare("SELECT 1 FROM lessons WHERE id = ?").bind(id).first()).toBeNull();
    expect(await env.DB.prepare("SELECT 1 FROM turns WHERE lesson_id = ?").bind(id).first()).toBeNull();
  });

  it("won't let another teacher delete my lesson", async () => {
    const a = await seedTeacher();
    const b = await seedTeacher();
    const id = await newLesson(a.email);
    expect((await del(b.email, `/api/lessons/${id}`)).status).toBe(404);
  });

  it("exports my data and files as a zip", async () => {
    const t = await seedTeacher();
    const id = await newLesson(t.email, { title: "Export me" });
    const r = await asTeacher(t.email, "/api/account/export");
    expect(r.headers.get("Content-Type")).toBe("application/zip");
    const files = unzipSync(new Uint8Array(await r.arrayBuffer()));
    const data = JSON.parse(strFromU8(files["data.json"]));
    expect(data.email).toBe(t.email);
    expect(data.lessons[0].title).toBe("Export me");
    expect(strFromU8(files[`${id}/in/water-cycle.pptx`])).toBe("pretend pptx bytes");
  });

  it("deletes an account: Macs fetch the delete turns, then everything is gone", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, QUESTIONS);
    await newLesson(t.email); // never claimed: deleted at once
    expect((await del(t.email, "/api/account", { confirm: "wrong@example.org" })).status).toBe(400);
    expect((await del(t.email, "/api/account", { confirm: t.email })).status).toBe(204);
    expect((await asTeacher(t.email, "/")).status).toBe(403);
    const d = await claim(mac.token);
    expect(d.lesson.id).toBe(id);
    await finish(mac.token, d.turn.id, { contract: 1, kind: "done", message: "Removed from this Mac." });
    expect((await asDevice(mac.token, "/api/device/status")).status).toBe(401);
    expect(await env.DB.prepare("SELECT 1 FROM teachers WHERE id = ?").bind(t.id).first()).toBeNull();
  });

  it("an account with no Mac lessons is removed at once", async () => {
    const t = await seedTeacher();
    await newLesson(t.email);
    expect((await del(t.email, "/api/account", { confirm: t.email })).status).toBe(204);
    expect(await env.DB.prepare("SELECT 1 FROM teachers WHERE id = ?").bind(t.id).first()).toBeNull();
  });
});
```

- [ ] **Step 2: Run to see it fail** — `npm test -- test/deletion.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement**

`src/deletion.ts`:

```ts
import type { Env } from "./env";
import { logEvent } from "./auth";
import { queueTurn } from "./turns";
import { syncAccessGroup } from "./access";
import { now } from "./util";

async function purge(env: Env, prefix: string) {
  let cursor: string | undefined;
  do {
    const list = await env.FILES.list({ prefix, cursor });
    if (list.objects.length) await env.FILES.delete(list.objects.map((o) => o.key));
    cursor = list.truncated ? list.cursor : undefined;
  } while (cursor);
}

/** Deletes a lesson's files and data now; if a Mac holds its folder, keeps a tombstone with a delete turn. */
export async function deleteLesson(env: Env, teacherId: string, lessonId: string): Promise<boolean> {
  const db = env.DB;
  const l = await db.prepare("SELECT id, home_device_id FROM lessons WHERE id = ? AND teacher_id = ? AND deleted_at IS NULL")
    .bind(lessonId, teacherId).first<{ id: string; home_device_id: string | null }>();
  if (!l) return false;
  await purge(env, `t/${teacherId}/${lessonId}/`);
  await db.batch([
    db.prepare("DELETE FROM files WHERE lesson_id = ?").bind(lessonId),
    db.prepare("DELETE FROM cards WHERE lesson_id = ?").bind(lessonId),
    db.prepare("DELETE FROM turns WHERE lesson_id = ?").bind(lessonId),
  ]);
  if (l.home_device_id) {
    await db.prepare("UPDATE lessons SET title = '', instructions = NULL, deleted_at = ? WHERE id = ?").bind(now(), lessonId).run();
    await queueTurn(db, teacherId, lessonId, "delete", { delete: true });
  } else {
    await db.prepare("DELETE FROM lessons WHERE id = ?").bind(lessonId).run();
  }
  await logEvent(db, teacherId, "lesson_deleted", lessonId);
  return true;
}

/** Removes a deleted teacher entirely once no tombstones are left. */
async function finishAccountIfDone(env: Env, teacherId: string) {
  const db = env.DB;
  const t = await db.prepare("SELECT deleted_at FROM teachers WHERE id = ?").bind(teacherId).first<{ deleted_at: number | null }>();
  if (!t?.deleted_at) return;
  if (await db.prepare("SELECT 1 FROM lessons WHERE teacher_id = ? LIMIT 1").bind(teacherId).first()) return;
  await db.batch([
    db.prepare("DELETE FROM devices WHERE teacher_id = ?").bind(teacherId),
    db.prepare("DELETE FROM pair_codes WHERE teacher_id = ?").bind(teacherId),
    db.prepare("DELETE FROM events WHERE teacher_id = ?").bind(teacherId),
    db.prepare("DELETE FROM teachers WHERE id = ?").bind(teacherId),
  ]);
}

export async function onDeleteFinished(env: Env, lessonId: string, teacherId: string) {
  await env.DB.batch([
    env.DB.prepare("DELETE FROM turns WHERE lesson_id = ?").bind(lessonId),
    env.DB.prepare("DELETE FROM lessons WHERE id = ? AND deleted_at IS NOT NULL").bind(lessonId),
  ]);
  await finishAccountIfDone(env, teacherId);
}

export async function deleteAccount(env: Env, teacherId: string) {
  const db = env.DB;
  const { results } = await db.prepare("SELECT id FROM lessons WHERE teacher_id = ? AND deleted_at IS NULL").bind(teacherId).all<{ id: string }>();
  for (const l of results) await deleteLesson(env, teacherId, l.id);
  await db.batch([
    db.prepare("UPDATE teachers SET deleted_at = ?, email = 'deleted+' || id || '@slide2video.invalid' WHERE id = ?").bind(now(), teacherId),
    db.prepare("UPDATE devices SET retiring = 1 WHERE teacher_id = ? AND revoked_at IS NULL").bind(teacherId),
  ]);
  await finishAccountIfDone(env, teacherId);
  await syncAccessGroup(env).catch(() => "skipped");
}
```

`src/access.ts` (stub; Task 7 replaces):

```ts
import type { Env } from "./env";
export async function syncAccessGroup(_env: Env): Promise<"synced" | "skipped"> {
  return "skipped";
}
```

`src/export.ts`:

```ts
import { Zip, ZipPassThrough, strToU8 } from "fflate";
import type { Context } from "hono";
import type { AppEnv } from "./env";
import { logEvent } from "./auth";

export async function exportZip(c: Context<AppEnv>): Promise<Response> {
  const t = c.get("teacher");
  const db = c.env.DB;
  const q = (sql: string) => db.prepare(sql).bind(t.id).all<any>().then((r) => r.results);
  const lessons = await q("SELECT id, title, instructions, created_at, updated_at FROM lessons WHERE teacher_id = ? AND deleted_at IS NULL");
  const files = await q("SELECT lesson_id, kind, name, path, r2_key, size, sha256, created_at FROM files WHERE teacher_id = ?");
  const cards = (await q("SELECT lesson_id, kind, body, created_at, answered_at FROM cards WHERE teacher_id = ?"))
    .map((r: any) => ({ ...r, body: JSON.parse(r.body) }));
  const turns = await q("SELECT lesson_id, seq, kind, input, state, created_at, finished_at FROM turns WHERE teacher_id = ?");
  const devices = await q("SELECT name, created_at, last_seen FROM devices WHERE teacher_id = ? AND revoked_at IS NULL");
  const data = { exported_at: new Date().toISOString(), email: t.email, lessons, cards, turns, devices,
    files: files.map(({ r2_key, ...f }: any) => f) };

  const { readable, writable } = new TransformStream<Uint8Array, Uint8Array>();
  const writer = writable.getWriter();
  const zip = new Zip((err, chunk, final) => {
    if (err) return void writer.abort(err);
    writer.write(chunk);
    if (final) writer.close();
  });
  c.executionCtx.waitUntil((async () => {
    const meta = new ZipPassThrough("data.json");
    zip.add(meta);
    meta.push(strToU8(JSON.stringify(data, null, 1)), true);
    for (const f of files) {
      const obj = await c.env.FILES.get(f.r2_key);
      if (!obj) continue;
      const entry = new ZipPassThrough(`${f.lesson_id}/${f.path}`);
      zip.add(entry);
      const reader = obj.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) { entry.push(new Uint8Array(0), true); break; }
        entry.push(value);
      }
    }
    zip.end();
  })().catch((e) => writer.abort(e)));
  await logEvent(db, t.id, "export");
  return new Response(readable, { headers: { "Content-Type": "application/zip",
    "Content-Disposition": 'attachment; filename="slide2video-export.zip"' } });
}
```

Append to `src/teacher-api.ts`:

```ts
import { deleteAccount, deleteLesson } from "./deletion";
import { exportZip } from "./export";

teacherApi.delete("/lessons/:id", async (c) =>
  (await deleteLesson(c.env, c.get("teacher").id, c.req.param("id"))) ? c.body(null, 204) : c.json({ error: "not found" }, 404));

teacherApi.get("/account/export", (c) => exportZip(c));

teacherApi.delete("/account", async (c) => {
  const t = c.get("teacher");
  const { confirm } = await c.req.json<{ confirm?: string }>().catch(() => ({ confirm: "" }));
  if (String(confirm ?? "").toLowerCase() !== t.email) return c.json({ error: "Type your email address to confirm." }, 400);
  await deleteAccount(c.env, t.id);
  return c.body(null, 204);
});
```

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "slide2video: lesson and account deletion (tombstones reach the Mac), export zip"`

---

### Task 7: Admin invites and the Access group

**Files:**
- Modify: `src/access.ts`, `src/teacher-api.ts`
- Test: `test/admin.test.ts`

**Interfaces:**
- Consumes: `isAdmin`, `deleteAccount`, `logEvent`.
- Produces: `syncAccessGroup(env, fetcher = fetch) -> Promise<"synced" | "skipped">` (PUT
  `https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/access/groups/{ACCESS_GROUP_ID}` with
  `{ name: "slide2video teachers", include: [{ email: { email } }…] }`, Bearer `CF_API_TOKEN`; throws on a
  non-2xx); routes `GET /api/admin/teachers`, `POST /api/admin/teachers` `{email}`, `DELETE /api/admin/teachers/:id`.

- [ ] **Step 1: Write the failing tests**

`test/admin.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { env } from "cloudflare:workers";
import { asTeacher, seedTeacher, uniqueEmail } from "./helpers";
import { syncAccessGroup } from "../src/access";

const ADMIN = "admin@example.org";

describe("admin", () => {
  it("is admin-only", async () => {
    const t = await seedTeacher();
    expect((await asTeacher(t.email, "/api/admin/teachers")).status).toBe(403);
    expect((await asTeacher(t.email, "/api/admin/teachers", { method: "POST", body: JSON.stringify({ email: uniqueEmail() }) })).status).toBe(403);
  });

  it("invites, lists with storage, and removes teachers", async () => {
    const email = uniqueEmail();
    const r = await asTeacher(ADMIN, "/api/admin/teachers", { method: "POST", body: JSON.stringify({ email: email.toUpperCase() }) });
    expect(r.status).toBe(201);
    expect((await asTeacher(email, "/")).status).toBe(200);
    const list = await (await asTeacher(ADMIN, "/api/admin/teachers")).json<any>();
    const row = list.teachers.find((x: any) => x.email === email);
    expect(row.bytes).toBe(0);
    expect((await asTeacher(ADMIN, `/api/admin/teachers/${row.id}`, { method: "DELETE" })).status).toBe(204);
    expect((await asTeacher(email, "/")).status).toBe(403);
  });

  it("rejects bad emails and won't remove the admin", async () => {
    expect((await asTeacher(ADMIN, "/api/admin/teachers", { method: "POST", body: JSON.stringify({ email: "not an email" }) })).status).toBe(400);
    const me = await env.DB.prepare("SELECT id FROM teachers WHERE email = ?").bind(ADMIN).first<any>();
    expect((await asTeacher(ADMIN, `/api/admin/teachers/${me.id}`, { method: "DELETE" })).status).toBe(400);
  });

  it("syncs the Access group with every invited email", async () => {
    await seedTeacher("sync-a@example.org");
    const fetcher = vi.fn(async () => new Response("{}", { status: 200 }));
    const e = { ...env, CF_API_TOKEN: "tok", CF_ACCOUNT_ID: "acc", ACCESS_GROUP_ID: "grp" };
    expect(await syncAccessGroup(e, fetcher as any)).toBe("synced");
    const [url, init] = fetcher.mock.calls[0] as any;
    expect(url).toBe("https://api.cloudflare.com/client/v4/accounts/acc/access/groups/grp");
    expect(init.method).toBe("PUT");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(JSON.parse(init.body).include).toContainEqual({ email: { email: "sync-a@example.org" } });
    expect(await syncAccessGroup(env, fetcher as any)).toBe("skipped");
  });

  it("reports a failed sync", async () => {
    const e = { ...env, CF_API_TOKEN: "tok", CF_ACCOUNT_ID: "acc", ACCESS_GROUP_ID: "grp" };
    await expect(syncAccessGroup(e, (async () => new Response("no", { status: 403 })) as any)).rejects.toThrow("403");
  });
});
```

- [ ] **Step 2: Run to see it fail** — `npm test -- test/admin.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement**

`src/access.ts`:

```ts
import type { Env } from "./env";

/** Makes the Access group "slide2video teachers" list exactly the invited (not deleted) emails. */
export async function syncAccessGroup(env: Env, fetcher: typeof fetch = fetch): Promise<"synced" | "skipped"> {
  if (!env.CF_API_TOKEN || !env.CF_ACCOUNT_ID || !env.ACCESS_GROUP_ID) return "skipped";
  const { results } = await env.DB.prepare("SELECT email FROM teachers WHERE deleted_at IS NULL ORDER BY email").all<{ email: string }>();
  const r = await fetcher(`https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/access/groups/${env.ACCESS_GROUP_ID}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${env.CF_API_TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify({ name: "slide2video teachers", include: results.map((t) => ({ email: { email: t.email } })) }),
  });
  if (!r.ok) throw new Error(`Access group update failed (${r.status})`);
  return "synced";
}
```

Append to `src/teacher-api.ts`:

```ts
import { isAdmin } from "./auth";
import { syncAccessGroup } from "./access";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

teacherApi.use("/admin/*", async (c, next) => {
  if (!isAdmin(c)) return c.json({ error: "Admins only." }, 403);
  await next();
});

teacherApi.get("/admin/teachers", async (c) => {
  const { results } = await c.env.DB.prepare(
    `SELECT t.id, t.email, t.created_at, COALESCE(SUM(f.size), 0) AS bytes
     FROM teachers t LEFT JOIN files f ON f.teacher_id = t.id WHERE t.deleted_at IS NULL GROUP BY t.id ORDER BY t.email`,
  ).all();
  return c.json({ teachers: results });
});

teacherApi.post("/admin/teachers", async (c) => {
  const { email } = await c.req.json<{ email?: string }>().catch(() => ({ email: "" }));
  const e = String(email ?? "").trim().toLowerCase();
  if (!EMAIL.test(e)) return c.json({ error: "That isn't an email address." }, 400);
  await c.env.DB.prepare("INSERT INTO teachers (id, email, created_at) VALUES (?, ?, ?) ON CONFLICT (email) DO NOTHING")
    .bind(newId("tch"), e, now()).run();
  await logEvent(c.env.DB, c.get("teacher").id, "invite", e);
  const access = await syncAccessGroup(c.env).catch((err) => `failed: ${err.message}`);
  return c.json({ email: e, access }, 201);
});

teacherApi.delete("/admin/teachers/:id", async (c) => {
  const id = c.req.param("id");
  if (id === c.get("teacher").id) return c.json({ error: "You can't remove yourself here." }, 400);
  const t = await c.env.DB.prepare("SELECT id FROM teachers WHERE id = ? AND deleted_at IS NULL").bind(id).first();
  if (!t) return c.json({ error: "not found" }, 404);
  await deleteAccount(c.env, id);
  await logEvent(c.env.DB, c.get("teacher").id, "uninvite", id);
  return c.body(null, 204);
});
```

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "slide2video: admin invites and Access group sync"`

---

### Task 8: Pages, client script, legal pages, local dev

**Files:**
- Create: `src/pages.ts`, `src/client.ts`, `src/legal.ts`, `test/pages.test.ts`
- Modify: `src/index.ts`

**Interfaces:**
- Consumes: everything above; `html`, `raw`, `esc`.
- Produces: pages `/`, `/lessons/new`, `/lessons/:id`, `/devices`, `/account`, `/admin`, `/terms`, `/privacy`;
  `/app.js`, `/app.css`; `lessonStatus(...)` text; `mdLite(text) -> Raw`.

- [ ] **Step 1: Write the failing tests**

`test/pages.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { exports } from "cloudflare:workers";
import { BASE, PLAN, QUESTIONS, asTeacher, claim, finish, newLesson, pairDevice, seedTeacher } from "./helpers";

const EVIL = `<script>alert(1)</script>"><img src=x onerror=alert(2)>`;

describe("pages", () => {
  it("serves the public pages without sign-in, with headers", async () => {
    for (const p of ["/terms", "/privacy", "/app.css"]) {
      const r = await exports.default.fetch(BASE + p);
      expect(r.status, p).toBe(200);
      expect(r.headers.get("Content-Security-Policy")).toContain("script-src 'self'");
    }
    expect(await (await exports.default.fetch(BASE + "/privacy")).text()).toContain("Cloudflare");
  });

  it("lists lessons with a status, escaping titles", async () => {
    const t = await seedTeacher();
    await newLesson(t.email, { title: EVIL });
    const page = await (await asTeacher(t.email, "/")).text();
    expect(page).not.toContain("<script>alert(1)");
    expect(page).not.toContain("<img src=x");
    expect(page).toContain("&lt;script&gt;");
    expect(page).toContain("Waiting for your Mac");
  });

  it("renders a questions card as a form, escaping everything", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, { ...QUESTIONS, message: EVIL,
      questions: [{ id: "grade", text: EVIL, options: [{ label: EVIL, detail: EVIL }], other: true }] });
    const page = await (await asTeacher(t.email, `/lessons/${id}`)).text();
    expect(page).not.toContain("<script>alert");
    expect(page).not.toContain("<img src=x");
    expect(page).toContain('data-kind="answers"');
    expect(page).toContain('name="q:grade"');
  });

  it("renders plan markdown safely", async () => {
    const t = await seedTeacher();
    const mac = await pairDevice(t.email);
    const id = await newLesson(t.email);
    const turn = await claim(mac.token);
    await finish(mac.token, turn.turn.id, { ...PLAN, markdown: `## Chapter 1\n- ${EVIL}` });
    const page = await (await asTeacher(t.email, `/lessons/${id}`)).text();
    expect(page).toContain("<h3>Chapter 1</h3>");
    expect(page).not.toContain("<script>alert");
    expect(page).toContain("Approve");
  });

  it("doesn't show another teacher's lesson", async () => {
    const a = await seedTeacher();
    const b = await seedTeacher();
    const id = await newLesson(a.email);
    expect((await asTeacher(b.email, `/lessons/${id}`)).status).toBe(404);
  });

  it("serves the client script and the other pages", async () => {
    const t = await seedTeacher();
    expect((await (await asTeacher(t.email, "/app.js")).text())).toContain("X-S2V");
    for (const p of ["/lessons/new", "/devices", "/account"]) expect((await asTeacher(t.email, p)).status, p).toBe(200);
    expect((await asTeacher(t.email, "/admin")).status).toBe(403);
    expect((await asTeacher("admin@example.org", "/admin")).status).toBe(200);
  });
});
```

- [ ] **Step 2: Run to see it fail** — `npm test -- test/pages.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement**

`src/legal.ts` (drafts; the page header says so):

```ts
import { html, type Raw } from "./http";

const DRAFT = html`<p class="note">Draft, to be reviewed by the school district or a lawyer before teachers are invited.</p>`;

export const terms: Raw = html`<h1>Terms of use</h1>${DRAFT}
<p>slide2video.com is an invite-only service run by Daniel Landi that helps teachers turn their own slide decks into
narrated study videos. The videos are made on the teacher's own Mac, with the teacher's own Claude subscription.</p>
<h2>What you may upload</h2>
<ul><li>Material you made or have the right to use for teaching: slides, PDFs, worksheets, images.</li>
<li><strong>Never student information</strong>: no student names, photos of students, student work or grades.</li></ul>
<h2>Your material</h2>
<p>You keep ownership of everything you upload and of the videos made from it. slide2video stores it only to show
it to you and to send it to the Macs you connected.</p>
<h2>The service</h2>
<p>The service may change or stop; you'll get at least 30 days' notice by email to download your material. Access
can be removed if these terms are broken.</p>
<h2>Contact</h2><p>Write to the person who invited you, or use the contact on the Privacy page.</p>`;

export const privacy: Raw = html`<h1>Privacy policy</h1>${DRAFT}
<h2>What is stored</h2>
<ul><li>Your email address (to let you sign in).</li>
<li>The files you upload, the questions and plans Claude sends back, your answers and notes, and the videos,
captions and pictures your Mac sends.</li>
<li>The names of the Macs you connected and when they last checked in.</li>
<li>A short log of actions (uploads, deletions, exports, connected Macs) to investigate problems.</li></ul>
<h2>Where</h2>
<p>On Cloudflare (hosting, file storage, database and sign-in). Storage is set to prefer western North America;
Cloudflare does not guarantee a US-only location for this kind of storage.</p>
<h2>Who processes what</h2>
<ul><li><strong>Cloudflare</strong> hosts the site, stores the files and sends sign-in codes.</li>
<li><strong>Your own Mac</strong> downloads your files and makes the videos. On it, and under your own accounts and
choices: Anthropic (Claude, through your Claude subscription) reads the deck; Microsoft or ElevenLabs makes the
narration; Google makes optional music and clips.</li>
<li>The website itself never sends your files to Anthropic, Microsoft, ElevenLabs or Google.</li></ul>
<h2>What is never done</h2>
<p>No advertising, no selling or sharing of your data, no profiles of you or of any student.</p>
<h2>How long, and your rights</h2>
<p>Everything stays until you delete it. Deleting a lesson removes it from the site at once and from your Mac the
next time it checks in. You can download everything (Account → Export) or delete your account at any time.</p>
<h2>If something goes wrong</h2>
<p>If your data is exposed, you'll be told by email within 72 hours of it being discovered.</p>
<h2>Schools</h2>
<p>A school district that needs a signed Washington Student Data Privacy Agreement can ask for one.</p>
<h2>Contact</h2><p>Daniel Landi, through the email address that sent your invitation.</p>`;
```

`src/client.ts`:

```ts
export const APP_CSS = `
:root{color-scheme:light dark;--fg:#1d1d1f;--bg:#fbfbfa;--muted:#6b6b6b;--line:#e2e2e0;--accent:#2b59c3;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--fg:#ececec;--bg:#161616;--muted:#a0a0a0;--line:#333;--accent:#8fb0ff;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,sans-serif;color:var(--fg);background:var(--bg)}
header,main,footer{max-width:820px;margin:0 auto;padding:16px}header nav a{margin-right:16px}a{color:var(--accent)}
.card{border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}.muted,.note{color:var(--muted)}
.error{color:var(--bad)}button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--line);cursor:pointer}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}input,textarea{font:inherit;width:100%;padding:8px;margin:4px 0 12px}
fieldset{border:1px solid var(--line);border-radius:8px;margin:12px 0}label{display:block}
input[type=radio],input[type=checkbox]{width:auto;margin-right:6px}video{width:100%;border-radius:8px}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:6px;border-bottom:1px solid var(--line)}`;

export const APP_JS = `
async function api(method, url, body) {
  const r = await fetch(url, { method, headers: { "X-S2V": "1", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.error || "Request failed (" + r.status + ")"); }
  return r.status === 204 ? null : r.json();
}
function fields(form) {
  const o = {};
  for (const el of form.elements) if (el.name && el.type !== "file") o[el.name] = el.type === "checkbox" ? el.checked : el.value;
  return o;
}
function answers(form) {
  const out = [];
  for (const fs of form.querySelectorAll("fieldset[data-q]")) {
    const id = fs.dataset.q, picked = fs.querySelector("input[type=radio]:checked");
    const other = fs.querySelector("input[name='o:" + id + "']");
    const isOther = !picked || picked.value === "__other";
    out.push({ question: id, choice: isOther ? null : picked.value, other: isOther && other ? other.value : null });
  }
  return { answers: out };
}
async function newLesson(form) {
  const f = fields(form);
  const { id } = await api("POST", "/api/lessons", { title: f.title, instructions: f.instructions, attest: f.attest });
  for (const [field, kind] of [["deck", "deck"], ["extra", "extra"]]) {
    for (const file of form.elements[field].files) {
      const r = await fetch("/api/lessons/" + id + "/files?name=" + encodeURIComponent(file.name) + "&kind=" + kind,
        { method: "PUT", headers: { "X-S2V": "1", "Content-Type": file.type || "application/octet-stream" }, body: file });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || "Upload of " + file.name + " failed");
    }
  }
  await api("POST", "/api/lessons/" + id + "/start");
  return { id };
}
document.addEventListener("submit", async (ev) => {
  const form = ev.target;
  if (!(form instanceof HTMLFormElement) || !form.dataset.api) return;
  ev.preventDefault();
  const spec = (ev.submitter && ev.submitter.dataset.api) || form.dataset.api;
  const [method, url] = spec.split(" ");
  for (const b of form.querySelectorAll("button")) b.disabled = true;
  try {
    const kind = form.dataset.kind;
    const res = kind === "new-lesson" ? await newLesson(form)
      : await api(method, url, kind === "answers" ? answers(form) : kind === "none" ? undefined : fields(form));
    location.href = form.dataset.next ? form.dataset.next.replace(":id", (res && res.id) || "") : location.href;
  } catch (e) {
    let p = form.querySelector(".error");
    if (!p) { p = document.createElement("p"); p.className = "error"; form.append(p); }
    p.textContent = e.message;
    for (const b of form.querySelectorAll("button")) b.disabled = false;
  }
});
if (document.body.dataset.refresh) setTimeout(() => location.reload(), Number(document.body.dataset.refresh) * 1000);`;
```

`src/pages.ts`:

```ts
import { Hono } from "hono";
import type { AppEnv, Teacher } from "./env";
import { html, raw, type Raw } from "./http";
import { isAdmin } from "./auth";
import { busy, latestCard } from "./turns";

export const pages = new Hono<AppEnv>();

function layout(title: string, body: Raw, t: Teacher, admin: boolean, refresh = 0): string {
  return html`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} · slide2video</title><link rel="stylesheet" href="/app.css"></head>
<body${refresh ? raw(` data-refresh="${refresh}"`) : raw("")}><header><nav><strong>slide2video</strong> &nbsp;
<a href="/">Lessons</a><a href="/devices">Devices</a><a href="/account">Account</a>${admin ? html`<a href="/admin">Admin</a>` : ""}
<span class="muted">${t.email}</span></nav></header><main>${body}</main>
<footer class="muted"><a href="/terms">Terms</a> · <a href="/privacy">Privacy</a></footer>
<script src="/app.js"></script></body></html>`.s;
}

/** Minimal, safe Markdown: escape first, then "## " headings and "- " list items. */
export function mdLite(text: string): Raw {
  const lines = text.split("\n").map((l) => {
    if (l.startsWith("## ")) return html`<h3>${l.slice(3)}</h3>`.s;
    if (l.startsWith("- ")) return html`<li>${l.slice(2)}</li>`.s;
    return l.trim() ? html`<p>${l}</p>`.s : "";
  });
  return raw(lines.join("\n"));
}

const ago = (s: number | null) => {
  if (!s) return "never";
  const m = Math.round((Date.now() / 1000 - s) / 60);
  return m < 2 ? "just now" : m < 120 ? `${m} min ago` : `${Math.round(m / 60)} h ago`;
};

async function lessonStatus(db: D1Database, lesson: any): Promise<string> {
  if (lesson.deleted_at) return "Removing from your Mac";
  const turn = await db.prepare("SELECT state, progress, not_before FROM turns WHERE lesson_id = ? ORDER BY seq DESC LIMIT 1").bind(lesson.id).first<any>();
  if (turn?.state === "running") return `Your Mac is working${turn.progress ? `: ${turn.progress}` : ""}`;
  if (turn?.state === "queued") {
    const home = lesson.home_device_id
      ? await db.prepare("SELECT last_seen FROM devices WHERE id = ?").bind(lesson.home_device_id).first<any>() : null;
    if (turn.not_before) return `Waiting for your Claude plan's limit to reset`;
    return home ? `Waiting for your Mac (last seen ${ago(home.last_seen)})` : "Waiting for your Mac";
  }
  const card = await latestCard(db, lesson.id);
  const body = card ? JSON.parse(card.body) : null;
  return ({ questions: "Waiting for your answers", plan: "Plan waiting for your approval",
    review: `Chapter ${body?.chapter} ready to review`, done: "Done", error: "Something went wrong" } as Record<string, string>)[card?.kind ?? ""] ?? "Not started";
}

pages.get("/", async (c) => {
  const t = c.get("teacher");
  const { results } = await c.env.DB.prepare("SELECT * FROM lessons WHERE teacher_id = ? ORDER BY updated_at DESC").bind(t.id).all<any>();
  const rows = [];
  for (const l of results) rows.push(html`<tr><td>${l.deleted_at ? html`<span class="muted">Deleted lesson</span>` : html`<a href="/lessons/${l.id}">${l.title}</a>`}</td><td>${await lessonStatus(c.env.DB, l)}</td></tr>`);
  return c.html(layout("Lessons", html`<h1>Lessons</h1><p><a href="/lessons/new">New lesson</a></p>
${rows.length ? html`<table><tr><th>Lesson</th><th>Status</th></tr>${rows}</table>` : html`<p class="muted">No lessons yet.</p>`}`, t, isAdmin(c), 30));
});

pages.get("/lessons/new", (c) => c.html(layout("New lesson", html`<h1>New lesson</h1>
<form data-api="POST /api/lessons" data-kind="new-lesson" data-next="/lessons/:id">
<label>Title <input name="title" required maxlength="200"></label>
<label>Slide deck (.pptx or .pdf) <input type="file" name="deck" accept=".pptx,.pdf" required></label>
<label>Other files (optional: worksheets, review sheets) <input type="file" name="extra" multiple accept=".pptx,.pdf,.docx,.png,.jpg,.jpeg"></label>
<label>Instructions for Claude (optional) <textarea name="instructions" maxlength="4000" rows="3"></textarea></label>
<label><input type="checkbox" name="attest" required> These files contain no student names, photos or work.</label>
<button class="primary">Upload and start</button></form>`, c.get("teacher"), isAdmin(c))));

function cardView(lessonId: string, card: any, open: boolean): Raw {
  const b = JSON.parse(card.body);
  const msg = html`<p>${b.message}</p>`;
  const file = (p: string) => `/api/lessons/${lessonId}/file?path=${encodeURIComponent(p)}`;
  if (card.kind === "questions") {
    const qs = b.questions.map((q: any) => html`<fieldset data-q="${q.id}"><legend>${q.text}</legend>
${q.options.map((o: any, i: number) => html`<label><input type="radio" name="q:${q.id}" value="${o.label}" ${i === 0 ? raw("checked") : ""}> ${o.label} ${o.detail ? html`<span class="muted">${o.detail}</span>` : ""}</label>`)}
${q.other ? html`<label><input type="radio" name="q:${q.id}" value="__other"> Other: <input name="o:${q.id}" maxlength="2000"></label>` : ""}</fieldset>`);
    return html`<div class="card">${msg}${open ? html`<form data-api="POST /api/lessons/${lessonId}/answer" data-kind="answers">${qs}<button class="primary">Send answers</button></form>` : qs}</div>`;
  }
  if (card.kind === "plan") {
    return html`<div class="card">${msg}${mdLite(b.markdown)}<p class="muted">Estimated cost: $${b.estimate.usd.toFixed(2)} · about ${b.estimate.minutes} min per video · ${b.estimate.chapters} chapter(s)</p>
${open ? html`<form data-api="POST /api/lessons/${lessonId}/change"><label>Change something <textarea name="feedback" rows="2"></textarea></label>
<button data-api="POST /api/lessons/${lessonId}/approve" class="primary" formnovalidate>Approve</button> <button>Send changes</button></form>` : ""}</div>`;
  }
  if (card.kind === "review") {
    return html`<div class="card"><h2>Chapter ${b.chapter}${b.version ? html` <span class="muted">v${b.version}</span>` : ""}</h2>${msg}
<video controls preload="metadata" src="${file(b.video)}">${b.captions ? html`<track kind="captions" src="${file(b.captions)}" default>` : ""}</video>
<p><a href="${file(b.video)}">Download video</a>${b.captions ? html` · <a href="${file(b.captions)}">Captions (.vtt)</a>` : ""}</p>
${open ? html`<form data-api="POST /api/lessons/${lessonId}/feedback"><label>What would you change? <textarea name="feedback" rows="3"></textarea></label>
<button data-api="POST /api/lessons/${lessonId}/continue" data-kind="none" class="primary" formnovalidate>Looks good, continue</button> <button>Send feedback</button></form>` : ""}</div>`;
  }
  if (card.kind === "error") {
    return html`<div class="card"><p class="error">${b.message}</p>${b.log_tail ? html`<details><summary>Details</summary><pre>${b.log_tail}</pre></details>` : ""}
${open && !b.retry_after ? html`<form data-api="POST /api/lessons/${lessonId}/retry" data-kind="none"><button class="primary">Try again</button></form>` : ""}</div>`;
  }
  return html`<div class="card">${msg}${b.readme ? mdLite(b.readme) : ""}</div>`;
}

pages.get("/lessons/:id", async (c) => {
  const t = c.get("teacher");
  const db = c.env.DB;
  const lesson = await db.prepare("SELECT * FROM lessons WHERE id = ? AND teacher_id = ? AND deleted_at IS NULL").bind(c.req.param("id"), t.id).first<any>();
  if (!lesson) return c.html(layout("Not found", html`<h1>Not found</h1>`, t, isAdmin(c)), 404);
  const { results: cards } = await db.prepare("SELECT * FROM cards WHERE lesson_id = ? ORDER BY created_at DESC, rowid DESC").bind(lesson.id).all<any>();
  const working = await busy(db, lesson.id);
  const status = await lessonStatus(db, lesson);
  const [current, ...older] = cards;
  const body = html`<h1>${lesson.title}</h1><p><strong>${status}</strong></p>
${current ? cardView(lesson.id, current, !working && !current.answered_at) : ""}
${older.length ? html`<details><summary>Earlier steps (${older.length})</summary>${older.map((cd: any) => cardView(lesson.id, cd, false))}</details>` : ""}
<form data-api="DELETE /api/lessons/${lesson.id}" data-kind="none" data-next="/"><button>Delete this lesson</button>
<span class="muted">Removes it from the website now and from your Mac when it next checks in.</span></form>`;
  return c.html(layout(lesson.title, body, t, isAdmin(c), working ? 20 : 0));
});

pages.get("/devices", async (c) => {
  const t = c.get("teacher");
  const { results } = await c.env.DB.prepare("SELECT id, name, last_seen FROM devices WHERE teacher_id = ? AND revoked_at IS NULL ORDER BY created_at").bind(t.id).all<any>();
  return c.html(layout("Devices", html`<h1>Your Macs</h1>
${results.length ? html`<table>${results.map((d: any) => html`<tr><td>${d.name}</td><td class="muted">last seen ${ago(d.last_seen)}</td>
<td><form data-api="DELETE /api/devices/${d.id}" data-kind="none"><button>Remove</button></form></td></tr>`)}</table>` : html`<p class="muted">No Mac connected yet.</p>`}
<h2>Add a Mac</h2><p>On the Mac, in Claude Code, run <code>/lesson-videos:setup</code> and choose to connect it. Type the code it shows here.</p>
<form data-api="POST /api/devices/pair"><label>Code <input name="user_code" required placeholder="KQ7-4M2" maxlength="9"></label><button class="primary">Connect</button></form>`, t, isAdmin(c)));
});

pages.get("/account", (c) => {
  const t = c.get("teacher");
  return c.html(layout("Account", html`<h1>Account</h1><p>Signed in as ${t.email}.</p>
<p><a href="/api/account/export">Download all my data and files (.zip)</a></p>
<h2>Delete my account</h2><p>Deletes every lesson and file from the website now, and from your Macs when they next check in.</p>
<form data-api="DELETE /api/account" data-next="/"><label>Type your email address to confirm <input name="confirm" required></label><button>Delete my account</button></form>`, t, isAdmin(c)));
});

pages.get("/admin", async (c) => {
  const t = c.get("teacher");
  if (!isAdmin(c)) return c.html(layout("Admins only", html`<h1>Admins only</h1>`, t, false), 403);
  const { results } = await c.env.DB.prepare(
    "SELECT t.id, t.email, COALESCE(SUM(f.size), 0) AS bytes FROM teachers t LEFT JOIN files f ON f.teacher_id = t.id WHERE t.deleted_at IS NULL GROUP BY t.id ORDER BY t.email",
  ).all<any>();
  return c.html(layout("Admin", html`<h1>Teachers</h1><table>${results.map((r: any) => html`<tr><td>${r.email}</td><td>${(r.bytes / 1e6).toFixed(1)} MB</td>
<td>${r.id === t.id ? "" : html`<form data-api="DELETE /api/admin/teachers/${r.id}" data-kind="none"><button>Remove</button></form>`}</td></tr>`)}</table>
<h2>Invite</h2><form data-api="POST /api/admin/teachers"><label>Email <input name="email" type="email" required></label><button class="primary">Invite</button></form>`, t, true));
});
```

`src/index.ts` final shape:

```ts
import { Hono } from "hono";
import type { AppEnv } from "./env";
import { html } from "./http";
import { securityHeaders } from "./http";
import { teacherAuth } from "./auth";
import { device } from "./device";
import { teacherApi } from "./teacher-api";
import { pages } from "./pages";
import { APP_CSS, APP_JS } from "./client";
import { privacy, terms } from "./legal";

const app = new Hono<AppEnv>();
app.use("*", securityHeaders);
app.get("/health", (c) => c.text("ok"));
app.get("/app.css", (c) => c.body(APP_CSS, 200, { "Content-Type": "text/css; charset=utf-8" }));
const legal = (title: string, body: typeof terms) =>
  html`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} · slide2video</title><link rel="stylesheet" href="/app.css"><main>${body}</main></html>`.s;
app.get("/terms", (c) => c.html(legal("Terms", terms)));
app.get("/privacy", (c) => c.html(legal("Privacy", privacy)));
app.route("/api/device", device);
app.use("*", teacherAuth);
app.get("/app.js", (c) => c.body(APP_JS, 200, { "Content-Type": "text/javascript; charset=utf-8" }));
app.route("/api", teacherApi);
app.route("/", pages);
export default app;
```

- [ ] **Step 4: Run tests and check** — `npm test && npm run check` — Expected: PASS.

- [ ] **Step 5: Local dev run**

```bash
cp .dev.vars.example .dev.vars   # set DEV_EMAIL to Daniel's address (ask him which)
npm run db:local && npm run dev
```

Open `http://localhost:8787/`: the Lessons page shows (signed in as `DEV_EMAIL`, created as admin only if it equals
`ADMIN_EMAIL`; otherwise insert it once with
`npx wrangler d1 execute slide2video --local --command "INSERT INTO teachers (id, email, created_at) VALUES ('tch_dev0000000000000000000', '<DEV_EMAIL>', 0)"`).
Create a lesson with `~/Projects/plugins/examples/water-cycle.pptx`; the Lessons page shows "Waiting for your Mac".

- [ ] **Step 6: Commit** — `git add -A && git commit -m "slide2video: pages, client script, draft Terms and Privacy"`

---

### Task 9: Deploy to slide2video.com and the first real lesson

Every step here acts outside the repo; **ask Daniel before each numbered step** and do it together.

- [ ] **Step 1: Domain on Cloudflare** — check `slide2video.com` is a zone in Daniel's Cloudflare account
  (`npx wrangler whoami`, then the dashboard). If it was registered elsewhere, Daniel changes its nameservers to
  Cloudflare's and waits for "Active".

- [ ] **Step 2: Storage**

```bash
npx wrangler d1 create slide2video --location wnam      # put the printed database_id in wrangler.jsonc
npx wrangler r2 bucket create slide2video-files --location wnam
npx wrangler d1 migrations apply slide2video --remote
```

- [ ] **Step 3: Access (Zero Trust dashboard, with Daniel)**
  1. Settings → Authentication: enable **One-time PIN**.
  2. Access → Groups: create **slide2video teachers**, include Daniel's email. Note the group id.
  3. Access → Applications → Add self-hosted: domain `slide2video.com`, policy **Allow** group *slide2video
     teachers*, session 30 days. Note the **AUD tag** and the team domain (`https://<team>.cloudflareaccess.com`).
  4. Add a second self-hosted application with policy **Bypass / Everyone** for the paths
     `slide2video.com/api/device`, `slide2video.com/terms`, `slide2video.com/privacy`, `slide2video.com/app.css`.
  5. API token (My Profile → API Tokens): permission **Account → Access: Organizations, Identity Providers, and
     Groups → Edit**, this account only.

- [ ] **Step 4: Config and secrets** — in `wrangler.jsonc` vars set `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD`,
  `ADMIN_EMAIL` (Daniel's sign-in address; ask him), `CF_ACCOUNT_ID`, `ACCESS_GROUP_ID`. Then
  `npx wrangler secret put CF_API_TOKEN`. Commit the vars (no secrets).

- [ ] **Step 5: Deploy and smoke test**

```bash
npm run check && npm test && npm run deploy
curl -s -o /dev/null -w '%{http_code}\n' https://slide2video.com/               # 302 (to Access)
curl -s -o /dev/null -w '%{http_code}\n' https://slide2video.com/terms          # 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://slide2video.com/api/device/pair/start   # 426
```

Sign in at https://slide2video.com with Daniel's email (one-time PIN): the Lessons page shows, with Admin.

- [ ] **Step 6: The first real lesson (M1 done-when)** — this is M1-A's Task 5 against production: on Daniel's
  Mac, `uv run ~/Projects/plugins/lesson-videos/scripts/lesson-videos.py pair`, enter the code on
  slide2video.com/devices, create a lesson with `examples/water-cycle.pptx`, and run `… worker --once` after each
  answer. Expected cards: questions → plan → review (chapter 1 plays on the site, the captions show) → done. Record
  timings and any Claude permission denials in the ledger.

- [ ] **Step 7: Push** — `git push -u origin main` (repo created in Task 1 step 1).
