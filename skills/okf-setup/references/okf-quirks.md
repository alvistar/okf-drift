# okf v0.6.0 and v0.9.0 — what was measured, not what the docs say

Every claim here was first verified by running okf v0.3.0 on 2026-09-16, either on a
scratch bundle made by the plugin's `okf-scaffold.sh` or during the 27-document migration
of a real repo, and re-measured on `okf version v0.6.0 (OKF v0.2 specification)` on
2026-10-08: the same probes run against both binaries side by side, plus the gate over three
real bundles (one code, two wiki), which passed unchanged. Re-measured again on
`okf version v0.9.0 (OKF v0.3 specification)` on 2026-11-23, side by side with v0.6.0, on
scratch bundles and on copies of three real bundles (two code, one wiki). Where a version
behaves differently the text says so; everything else held. Re-measure after upgrading;
correct this file when a number disagrees. The gate accepts the version measured last
(v0.9.0 since plugin 0.21.0) and warns on any other.

Both are built with Go 1.26: `go install …/cmd/okf@v0.9.0` needs Go 1.26 or newer (an
older `go` switches toolchain itself when `GOTOOLCHAIN` allows it).

The format itself is the Open Knowledge Format, `SPEC.md` in
github.com/open-knowledge-format/open-knowledge-format (v0.3, 2026-10-23). The copy in
GoogleCloudPlatform/knowledge-catalog is deprecated and stops at v0.2; okf v0.9.0 still
links to it.

## What `okf validate` gates, and what it only mentions

Exit code is 1 for:

| Finding | Needs flag |
|---|---|
| a concept without `type:` — **v0.6.0 only**: v0.9.0 skips it silently (OKF v0.3 §3.2), so only the gate's own `no type:` / `no frontmatter` catches it | none (an error) |
| a `## Related` / body link to a concept that does not exist | `--strict` |
| an **orphan** — a concept with no links in *and* no links out | `--strict` |
| a `status` outside `draft\|stable\|deprecated` (a `gate_findings` entry) | `--strict` |
| a bare-string `sources` item (a `gate_findings` entry) | `--strict` |
| a concept whose `stale_after` is **today or earlier** | `--stale` |

The stale test is `<=`: `concept is stale (stale_after 2026-10-08 <= 2026-10-08)` on the
day itself (measured on v0.3.0, v0.6.0 and v0.9.0). The gate warns about a `stale_after` within the
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

**Links that leave the bundle.** OKF v0.3 §6 makes a link that resolves outside the bundle
root external: valid, never read from disk, and §11.2 forbids rejecting a bundle for it.
Neither okf agrees, and the two disagree with each other. Measured under `--strict`:

| Link in a concept body | v0.6.0 | v0.9.0 |
|---|---|---|
| `[t](../../docs/a.md)`, `[t](../../docs/a.md#h)` | broken concept link | **error** `escapes bundle root (path traversal denied)`, not conformant |
| `[t](../../src/a.ts)` (not `.md`) | not counted | **error**, as above |
| `[t](<../../docs/a.md>)` (angle brackets) | not counted | broken: `target asset does not exist`, the brackets kept in the path (okf-agent-memory#69); `<x.md>` inside the bundle breaks too |
| `[t](/docs/a.md)` | broken concept link | broken concept link |
| `[t](https://…)`, `[t][r]` + `[r]: ../../docs/a.md` | not counted | not counted |
| a missing non-`.md` file inside the bundle | not counted | broken |
| link syntax inside a code span (`` `[t](x.md)` ``) | parsed as a link | parsed as a link |
| link syntax inside a fenced block | ignored | ignored |

A link to a category `index.md` is broken on both ("reserved index.md is navigation, not a
concept"). So a concept cites a repository file outside `knowledge/` with the plain
relative form, `[t](../../docs/a.md)`, a space as `%20`: clickable on GitHub and in an IDE,
and valid for the spec. The gate drops okf's finding on such a link and checks it itself —
the target must exist inside the repository — and refuses the angle-bracket form and link
syntax inside a code span (`docs/adr/0003-links-outside-the-bundle.md`; okf-agent-memory#70
asks okf to treat these links as §6 says). `okf-links.sh` rewrites the angle form, which
this file recommended while v0.6.0 was the only version measured.

## `okf create` — prefer writing the file

- On v0.3.0 `okf create --help` **created a concept named `--help.md`** and added it to
  `index.md`. v0.6.0 and v0.9.0 print help and write nothing.
- v0.6.0 has `--type` (default `Fact`), `--title` (default: the last id segment),
  `--desc`, `--body`, `--status` (default `stable`), `--tags`, `--actor`, `--no-log`,
  `--no-index`, `--json`. v0.3.0 had only `-desc`, `-body`, `-actor`, `-json`. v0.9.0 adds
  `--stale-after` and `--change-note`; the note goes to the root `log.md`, which is the
  frozen log here, so the plugin never passes it.
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
headings, so the gate checks them itself (v0.9.0 the same). A `README.md` inside the bundle
**is** a concept to v0.6.0 and is rejected for having no frontmatter; v0.9.0 skips it, as
OKF v0.3 §3.2 says, and the gate still fails it (`no frontmatter`). That is why the format guides live
at the top of `playbooks/index.md` and `decisions/index.md`: reserved, so no
frontmatter, no orphan check, no search pollution — and, being reserved, nothing will
ever find them by search, so `CLAUDE.md` says to read the index.

## YAML

Two different parsers read the frontmatter, and they disagree.

- **okf's own parser** (v0.3.0, unchanged in v0.6.0 and v0.9.0) reads a `description:` line whole, unquoted `#` included
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
measured). v0.6.0 reports it neither as an error nor as a warning — a script that reads
only those two lists misses it; read `gate_passed`. v0.9.0 reports the same text in both
`warnings` and `gate_findings`; the gate prints it once. So a decision in force is `stable`
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

`okf init <dir>` writes exactly two files: `index.md` (with `okf_version: "0.2"`; v0.9.0
writes `"0.3"`) and `log.md`. `okf bootstrap <dir>` adds an `AGENTS.md` in Agent-Action-Grammar style (RFC
2119 `MUST`/`NEVER` rules, "diagrams => ASSERT(mermaid)"), a `Makefile`, and
`.agents/skills/okf-memory/` with six guide files. None of that writes a concept. This
skill does not use bootstrap: its `AGENTS.md` house style is not the project's. (Under
v0.3.0 the `.agents/skills` copy also documented `--type`/`--title` flags the binary did not
have; v0.6.0 has them.) `okf agents lint` checks an `AGENTS.md` against five AAG rules and a
400-token budget on the managed block — v0.6.0 also prints the whole file's tokens; useful
only if you adopt that style.

