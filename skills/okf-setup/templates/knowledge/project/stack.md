---
type: Reference
title: stack
description: Languages, frameworks, key libraries, what is deliberately not used, and version constraints. Load when working with a specific technology.
tags:
- library
- package
- dependency
- technology
- version
sources: []
# The manifests (package.json, Cargo.toml, pyproject.toml, go.mod) and any wrapper or
# adapter that IS the way a library is used here.
code_refs: []
last_updated: {{DATE}}
stale_after: {{STALE_6M}}
---

# Stack

<!-- This concept says WHAT is used and under which constraints. WHY it was chosen over
     the alternatives is a decision — write it in decisions/, link it from here.
     Replace every annotation comment with content from this codebase, then delete it. -->

## Core Technologies
<!-- Primary language, framework, runtime — with the version where it matters.
     Example: - **Python 3.11** — primary language; - **FastAPI** — web framework, async by default -->

## Key Libraries
<!-- Libraries central to how this project works, where the agent must know "we use
     THIS, not the alternative". Link the decision when there is one.
     Example: - **SQLAlchemy** (not raw psycopg2) — all database access; link the decisions/ file that chose it.
     (No link syntax inside this comment: okf resolves links in comments too, and a
     link to a decision that does not exist yet is a broken link.) -->

## What We Deliberately Do NOT Use
<!-- Technologies or patterns explicitly avoided, so nothing reintroduces them.
     Example: - No class components — hooks only -->

## Version Constraints
<!-- Only if there are version-specific facts to know. Otherwise delete the section.
     Example: "We are on React 17, not 18 — concurrent features are not available." -->

## Related

- [conventions](/project/conventions.md) — how a technology is used in this codebase
- [architecture](/architecture/architecture.md) — where a library sits in the flow
