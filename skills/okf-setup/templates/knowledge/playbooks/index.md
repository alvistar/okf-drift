# Playbooks

Task-specific guidance — what you would tell your agent if you were sitting next to it: the real commands, the real paths, and the failures that do not look like their cause. Check the index below before starting a task; if a playbook exists, follow it.

## When to write one

When a task recurs and has a repeatable workflow; when an integration has gotchas the code does not show; when something broke and must not break the same way again. Not for a task with no project-specific trap. Every concept costs search relevance, links and review — a playbook earns its place by saving someone a wrong turn.

## How to write one

Create `playbooks/<slug>.md`, one task per file (several tasks share a file only when they genuinely share Context — then one `## Task: …` heading each).

```markdown
---
type: Playbook
title: Run the 32-bit lane locally
description: Run the i686 suite on a Mac — the one route that fails, the two traps that misreport, and the mutation that proves the lane bites.
tags:
- 32-bit
- i686
- cross-compile
sources: []
code_refs:
- scripts/run-the-32-bit-lane.sh
last_updated: 2026-09-16
---

# Run the 32-bit lane locally

## Context
Why this playbook exists — name the mistake that created it.

## Steps
Real commands, in order, with measured timings and the date they were measured.

## Gotchas
Each with the exact error text you will see.

## Verify
Not "run the tests": the mutation or check that shows the gate can FAIL.

## Debug
Symptom → cause.

## Related
- [architecture](/architecture/architecture.md) — when to follow this link
```

Rules the gate enforces: at least one `## Related` link (a row here does not connect a concept to the graph); a row below with the description verbatim.

## Index
