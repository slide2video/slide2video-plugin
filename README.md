# <repo-name>

<!-- Human-facing overview: what this is, how to run it. -->

---

*Created from [`repo-template`](https://github.com/DanielLandi/repo-template).
After creating the repo: fill in `AGENTS.md` (pick a contribution tier),
`SERVICES.md`, and this README; then run `./bootstrap.sh` and delete this
footer.*

*`./bootstrap.sh` defaults to Tier A and requires a check named `test`. Pass
`TIER=B` (or `C`) for repo settings without branch protection, and
`REQUIRED_CHECKS=` to match your CI — `REQUIRED_CHECKS=ci,lint`, or empty for
PR-required-but-no-checks. **Never require a check that will not report on
every PR**: a path-filtered or not-yet-existing job leaves PRs stuck on
"Expected — Waiting for status" permanently.*
