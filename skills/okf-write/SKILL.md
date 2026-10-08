---
name: okf-write
disable-model-invocation: true
description: |
  Record into an OKF knowledge bundle — the Grow step: write the decision, the playbook
  or the surgical concept edit, refresh project/state.md, bind every new **code** `code_refs`
  path (the bootstrap does it; high-churn files — scripts, CI, VERSION — are never bound);
  settle drift with the format-only sweep, then re-stamp what you read with
  okf-restamp.sh (never silently — it writes the log line); okf-tidy.sh keeps index rows
  and last_updated; pass the gate.

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

This is the write half of a two-part bargain. `/okf-read` marks a concept STALE when its
bound code has moved — so a concept becomes trustworthy again only when somebody reviews
it and says so. This skill is where that happens, and the rule that makes it worth
anything is:

> **The agent may re-stamp a binding. It may never re-stamp one silently.**

`drift link … --doc-is-still-accurate` is a claim that a human-readable statement
survived a code change. It leaves no trace in the concept, in git, or in `drift.lock`
beyond a changed hex signature. So every re-stamp is paired with a dated line in
`knowledge/log.md` naming what was checked against what. Without that line the plugin
degrades into a tool that silences its own alarm. `okf-restamp.sh` writes that line;
you supply what you read.

**Run the plugin's write helpers through the pinned launcher**, like the gate:

```sh
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" <script> <args>
```

Below, `okf-tidy.sh …`, `okf-restamp.sh …` and `okf-drift-bootstrap.sh …` mean exactly
that. A pin older than the release that ships a helper has no digest for it and the
launcher refuses it; upgrade the pin with `/okf-setup`, never run the plugin's copy.

## Step 0 — What actually changed?

Answer before writing anything. One of four shapes:

| What happened | Where it goes |
|---|---|
| A choice was made that closes off alternatives | `decisions/<slug>.md` |
| A task was done that will recur, and a wrong turn was available | `playbooks/<slug>.md` |
| A concept says something that is no longer true | a surgical edit to that concept |
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
  hand: Step 4's `okf-tidy.sh` adds the row and keeps it in step with the frontmatter.

### A playbook

`knowledge/playbooks/<slug>.md`, format at the top of `knowledge/playbooks/index.md`.
Write it only if a wrong turn was genuinely available: the value is the trap, not the
steps. Same index row rule.

### A surgical concept edit

Change the sentences that are wrong. Do not rewrite a concept because you were in it.
The bundle's worth is that a reader can trust an old line as much as a new one.

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
- **The story goes to `knowledge/log.md`.** When an evidence entry has become history
  rather than evidence, move it there.

The item count is not the budget; the line length is. Measured on the reference
consumer: with nowhere to put per-item evidence, the snapshot grew to 58 KB (~15k tokens,
the longest item 2,744 characters) while keeping its three lists. Split into a one-line
snapshot and an evidence file, the same items came to 7.7 KB, the longest 201.

## Step 2 — Bind the new ground

Every **code** `code_refs` entry you added needs a drift binding, and the bootstrap makes
it — run it after writing, it skips what the lock already holds:

```sh
okf-drift-bootstrap.sh knowledge
```

Keep `code_refs` entries as file paths — never put `#Symbol` there. A symbol anchor belongs
in `drift.lock`, added by hand with `drift link <doc> <path#Symbol>` (next section).

### Do not bind high-churn files

A binding is an alarm, and an alarm on a file that changes every week for reasons the
concept does not care about teaches the reader to re-stamp without reading. Measured on
the reference consumer: three build/run scripts and the CI/version files held 11% of the
bindings and took 23% of all re-stamps (`build.sh` alone 113), almost never with a claim
moving.

**Never bind:** build, run, deploy and test-runner scripts; CI workflows; `VERSION`,
changelogs, lockfiles and package manifests; generated files. The bootstrap already leaves
shell scripts and every non-code path unbound — do not hand-link them either.

