---
name: okf-read
disable-model-invocation: true
description: |
  Recall from an OKF knowledge bundle without serving a stale fact as a fact:
  `okf search --json` joined with `drift check --format json`, so a concept whose bound
  code changed since it was written is marked STALE in place, with the anchor and the
  commit to blame. Without drift (no binary, no lock) recall still searches, says so on
  the first line and labels every hit `drift not run`; a `wiki` bundle recalls without the
  join by design.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-read.

  Trigger on: "/okf-read", "what do we know about", "search the knowledge bundle",
  "is this concept still true", "why is that concept stale".
---

# /okf-read — recall, minus whatever the code has since contradicted

One of three skills in the `okf-drift` plugin: `/okf-setup` lays the bundle down,
`/okf-write` records into it, `/okf-read` recalls from it. **Every path below is relative
to the target repository root**, and every command runs from there.

A knowledge bundle's failure mode is not being empty. It is being confidently wrong: a
concept written six weeks ago, indexed, well-linked, top of the search results, and
describing a function that was rewritten last Tuesday. `okf search` cannot see that —
BM25 ranks relevance, not truth. This skill closes that gap by marking, beside each hit,
whether the code under it moved since it was written.

## The command

```sh
# Invoke okf-drift:okf-runtime in recall mode with "<terms>" and optional bundle
```

Use it **instead of** `okf search`, for the same queries you would have typed. It runs
`okf search --json`, runs `drift check --format json`, joins them on
`<bundle>/<concept_id>.md`, and prints every hit in rank order with its signals.

Recall answers one question: *what is WRITTEN about this area, and what was observed about
it?* Use it before asserting anything about the architecture or a decision in a plan, a PR
body or a review, and before editing a file a concept governs (`okf search --for-path
<file>`, then `git status` and `git log` on that file — the hit's `last_updated` cannot see
an uncommitted edit). To find code — a symbol, a caller, a string — use Grep and LSP;
recall does not index code.

When you know the file rather than the topic, `okf search --for-path <file>` still
answers — but it has no drift join, so check the result's `last_updated` against
`git log` on that file before quoting it, or re-run the topic through `okf-recall.sh`.

## Reading the output

```
4 hit(s) for "cose domain separation" in knowledge — 1 STALE

  architecture/protocol-core                   Reference    3.58   11 targets unchanged · stable · review current
      The encoding and crypto layer — canonical CBOR, COSE Sign1 domain separation, …

  playbooks/bound-a-decode-path                Playbook     2.11   STALE: code moved after it was written · stable · review current
      Give a decode path receiver-chosen DecodeBounds and prove the bound arrived …
      last_updated 2026-09-11; the code under it moved since:
        core/crates/core/src/cbor.rs#decode_bounded  [changed_after_baseline]
          last commit touching this file (not necessarily the cause): 4f2a11cb 2026-09-16 tighten the length guard (Alessandro Viganò)

  decisions/cose-and-canonical-cbor-are-…      Decision     2.90   no tracked target · stable · review expired 2026-08-30
      COSE and canonical CBOR are hand-rolled …

  decisions/k-w-uses-ed25519                   Decision     1.12   no tracked target · deprecated · no review date
      Superseded …

"targets unchanged" means the code under the anchors did not move. …
STALE means the code a concept is bound to changed after the concept was last believed. …
```

**No word in this output may be read as "verified".** Each surviving hit carries three
INDEPENDENT signals, and none of them is a statement about the prose:

| Signal | What it is | What it is not |
|---|---|---|
| `N target(s) unchanged` / `STALE: …` / `BROKEN LINK: …` / `no tracked target` / `not drift-tracked (wiki)` / `drift not run` | an observation about the **anchors**: drift re-fingerprinted N declarations and none moved; or at least one moved since the concept was last believed; or (BROKEN LINK) none moved but a markdown link in it points at nothing; or the concept has no anchor and nothing checked it; or (a `wiki` bundle with no `drift.lock`, or no drift available) drift did not run at all | a statement that the concept is true, or that it covers what you are about to do — a claim no anchor touches is invisible to it, and a concept with a live anchor can still be false |
| `stable` / `deprecated` / `draft` / `no status` | the author's own `status:` | a freshness signal. A **deprecated** concept is history: find its `Superseded by` link and read the successor instead |
| `review current` / `review expired <date>` / `no review date` | `stale_after` against today — when a human said they would re-read it | a check that anyone did |

The three disagree routinely, and that is the point: a concept can be `11 targets
unchanged · deprecated · review expired`.

Use the hits at the confidence the three signals actually support.

**A STALE hit is a lead, not a fact.** It was true when someone wrote it, and the ground
has moved under it since. Its prose may still be right — but nothing has checked, and
the concept cannot tell you which of its sentences the change touched. It used to be
withheld in a separate block; measured over the reference consumers' sessions, the
concept was always worth reading beside the code, and the CI gate keeps `main` fresh, so
a stale hit appears mid-branch — usually because this session moved the code. So:

