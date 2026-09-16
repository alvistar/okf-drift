---
name: okf-setup
description: |
  Set up an OKF v0.2 knowledge bundle (github.com/okf-memory/okf-agent-memory) in a
  repository with a FIXED layout: project/{state,stack,setup,conventions},
  architecture/, decisions/ (one concept per decision), playbooks/ — validating
  `--strict` from the first commit. Ships the population and resync prompts, the
  CLAUDE.md section, and the gate for everything `okf validate` does not check.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-setup.

  Trigger on: "/okf-setup", "set up okf", "scaffold knowledge/", "new repo knowledge
  bundle", "populate the knowledge bundle", "resync knowledge".
---

# /okf-setup — A fixed OKF knowledge bundle for a repository

One of four skills in the `okf-drift` plugin: `/okf-setup` lays the bundle down in a
repo that has none, `/okf-migrate` builds it from an existing mex scaffold,
`/okf-write` records into it (the Grow step, with `drift link`), `/okf-read` recalls
from it (search joined with `drift check`, so a stale concept is never served as a
fact). The scripts the four share are at `${CLAUDE_PLUGIN_ROOT}/scripts/`.

`okf init` writes two files and prescribes nothing else. This skill lays down a fixed
layout whose value is the section prompts inside each concept — what belongs there and
what does not — and a gate that fails until they are replaced by facts.

Everything in `references/okf-quirks.md` was measured on okf v0.3.0 on 2026-09-16, and
the design was reviewed adversarially by a second model the same day (the findings that
survived are in the templates and the gate). Re-read the quirks after an upgrade before
trusting a green validation.

**Every path in this document is relative to the target repository root.**

## What you get

```
knowledge/
  index.md                  reserved — category map + the state link; no routing table
  log.md                    reserved — dated history and rationale
  project/
    index.md
    state.md                Reference — Working / Not yet built / Known issues: a SNAPSHOT
    stack.md                Reference — what is used and under which constraints (the why is a decision)
    setup.md                Reference — clone-to-running and what goes wrong on the way
    conventions.md          Reference — naming, structure, patterns, the project's Verify Checklist
  architecture/
    index.md
    architecture.md         Reference — flow, components, external deps, what does NOT exist here
  decisions/
    index.md                the format for a decision, then one row per decision
  playbooks/
    index.md                the format for a playbook, then one row per playbook
.okf-drift-version          the okf-drift tag this repo runs the scripts from (Step 3)
scripts/okf-shim.sh         fetches and caches a script at that tag (Step 3)
scripts/okf-check.sh        two-line wrapper — the gate, six steps, drift join included (Step 3)
scripts/okf-recall.sh       two-line wrapper — search joined with drift, for /okf-read (Step 3)
drift.lock                  one content signature per (concept, code_ref) pair (Step 3b)
.github/workflows/knowledge.yml   the gate on every PR and on push to main (Step 3c)
CLAUDE.md                   + Knowledge Bundle · Work Loop · Navigation (Step 3)
```

Five concepts, pre-wired with `## Related` links so `okf validate --strict` passes
before a word is written. Decisions and playbooks are one file each, added during
population and from real work.

What is deliberately **not** here, and why: no routing table in the root index (the
description already says "Load when…" and `okf search` routes); no format guides as
concepts (they are agent instructions, they polluted search, and they needed decorative
links to avoid being orphans — they live at the top of the reserved category indexes);
no session-contract concept (the behavioural loop is policy and lives in `CLAUDE.md`;
the project state is knowledge and lives in `project/state.md`); no single append-only
decision log (one concept per decision is OKF's own shape and is what search, `status`
and `stale_after` are per-concept for).

## Who runs what

Nothing here launches an interactive session. The scaffold script and the gate are the
agent's; the population and resync prompts are run **by the agent in a session that can
read the repo** — hand them over only when the user wants to run them elsewhere.

## Step 0 — okf present, and which one

```bash
okf version          # expect: okf version v0.3.0 (OKF v0.2 specification)
drift --version      # expect: drift v0.10.1  (Step 3b; not needed before it)
```

