---
name: okf-write
description: |
  Record into an OKF knowledge bundle — the Grow step: update project/state.md, write a
  decision or a playbook, fix a concept that is now wrong, bump the dates, add the
  drift link for every code_refs path, and pass the gate before committing.

  NOT YET IMPLEMENTED — placeholder for the drift phase. See the plan named below.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-write.
---

# /okf-write — not yet implemented

This skill is the write half of the `okf-drift` plugin. Its shape is decided; its
implementation waits on the drift phase, which has its own plan (follow-ups 1 and 2 of
`docs/plans/2026-09-15-001-chore-migrate-mex-to-okf-plan.md` in
offline-payment-attestation, to be planned and `/plan-eng-review`ed before code).

What it will do, in order:

1. Take what changed (a decision made, a task that recurred, a fact that moved) and
   write it in the layout `/okf-setup` lays down: `decisions/<slug>.md` with
   `status: stable`, `playbooks/<slug>.md`, or a surgical edit to a concept.
2. Refresh `project/state.md` as a snapshot; put the story in `log.md`.
3. `drift link knowledge/<concept>.md <path>` for every `code_refs` entry that is new,
   so `drift.lock` knows what the concept depends on.
4. Bump `last_updated` (and `stale_after` when the concept was actually reviewed).
5. Run `scripts/okf-check.sh` — which by then includes `drift check` as its sixth step —
   and report what it says.

Until then, do this by hand following the Work Loop in the target repo's `CLAUDE.md`
and the formats at the top of `knowledge/decisions/index.md` and
`knowledge/playbooks/index.md`.
