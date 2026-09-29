# Playbooks

Recurring procedures — what you would tell someone doing the task for the first time: the real steps, the real places, and the traps that do not look like their cause. Check the index below before starting a task; if a playbook exists, follow it.

## When to write one

When a task recurs and has a repeatable workflow, or when something went wrong in a way that must not repeat. Not for a task with no trap. Every concept costs search relevance, links and review.

## How to write one

Create `playbooks/<slug>.md`, one task per file.

```markdown
---
type: Playbook
title: Pay a tax form
description: Pay a tax form from the accountant's PDF — pick the channel, fill it with the right tool, stop before executing.
tags:
- tax
- payment
sources: []
last_updated: 2026-09-29
---

# Pay a tax form

## Context
Why this playbook exists — name the mistake that created it.

## Steps
The real steps, in order, with the date they were last done this way.

## Gotchas
Each with what you will actually see.

## Related
- [a reference](/reference/some-fact.md) — when to follow this link
```

Rules the gate enforces: at least one `## Related` link (a row here does not connect a concept to the graph); a row below with the description verbatim.

## Index
