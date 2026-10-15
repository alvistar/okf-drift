# okf v0.6.0 — what was measured, not what the docs say

Every claim here was first verified by running okf v0.3.0 on 2026-09-16, either on a
scratch bundle made by the plugin's `okf-scaffold.sh` or during the 27-document migration
of a real repo, and re-measured on `okf version v0.6.0 (OKF v0.2 specification)` on
2026-10-08: the same probes run against both binaries side by side, plus the gate over three
real bundles (one code, two wiki), which passed unchanged. Where v0.6.0 behaves
differently the text says so; everything else held. Re-measure after upgrading; correct this
file when a number disagrees.

v0.6.0 is built with Go 1.26: `go install …/cmd/okf@v0.6.0` needs Go 1.26 or newer (an
older `go` switches toolchain itself when `GOTOOLCHAIN` allows it).

## What `okf validate` gates, and what it only mentions

Exit code is 1 for:

| Finding | Needs flag |
|---|---|
| a concept without `type:` | none (an error) |
| a `## Related` / body link to a concept that does not exist | `--strict` |
| an **orphan** — a concept with no links in *and* no links out | `--strict` |
| a `status` outside `draft\|stable\|deprecated` (a `gate_findings` entry) | `--strict` |
| a bare-string `sources` item (a `gate_findings` entry) | `--strict` |
| a concept whose `stale_after` is **today or earlier** | `--stale` |

The stale test is `<=`: `concept is stale (stale_after 2026-10-08 <= 2026-10-08)` on the
day itself (measured on v0.3.0 and v0.6.0). The gate warns about a `stale_after` within the
next 30 days so the review can happen before that day, not on it.

Exit code stays **0**, with a line in `warnings`, for:

- a `code_refs` path that does not exist in the repo (`--drift`). Even with `--strict`.
  A `path#Symbol` entry is read as a path, so it lands here too: `code_refs` holds file
  and directory paths only.
- **(new in v0.4.1)** a concept not listed in its parent `index.md`:
  `a.md: concept is not listed in parent index index.md` (`--drift`). v0.3.0 said nothing.
  The gate already failed this itself; under v0.6.0 the same concept is reported twice,
  once as okf's warning and once as the gate's own `not listed in` line.
- a heading in the root `log.md` that is not a bare ISO date (see Reserved names). okf
  does not check a log entry's headings; the gate does.

Exit code stays 0 with **no output at all** for:

- an `index.md` row whose description differs from the concept's `description:`
- a concept with no `description:`
- an unfilled placeholder (`[TO DETERMINE]`, `{{DATE}}`, …)

`--drift`'s help text says "check descriptions and code_refs for drift between index.md and
concepts". Measured on v0.6.0: it checks `code_refs` paths and that each concept is listed in
its parent index, never the descriptions. The pinned gate (`okf-runtime`) covers the rest and
turns the warning list into a failure.

## A bundle root that is a symlink

