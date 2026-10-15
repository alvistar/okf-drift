---
name: okf-write
description: |
  Record into an OKF knowledge bundle — the Grow step: write the decision, the playbook
  or the surgical concept edit, correct a concept the code contradicts (read-repair),
  refresh project/state.md; every concept holds what the code does not say and names
  where to look; one line per change in the branch's log entry (okf-log.sh add);
  okf-tidy.sh keeps index rows and last_updated; pass the gate.

  Model-invocable: the Grow step of the Work Loop and read-repair load it on their own.
  It writes local files and never commits or pushes by itself.

  Trigger on: "/okf-write", "record this decision", "write a playbook", "update the
  knowledge bundle", "the concept is out of date", "the code contradicts the concept".
---

# /okf-write — record what the session learned

`/okf-write` records; `/okf-read` recalls. Gate and recall run through the
model-invocable `okf-drift:okf-runtime` skill with the consumer's pin. Resolve
`PLUGIN_ROOT` two directories above this skill's absolute base directory supplied by the
host, and `REPO_ROOT` to the consumer root.

**Every path in this document is relative to the target repository root.** Run
everything from there: `code_refs` are rooted there.

**The code is the source of truth.** The bundle holds what the code does not say: why a
choice was made, the invariants, the traps met, the conventions, how to behave, and where
to look (`code_refs`). Writing a concept is not copying the code into prose; a reader can
always read the code, and a copy goes wrong the first time the code changes. See
`docs/adr/0002-drop-drift-code-is-the-source-of-truth.md` in the plugin.

**Run the plugin's write helpers through the pinned launcher**, like the gate:

```sh
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" <script> <args>
```

Below, `okf-tidy.sh …` and `okf-log.sh …` mean exactly that. A pin older than the release
that ships a helper has no digest for it and the launcher refuses it; upgrade the pin with
`/okf-setup`, never run the plugin's copy.

**Every new line goes in the branch's log entry, through `okf-log.sh add`.** Never edit
`knowledge/log.md`: it is the frozen log, and the gate fails any change to it. Each branch
writes one log entry, `knowledge/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`; the helper finds
the one this branch already added or creates it, and puts the line under today's heading:

```sh
okf-log.sh add knowledge '* <what changed in the bundle, and why>'
```

It prints the base ref it compared against. On a detached HEAD or the default branch it
refuses: pass `--slug <slug>`. When it finds more than one candidate, it refuses and asks
for `--entry <path>`. After a `git branch -m` it keeps the entry the old name added and
records the new name; when the reflog no longer shows the rename, it refuses and names the
entry: pass `--entry <that path>` to keep it, or `--slug <slug>` for a new one. A bundle whose root `log.md` has no marker is not split yet: run
`/okf-migrate` first.

## Step 0 — What actually changed?

Answer before writing anything. One of these shapes:

| What happened | Where it goes |
|---|---|
| A choice was made that closes off alternatives | `decisions/<slug>.md` |
| A task was done that will recur, and a wrong turn was available | `playbooks/<slug>.md` |
| A concept says something that is no longer true | a surgical edit to that concept |
| A concept you relied on this session contradicts the code (read-repair) | a surgical edit to that concept |
| A decision has been superseded | `status: deprecated` on it, a `Superseded by` link to its successor, and the successor written |
| What works / is missing / is broken moved | its one line in `project/state.md`, its entry in `project/state-evidence.md` |

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

### The writing rule: name where the fact lives

This applies to every concept, of every type.

**A concept never restates what the code already says**: signatures, defaults, step
lists, numbers, field lists, the order of a pipeline, the flags a script takes. Name where
the fact lives instead — "the steps `build.sh` runs", "the bounds `DecodeBounds::DEFAULT`
sets" — and list that path in `code_refs`, so `okf search --for-path` finds the concept.
What the concept says in its own words is what the code cannot: why it is so, what must
stay true, the trap a reader would otherwise walk into, the convention, what to do.

A fact that must be quoted from the code, because the reader needs it to act, is written
as a **dated observation**: "on 2026-09-28, `model.yml` ran on `spec/**`". The date tells
the reader how old the quote is and that the code is where to check it.

A claim of absence, exclusivity or count ("the only caller", "three backends") is the
easiest to go silently wrong: adding a member changes nothing the concept names. Remove
it, write it as a dated observation, or name the check that proves it and where it runs.