1. **Read the code**, at the path named — the **current working tree and staged
   changes** first, and only then the history. drift blames with `git log -1 -- <file>`,
   so the commit it names is the LAST COMMIT TO TOUCH THE FILE, not necessarily the one
   that moved the ground under the concept: an unrelated reformat lands there just as
   readily. That is what the line says, in those words. The code as it stands is the fact
   now; the commit is a lead.
2. Quote the stale concept only for what the code confirms. Its claims about *other*
   things are no safer: you do not know where the inaccuracy stops.
3. If the concept turns out to be wrong — or right — **fix or confirm it with
   `/okf-write`**, whose `okf-restamp.sh` re-stamps the binding and writes the dated line
   in `log.md` saying what was read. Do not run `drift link --doc-is-still-accurate`
   yourself as a way to make the mark go away.
4. Stale is not a bug report. A bundle where nothing is ever stale is either a dead
   codebase or a lock nobody bootstrapped.

`blame` carrying **"(uncommitted change — nothing to blame yet)"** in place of a subject
means the change is in the working tree and not committed. Still a real change — drift
signs content, not commits.

A concept whose only fault is a **broken markdown link**, with no moved anchor, is
labelled `BROKEN LINK: …` instead of STALE (it still counts in the header's STALE total);
the link shows as `broken link at line N: <target>`. Smaller problem, real one: the
reader was sent somewhere that no longer exists.

## Without drift

When `drift` is not on PATH, or there is no `drift.lock` at the repository root, recall
still searches. The first line says so, and every hit is labelled `drift not run`:

```
warn  drift did not run (there is no drift.lock at the repository root): nothing below was checked against the code
```

It used to exit 2 here, on the theory that a recall which silently degrades is worse than
none. The degradation is no longer silent — it is on the first line and on every hit — and
exit 2 turned a missing binary into no recall at all, so agents fell back to bare `okf
search`, which says nothing. Treat a `drift not run` hit like a `no tracked target` one:
nothing checked it. To restore the join, install the pinned drift or bootstrap the lock
(`/okf-setup` Step 3b).

A drift that RAN and failed — an exit above 1, no JSON, a report with a concept missing —
is still exit 2: that is a broken detector, not an absent one.

A bundle declared `wiki` in `.okf-profile` with no `drift.lock` binds no code by design, and
labels every hit `not drift-tracked (wiki)` with no warning. A wiki that has a `drift.lock`
gets the join back. An unknown profile value exits 2. See `/okf-setup`, *Profile: wiki*.

## Measured facts the join rests on

drift v0.10.1, okf v0.3.0, measured 2026-09-16. Re-measure after either upgrade; the full
drift section is in `../okf-setup/references/okf-quirks.md`.

- `drift check --format json` emits `schema_version: "drift.check.v1"`, documented in the
  drift repo at `docs/check-json-schema.md` with a JSON Schema alongside. (An earlier note
  claiming drift had no JSON output was wrong for this version.)
- The exit code is independent of the format: 0 when nothing is stale and no link is
  broken, 1 otherwise; `summary.result` mirrors it. The gate reads findings across the
  repository: a non-zero report with stale/broken docs outside the knowledge bundle is
  noted but does not fail a fresh bundle, while a non-zero report with no findings is an
  execution error.
- `docs[]` has one entry per markdown file drift discovers **under the working
  directory** — run from the repository root that is every `.md` in the repo (74 in
  repo A), not only the bundle, so filter on `path`. A doc with no anchors is
  `fresh`: a concept with no `code_refs`, or only non-code `code_refs`, is never marked
  stale, and never vouched for either.
- Per-doc `result` is `fresh` | `stale` | `broken`. A stale anchor carries `reason.code`
  (`changed_after_baseline`) and `blame {author, commit, date, subject}`.
- `okf search --json` is an **array** of `{concept_id, title, type, description, score,
  tags, code_refs, matched_on, inbound, …}`. There is no `path` field — the doc path is
  `<bundle>/<concept_id>.md`, and that is what the join is keyed on.
- The bundle's own root-relative links (`/project/stack.md`) are not counted as drift
  links at all, so okf's link style never surfaces here as broken.
- `drift link <doc> <target>` writes **only `drift.lock`** (TOML `[[bindings]]` with
  `doc`, `target`, `sig`) — it never touches the doc. Provenance is a content signature,
  not a commit.
- Editing the doc does **not** clear staleness. Only `drift link … --doc-is-still-accurate`
  re-stamps the signature — which is why re-stamping is `/okf-write`'s step 3
  (`okf-restamp.sh`) and not a side effect of fixing the prose.
- `drift status --format json` → `[{doc, files[]}]`, the inverse index. `drift refs
  <target>` names the docs bound to one path. `drift check --changed <path>` narrows the
  check to the docs anchored to that path — useful in a pre-commit hook, not needed here.
- `drift check --help` is **not** valid and errors. `drift --help` is.
