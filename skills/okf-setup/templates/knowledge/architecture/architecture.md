---
type: Reference
title: architecture
description: How the major pieces of this project connect and flow. Load when working on system design, integrations, or understanding how components interact.
tags:
- architecture
- system design
- integration
- flow
sources: []
# Repo-relative paths (files or directories) this concept governs: `okf search --for-path`
# answers through them, and `okf validate --drift` WARNS (exit 0) on one that no longer
# exists. Name the narrow directories or boundary files that embody the architecture —
# a top-level `src/` on every concept makes --for-path noise.
code_refs: []
last_updated: {{DATE}}
---

# Architecture

<!-- Replace every annotation comment with content from THIS codebase, then delete the
     comment: the gate fails on any comment left in a concept, and search indexes comment
     text, so the example names below would match queries until removed. -->

## System Overview
<!-- How the major pieces connect. Focus on FLOW, not technology — how does a
     request/action move through the system? Use the actual names of the components.
     A text flow diagram or short prose, readable in 30 seconds.
     Example: "Request comes in via Express router → validated by middleware → service
     layer → repository → PostgreSQL → serializer → JSON response." -->

## Key Components
<!-- The major components, modules or services: name, what it does, what it depends on.
     Only the non-obvious ones or those with important constraints. Typically 3-7.
     Example: - **AuthService** — all authentication logic; depends on UserRepository -->

## External Dependencies
<!-- Third-party services, APIs, databases: what, used for, constraints. Only those that
     exist; a project with one is a project with one.
     Example: - **PostgreSQL** — primary database; all writes go through the repository layer -->

## What Does NOT Exist Here
<!-- Explicit boundaries — what is deliberately outside this system, so nothing gets
     built that belongs elsewhere. Typically 2-5.
     Example: - No background jobs — that lives in the worker service (separate repo) -->

## Related

- [stack](/project/stack.md) — when specific technology details are needed
- [state](/project/state.md) — for which of these components is working today
