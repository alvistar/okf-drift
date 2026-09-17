# okf v0.3.0 — what was measured, not what the docs say

Every claim here was verified by running the binary (`okf version v0.3.0 (OKF v0.2
specification)`, installed with `go install`) on 2026-09-16, either on a scratch bundle
made by the plugin's `okf-scaffold.sh` or during the 27-document migration of a real repo.
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
Measured: it does not. It checks `code_refs` paths. The pinned gate (`okf-runtime`) covers the
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

**Every `.md` link in a concept body is a concept link**, including one that leaves
the bundle. Measured under `--strict`: `[t](../../docs/a.md)`, `[t](../../docs/a.md#h)`
and `[t](/docs/a.md)` are all `broken concept link`; a link to a category `index.md`
is broken too ("reserved index.md is navigation, not a concept"). **Not counted at
all**: an angle-bracket destination `[t](<../../docs/a.md>)`, a non-`.md` target
(`../../src/a.ts`), an `https://` URL, and a reference-style link (`[t][r]` +
`[r]: ../../docs/a.md`). The angle form is CommonMark and renders as a normal link, so
it is how a concept cites a repo document outside `knowledge/` — with the path listed
under `sources:` as well. `okf-migrate.py` rewrites outbound links that way (19 in the
repo B scaffold).

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
validated for frontmatter, not searched. **`log.md` is not entirely unvalidated, though:
every `## ` heading in it must be a bare ISO date.** Measured on okf v0.3.0 during the
repo B migration: `## 2026-09-16 — migration from .mex/` is a `warnings` entry,
`log.md: log heading '…' is not ISO 8601 YYYY-MM-DD` — exit 0 from `okf validate`, but
fatal under `okf-check.sh`, which treats warnings as failures. Put the title on the line
below the heading. A `README.md` inside the bundle **is** a
concept and is rejected for having no frontmatter. That is why the format guides live
at the top of `playbooks/index.md` and `decisions/index.md`: reserved, so no
frontmatter, no orphan check, no search pollution — and, being reserved, nothing will
ever find them by search, so `CLAUDE.md` says to read the index.

## YAML

Two different parsers read the frontmatter, and they disagree.

- **okf's own parser** (v0.3.0) reads a `description:` line whole, unquoted `#` included
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

Recognised by 0.3.0: `type` (required), `title`, `description`, `tags`, `status`,
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

## `okf bootstrap` and `okf agents`

`okf init <dir>` writes exactly two files: `index.md` (with `okf_version: "0.2"`) and
`log.md`. `okf bootstrap <dir>` adds an `AGENTS.md` in Agent-Action-Grammar style (RFC
2119 `MUST`/`NEVER` rules, "diagrams => ASSERT(mermaid)"), a `Makefile`, and
`.agents/skills/okf-memory/` with six guide files. None of that writes a concept. This
skill does not use bootstrap: its `AGENTS.md` house style is not the project's, and the
`.agents/skills` copy documents `--type`/`--title` flags the binary does not have.
`okf agents lint` checks an `AGENTS.md` against five AAG rules and a 400-token budget;
useful only if you adopt that style.

# drift v0.10.1 — the same treatment

Measured on 2026-09-16 (`drift v0.10.1`, installed at `~/.local/bin/drift`), on a scratch
git repository built for the purpose and on repo A's bundle. drift is what supplies
the thing OKF has no answer for: `code_refs` tells you a path **vanished**, drift tells you
it **changed**.

## `drift link` — three refusals worth knowing before you script it

| Input | Result |
|---|---|
| a file target, not yet bound | exit 0, `added <doc> -> <target> sig:<16 hex>` |
| a target **already in the lock** | **exit 1**, `refused: target changed since last link` |
| a **directory** target (`src/`, `src`) | **exit 1**, `error: ReadFailed` |
| a target that does not exist | exit 1, `error: target not found: <path>` |
| the very first link in a repo with no lock | exit 0, but prints `error: ReadFailed` first — that is drift failing to read the `drift.lock` it is about to create. Harmless, and indistinguishable by eye from the directory failure. |

The second row is the one that matters. **`drift link` refuses every second link on a
path, whether or not anything changed** — the message says "target changed since last
link" even when `drift check` calls that same binding `fresh` in the same second. So
idempotency has to come from the caller: `okf-drift-bootstrap.sh` reads the existing
`doc`/`target` pairs out of `drift.lock` and skips them. There is no `--force` and no
`--if-absent`.

