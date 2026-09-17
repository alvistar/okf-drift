---
name: okf-write
disable-model-invocation: true
description: |
  Record into an OKF knowledge bundle — the Grow step: write the decision, the playbook
  or the surgical concept edit, refresh project/state.md, bind every new **code** `code_refs`
  path with `drift link`; non-code paths are watched for existence by `okf` alone; re-stamp
  a concept you reviewed against a code change (never silently — a dated line in log.md
  goes with it), bump the dates, pass the gate.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-write.

  Trigger on: "/okf-write", "record this decision", "write a playbook", "update the
  knowledge bundle", "the concept is out of date", "re-stamp the drift binding".
---

# /okf-write — record what the session learned, and re-ground it

`/okf-write` records; `/okf-read` recalls. Gate and recall run through the
model-invocable `okf-drift:okf-runtime` skill with the consumer's pin. For the explicit
binding bootstrap below, resolve `PLUGIN_ROOT` two directories above this skill's
absolute base directory supplied by the host, and `REPO_ROOT` to the consumer root.

**Every path in this document is relative to the target repository root.** Run
everything from there: `code_refs` and `drift.lock` are both rooted there.

This is the write half of a two-part bargain. `/okf-read` withholds a concept whose
bound code has moved — so a concept becomes trustworthy again only when somebody reviews
it and says so. This skill is where that happens, and the rule that makes it worth
anything is:

> **The agent may re-stamp a binding. It may never re-stamp one silently.**

`drift link … --doc-is-still-accurate` is a claim that a human-readable statement
survived a code change. It leaves no trace in the concept, in git, or in `drift.lock`
beyond a changed hex signature. So every re-stamp is paired with a dated line in
`knowledge/log.md` naming what was checked against what. Without that line the plugin
degrades into a tool that silences its own alarm.

## Step 0 — What actually changed?

Answer before writing anything. One of four shapes:

| What happened | Where it goes |
|---|---|
| A choice was made that closes off alternatives | `decisions/<slug>.md` |
| A task was done that will recur, and a wrong turn was available | `playbooks/<slug>.md` |
| A concept says something that is no longer true | a surgical edit to that concept |
| What works / is missing / is broken moved | `project/state.md` |

More than one can be true. None being true is a legitimate answer — say so and stop. A
session that fixed a typo does not owe the bundle anything.

Find the concepts the change touches before writing a new one:

```sh
# Invoke okf-drift:okf-runtime in recall mode with "<the terms you would type>"
okf search --for-path <the file you changed>
```

`--for-path` resolves through `code_refs` only, and a wrong prefix returns nothing
rather than a near miss — check the path against the repo before concluding that no
concept governs it.

## Step 1 — Write it

### A decision

`knowledge/decisions/<slug>.md`. **The format is at the top of
`knowledge/decisions/index.md`** — read it; search will never return it, because
`index.md` is reserved and not indexed.

- `status: stable` for a decision in force. The vocabulary is okf's own and `--strict`
  enforces it: `draft|stable|deprecated`. There is no `active`.
- `date:` is an ISO date and the gate requires it.
- The slug is permanent and the file is never deleted. Superseding means the old file
  goes `status: deprecated` with a `Superseded by` link to the new one, the new one links
  back, and the old one loses its `stale_after`.
- A decision **must link to a concept outside `decisions/`** — an island of decisions
  that only cite each other passes `okf validate --strict` and tells a reader nothing.
- Add the row to `knowledge/decisions/index.md` carrying the `description:` **verbatim**.
  The gate compares them both ways, because `okf` itself reads no index.

### A playbook

`knowledge/playbooks/<slug>.md`, format at the top of `knowledge/playbooks/index.md`.
Write it only if a wrong turn was genuinely available: the value is the trap, not the
steps. Same index row rule.

### A surgical concept edit

Change the sentences that are wrong. Do not rewrite a concept because you were in it.
The bundle's worth is that a reader can trust an old line as much as a new one.

### `project/state.md`

A **snapshot**, not a history: Working (3-7), Not yet built and Known issues (0-7 each,
with an explicit "None known." when empty). The gate checks all three lists exist. How
it got here goes in `knowledge/log.md`.

## Step 2 — Bind the new ground

Every **code** `code_refs` entry you added needs a drift binding; non-code paths are watched
for existence by `okf` alone. Keep `code_refs` entries as file paths — never put `#Symbol`
there. A symbol anchor belongs in `drift.lock`, added with `drift link <doc> <path#Symbol>`:

```sh
drift link knowledge/<category>/<slug>.md <repo-relative-path>
```

or, for a whole bundle at once (idempotent — it skips what the lock already holds):

