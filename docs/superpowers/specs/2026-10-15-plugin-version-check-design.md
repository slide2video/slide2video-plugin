# Plugin version check between lesson-videos and slide2video.com

**Date:** 2026-10-15 · **Status:** design approved in chat; written spec awaiting review
**Repos:** `plugins` (`lesson-videos`: site calls, `worker --status` / `--watch`, the serve and setup skills,
`site-contract/`) + `slide2video` (device API, Devices list, waiting lesson panel, migration `0005`)

## 1. Purpose

Today a computer tells the website only a contract number (`X-LV-Contract: 1`), changed by hand for breaking
changes. Nobody can see which plugin version a computer runs, and a teacher on an old plugin gets no hint until
something breaks. After this change:

- the website knows the plugin version it was built for;
- every computer reports its plugin version, and the Devices list shows it per computer;
- a computer on a different **major** version is refused, with the steps to update; an older version within the
  same major keeps working but is told, in Claude Code and on the website, that an update is available;
- both repos' `AGENTS.md` say when a plugin release requires updating and deploying the website.

**Decisions taken in the brainstorm (2026-10-15):**

| Topic | Decision |
|---|---|
| Refuse vs warn | Refuse only on a **different major** (website 2.1.0: plugin 1.4.0 refused, plugin 2.0.0 works with an "update available" warning). Older within the major: warn. Newer within the major: fine, no warning. |
| Contract number | The plugin's **major version replaces it.** A breaking change to the job contract = a major bump. |
| First release | This ships as **lesson-videos 1.0.0** (on 0.x every release would count as the same major). Computers on 0.7.0 are refused once and told to update; no pre-1.0 compatibility is kept beyond the rollout step in §6. |
| Where the website's version lives | Pinned at deploy time in the copied `contract/contract.json`, not fetched from GitHub at run time. |
| Update steps shown everywhere | Run `/plugin update lesson-videos`, then close and reopen Claude Code, then run `/lesson-videos:serve`. Reopening is needed because a running worker keeps its old code. |

**Success:** with the website at 1.0.0, a computer on 0.7.0 is told to update by both Claude Code and the Devices
list; after updating it shows "Online · lesson-videos 1.0.0". When the website is later deployed at 1.1.0, a
computer still on 1.0.0 keeps working and both places say an update is available.

## 2. The contract

`lesson-videos/site-contract/contract.json` (copied to `slide2video/contract/contract.json`) becomes:

```json
{"plugin": "1.0.0"}
```

- `plugin` is the plugin version the website is built for, `MAJOR.MINOR.PATCH` (digits only).
- The **contract version** is that version's major. It is what the schemas' `"contract": {"const": N}` and the
  `"contract"` field in turns and cards carry. For 1.x it stays `1`, so today's schemas and payloads are unchanged.
  A major bump bumps the schemas' `const` with it.
- `lv.contract.VERSION` and the site's `CONTRACT_VERSION` are derived from `plugin` (major), not stored separately.
- Plugin packaging test (`tests/test_packaging.py`): `contract.json` `plugin` parses, has the **same major** as the
  plugin's own version, and is **not newer** than it.

## 3. The wire

**Every device call** (pairing included) sends `X-LV-Plugin: <the plugin's own version>`.

**The website** (`slide2video/src/device.ts`, replacing the `X-LV-Contract` middleware):

1. Parse `X-LV-Plugin`. Missing or not `MAJOR.MINOR.PATCH` → the plugin is treated as too old.
2. For routes that identify a computer (everything after `deviceAuth`): authenticate first, then store
   `devices.plugin_version` (the header value, or NULL when unreadable) together with `last_seen`, then compare.
   Pairing routes (`/pair/start`, `/pair/poll`) compare without storing (no computer yet).
3. Compare with the website's `plugin`:
   - **Plugin major lower, or unreadable** → `426 {"error": NEEDS_UPDATE}`;
   - **Plugin major higher** → `426 {"error": SITE_BEHIND}`;
   - **Same major** → continue.
4. **Every** answer to a device call that passed the check carries `X-LV-Latest: <website plugin>`.

Messages (one source each, in the site's `contract.ts`; the plugin only prints what the website sends):

- `NEEDS_UPDATE`: "This computer has lesson-videos {have}; slide2video.com needs {major}.x. To update: run
  /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve." (`{have}` is
  "an older version" when the header was missing or unreadable.)
- `SITE_BEHIND`: "slide2video.com hasn't caught up with lesson-videos {have} yet. Nothing to do on this computer;
  try again later."

The plugin's existing 426 handling (`site.call`: print the website's `error`, else its own `UPDATE`) stays;
`UPDATE` (the fallback) gains the reopen step.

**Database:** migration `0005_plugin_version.sql`: `ALTER TABLE devices ADD COLUMN plugin_version TEXT;`.

## 4. Claude Code side (`plugins/lesson-videos`)

- `lesson-videos/scripts/lv/__init__.py` version → `1.0.0` (with `plugin.json` and the marketplace entry).
- `site.call` adds `X-LV-Plugin` to every call and keeps the last `X-LV-Latest` it saw (a module-level value;
  `net.request` returns or exposes the response headers as needed).
