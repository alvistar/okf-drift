---
name: okf-read
disable-model-invocation: true
description: |
  Recall from an OKF knowledge bundle without serving a stale fact as a fact:
  `okf search --json` joined with `drift check --format json`, so a concept whose bound
  code changed since it was written is withheld from the answer and reported with the
  commit to blame. Drift is a hard dependency — no lock, no recall.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-read.

  Trigger on: "/okf-read", "what do we know about", "search the knowledge bundle",
  "is this concept still true", "why was that concept withheld".
---

# /okf-read — recall, minus whatever the code has since contradicted

One of three skills in the `okf-drift` plugin: `/okf-setup` lays the bundle down,
`/okf-write` records into it, `/okf-read` recalls from it. **Every path below is relative
to the target repository root**, and every command runs from there.

A knowledge bundle's failure mode is not being empty. It is being confidently wrong: a
concept written six weeks ago, indexed, well-linked, top of the search results, and
describing a function that was rewritten last Tuesday. `okf search` cannot see that —
BM25 ranks relevance, not truth. This skill closes that gap by refusing to serve what it
cannot vouch for.

## The command

```sh
# Invoke okf-drift:okf-runtime in recall mode with "<terms>" and optional bundle
```

Use it **instead of** `okf search`, for the same queries you would have typed. It runs
`okf search --json`, runs `drift check --format json`, joins them on
`<bundle>/<concept_id>.md`, and prints two blocks.

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
4 hit(s) for "cose domain separation" in knowledge

  architecture/protocol-core                   Reference    3.58   11 targets unchanged · stable · review current
      The encoding and crypto layer — canonical CBOR, COSE Sign1 domain separation, …
  decisions/cose-and-canonical-cbor-are-…      Decision     2.90   no tracked target · stable · review expired 2026-08-30
      COSE and canonical CBOR are hand-rolled …
  decisions/k-w-uses-ed25519                   Decision     1.12   no tracked target · deprecated · no review date
      Superseded …

"targets unchanged" means the code under the anchors did not move. It does not mean the
prose is right, and it says nothing about claims the anchors do not cover. "no tracked
target" means nothing was checked. A deprecated concept is history: read its successor.

WITHHELD — 1 concept(s) matched, but the code under them moved after they were written.
Do not quote these as facts. Read the code they point at, or fix the concept with
/okf-write, which re-stamps the binding and logs that it did.

  playbooks/bound-a-decode-path                Playbook     2.11   last_updated 2026-09-11
      Give a decode path receiver-chosen DecodeBounds and prove the bound arrived …
      core/crates/core/src/cbor.rs#decode_bounded  [changed_after_baseline]
          last commit touching this file (not necessarily the cause): 4f2a11cb 2026-09-16 tighten the length guard (Alessandro Viganò)
```

**No word in this output may be read as "verified".** Each surviving hit carries three
INDEPENDENT signals, and none of them is a statement about the prose:

| Signal | What it is | What it is not |
|---|---|---|
| `N target(s) unchanged` / `no tracked target` | an observation about the **anchors**: drift re-fingerprinted N declarations and none moved, or the concept has no anchor and nothing checked it | a statement that the concept is true, or that it covers what you are about to do — a claim no anchor touches is invisible to it, and a concept with a live anchor can still be false |
| `stable` / `deprecated` / `draft` / `no status` | the author's own `status:` | a freshness signal. A **deprecated** concept is history: find its `Superseded by` link and read the successor instead |
| `review current` / `review expired <date>` / `no review date` | `stale_after` against today — when a human said they would re-read it | a check that anyone did |

The three disagree routinely, and that is the point: a concept can be `11 targets
unchanged · deprecated · review expired`.

**The hit block** is what `okf search` would have given you, minus the withheld. Use it
normally, at the confidence the three signals actually support.

**The WITHHELD block is not a softer result. It is a refusal.** A withheld concept is a
document that was true when someone wrote it and has had the ground moved under it
since. Its prose may still be right — but nothing has checked, and the concept cannot
tell you which of its sentences the change touched. So:

1. **Read the code**, at the path named — the **current working tree and staged
   changes** first, and only then the history. drift blames with `git log -1 -- <file>`,
   so the commit it names is the LAST COMMIT TO TOUCH THE FILE, not necessarily the one
   that moved the ground under the concept: an unrelated reformat lands there just as
   readily. That is what the line says, in those words. The code as it stands is the fact
   now; the commit is a lead.
2. Do not quote, paraphrase or reason from the withheld concept's claims about that
   path. Its claims about *other* things are no safer: you do not know where the
   inaccuracy stops.
3. If the concept turns out to be wrong — or right — **fix or confirm it with
   `/okf-write`**, which re-stamps the binding and writes the dated line in `log.md`
   saying who checked what. Do not run `drift link --doc-is-still-accurate` yourself as a
   way to make the block go away.
4. Withheld is not a bug report. A bundle with nothing ever withheld is either a dead
   codebase or a lock nobody bootstrapped.

`blame` carrying **"(uncommitted change — nothing to blame yet)"** in place of a subject
means the change is in the working tree and not committed. Still a real change — drift
signs content, not commits.

A concept can also be withheld for a **broken markdown link** rather than a moved
anchor; that shows as `broken link at line N: <target>`. Smaller problem, real one: the
reader was sent somewhere that no longer exists.

## The hard dependency, and why it is one

`okf-recall.sh` exits **2**, with one line and no results, when `drift` is not on PATH or
there is no `drift.lock` at the repository root:

```
no drift.lock at the repository root — okf-recall will not serve concepts it cannot
check; use /okf-setup to bootstrap the pinned drift runtime first
```

It does not fall back to a bare `okf search`. That is deliberate. A recall that silently
degrades into an unverified one is worse than no recall, because the caller cannot tell
the two apart — and the caller is usually a model that will happily quote either. If you
hit this, stop and request the explicit binding bootstrap described in `/okf-setup` Step 3b.
Do not fall back to unverified search.

The gate takes the opposite position for the same reason: the pinned gate's step 6
only **warns** when there is no lock, because a gate must keep working in a repository
that has not adopted the drift phase. Recall refuses; the gate degrades. The asymmetry is
the point — a skipped gate step is visible in the gate's own output, a missing drift
check inside a recall is visible nowhere.

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
  `fresh`: a concept with no `code_refs`, or only non-code `code_refs`, is never withheld,
  and never vouched for either.
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
  re-stamps the signature — which is why re-stamping is `/okf-write`'s step 3 and not a
  side effect of fixing the prose.
- `drift status --format json` → `[{doc, files[]}]`, the inverse index. `drift refs
  <target>` names the docs bound to one path. `drift check --changed <path>` narrows the
  check to the docs anchored to that path — useful in a pre-commit hook, not needed here.
- `drift check --help` is **not** valid and errors. `drift --help` is.
