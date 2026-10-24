# Decisions

One concept per decision. A decision is worth recording when it is non-obvious, when it constrains what comes next, or when knowing *why* prevents a mistake — not for every choice made.

## How to record one

Create `decisions/<slug>.md`. The slug is permanent: OKF ids are paths, and renaming one breaks every link to it, so choose a slug that names the decision, not its current title.

```markdown
---
type: Decision
title: Tasks live in the task tracker
description: The task tracker is the only source of truth for tasks; this bundle records facts, matters and decisions, not things to do.
status: stable
date: 2026-09-01
tags:
- tasks
sources: []
last_updated: 2026-09-29
---

# Tasks live in the task tracker

## Context and Problem Statement
## Considered Options
- <option> — why it lost, in one line
## Decision Outcome
Chosen option: <option>, because <the reason that decided it>.
### Consequences
### Confirmation

## Related
- [a matter](/matters/some-case.md) — where the consequence shows
```

The body follows [MADR](https://adr.github.io/madr/)'s minimal template, adapted: each considered option carries the reason it lost on its own line, `## Related` replaces More Information, and the frontmatter is OKF's. `### Confirmation` is optional: write it only to name the invariant the decision protects and the check or test that enforces it, never to restate that check; otherwise leave the heading out, since the gate rejects an empty section. Decisions written in the earlier Context / Decision / Reasoning shape stay as they are.

Rules the gate enforces:

- `status` uses OKF's own vocabulary, which `okf validate --strict` enforces: `stable` for a decision in force, `deprecated` for one superseded (`draft` while it is still being discussed). `date` and `last_updated` are ISO dates.
- Every decision links to at least one concept **outside** `decisions/` — a decision that only points at other decisions is an island `okf validate` cannot see.
- A superseded decision is never deleted: set `status: deprecated`, add a `Superseded by` line under `## Related` that links the new decision's `/decisions/<new-slug>.md`, and have the new decision link back. Deprecated decisions take no `stale_after`.
- Add a row below with the description verbatim.

## Index