**Changed in v0.6.0.** A `knowledge` that is a symlink to a directory outside the one
holding it is refused: `Error loading bundle: bundle root "knowledge" resolves outside its
parent directory`, no JSON, with or without a trailing slash. v0.3.0 loaded the same link
as an **empty** bundle (`concept_count: 0`, `gate_passed: true`) without the slash, and the
outside directory unchecked with it. The gate checks the resolved path itself before
calling okf and fails with the cause named. A symlink that stays inside the parent
directory (`knowledge -> kb-real`) loads in full on v0.6.0; v0.3.0 loaded it as empty too
(`concept_count: 0` against 2) — the walk did not follow a symlinked root (okf issue #45).

## Orphans

A concept is an orphan only when it has **zero** links in either direction. One
outbound `## Related` link is enough to clear it. Links from a reserved `index.md` do not
count — during the migration `playbooks/how-to-write-a-playbook` was listed in two
indexes and still reported as an orphan until it got a `## Related` section of its own.

Link form does not matter to the checker: `[t](/project/stack.md)` (root-relative) and
`[t](../project/stack.md)` (relative) both resolve. `okf relate` writes the relative
form under an `# Related Concepts` H1; the templates use the root-relative form under
`## Related`. Pick one per bundle and stay with it — the reader is a human.

**Every `.md` link in a concept body is a concept link**, including one that leaves
the bundle. Measured under `--strict`: `[t](../../docs/a.md)`, `[t](../../docs/a.md#h)`
and `[t](/docs/a.md)` are all `broken concept link`; a link to a category `index.md`
is broken too ("reserved index.md is navigation, not a concept"). **Not counted at
all**: an angle-bracket destination `[t](<../../docs/a.md>)`, a non-`.md` target
(`../../src/a.ts`), an `https://` URL, and a reference-style link (`[t][r]` +
`[r]: ../../docs/a.md`). The angle form is CommonMark and renders as a normal link, so
it is how a concept cites a repo document outside `knowledge/` — with the path listed
under `sources:` as well. The mex conversion (removed in 0.14.0) rewrote outbound links
that way (19 in the repo B scaffold).

## `okf create` — prefer writing the file

- On v0.3.0 `okf create --help` **created a concept named `--help.md`** and added it to
  `index.md`. v0.6.0 prints help and writes nothing.
- v0.6.0 has `--type` (default `Fact`), `--title` (default: the last id segment),
  `--desc`, `--body`, `--status` (default `stable`), `--tags`, `--actor`, `--no-log`,
  `--no-index`, `--json`. v0.3.0 had only `-desc`, `-body`, `-actor`, `-json`.
- It writes `generated: { by: agent/cli, at: "<iso>" }`, which is provenance the
  templates do not carry, and no `last_updated`, which the gate requires. Nothing in okf
  validates `generated`.

So the skill writes files from templates and runs `validate`. `okf relate` is fine for
adding a link, `okf update` for a description — but check the file afterwards.

## Reserved names

`index.md` and `log.md` are reserved at every level: not concepts, not counted, not
validated for frontmatter, not searched. **The root `log.md` is not entirely unvalidated,
though: every `## ` heading in it must be a bare ISO date.** Measured on okf v0.3.0 during
the repo B migration, and again on v0.6.0: `## 2026-09-16 — migration from .mex/` is a
`warnings` entry, `log.md: log heading '…' is not ISO 8601 YYYY-MM-DD` — exit 0 from
`okf validate`, but fatal under `okf-check.sh`, which treats warnings as failures. Put the
title on the line below the heading.

Since 0.14.0 the root `log.md` is the **frozen log**: the history written before the split,
then a pointer to `log/` and an `<!-- okf-log frozen <date> sha256:<hex> -->` marker as the
last line. Nothing writes it again; the gate fails any change above the marker and names
`/okf-migrate` when the marker is missing. Each branch writes one **log entry**,
`log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`, with the same `## YYYY-MM-DD` headings, newest
first, and only through `okf-log.sh add`. okf v0.6.0 treats that nested `log.md` as
reserved too (not a concept, not searched, passed by `okf validate`) but never checks its
headings, so the gate checks them itself. A `README.md` inside the bundle **is** a
concept and is rejected for having no frontmatter. That is why the format guides live
at the top of `playbooks/index.md` and `decisions/index.md`: reserved, so no
frontmatter, no orphan check, no search pollution — and, being reserved, nothing will
ever find them by search, so `CLAUDE.md` says to read the index.

## YAML

Two different parsers read the frontmatter, and they disagree.

- **okf's own parser** (v0.3.0, unchanged in v0.6.0) reads a `description:` line whole, unquoted `#` included
  — measured: `… (issue #48); the rest` comes back intact from `okf search --json`. But
  it stops at the end of the line: a value **folded over two lines** (what PyYAML's
  dumper does to any long string) is truncated at the fold, silently, in search results
  and in `okf show`. The first migrated bundle (repo A) had 22 of those and nobody saw it
  until the gate compared index rows to descriptions.
- **A real YAML library** (PyYAML, the one that wrote the migration) treats an unquoted
  ` #` as a comment: that is where `… (issue` came from, at migration time, before okf
  ever read the file.

So: one line, always; quoted when it contains `#`, `: `, or a leading `[`, so that both
parsers agree on it. The same for `tags:` entries. `okf-check.sh` fails a multi-line
description for exactly this reason.

## Fields

Recognised by 0.3.0 and 0.6.0: `type` (required), `title`, `description`, `tags`, `status`,
`stale_after`, `sources`, `code_refs`. **`last_updated` and `date` are not** — they are
carried through and ignored, which is why the gate checks their format.

**`status` IS an enum under `--strict`**: `draft|stable|deprecated`. Any other word is a
`gate_findings` entry and exit 1 (`status 'active' is not draft|stable|deprecated`,
measured). It is reported neither as an error nor as a warning — a script that reads
only those two lists misses it; read `gate_passed`. So a decision in force is `stable`
and a superseded one is `deprecated`; there is no "active".

**`sources` entries must be mappings with a `resource` key** under `--strict`: a bare
string item is `sources[N] has no 'resource'` in `gate_findings`, exit 1 (measured on the
repo B migration dry run — 11 findings from links the migrator had listed as plain
paths). Write `- resource: docs/x.md`; whether the path exists is not checked.

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
near miss (`core/src/cbor.rs` found nothing; the real path was
`core/crates/core/src/cbor.rs`).

## Search scopes (new in v0.5.0)

`okf search` now searches four layers by default (`--scope all`): the project bundle, then
`.okf/vendor/` (bundles fetched by `okf pull`), then `~/.okf` (or `OKF_USER_DIR`), then
`/etc/okf` (or `OKF_SYSTEM_DIR`). Results rank by layer first, so a query the bundle
answers well fills the list with project hits and a user-layer note shows up only when the
bundle has little to say — measured: `qwertyzzz` matched only a note in `OKF_USER_DIR` and
came back as `user:notes/q`, scope `user`. Those ids have no file in the bundle, so
recall passes `--scope project`. Each hit now carries `scope`, `origin`
and `priority` as well.

## `okf bootstrap` and `okf agents`

`okf init <dir>` writes exactly two files: `index.md` (with `okf_version: "0.2"`) and
`log.md`. `okf bootstrap <dir>` adds an `AGENTS.md` in Agent-Action-Grammar style (RFC
2119 `MUST`/`NEVER` rules, "diagrams => ASSERT(mermaid)"), a `Makefile`, and
`.agents/skills/okf-memory/` with six guide files. None of that writes a concept. This
skill does not use bootstrap: its `AGENTS.md` house style is not the project's. (Under
v0.3.0 the `.agents/skills` copy also documented `--type`/`--title` flags the binary did not
have; v0.6.0 has them.) `okf agents lint` checks an `AGENTS.md` against five AAG rules and a
400-token budget on the managed block — v0.6.0 also prints the whole file's tokens; useful
only if you adopt that style.