Absent: `go install github.com/okf-memory/okf-agent-memory/cmd/okf@latest` and make sure
`$(go env GOPATH)/bin` is on PATH. Another version: the gate prints a warning; re-run the
probes in `references/okf-quirks.md` before believing either the tool or this skill.

**Never run `okf create --help`** — it creates a concept called `--help.md`.

## Step 1 — Is there a bundle already?

```bash
test -d knowledge && echo "BUNDLE EXISTS"
scripts/okf-check.sh 2>/dev/null || "${CLAUDE_PLUGIN_ROOT}/scripts/okf-check.sh" knowledge
```

- No bundle → Step 2.
- A bundle that passes the gate → the job is Step 5 (resync) or nothing. Do not
  scaffold over it.
- A bundle that fails on comments/placeholders → Step 4 (populate). Missing files from
  the layout above: `okf-scaffold.sh --force .` adds only what is absent, never
  overwrites.
- A `.mex/` directory and no `knowledge/` → a migration, not a setup. The bristleworm
  migration plan (`docs/plans/2026-09-15-001-chore-migrate-mex-to-okf-plan.md` in
  offline-payment-attestation) is the worked example; its `Result` section lists what
  the plan got wrong. Note that bundle predates this layout (it still has the routing
  table, a session contract and a single decisions file) — converting it is a
  separate, mechanical task.

## Step 2 — Scaffold

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/okf-scaffold.sh" --name "<Project Name>" .
```

Copies the templates with the name and dates substituted (`stale_after` = +3 months on
state, +6 on stack and setup), refuses an existing `knowledge/`, and runs
`okf validate knowledge --strict --drift`. Expect
`5 concept(s), 0 error(s), 0 warning(s); 0 broken link(s), 0 orphan(s)`. Anything else
is a bug in this skill — report it rather than patching the output.

## Step 3 — CLAUDE.md and the gate

1. Merge `templates/CLAUDE-knowledge-section.md` into `CLAUDE.md`: **Knowledge
   Bundle**, **Work Loop**, **Navigation**. If `CLAUDE.md` does not exist, create it
   with the identity block first (`# <Project>`, *What This Is*, *Non-Negotiables*,
   *Commands* — terse, it is loaded every turn) and the three sections after. If it
   exists, add the three sections and touch nothing else; population fills the rest.
   The daily commands live **only** in `CLAUDE.md`; `setup.md` does not repeat them.
2. Install the shim and pin the tag. CI, the Work Loop and `/okf-read` all call the gate
   and the recall script **from the repo**, so neither may depend on this plugin being
   installed — but a vendored copy of either drifts from the plugin silently, and nothing
   in the repo can see that it has. So the repo carries a one-line pin and two two-line
   wrappers instead:

   ```bash
   mkdir -p scripts
   cp "${CLAUDE_PLUGIN_ROOT}/scripts/okf-shim.sh" scripts/okf-shim.sh
   printf 'v%s\n' "$(jq -r .version "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json")" > .okf-drift-version
   for s in okf-check okf-recall; do
     printf '#!/bin/sh\n# %s.sh from alvistar/okf-drift at the tag in .okf-drift-version — see scripts/okf-shim.sh.\nexec "$(dirname "$0")/okf-shim.sh" %s.sh "$@"\n' "$s" "$s" > "scripts/$s.sh"
   done
   chmod +x scripts/okf-shim.sh scripts/okf-check.sh scripts/okf-recall.sh
   ```

   The shim resolves `$OKF_DRIFT_ROOT/scripts/<name>` first when that variable is set (a
   local plugin checkout, for developing the plugin itself), otherwise fetches the script
   once from `raw.githubusercontent.com/alvistar/okf-drift/<tag>/scripts/<name>` into
   `${XDG_CACHE_HOME:-$HOME/.cache}/okf-drift/<tag>/`. Commit all four paths. Upgrading the
   repo later is editing the one line in `.okf-drift-version`.

   Run `scripts/okf-check.sh knowledge` once now to prove the fetch works. It
   **fails on a fresh scaffold** — annotation comments and placeholders — which is the
   correct answer until Step 4; what you are checking here is that it ran at all.

