---
name: okf-read
description: |
  Recall from an OKF knowledge bundle without serving stale facts: `okf search --json`
  joined with `drift check --format json`, so a concept whose code_refs changed since
  it was written is withheld from the answer and reported with the commit to blame.

  NOT YET IMPLEMENTED — placeholder for the drift phase. See the plan named below.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-read.
---

# /okf-read — not yet implemented

This skill is the read half of the `okf-drift` plugin. Its shape is decided; its
implementation waits on the drift phase, which has its own plan (follow-ups 1 and 2 of
`docs/plans/2026-09-15-001-chore-migrate-mex-to-okf-plan.md` in
offline-payment-attestation, to be planned and `/plan-eng-review`ed before code).

What it will do:

```
scripts/okf-recall.sh "<terms>"
  ├─ okf search "<terms>" knowledge --json      → candidates [id, path, description, score]
  ├─ drift check --format json                  → docs[] with status and blame
  └─ join on docs[].path == knowledge/<id>.md
       ├─ fresh   → returned as okf search would
       └─ drifted → WITHHELD, listed separately with the blaming commit and the
                    concept's last_updated, so the agent reads the code instead of
                    the prose, or fixes the concept first
```

Drift is a hard dependency of this skill by design: a recall that cannot tell a fact
from a stale one is what the plugin exists to replace. With no `drift.lock` in the repo
the skill stops and says so rather than degrading to a bare search.

The first task of that phase is a measurement, not code: whether `drift check` has a
`--format json` with the `drift.check.v1` schema the migration plan recorded, or only
the text output an earlier note said is the interface. The join is written against
whichever is true.

Until then: `okf search "<terms>"`, and read `last_updated` against `git log` on the
concept's `code_refs` before trusting it.