```sh
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-drift-bootstrap.sh knowledge
```

Measured on drift v0.10.1, and each of these will bite otherwise:

- `drift link` on a binding the lock **already holds** exits 1 with *"refused: target
  changed since last link"* — even when `drift check` calls that same binding fresh. It
  is not telling you something changed; it refuses every second link on a path. Skip what
  is already bound, do not relink it. The bootstrap treats a code path as already covered
  when this document holds either the plain path or any `path#Symbol` binding, so rerunning
  it does not add a whole-file binding beside a symbol binding.
- A **directory** target is rejected (`error: ReadFailed`) — drift signs file content.
  The bootstrap expands a directory `code_ref` into its git-tracked files and skips one
  wider than 20 files. The fix for that skip is a narrower `code_ref`, not a bigger cap.
- A missing target is rejected (`error: target not found: <path>`). `okf validate
  --drift` calls the same path a warning at exit 0; the gate fails on it.

`drift link` writes **only `drift.lock`** at the repository root. It does not touch the
concept, so okf, the indexes and the rest of the gate are unaffected by it.

## Step 3 — Re-stamp what you reviewed, and log that you did

When a concept was flagged — by `/okf-read`'s WITHHELD block or by the gate's step 6 —
and you have **read the changed code and confirmed the prose still holds**:

```sh
drift link knowledge/<category>/<slug>.md <path> --doc-is-still-accurate
```

Editing the concept does **not** clear the flag. Measured: only that flag re-stamps the
signature. So a re-stamp is always a deliberate act, and it is always paired with a line
in `knowledge/log.md`:

```
- 2026-09-16 — reviewed `architecture/protocol-core` against
  `core/crates/core/src/cbor.rs` (commit 4f2a11c, "tighten the length guard"):
  the §5 encoding claims are unchanged; the bound-length paragraph was wrong and is
  rewritten. Re-stamped.
```

Name the concept, the path, the commit that moved it, what you checked, and what you
changed — or that nothing needed changing. **If you did not actually read the code, do
not re-stamp.** Leave it flagged and say so; a withheld concept is a working alarm, and
an unearned re-stamp is worse than no drift at all.

## Step 4 — Dates

- `last_updated`: bump on every concept you touched. ISO — the gate checks the format
  because okf carries the field without validating it.
- `stale_after`: bump **only when you actually reviewed the concept** against reality,
  not when you edited a line in it. Advancing one without the other leaves the concept
  permanently expired or permanently trusted; both are wrong.

## Step 5 — Gate, then report

```sh
# Invoke okf-drift:okf-runtime in gate mode
```

Six steps: okf's own gate with its warnings treated as fatal, the indexes both ways, the
frontmatter okf ignores, template residue, the reserved files, and `drift check`. Green
is the only acceptable result before a commit. Step 6 warns rather than fails when there
is no `drift.lock` — on a repo that has not adopted drift that warning is the whole
story; on one that has, it means something is wrong with the lock.

Report to the user: what was recorded and where; every code-path `drift link` run and every
re-stamp with the log line that accompanies it; the dates bumped; the gate's last line;
and anything you chose **not** to record, with why.

Nothing here publishes and nothing here takes a version bump — the bundle is not a
released artifact. If the repository's `VERSION` governs something else, leave it alone.

## Older bundles: record in the file that exists

Some repositories carry an OKF bundle laid down before this layout: a single
`architecture/decisions.md` instead of a `decisions/` directory, a
`project/session-contract.md` instead of `project/state.md`, a routing table in the root
`index.md`. the first migrated repo (repo A) is the worked example.

**Do not invent the new layout inside an old one.** A `decisions/` directory holding one
file, in a bundle whose decisions all live in `architecture/decisions.md`, splits the
corpus in two and neither half is findable. Instead:

- A decision goes as a new section in `architecture/decisions.md`, in the shape the
  sections already there use. Bump that file's `last_updated`.
- The project snapshot goes wherever the bundle keeps it — `project/session-contract.md`
  in the first migrated repo. The gate `warn`s about a missing `project/state.md`; that warning is
  correct, and it is not yours to silence by creating the file.
- Playbooks, concepts, `log.md`, index rows, `code_refs`, `drift link` and the re-stamp
  rule are identical in both layouts — none of that is layout.
- The gate will report findings that predate your change. In the old layout the routing
  table duplicates rows with a trailing "when to load" clause the verbatim rule forbids,
  and folded multi-line `description:` values are truncated by okf's own parser. Do not
  fold those into your commit and do not report them as your failures. Converting the
  layout is its own task.

Say which layout you found before you write, so the user can correct you cheaply.