The gate does not check this rule. You do, on every line you write.

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
- The row in `knowledge/decisions/index.md` carries the `description:` **verbatim**; the
  gate compares them both ways, because `okf` itself reads no index. Do not copy it by
  hand: Step 2's `okf-tidy.sh` adds the row and keeps it in step with the frontmatter.

### A playbook

`knowledge/playbooks/<slug>.md`, format at the top of `knowledge/playbooks/index.md`.
Write it only if a wrong turn was genuinely available: the value is the trap, not the
steps. The steps live in the scripts and the code; the playbook names them and says
where the wrong turn is. Same index row rule.

### A surgical concept edit

Change the sentences that are wrong. Do not rewrite a concept because you were in it.
The bundle's worth is that a reader can trust an old line as much as a new one. A
sentence you change that restated the code becomes a pointer to where the fact lives, by
the writing rule above.

### Read-repair

When a concept you relied on this session — opened and used its content — says one thing
and the code says another, **the code wins**. If this session already writes the
repository, fix the concept here as a surgical edit and log it with `okf-log.sh add` like
any other edit: what the concept said, what the code says, where. The log entry gets no
other record of it, and no field is stamped. In a session that writes nothing, do not start writing to
fix it: say in the answer which concept and which code disagree.

A concept that only appeared in a result list, and one with no visible contradiction,
owes nothing. Recall's change hint ("code changed since this concept") says where to read
the code first; by itself it is not a contradiction and asks for no edit.

### `project/state.md`

A **snapshot**, not a history, read at the start of every session — so every character
in it is paid on every turn after. Three lists, Working, Not yet built and Known issues,
with an explicit "None known." when one is empty; the gate checks all three exist.

- **One line per item**, one or two sentences, ending with a bracket saying how far the
  claim reaches (the project's own ladder: `[spec]`, `[code]`, `[CI]`, `[staging]`,
  `[prod]`…). The gate warns on an item past 300 characters.
- **The evidence goes to `project/state-evidence.md`**, under the same item in the same
  order: what was observed, where, when, and what is still owed. That file is read by
  item, never whole.
- **The story goes to the branch's log entry** (`okf-log.sh add`). When an evidence entry
  has become history rather than evidence, move it there.

The item count is not the budget; the line length is. Measured on the reference
consumer: with nowhere to put per-item evidence, the snapshot grew to 58 KB (~15k tokens,
the longest item 2,744 characters) while keeping its three lists. Split into a one-line
snapshot and an evidence file, the same items came to 7.7 KB, the longest 201.

## Step 2 — Bookkeeping: log, rows and dates

Log every change to the bundle in prose with `okf-log.sh add`: what changed, and why.
Then:

```sh
okf-tidy.sh knowledge
```

It sets `last_updated` to today on every concept that differs from `HEAD` (modified, added
or untracked), rewrites every index row whose description is not its concept's
`description:` verbatim, and adds the missing row for a new concept to its category's
`index.md`. It prints each change and is idempotent; run it once, after writing.

What it leaves to you:

- `stale_after`: bump **only when you actually reviewed the concept** against reality,
  not when you edited a line in it. Advancing one without the other leaves the concept
  permanently expired or permanently trusted; both are wrong.
- A new row lands after the last one; move it if the index is ordered by meaning.

## Step 3 — Gate, then report

```sh
# Invoke okf-drift:okf-runtime in gate mode
```

Six steps: okf's own gate (with `--drift`, okf's check for dead `code_refs` paths) with
its warnings treated as fatal, the indexes both ways, the frontmatter okf ignores,
template residue, the reserved files, and a leftover `drift.lock` (drift was removed;
`/okf-migrate` deletes it). Green is the only acceptable result before a push.

Report to the user: what was recorded and where; each read-repair, with the concept and
the code that disagreed; what `okf-tidy.sh` changed; the gate's last line; and anything
you chose **not** to record, with why.

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
- Playbooks, concepts, log entries, index rows, `code_refs`, the writing rule and
  read-repair are identical in both layouts — none of that is layout.
- The gate will report findings that predate your change. In the old layout the routing
  table duplicates rows with a trailing "when to load" clause the verbatim rule forbids,
  and folded multi-line `description:` values are truncated by okf's own parser. Do not
  fold those into your commit and do not report them as your failures. Converting the
  layout is its own task.

Say which layout you found before you write, so the user can correct you cheaply.
