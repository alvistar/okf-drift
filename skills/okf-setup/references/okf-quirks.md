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

# drift v0.10.1 — the same treatment

Measured on 2026-09-16 (`drift v0.10.1`, installed at `~/.local/bin/drift`), on a scratch
git repository built for the purpose and on the bristleworm bundle. drift is what supplies
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
  from a repo root that is the whole repo (74 entries in bristleworm, of which 31 are the
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
