# okf v0.3.0 — what was measured, not what the docs say

Every claim here was verified by running the binary (`okf version v0.3.0 (OKF v0.2
specification)`, installed with `go install`) on 2026-09-16, either on a scratch bundle
made by `scripts/okf-scaffold.sh` or during the 27-document migration of a real repo.
Re-measure after upgrading; correct this file when a number disagrees.

## What `okf validate` gates, and what it only mentions

Exit code is 1 for:

| Finding | Needs flag |
|---|---|
| a concept without `type:` | none (an error) |
| a `## Related` / body link to a concept that does not exist | `--strict` |
| an **orphan** — a concept with no links in *and* no links out | `--strict` |
| a concept whose `stale_after` is in the past | `--stale` |

Exit code stays **0**, with a line in `warnings`, for:

- a `code_refs` path that does not exist in the repo (`--drift`). Even with `--strict`.

Exit code stays 0 with **no output at all** for:

- a concept listed in no `index.md` (root or category) — indexes are navigation, nothing checks them
- an `index.md` row whose description differs from the concept's `description:`
- a concept with no `description:`
- an unfilled placeholder (`[TO DETERMINE]`, `{{DATE}}`, …)

`--drift`'s help text says "check for drift between index.md and concept descriptions".
Measured: it does not. It checks `code_refs` paths. `scripts/okf-check.sh` covers the
rest and turns the warning list into a failure.

## Orphans

A concept is an orphan only when it has **zero** links in either direction. One
outbound `## Related` link is enough to clear it. Links from a reserved `index.md` do not
count — during the migration `playbooks/how-to-write-a-playbook` was listed in two
indexes and still reported as an orphan until it got a `## Related` section of its own.

Link form does not matter to the checker: `[t](/project/stack.md)` (root-relative) and
`[t](../project/stack.md)` (relative) both resolve. `okf relate` writes the relative
form under an `# Related Concepts` H1; the templates use the root-relative form under
`## Related`. Pick one per bundle and stay with it — the reader is a human.

## `okf create` — prefer writing the file

- `okf create --help` **creates a concept named `--help.md`** at the bundle root and adds
  it to `index.md`. There is no help. The flags are `-desc`, `-body`, `-actor`, `-json`.
- `--type` and `--title` do not exist in 0.3.0, although the `SKILL.md` that
  `okf bootstrap` writes documents both. A created concept gets `type: Fact` and a title
  equal to the last id segment. You then edit the file anyway.
- It writes `generated: { by: agent/cli, at: "<iso>" }`, which is provenance the
  templates do not carry. Add it if you want it; nothing validates it in 0.3.0.

So the skill writes files from templates and runs `validate`. `okf relate` is fine for
adding a link, `okf update` for a description — but check the file afterwards.

## Reserved names

`index.md` and `log.md` are reserved at every level: not concepts, not counted, not
validated for frontmatter, not searched. A `README.md` inside the bundle **is** a
concept and is rejected for having no frontmatter. That is why the format guides live
at the top of `playbooks/index.md` and `decisions/index.md`: reserved, so no
frontmatter, no orphan check, no search pollution — and, being reserved, nothing will
ever find them by search, so `CLAUDE.md` says to read the index.

## YAML

`description:` is parsed as YAML. An unquoted `#` starts a comment and silently
truncates the value: `… (issue #48); the rest` became `… (issue`. Quote a description
that contains `#`, `:` followed by a space, or a leading `[`. The same applies to
`tags:` entries. `okf-check.sh` only reads single-line descriptions — keep them on one
line, quoted if needed.

## Fields

Recognised by 0.3.0: `type` (required), `title`, `description`, `tags`, `status`,
`stale_after`, `sources`, `code_refs`. **`last_updated` and `date` are not** — they are
carried through and ignored, which is why the gate checks their format.

**`status` IS an enum under `--strict`**: `draft|stable|deprecated`. Any other word is a
`gate_findings` entry and exit 1 (`status 'active' is not draft|stable|deprecated`,
measured). It is reported neither as an error nor as a warning — a script that reads
only those two lists misses it; read `gate_passed`. So a decision in force is `stable`
and a superseded one is `deprecated`; there is no "active". `sources` is not validated
as paths.

## Search

BM25 over title, id, description, tags and body, per concept. **The body includes HTML
comments**: on a bare scaffold `okf search "FastAPI"` returns `project/stack` because
the annotation example mentions FastAPI. Template comments must be deleted, not merely
answered; the gate fails on any `<!--` left in a concept. `tags` are the ex-mex
`triggers` and carry the query terms a task description would contain; a term that is
only in the body still matches, with a thin margin (`"Face ID"` scored 1.20 against a
runner-up at 0.25 on the migrated bundle — correct, but resting on body text alone).

`okf search --for-path <file>` resolves through `code_refs` only. Paths are
repo-relative from the bundle's parent; a wrong prefix returns nothing rather than a
near miss (`opa-core/src/cbor.rs` found nothing; the real path was
`opa-core/crates/opa-core/src/cbor.rs`).

## `okf bootstrap` and `okf agents`

`okf init <dir>` writes exactly two files: `index.md` (with `okf_version: "0.2"`) and
`log.md`. `okf bootstrap <dir>` adds an `AGENTS.md` in Agent-Action-Grammar style (RFC
2119 `MUST`/`NEVER` rules, "diagrams => ASSERT(mermaid)"), a `Makefile`, and
`.agents/skills/okf-memory/` with six guide files. None of that writes a concept. This
skill does not use bootstrap: its `AGENTS.md` house style is not the project's, and the
`.agents/skills` copy documents `--type`/`--title` flags the binary does not have.
`okf agents lint` checks an `AGENTS.md` against five AAG rules and a 400-token budget;
useful only if you adopt that style.