**`#Symbol` anchors work in six languages and refuse everywhere else.** The parsers are
tree-sitter grammars shipped in the binary — `src/queries/{go,java,python,rust,typescript,zig}.scm`
— and there is no C, no Swift, no Objective-C, no JavaScript beyond what the TypeScript
grammar covers. **The grammar is selected by file EXTENSION, and `.mjs`/`.cjs` are not in
it**: measured on the repo B migration, `drift link doc scripts/manifest.cjs#classify`
and the same on four `.mjs` scripts all refuse with `cannot compute fingerprint for target`,
while every `.ts` anchor in the same run linked. Node-side build and guard scripts are
therefore whole-file bindings, and a reformat of one reads as drift. Measured: `drift link doc src/a.c#guard` and `doc src/k.swift#KeyManager`
both refuse with `error: cannot compute fingerprint for target`; `doc src/r.rs#guard`
links. A whole-file anchor works for any file, but for an unsupported language it is a
**raw content** signature: a whitespace-only reformat of `a.c` went stale, while a
reformat of `r.rs` (AST-normalised) stayed fresh, and changing `other()` next to the
bound `guard` stayed fresh only in Rust. In a Rust + Python + C + Swift family that means the Rust crates, the Python
backend and the model harness can be anchored at symbol level; the C firmware and the
Swift app only at file level, with
every `clang-format`/`swift-format` pass reading as drift. Bind narrow files there, and
expect to re-stamp after a formatter run.

### What the bootstrap binds

`okf-drift-bootstrap.sh` keeps every `code_refs` path for `okf`'s existence check, but
automatically gives `drift` bindings only to this fixed extension list. Symbol-capable
files are `go java py rs ts tsx zig`; file-level code is `js mjs cjs jsx sh bash zsh c h
cc cpp hpp m swift kt kts rb php sql lua`. A trailing `#Symbol` is stripped before the
extension test. A path with no extension (`VERSION`, `Makefile`) or a data/document
extension (`json`, `yaml`, `toml`, `md`, `txt`, `lock`, …) is reported `not-code` and is
not linked. If a concept describes the content of such a data file, use a hand
`drift link` as the escape hatch; existing non-code bindings are reported with their
exact `drift unlink` command and are never removed by the bootstrap.

### Which `#Symbol` names are accepted — measured, Rust and Python

Measured 2026-09-16 on a scratch git repo, then applied to repo A. A refusal is
always the same line, `error: cannot compute fingerprint for target: <path>#<name>`,
exit 1 — it never says *why*, so a path-shaped name and a typo are indistinguishable.

| Language | Accepted | Refused |
|---|---|---|
| Rust | free `fn`, `struct`, `enum`, `trait`, `pub const`, an `impl`-block method by its **bare** name (`#check`), a `#[test] fn` by its bare name | `#Type::method`, `#mod::fn` — **any** `::` path; a `mod` itself (`#tests`, `#inner`); an unknown name |
| Python | module-level `def`, `async def`, `class`, a method by its **bare** name (`#resolve`, `#__init__`) | `#Class.method`; a **module-level assignment** (`MAX_LEN = 64`) |

So there is no qualified form at all: you address a declaration by its bare identifier
or not at all. Three consequences that decide how you bind:

- **A bare name occurring twice in one file binds the FIRST occurrence only.** Two
  `impl` blocks each with `fn check`: the anchor tracked `A::check` and changing
  `B::check` was reported fresh. Nothing warns. Before binding a common method name
  (`vend`, `new`, `from`, `encode`), check it is unique in that file — or accept that
  you are anchoring the first declaration and say which one in the log.
- **A Rust `#Struct` covers the struct declaration ONLY, not its `impl` blocks.**
  Changing a method body left `#DecodeBounds` fresh; adding a field staled it. To watch
  a method, bind the method. **Python is the opposite**: a `#Class` anchor covers the
  whole class body, so editing `Registry.resolve` staled both `#Registry` and
  `#resolve`.
- **A Python constant cannot be anchored**, where a Rust `pub const` can. If a
  concept's claim rests on a module-level list or dict (a registry, a roster, an
  invariant table), the whole file is the only anchor that watches it.

Narrowing is worth it: adding a statement to a bound `decode_canonical` in a 670-line
`cbor.rs` staled exactly the two `#decode_canonical` anchors and left the other 16
anchors on that file fresh; adding a statement to an unbound sibling function left all
18 fresh, where a whole-file anchor on the same edit went stale.

Keep a binding whole when the prose is a claim about the file *as a set* — "exporting
33 functions plus three enums", an ABI's export list, a domain-tag registry that is a
Rust `mod`, an invariant count that lives in a module-level list. Those are exactly the
cases a symbol anchor would stop watching.