- **`worker --status`**: "Connected to {site} as {email} (this device: {name}, lesson-videos {version})." When
  `X-LV-Latest` is newer than the plugin within the same major, a second line:
  "A newer lesson-videos ({latest}) is available. To update: run /plugin update lesson-videos, then close and
  reopen Claude Code, then run /lesson-videos:serve."
- **`worker --watch`**: the start line names the version ("Making videos for {site} as {email} on {name} with
  lesson-videos {version}. …"). The update line above is printed once after the start line when it applies, and
  again only when a later answer brings a **different** `X-LV-Latest` that is still newer. It never stops the
  worker. A 426 stops it, as today, with the website's message.
- **Skills**:
  - `serve`: the "Update the lesson-videos plugin" case becomes "run `/plugin update lesson-videos`, then close and
    reopen Claude Code, then run this skill again"; a "hasn't caught up" message means nothing to do on this
    computer; "Is it working?" may mention the version line; the "newer version is available" line is passed on in
    plain words without stopping anything.
  - `setup`: where it tells the teacher to update the plugin, the same three steps.
- Version comparison lives in one small helper (`lv/version.py` or inside `site.py`): parse `MAJOR.MINOR.PATCH`,
  compare tuples. No dependency.

## 5. Website side (`slide2video`)

- `src/contract.ts`: `PLUGIN` (the string), `CONTRACT_VERSION` (its major), `parseVersion`, `compareVersions`,
  `NEEDS_UPDATE`, `SITE_BEHIND`.
- **Devices list** (`/devices`): each computer's meta line adds the version:
  - same major, not older → "Online · lesson-videos 1.0.0" (any state: Online, Offline, Stopping…, Disconnected);
  - same major, older → "… · lesson-videos 1.0.0 · update available (1.1.0)";
  - different major, or NULL (never reported, e.g. still on 0.7.0) → "Needs an update", with the three steps
    under the row. The Disconnect button stays hidden for it (it cannot pick up a stop anyway).
- **Waiting lesson panel and lessons list** (the "Starting soon" logic): a computer that needs an update is never
  "ready". When the lesson's home computer (or, before it has one, every one of the teacher's computers) needs an
  update, the panel reads "**{name} needs an update** before it can make this video" with the three steps, and
  the list status reads "Waiting for {name} to update".
- Cross-teacher: the version is shown only on the owner's own pages; nothing new is exposed across teachers.

## 6. Rollout (order matters)

1. **Plugin 1.0.0** is released first. It sends **both** `X-LV-Plugin: 1.0.0` and `X-LV-Contract: 1`, so the
   website still running the old check accepts it. It reads `X-LV-Latest` when present and ignores its absence.
2. **The website** is deployed with `contract/contract.json` = `{"plugin": "1.0.0"}` and migration `0005`
   applied to the remote D1.
3. Computers still on 0.7.0 send no `X-LV-Plugin` and are refused with `NEEDS_UPDATE`. 0.7.0 already prints the
   website's 426 message, so they see the full steps without any change on their side.
4. A later plugin release drops `X-LV-Contract`.

## 7. The rule, in both `AGENTS.md`

- **plugins** (`lesson-videos` section): "`site-contract/contract.json` `plugin` is the plugin version
  slide2video.com is built for. When a release changes anything the website or the worker relies on (the job
  contract, device calls, card or turn fields, what the website shows about computers), set `plugin` to the new
  version, copy `site-contract/` to slide2video, and deploy the website. A breaking change to the contract is a
  **major** bump (and bumps the schemas' `const`). Releases that touch neither need no website deploy: a computer
  newer than the website, within its major, is fine."
- **slide2video** (Paired repo section, replacing the `X-LV-Contract` sentence): "`contract/contract.json`
  `plugin` is the plugin version this website is built for; every computer is compared with it (`X-LV-Plugin`:
  a different major is refused, an older one is told to update). Changing it means deploying."

## 8. Testing

**Website (vitest):**
- `parseVersion` / `compareVersions`: valid, invalid, equal, older/newer by major, minor and patch.
- Device check: missing, unreadable, lower major → 426 `NEEDS_UPDATE`; higher major → 426 `SITE_BEHIND`; same
  major older, equal, newer → passes; `X-LV-Latest` on passing answers (200 and 204); pairing routes check
  without storing.
- `devices.plugin_version` is stored on an authenticated call, including a refused one, and `last_seen` too.
- Devices list: version shown; "update available"; "Needs an update" with the steps and no Disconnect; NULL
  version shows "Needs an update"; another teacher never sees the row.
- Waiting panel and lessons list: a computer that needs an update shows the update panel, never "Starting soon".
- Existing tests that send `X-LV-Contract` switch to `X-LV-Plugin` via the helpers.

**Plugin (pytest):**
- `site.call` sends `X-LV-Plugin` and `X-LV-Contract`; records `X-LV-Latest`.
- `worker --status` prints the version and, when older within the major, the update line; not when equal or newer.
- `worker --watch` prints the update line once, again only when `X-LV-Latest` changes, and keeps running; a 426
  with either message stops it and prints the message.
- Packaging: `contract.json` `plugin` same major as, and not newer than, the plugin version; the three version
  files agree at 1.0.0.
- Skill text: serve and setup carry the three steps (close and reopen Claude Code included).

## 9. Out of scope

- Fetching the newest version from GitHub at run time.
- Updating the plugin automatically, or restarting Claude Code for the teacher.
- Version checks for the local `/lesson-videos:make` flow (no website involved).
