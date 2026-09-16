## Knowledge Bundle
Project knowledge lives in `knowledge/` as an Open Knowledge Format (OKF v0.2) bundle: `project/` (state, stack, setup, conventions), `architecture/`, `decisions/` (one concept per decision), `playbooks/` (one per recurring task). Find concepts with `okf search "<terms>"` or, before editing a file, `okf search --for-path <file>`. The bundle has no code graph: use Grep, Glob and LSP for callers and source navigation. The format for a new playbook or decision is at the top of `knowledge/playbooks/index.md` and `knowledge/decisions/index.md` — search will not find it, read the index.

## Work Loop
1. **Context** — read `knowledge/project/state.md`; search for the concepts the task touches; check `knowledge/playbooks/index.md` for a matching playbook and follow it.
2. **Build** — if you deviate from a playbook or a convention, say so before writing code.
3. **Verify** — run the Verify Checklist in `knowledge/project/conventions.md` item by item before presenting code.
4. **Grow** — after meaningful work: update `state.md` if what works / is missing / is broken changed; fix any concept that is now wrong; write a decision or a playbook if one was made or one would have saved a wrong turn; bump `last_updated` (and `stale_after` when you reviewed the concept) on what you touched; add a dated line to `knowledge/log.md` when the why matters; run `scripts/okf-check.sh` before committing.

## Navigation
At the start of every session read `knowledge/index.md` and `knowledge/project/state.md` before doing anything else.