The third row is why `code_refs` wants to be narrow. drift signs **file content**, so a
directory has nothing to sign. `okf-drift-bootstrap.sh` expands a directory `code_ref`
into `git ls-files -- <dir>` and skips anything wider than `OKF_DRIFT_MAX_DIR_FILES`
(default 20), because a hundred anchors under one concept makes that concept permanently
stale and the WITHHELD block permanently full. Narrow the `code_ref` instead of raising
the cap.

## `drift check`

- `--format json` emits `schema_version: "drift.check.v1"`. The schema doc lives in the
  drift repo at `docs/check-json-schema.md`, with a JSON Schema at
  `docs/schemas/drift.check.v1.json`.
- Exit 0 iff nothing is stale and no link is broken; `summary.result` (`pass`/`fail`)
  mirrors it, independent of `--format`.
- `docs[]` covers **every `.md` drift discovers under the current working directory** —
  from a repo root that is the whole repo (74 entries in repo A, of which 31 are the
  bundle). Filter on `path`. A doc with no anchors is reported, and is `fresh`.
- Run from a **subdirectory** it still finds the repo-root `drift.lock`, still reports
  root-relative paths, but scans only the docs under that subdirectory. So
  `cd knowledge && drift check` is a bundle-only check for free. `okf-check.sh` instead
  runs it from the bundle's parent and filters, so that the doc paths it prints match the
  ones `drift link` takes.
- Per-doc `result` is `fresh` | `stale` | `broken`. `broken` means a dead markdown link,
  and the summary counts such a doc under `docs_stale` as well as `links_broken` — so
  "every doc `fresh`" is a stronger statement than `docs_stale == 0`, and is the condition
  the gate uses.
- A stale anchor carries `reason: {code: "changed_after_baseline", message}` and
  `blame: {author, commit, date, subject}`. An **uncommitted** change to a bound file is
  stale too, with blame falling back to the last commit that touched the file — which
  reads as a wrong accusation unless you know that.
- `--changed <path>` narrows `docs[]` to the docs anchored to that path. The summary's
  `anchors_total` still counts every anchor on those docs, not just the matching one.

## Links, and why okf's link style is invisible to drift

drift also lints markdown links. Measured: a relative link to a missing file
(`[x](./nowhere.md)`) is `links_broken`; a **root-relative** link (`[x](/src/a.rs)`,
`[x](/project/stack.md)`) is not counted as a link at all — `links_total` stayed 0. The
okf templates use root-relative links under `## Related`, so the bundle's own link graph
never appears in drift's link count. Both tools check it; neither checks the other's form.

## `drift.lock`

TOML at the repository root, `version = 1` then one `[[bindings]]` table per binding with
`doc`, `target`, `sig`. Nothing else: no timestamps, no commit, no author. It is the only
file `drift link` writes — the concept itself is never touched, which is what lets okf,
the indexes and the gate stay ignorant of drift entirely.

`sig` is a content signature of the target, taken at link time. Which means a binding
written now is fresh now, by construction — if a fresh bootstrap reports anything stale,
the lock was not written by that bootstrap.

**Deleting the doc does not delete its bindings.** After `git rm knowledge/x.md`,
`drift check` still lists `knowledge/x.md` in `docs[]` and still evaluates its anchors
from the lock alone (measured during repo A's layout conversion: the removed
`architecture/decisions.md` kept reporting two fresh anchors). Only `drift unlink` removes
them. drift never fails on it, so the gate does: a lock entry whose doc no longer exists
is a `FAIL` in step 6.

## The one that changes how you write the skill

**Editing the doc does not clear staleness.** Rewriting the concept, saving it, committing
it — none of it. The only thing that re-stamps the signature is
`drift link <doc> <target> --doc-is-still-accurate`. That is a feature: it forces the
re-grounding to be a deliberate claim rather than a side effect of touching a file. It is
also why `/okf-write` pairs every re-stamp with a dated line in `knowledge/log.md`: the
lock records *that* a signature changed and never *why*, so the audit trail has to be
written by hand or it does not exist.

## Miscellany

- `drift check --help` is **not valid** and errors out. `drift --help` is the only help.
- `drift status --format json` → `[{doc, files[]}]`. `drift refs <target>` → the docs
  bound to one path. `drift unlink` removes bindings.
- Output goes through a progress renderer that emits `\r`: captured to a file, a
  successful `drift link` line can be partly overwritten. Read the exit code, not the text.
- `repo` in the JSON was `null` in every run here.
