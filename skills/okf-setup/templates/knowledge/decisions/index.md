# Decisions

One concept per decision. A decision is worth recording when it is non-obvious, when it constrains future work, or when knowing *why* prevents a mistake — not for every choice made.

## How to record one

Create `decisions/<slug>.md`. The slug is permanent: OKF ids are paths, and renaming one breaks every link to it, so choose a slug that names the decision, not its current title.

```markdown
---
type: Decision
title: Fixtures must be independently derived
description: Python fixtures are derived from the spec, never from Rust output, so parity is a test and not a tautology.
status: stable
date: 2026-09-04
tags:
- fixture
- parity
sources:
- resource: docs/plans/2026-09-04-001-fixtures-plan.md
code_refs:
- core/fixtures/
last_updated: 2026-09-16
---

# Fixtures must be independently derived

## Context and Problem Statement
## Considered Options
- <option> — why it lost, in one line
## Decision Outcome
Chosen option: <option>, because <the reason that decided it>.
### Consequences
### Confirmation

## Related
- [stack](/project/stack.md) — the parity this decision protects
```

The body follows [MADR](https://adr.github.io/madr/)'s minimal template, adapted: each considered option carries the reason it lost on its own line, `## Related` replaces More Information, and the frontmatter is OKF's. `### Confirmation` is optional: write it only to name the invariant the decision protects and the check or test that enforces it, never to restate that check; otherwise leave the heading out, since the gate rejects an empty section. Decisions written in the earlier Context / Decision / Reasoning shape stay as they are.

Rules the gate enforces:

- `status` uses OKF's own vocabulary, which `okf validate --strict` enforces: `stable` for a decision in force, `deprecated` for one superseded (`draft` while it is still being discussed). `date` and `last_updated` are ISO dates.
- Every decision links to at least one concept **outside** `decisions/` — a decision that only points at other decisions is an island `okf validate` cannot see.
- A superseded decision is never deleted: set `status: deprecated`, add a `Superseded by` line under `## Related` that links the new decision's `/decisions/<new-slug>.md`, and have the new decision link back. Deprecated decisions take no `stale_after`.
- Add a row below with the description verbatim.

## Index