**Instead:** list the file in `code_refs` (so `okf search --for-path` still finds the
concept), give the concept a `stale_after`, and write the claim so it survives the churn:
name where the fact lives ("the steps `build.sh` runs") rather than restating it ("the
nine steps of the build"). A claim whose truth genuinely lives in such a file — a CI
trigger, a pinned version — is written as a dated observation ("on 2026-09-28,
`model.yml` ran on `spec/**`"), which is honest about its age without an alarm.

The exception is a script whose **logic** the concept describes — a release gate, a
migration — and that changes rarely. Hand-link that one, symbol-narrow where drift parses
the language.

### Where the anchor goes

The bootstrap binds whole files; narrowing is a hand `drift link` per symbol, and this is
the rule for choosing what to link.

**List what this claim depends on, then anchor all of it.** For each sentence the concept
makes about code, name the declarations, the dispatch, the defaults and the data the
sentence would be false without. Anchor every one of them. Stop following calls only at a
boundary you state in the log line.

1. **The entry point stays anchored when routing or defaults live there.** OPA's
   `admit_reusable` is a six-line wrapper, but it chooses `DecodeBounds::DEFAULT`; its
   sibling chooses `UNLIMITED`; the checks the prose describes are in
   `admit_reusable_with_limits`. The claim depends on all three. Anchoring only the body
   misses a change to the defaults; anchoring only the wrapper misses a change to the
   checks.
2. **Every implementation the prose cites, in every language.** "Rust checks the ceiling
   and Python re-derives the total" with one Rust anchor is half-watched.
3. **A claim of absence, exclusivity or count is not watched by any anchor**, symbol or
   file: adding a member changes no watched declaration, and anchoring the test that
   counts members does not run it. Either the claim is removed (OPA removed the glossary
   term count on 2026-09-18, and `CLAUDE.md` says why), or it is written as a dated
   measurement, or the check that proves it runs in a lane the concept names.
4. **An unsupported language is a whole file.** C, Swift, `.mjs`/`.cjs`: bind the
   narrowest file. drift hashes those raw, so a formatter alarms on them; Step 3's
   format-only sweep settles that, and anything it leaves is read against the diff.

A bare `#name` binds the **first** declaration of that name in the file, silently. Before
binding a common name (`vend`, `new`, `check`), confirm it is unique in the file; if it is
not and the intended one is not the first, keep the whole file. The log line names the
declaration chosen and the boundary where you stopped following the claim.

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

When the gate's step 6 (or `/okf-read`'s STALE mark) flags anchors, settle them in this
order.

**1. The format-only sweep, first, when more than one anchor drifted:**

```sh
okf-restamp.sh --format-only knowledge
```

For each stale anchor it finds the version of the file the binding was signed against and
compares it with the working tree. It re-stamps, with ONE log line for the whole sweep,
only a file in a language drift hashes raw — C, C++, Objective-C, Swift, Kotlin, C#,
Dart — whose lines, blank ones included, are unchanged but for indentation and trailing
whitespace. Everything else it lists as `needs reading` and leaves stale.

It is deliberately narrow. In Rust, Python, TS/JS, Go, Zig and Java drift already ignores
formatting, so what it flags there changed a token, and no rule short of a parser can tell
a harmless token change from a real one: an earlier draft that normalised whitespace,
trailing commas and import order re-stamped `(x,)` → `(x)`, `x-- - y` → `x - --y` and a
swapped `from a import x`, among 23 such cases an independent review built. A `cargo fmt`
is therefore read, not swept; the sweep pays off on a `clang-format` or Swift reindent.

**2. Each anchor left: read it, then either fix the concept or re-stamp it.**

Read the changed code against the concept's claims. If a claim is wrong, fix it (Step 1's
surgical edit) and log the edit in prose as usual. Editing does **not** clear the flag —
measured, only `--doc-is-still-accurate` re-stamps the signature — so an edited concept
is re-stamped too.

If the prose still holds:

```sh
okf-restamp.sh knowledge/<category>/<slug>.md '<anchor identity>' '<what you read against what>'
```

`<anchor identity>` is exactly what the gate printed (`path#symbol` for a symbol anchor).
The script refuses an anchor that is not stale, an identity drift does not hold, and a
note too short to say anything. It runs `drift link … --doc-is-still-accurate` and adds
one line under today's heading in `log.md`:

```
* STILL ACCURATE, re-stamped `architecture/protocol-core.md` <- `core/src/cbor.rs#validate_item`
  (last commit on the file: 4f2a11cb "tighten the length guard"): read the length guard
  against §5's bound; unchanged
```

The note says what you read and what it was checked against — one clause, not a
paragraph. Prose belongs to what changed in the bundle, not to what did not. **If you did
not actually read the code, do not re-stamp.** Leave it flagged and say so; a stale
concept is a working alarm, and an unearned re-stamp is worse than no drift at all.

## Step 4 — Bookkeeping: rows and dates

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

## Step 5 — Gate, then report

```sh
# Invoke okf-drift:okf-runtime in gate mode
```

Six steps: okf's own gate with its warnings treated as fatal, the indexes both ways, the
frontmatter okf ignores, template residue, the reserved files, and `drift check`. Green
is the only acceptable result before a push. Step 6 warns rather than fails when there
is no `drift.lock` — on a repo that has not adopted drift that warning is the whole
story; on one that has, it means something is wrong with the lock.

Report to the user: what was recorded and where; the bootstrap's new bindings; the
format-only sweep's count and every reviewed re-stamp; what `okf-tidy.sh` changed; the
gate's last line; and anything you chose **not** to record, with why.

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
