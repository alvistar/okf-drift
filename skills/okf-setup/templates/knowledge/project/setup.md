---
type: Reference
title: setup
description: Prerequisites, first-time setup, environment variables, and the issues that actually occur. Load when setting up the project or when the environment misbehaves.
tags:
- setup
- install
- environment
- getting started
- local development
sources: []
# The scripts and env templates the steps below name.
code_refs: []
last_updated: {{DATE}}
stale_after: {{STALE_6M}}
---

# Setup

<!-- The day-to-day commands live in CLAUDE.md, which is always loaded — do not repeat
     them here. This concept is the clone-to-running path and what goes wrong on it.
     Replace every annotation comment with content from this codebase, then delete it. -->

## Prerequisites
<!-- What must be installed first, with exact versions where they matter.
     Example: - Node.js 20+; - PostgreSQL 15 -->

## First-time Setup
<!-- Exact steps from clone to running, in order, with the project's real commands.
     Example: 1. `pnpm install`  2. copy `.env.example` to `.env`  3. `pnpm db:migrate` -->

## Environment Variables
<!-- Each variable: required / conditional / optional, and what it does. NEVER a value —
     this file is committed.
     Example: - `DATABASE_URL` (required) — PostgreSQL connection string -->

## Common Issues
<!-- Only issues that have actually occurred, with the fix. None yet is a valid answer:
     write "None recorded yet." rather than a hypothetical.
     Example: **Port already in use:** `lsof -i :3000`, then kill the PID -->

## Related

- [stack](/project/stack.md) — the versions the prerequisites pin
