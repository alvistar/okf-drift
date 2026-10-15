---
name: okf-read
disable-model-invocation: true
description: |
  Recall from an OKF knowledge bundle: `okf search --json` with, beside each hit, its
  status, its review date and a change hint — how many commits touched the concept's
  `code_refs` after the concept's last commit, and the last one. The code is the source of
  truth: read it before relying on a hinted concept, and when the two disagree the code
  wins (read-repair).

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-read.

  Trigger on: "/okf-read", "what do we know about", "search the knowledge bundle",
  "is this concept still true", "the code changed under this concept".
---

# /okf-read — recall, and read the code where it moved

One of the skills in the `okf-drift` plugin: `/okf-setup` lays the bundle down,
`/okf-write` records into it, `/okf-read` recalls from it. **Every path below is relative
to the target repository root**, and every command runs from there.

**The code is the source of truth.** The bundle holds what the code does not say: why,
invariants, traps met, conventions, how to behave, and where to look (`code_refs`). A
concept that disagrees with the code is wrong, however well it ranks: `okf search` ranks
relevance, not truth. Recall marks, beside each hit, whether the code it points at has
moved since the concept was last committed, so you know where to read before you rely on
it. See `docs/adr/0002-drop-drift-code-is-the-source-of-truth.md` in the plugin.

## The command

```sh
# Invoke okf-drift:okf-runtime in recall mode with "<terms>" and optional bundle
```

Use it **instead of** `okf search`, for the same queries you would have typed. It runs
`okf search --json --scope project` and prints every hit in rank order with its signals.

Recall answers one question: *what is WRITTEN about this area, and where does the code
say it?* Use it before asserting anything about the architecture or a decision in a plan,
a PR body or a review, and before editing a file a concept governs. To find code — a
symbol, a caller, a string — use Grep and LSP; recall does not index code.

When you know the file rather than the topic, `okf search --for-path <file>` answers
from `code_refs`, without the hint. A concept reached that way, by qmd, or by opening it
directly is held to the same rule as a recalled one: check what you rely on against the
code.

## Reading the output

```
3 hit(s) for "cose domain separation" in knowledge

  architecture/protocol-core                   Reference    3.58   stable · review current
      The encoding and crypto layer — canonical CBOR, COSE Sign1 domain separation, …

  playbooks/bound-a-decode-path                Playbook     2.11   stable · review due 2026-11-02
      Give a decode path receiver-chosen DecodeBounds and prove the bound arrived …
      code changed since this concept: 2 commit(s) on core/crates/core/src/cbor.rs (last 4f2a11cb 2026-09-16 "tighten the length guard")

  decisions/k-w-uses-ed25519                   Decision     1.12   deprecated · no review date
      Superseded …

A deprecated concept is history: read its successor.
1 hit(s) with a change hint: code under their code_refs changed after the concept's
last commit. …
```

Each hit carries two signals from its frontmatter, and optionally a change hint. None of
them says the prose is true:

| Signal | What it is | What it is not |
|---|---|---|
| `stable` / `deprecated` / `draft` / `no status` | the author's own `status:` | a freshness signal. A **deprecated** concept is history: find its `Superseded by` link and read the successor instead |
| `review current` / `review due <date>` / `review expired <date>` / `review date invalid (<date>)` / `no review date` | `stale_after` against today — when a human said they would re-read it. `due` = within the next 30 days (`OKF_REVIEW_WINDOW_DAYS`); the day itself is already `expired`, as it is for the gate; dates are UTC, as okf's are | a check that anyone did |
| `code changed since this concept: N commit(s) on <paths> (last <sha> <date> "<subject>")` | the **change hint**: N commits touched the concept's `code_refs` after the concept's own last commit, and the newest of them | a statement that the concept is wrong. A function can change without what the concept says about it changing |

No hint means one of: no commit touched those paths since; the concept has no
`code_refs`; the concept has never been committed; or this is not a git work tree. It
counts commits only, so an uncommitted change in the working tree never shows: run
`git status` on the paths you are about to rely on. It counts from the concept's last
commit, so any edit to the concept, a cosmetic one included, resets it.

## Relying on a concept

**Read the code where it matters.** Before you use a concept's content — quote it, plan
on it, edit code because of it — read the code it points at for the part you use. A
change hint says where to start: the paths it names, the current working tree first,
then the commits. Quote the concept only for what the code confirms.

**Read-repair: when they disagree, the code wins.** If a concept you rely on contradicts
the code:

- In a session that already writes the repository, fix the concept with `/okf-write`, as
  an ordinary surgical edit logged in the branch's log entry like any other.
- In a read-only session, write nothing: say in your answer which concept and which code
  disagree, and answer from the code.

A concept that only appeared in the results, and one you relied on with no visible
contradiction, owes nothing. There is no field to stamp and no line to log for a concept
you checked and found right.

## Profiles

A bundle declared `wiki` in `.okf-profile` describes no code; its concepts carry no
`code_refs`, so recall prints no hint. An unknown profile value exits 2. See
`/okf-setup`, *Profile: wiki*.

## Measured facts recall rests on

okf v0.6.0, measured 2026-10-08. Re-measure after an upgrade; the full list is in
`../okf-setup/references/okf-quirks.md`.

- `okf search --json` is an **array** of `{concept_id, title, type, description, score,
  tags, matched_on, inbound, scope, origin, priority, …}`. There is no `path` field — the
  concept file is `<bundle>/<concept_id>.md`, which recall reads for `status`,
  `stale_after` and `code_refs`.
- `okf search --json` does not emit `status` even when the frontmatter carries it, so
  recall reads it from the file.
- Since okf v0.5.0 search defaults to every scope: `~/.okf`, `/etc/okf` and `.okf/vendor/`
  join the results as `user:…`/`@…` ids that have no file in the bundle. Recall passes
  `--scope project`, so only the bundle is searched.
- A `code_refs` entry may be a directory; the hint counts commits under it.
