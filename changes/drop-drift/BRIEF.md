# BRIEF — drop drift (0.15.0)

Decision and evidence: `docs/adr/0002-drop-drift-code-is-the-source-of-truth.md`.
Terms: `GLOSSARY.md` (change hint, read-repair). Do not confuse drift (the tool, removed)
with `okf validate --drift` (okf's own dead-`code_refs` check, kept).

## Out of scope

Migrating the consumer repos (margins/ai-review, offline-payment-attestation, pinguino,
others): the owner does it separately. Renaming the plugin. 1.0.0. Any change to
`stale_after` or its gate.

## Remove

- `scripts/okf-restamp.sh`, `scripts/okf-lock-merge.py`, `scripts/okf-drift-bootstrap.sh`.
- `scripts/okf-check.sh`: the drift join, the "no tracked target" report, the
  "drift did not run" warning. Keep every structural check and `okf validate --drift`.
- `scripts/okf-recall.sh`: the `drift check` join and the STALE marking.
- `scripts/okf-pin.sh` and `.github/workflows/release.yml`: `drift-bootstrap` (and the
  removed scripts) from the required SHA256SUMS set.
- `scripts/okf-integrate.py`: the `drift.lock` validation and messages.
- `.github/workflows/ci.yml`: the drift install/pin and every drift fixture
  (`drift link`, `drift.lock` counts, "drifted from" asserts).
- Selftests (`okf-runtime-selftest.py`, `okf-launcher-selftest.py`,
  `okf-shim-selftest.sh`): drift cases; add the cases below.

## Add

- **Change hint** in `okf-recall.sh` output, per hit:
  commits on `<code_refs>` after the concept's last commit (`git rev-list --count
  <base>..HEAD -- <code_refs>`; a date cannot order two commits of one day) →
  `code changed since this concept: N commit(s) on <paths> (last <sha> <date> "<subject>")`,
  or nothing when N = 0, no `code_refs`, no commit, or outside git.
  Directories work as paths. Informative only, never an exit code.
- **Gate**: fail while `drift.lock` exists at the repo root
  (`drift.lock found: drift is no longer used, run /okf-migrate`).
- **Selftests**: hint with 0 / N commits, directory `code_refs`, concept without
  `code_refs`; gate red on a leftover `drift.lock`.

## Rewrite (skills and templates)

- `skills/okf-write/SKILL.md`: drop step 3 (re-stamp), binding, anchoring, "do not bind
  high-churn files". Generalise its "name where the fact lives" rule to every concept:
  no signatures, defaults, step lists, numbers or field lists that live in the code;
  hold why, invariants, traps, conventions, how to behave, where to look (`code_refs`);
  a fact that must be quoted from the code is a dated observation.
- `skills/okf-read/SKILL.md` and `skills/okf-runtime/SKILL.md`: recall shows the change
  hint; read-repair rule — when a concept you rely on contradicts the code, the code
  wins; fix the concept with an ordinary `/okf-write` edit if the session already
  writes the repo, else say so in the answer. Concepts only listed in results: nothing.
  No `verified_at`, no dedicated log line.
- `skills/okf-setup/SKILL.md`, `templates/CLAUDE-knowledge-section.md`,
  `templates/knowledge.yml`: no drift install, bootstrap, `drift check --changed`,
  re-stamp or lock-merge; Context/Grow loop restated with the hint and read-repair.
- `skills/okf-setup/references/okf-quirks.md`: drop drift measurements; keep okf ones.
- `skills/okf-migrate/SKILL.md`: add a "drop drift" part. It explains what to migrate:
  delete `drift.lock`; review the CI workflow (remove the drift install/pin and the
  bootstrap step); replace the `CLAUDE.md` knowledge section with the new template,
  keeping the repo's own additions (show the diff before writing); then, on request,
  review every concept against the writing rule, proposing per concept a cut or a
  rewrite as "where to look + why", shown before writing. Idempotent; no commit.
- `README.md`: drop "the two halves" (drift gate, re-stamp rule) and the lock resolver;
  describe the hint, read-repair and the writing rule.

## Release

`VERSION` 0.15.0; `CHANGELOG.md` entry marking the break (consumers must run
`/okf-migrate`). Land per `landing-classify`; no push or PR without the owner's go-ahead.
