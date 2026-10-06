# <repo-name>

<!-- One-to-three lines: what this repo is, what it produces, where it runs. -->

## Contribution flow

<!-- Keep exactly ONE of the three tier blocks below and delete the others.
     Tier A = deployed or paired product. Tier B = solo dev tool.
     Tier C = static site / config repo. -->

This is a **Tier A repo** (deployed/paired product): code changes land via
feature branch → PR → CI green → **squash merge** (`gh pr merge --squash`), so
every PR is exactly one commit on `main`. No direct pushes to `main`. (Run
`REQUIRED_CHECKS=<your CI job names> ./bootstrap.sh` once to enable branch
protection and this merge policy — and verify it took, since this sentence is
false until you do.)

This is a **Tier B repo** (solo dev tool): work on a short-lived branch off
`main`, run the local test gates below, merge back to `main` directly (no PR
needed), and push. PRs are optional and only opened when asked.

This is a **Tier C repo** (static site / config): edit and push to `main`
directly. <!-- State what a push triggers, e.g. "Pages redeploys in ~30s". -->

## Work tracking

GitHub Issues is the single source of truth for pending work — no file-based
trackers. Capture follow-ups with the `inbox` skill; milestones are umbrella
issues (`gh issue list --label milestone`); close via PR with `Closes #n` (or
reference the issue from the commit). For sandboxed sessions pass
`-R DanielLandi/<repo-name>` to `gh`.

## Build & test

<!-- The commands an agent needs: setup, test gate(s), run. Delete if N/A. -->

```bash
# setup:
# test (THE gate before merging):
# run:
```

## External services

See [`SERVICES.md`](./SERVICES.md) — update it in the same commit whenever a
service dependency is added, removed, or re-keyed.

## Frozen directories

Anything under `docs/archive/` or any file with an `⚠️ ARCHIVED` banner is
historical reference only — never a source of truth for current behavior.