What the gate adds to `okf validate --strict --drift --stale` (all measured absent from
the tool): warnings treated as failures (a dead `code_refs` path is a warning at exit
0); index rows resolve, are unique, and carry the concept's description verbatim, and
every concept has a row in its category index; one-line descriptions, ISO
`last_updated`/`stale_after`; decisions have an ISO `date`, a link to a concept outside
`decisions/` (an island of decisions passes `--strict`), and a `Superseded by` link when
`status: deprecated` (the vocabulary `draft|stable|deprecated` is okf's own and
`--strict` enforces it — `active` is rejected); no HTML comment left in
a concept (search indexes comment text), no placeholder, no empty section; root
`okf_version`, `log.md`, and `state.md`'s three lists. Empty `code_refs` is a warning:
coverage is a judgement.

Step 6 of the gate is the drift join — see Step 3b. Until there is a `drift.lock` it
`warn`s and skips, so the gate keeps working in a repo that has not adopted drift.

## Step 3b — Bind the bundle to the code

`code_refs` tells you a governed path **vanished**. It cannot tell you the path
**changed**, which is the way a concept actually goes wrong. `drift`
(`~/.local/bin/drift`, v0.10.1 measured) closes that: a content signature per (concept,
path) pair in a repo-root `drift.lock`, and a `blame` when the signature no longer
matches.

```bash
drift --version                                             # expect: drift v0.10.1
"${CLAUDE_PLUGIN_ROOT}/scripts/okf-drift-bootstrap.sh"      # from the REPOSITORY ROOT
```

It reads every `code_refs:` entry in the bundle and runs one `drift link` per entry. It
is idempotent by skipping what `drift.lock` already holds — it has to be, because
`drift link` **refuses** a binding the lock already carries (exit 1, "refused: target
changed since last link") whether or not anything changed. A directory `code_ref` is
expanded into its git-tracked files, because drift signs file content and rejects a
directory outright; one wider than `OKF_DRIFT_MAX_DIR_FILES` (20) is skipped, and the fix
is a narrower `code_ref`.

Run it **after** Step 4 on a repo being populated — there is nothing to bind before the
concepts have `code_refs`. On a bundle that is already populated, run it now. Either way
the last line must be `drift check: pass`: a signature is taken from current content, so
a binding written a second ago cannot be stale. If one is, the lock was not written by
that run.

Commit `drift.lock`. It is shared state, exactly like the bundle.

The full drift measurements — every refusal, the JSON shape, and the one that shapes the
whole design (editing a doc does **not** clear its staleness; only
`drift link … --doc-is-still-accurate` does) — are in `references/okf-quirks.md`.

## Step 3c — CI

The Work Loop is the first filter, and it only fires in a session that touched
`knowledge/`. **The PR that makes a concept stale is almost always one that touches only
code**, and nobody in that PR has a reason to run the gate. So the gate is also a blocking
CI job:

```bash
mkdir -p .github/workflows
cp "${CLAUDE_PLUGIN_ROOT}/skills/okf-setup/templates/knowledge.yml" .github/workflows/knowledge.yml
```

Copy it verbatim. `runs-on` falls back to `ubuntu-latest` in a repo with no `RUNNER_LABEL`
variable, so the template needs no edit either way. If the repo already has workflows,
read one first: check that **nothing there already runs the gate** (don't add a second
copy), and if its conventions differ from the template in a way that matters — a pinned
action SHA, a different Go setup, a required job name — match them rather than the
template. Do not relax the two rules the template encodes: `fetch-depth: 0` (drift's
`blame` reads `git log`; shallow gives you "changed" with no commit to name) and `push`
scoped to `main` (both triggers on a topic branch cancel each other in the concurrency
group and GitHub reports the cancelled run as a check that did not succeed).

Then one sentence in `CLAUDE.md` — appended to the paragraph that already describes what
CI runs, or as a new `## CI` line if there is none:

> `.github/workflows/knowledge.yml` runs `scripts/okf-check.sh knowledge` on every PR and
> on push to `main`: a code change can make a concept stale without touching `knowledge/`,
> and a stale concept blocks the merge until it is re-stamped via `/okf-write`.

Run the job's own steps locally before committing (`okf version && drift --version`, then
`scripts/okf-check.sh knowledge`) — the gate is the same script in both places, so a green
run here is a green run there.