## OKF v0.3 bundles (since plugin 0.21.0)

The root `index.md` declares `okf_version: "0.3"` with a `title` and a `description`
(§8.1); the gate requires all three and names `/okf-migrate` on an older version. Since
0.21.0 the gate accepts okf v0.9.0 only: v0.6.0 implements OKF v0.2 and warns.

Path fields resolve like links (§6): a leading `/` from the bundle root, anything else
from the folder of the file that holds it. Measured on v0.9.0 (2026-11-23), on a 0.3
bundle:

| `sources[].resource` in `knowledge/a/x.md` | okf v0.9.0 | gate |
|---|---|---|
| `../../GLOSSARY.md` (exists) | error `sources[0].resource … escapes bundle root`, not conformant | drops okf's finding; passes |
| `GLOSSARY.md` (exists only from the repository root) | nothing | FAIL: names a file from the repository root; write it relative to the concept |
| `../../notes/private.md` (absent in this checkout) | the same escape error | drops it; one grouped warning, never a failure |
| `/a/y.md` | nothing | must exist in the bundle, else the same warning |
| `https://…`, `Claude memory: x` (any space) | nothing | not a path; never checked |

okf v0.9.0 never checks that a `sources` resource exists. `superseded_by` counts as a graph
edge and a missing target is okf's error; the gate requires `status: deprecated` beside it
and, on a deprecated decision, the field itself. `okf-format.sh` moves a v0.2 bundle.

## What v0.9.0 added that this plugin does not use

- **`okf validate --drift-git`** warns for each concept whose `code_refs` have a commit
  newer than the concept's last touch: 456 warnings on the margins bundle. The gate treats
  warnings as fatal and never passes the flag; the change hint in recall is the signal
  (ADR 0002).
- **`trust_tier` and `staleness`** in `okf search --json` and `okf show`, computed from
  `verified` (OKF v0.3 §5.3: an event counts only when no later change exists). The plugin
  writes no `verified` and ignores both fields; every concept reads `unverified`.
- **`x-okf-memory-protected: true`** makes `okf update` and the MCP tools refuse an
  agent's edit. The skills write files directly and do not honour it: it would block
  read-repair.
- **`okf changes --since`** lists changes from the root `log.md`; here the history after
  the split lives in log entries, which it does not read.
- **`scopes:`** in the root `index.md` (new in v0.8.0): an unknown value such as
  `scopes: [bundle]` makes v0.9.0 exit 2 with no JSON. The templates write no `scopes:`.
- **`superseded_by`** counts as a graph edge on v0.9.0 (it clears an orphan) and a missing
  target is an error; v0.6.0 ignores it.

None of `validate`, `search`, `show`, `--scorecard` or `--drift-git` writes a file on
v0.9.0 (checksums unchanged, on a scratch bundle and on a real repository).
