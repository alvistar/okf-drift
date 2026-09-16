---
type: Reference
title: conventions
description: How code is written in this project — naming, structure, patterns, and the checks most likely to catch a mistake here. Load when writing or reviewing code.
tags:
- convention
- naming
- style
- structure
- checklist
sources: []
# Paths that EMBODY a convention: the lint config, a canonical example file.
code_refs: []
last_updated: {{DATE}}
---

# Conventions

<!-- Only conventions that are actually enforced — not aspirations, not generic advice.
     Replace every annotation comment with content from this codebase, then delete it. -->

## Naming
<!-- Files, functions, variables, classes, tables/columns — whichever are non-obvious.
     Example: - Files: kebab-case (`user-profile.ts`, not `UserProfile.ts`) -->

## Structure
<!-- How code is organised within files and across the codebase — the things most
     likely to be got wrong.
     Example: - Business logic lives in services/, never in route handlers -->

## Patterns
<!-- Recurring code patterns that must be followed, with a before/after example for the
     important ones.
     Example: Always return a Result from the service layer, never throw:
       return { success: false, error: 'User not found' }   // not: throw new Error(...) -->

## Verify Checklist
<!-- The checks most likely to catch a mistake IN THIS CODEBASE — the ones a reviewer
     here actually makes. CLAUDE.md tells the agent to run this list before presenting
     code; this concept owns what is on it. Typically 4-8.
     Example: - [ ] All database access goes through the repository layer -->

## Related

- [architecture](/architecture/architecture.md) — when a convention depends on the system structure