## Step 4 — Populate

`references/populate-prompt.md`: **A** for an existing codebase, **B** for nothing
built yet. Run A yourself when you are in a session with the repo. It replaces the
annotations with facts (and deletes them), records 3-6 decisions from `git log`, seeds
3-5 playbooks, wires the links, and ends with the gate and the list of every
`[TO DETERMINE]` left, with what would fill it.

Before running A on a repo with a README or `docs/`: those are summarised and listed
under `sources:`, never copied. Say so in the hand-over.

Verify with a **fresh** session: "Read `knowledge/index.md` and
`knowledge/project/state.md`, then tell me what you know about this project." Then
`okf search` three phrases you would actually type and check the first hit.

Commit the bundle, `CLAUDE.md` and `scripts/okf-check.sh` together. Nothing publishes;
no version bump.

## Step 5 — Keep it true

The Work Loop in `CLAUDE.md` is the mechanism: state, concept, decision or playbook,
dates, log, gate. When that has slipped, `references/sync-prompt.md` is the resync: a
zero-token check (validate, the gate, and `git log --since=<last_updated> --
<code_refs>` per concept — the closest thing to grounding drift OKF affords) followed
by a surgical-edit prompt. A review advances **both** `last_updated` and `stale_after`,
or the concept stays expired.

## Rules the templates encode

- **`type:` is the only field okf requires.** `title`, `description`, `tags`, `status`,
  `stale_after`, `sources`, `code_refs` are recognised; `last_updated` and `date` are
  carried and ignored — the gate checks them.
- **A concept needs one link, in either direction, in a concept body.** Index rows do
  not count. Link what a reader would follow next; no quotas, no decorative edges.
- **Index rows carry the concept's `description:` verbatim.** The gate compares them
  both ways because `okf` reads no index.
- **`description:` on one line, quoted when it contains `#` or `: `.** YAML truncated
  one at `(issue #48)` during the migration.
- **`code_refs` are repo-relative, narrow, and must exist.** The directories or
  boundary files the concept governs — not `src/` on everything, which makes
  `--for-path` noise and the resync loop permanently hot.
- **Comments and links inside comments count.** Search indexes comment text; okf
  resolves a link inside a comment. Annotations are replaced and deleted.
- **`index.md` and `log.md` are reserved at every level; `README.md` is not.**
- **Decisions: slug is permanent, file is never deleted.** In force → `status: stable`;
  superseded → `status: deprecated`, a `Superseded by` link, the new file links back, no
  `stale_after`. `--strict` rejects any other status word.
- **`state.md` is a snapshot.** Working 3-7; Not yet built and Known issues 0-7 with an
  explicit "None known." when empty; history goes to `log.md`.

## What OKF does not give you, said once

No code graph, no symbol-level drift, no `impact`. `code_refs` + `--drift` tell you a
path vanished; `drift.lock` (Step 3b) tells you a governed path **changed**, and who
changed it — file-level, not symbol-level, so a formatting pass flags a concept exactly
as a rewrite does. Whether the prose is still *true* after that flag is the agent's job,
in `/okf-write`'s step 3, paired with a line in `log.md` saying what was checked. That is
the trade this layout makes for a corpus that outlives both tools.

## Report

Give the user: the okf and drift versions; the validate line after scaffolding;
the bootstrap counts (linked / skipped / failed) and the `drift check` line after it; the gate result
after population with every placeholder left and why; the decisions recorded; the
three search checks; the files to commit; and anything in `references/okf-quirks.md`
the run contradicted.
