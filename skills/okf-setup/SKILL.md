---
name: okf-setup
disable-model-invocation: true
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
repo that has none, `/okf-migrate` moves an existing bundle to the split log layout,
`/okf-write` records into it (the Grow step), `/okf-read` recalls from it (search with a
change hint beside each hit whose code moved since the concept's last commit). Gate and
recall use the model-invocable `okf-drift:okf-runtime` skill.
For setup-only commands below, set `PLUGIN_ROOT` to two directories above this
skill's absolute base directory supplied by the host, and `REPO_ROOT` to the
absolute consumer root. These are explicit shell variables, not assumed environment.

`okf init` writes two files and prescribes nothing else. This skill lays down a fixed
layout whose value is the section prompts inside each concept — what belongs there and
what does not — and a gate that fails until they are replaced by facts.

Everything in `references/okf-quirks.md` was measured on okf v0.3.0 on 2026-09-16 and
re-measured on okf v0.6.0 on 2026-10-08, and the design was reviewed adversarially by a second model on 2026-09-16 (the findings that
survived are in the templates and the gate). Re-read the quirks after an upgrade before
trusting a green validation.

**Every path in this document is relative to the target repository root.**

## What you get

```
knowledge/
  index.md                  reserved — category map + the state link; no routing table
  log.md                    reserved — the frozen log: a pointer to log/ and its marker
  log/<date>-setup-<hex>/log.md   the first log entry, with the "Created" line; each branch adds its own
  project/
    index.md
    state.md                Reference — Working / Not yet built / Known issues: a one-line SNAPSHOT
    state-evidence.md       Reference — the evidence behind each state line, read by item
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
.okf-drift-version          lockfile: the okf-drift tag, then one <sha256>  <name> per script (Step 3)
.github/workflows/knowledge.yml   the gate on every PR and on push to main (Step 3b)
CLAUDE.md                   + Knowledge Bundle · Work Loop · Navigation (Step 3)
```

Six concepts, pre-wired with `## Related` links so `okf validate --strict` passes
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
okf version          # expect: okf version v0.6.0 (OKF v0.2 specification)
```

Absent: `go install github.com/okf-memory/okf-agent-memory/cmd/okf@v0.6.0` (Go 1.26+) and make sure
`$(go env GOPATH)/bin` is on PATH. Another version: the gate prints a warning; re-run the
probes in `references/okf-quirks.md` before believing either the tool or this skill.

**Do not create concepts with `okf create`** — the skill writes them from templates (see
`references/okf-quirks.md`). On okf v0.3.0, `okf create --help` even created a concept called
`--help.md`; v0.6.0 prints help.

## Step 1 — Is there a bundle already?

```bash
test -d knowledge && echo "BUNDLE EXISTS"
# If a pin exists, invoke okf-drift:okf-runtime in gate mode.
# Missing pin: install integration in Step 3 explicitly; never bypass the pin.
```

- No bundle → Step 2.
- A bundle that passes the gate → the job is Step 5 (resync) or nothing. Do not
  scaffold over it.
- A bundle that fails on comments/placeholders → Step 4 (populate). Missing files from
  the layout above: `okf-scaffold.sh --force .` adds only what is absent, never
  overwrites.
- A bundle the gate fails with `log.md: not frozen` (it predates log entries) or with
  `drift.lock found` (it predates 0.15.0) → `/okf-migrate` first, then back here.

## Step 2 — Scaffold

```bash
"${PLUGIN_ROOT}/scripts/okf-scaffold.sh" --name "<Project Name>" .
```

Copies the templates with the name and dates substituted (`stale_after` = +3 months on
state, +6 on stack and setup), refuses an existing `knowledge/`, starts the bundle split
(`okf-log.sh split` freezes the root `log.md`, then `okf-log.sh add --slug setup` writes
the "Created" line in the first log entry, unless `log/` already holds one, so a
`--force` re-run adds no second line; neither needs a repository), and runs
`okf validate knowledge --strict --drift`. Expect
`5 concept(s), 0 error(s), 0 warning(s); 0 broken link(s), 0 orphan(s)`. Anything else
is a bug in this skill — report it rather than patching the output.

## Step 3 — CLAUDE.md and the gate

Use the plugin-only integration helper for both fresh setup and conversion of an
existing wrapper-based installation. It changes only the pin, recognized instruction
sections and workflow, and removes recognized generated legacy files. It never
scaffolds, edits `knowledge/`, or changes project navigation.

```bash
python3 "$PLUGIN_ROOT/scripts/okf-integrate.py" \
  --repo-root "$REPO_ROOT" --tag v0.15.0 --dry-run
# Review the proposed paths, then repeat without --dry-run.
python3 "$PLUGIN_ROOT/scripts/okf-integrate.py" \
  --repo-root "$REPO_ROOT" --tag v0.15.0
```

Requires Python 3.11+. **v0.7.0 is the first release the helper accepts**, but the
Knowledge Bundle and Work Loop sections installed here describe the gate and recall of
**v0.15.0** (no drift, the change hint, the gate failing on a leftover `drift.lock`): pin
that release or a later one. An older pin runs an older gate than the one `CLAUDE.md`
describes. Choose an explicitly approved
published version; never derive a project upgrade from the installed
plugin version. The helper calls `okf-pin.sh` against the release's `SHA256SUMS`,
stages the result, and validates it before changing the consumer. Omitting `--tag`
keeps an already compatible pin byte-for-byte. See README **Integration conversion**
for recognition and refusal rules. Unknown/customized files require a deliberate
human merge; do not overwrite them to get past preflight.

The helper preserves all other CLAUDE sections and any existing Navigation section.
Fresh instructions respect the project's existing read order. Historical wrapper
references inside knowledge are reported, left untouched, and explicitly subordinate
to CLAUDE's new operational instructions. If deletion would invalidate `code_refs`,
stop; no bundle edit is authorized.

Invoke `okf-drift:okf-runtime` in gate mode now. A fresh scaffold must fail on
annotations/placeholders; verify that the pinned gate actually ran, not just that a
command returned nonzero. Keep the integration and pin in version control; consumer
repositories carry no OKF scripts.

What the gate adds to `okf validate --strict --drift --stale` (all measured absent from
the tool): warnings treated as failures (a dead `code_refs` path is a warning at exit
0); index rows resolve, are unique, and carry the concept's description verbatim, and
every concept has a row in its category index; one-line descriptions, ISO
`last_updated`/`stale_after`; decisions have an ISO `date`, a link to a concept outside
`decisions/` (an island of decisions passes `--strict`), and a `Superseded by` link when
`status: deprecated` (the vocabulary `draft|stable|deprecated` is okf's own and
`--strict` enforces it — `active` is rejected); no HTML comment left in
a concept (search indexes comment text), no placeholder, no empty section; root
`okf_version`, `log.md`, and `state.md`'s three lists (a state item past 300 characters
is a warning). Empty `code_refs` is a warning:
coverage is a judgement. A `stale_after` within the next 30 days
(`OKF_REVIEW_WINDOW_DAYS`) is a warning, because okf fails the concept on that day; an
impossible one (`2026-13-01`) is a failure. A bundle root that resolves outside its parent
directory (a `knowledge -> /elsewhere` symlink) fails before okf runs.

The gate fails while a `drift.lock` exists beside the bundle: drift is no longer used
(`docs/adr/0002-drop-drift-code-is-the-source-of-truth.md` in okf-drift), and the lock
means the repository has not run `/okf-migrate`. Nothing in the gate checks whether a
concept is still true of the code; that is read-repair's job, at the moment an agent
relies on the concept.

## Step 3b — CI

Step 3 installs `templates/knowledge.yml` verbatim. Its standalone bootstrap downloads
the launcher at the project's pinned tag, verifies its pinned digest before execution,
and calls the root-aware launcher; no installed plugin is needed. It explicitly
unsets the development override. See README **Standalone bootstrap** for the local
plugin-free command; the workflow template is the single bootstrap source.

Keep the every-PR/main-only-push triggers and the explicit dependency preflight. Read existing workflows first to avoid duplicate gates. A customized
workflow is a manual integration decision; the helper refuses it rather than silently
relaxing its checks. Test the job's actual bootstrap, not just a direct plugin script.

## Step 4 — Populate

`references/populate-prompt.md`: **A** for an existing codebase, **B** for nothing
built yet. Run A yourself when you are in a session with the repo. It replaces the
annotations with what the code does not say, written to the writing rule (see *Rules the
templates encode*), and deletes them; records 3-6 decisions from `git log`, seeds
3-5 playbooks, wires the links, and ends with the gate and the list of every
`[TO DETERMINE]` left, with what would fill it.

Before running A on a repo with a README or `docs/`: those are summarised and listed
under `sources:`, never copied. Say so in the hand-over.

Verify with a **fresh** session: "Read `knowledge/index.md` and
`knowledge/project/state.md`, then tell me what you know about this project." Then
`okf search` three phrases you would actually type and check the first hit.

Commit the bundle, `CLAUDE.md`, pin and workflow together. Nothing publishes;
no version bump.

## Step 5 — Keep it true

The Work Loop in `CLAUDE.md` is the mechanism: state, concept, decision or playbook,
dates, log, gate, and read-repair whenever a concept an agent relies on contradicts the
code. When that has slipped, `references/sync-prompt.md` is the resync: a zero-token
check (validate, the gate, and the commits on each concept's `code_refs` since its last
commit, the same count recall shows as a change hint) followed by a surgical-edit
prompt. A review advances **both** `last_updated` and `stale_after`,
or the concept stays expired.

## Profile: wiki — a knowledge base that describes no code

Everything above assumes a software repository. A personal or company knowledge base —
people, things owned, open matters, procedures, decisions — has no code, no `code_refs`
to fill and no project snapshot to keep. Scaffold it with:

```bash
"${PLUGIN_ROOT}/scripts/okf-scaffold.sh" --profile wiki --name "<Name>" .
```

That lays down `index.md`, the frozen `log.md` with the "Created" line in its first log
entry under `log/`, `reference/`, `playbooks/` and `decisions/` (the
last two with non-code formats at the top of their indexes), and writes `.okf-profile`
containing `wiki` beside the bundle. Add the categories the knowledge base needs — the
reference consumer uses `contacts/`, `assets/`, `matters/` (one per case, with its state
dated inside it) — each with an `index.md` and a row in the root index.

What the profile changes, and nothing else:

- **Gate.** Neither a missing `project/state.md` nor an empty `code_refs` is reported.
  Everything else — frontmatter, one-line descriptions, indexes both ways, decisions,
  links, empty sections, placeholders, a leftover `drift.lock` — is checked exactly as
  for code.
- **Recall.** Unchanged: `status · review` per hit. A concept with no `code_refs` gets no
  change hint, so a wiki's hits carry none.

In both profiles the gate FAILS on a bundle with no concept, and warns on an open
question written into a concept — `[TO VERIFY]` or `[DA VERIFICARE]` — so an unconfirmed
claim stays visible instead of passing.

Skip Step 3b: there is no CI job to install. To run the gate and recall through
`okf-drift:okf-runtime`, pin a release at or above v0.15.0 with `okf-pin.sh` (the pin alone; the integration helper also installs the code-profile CI
workflow and Work Loop, which a wiki does not use). Give `CLAUDE.md` a short
Knowledge base section instead of the Work Loop: what lives in the bundle and what lives
elsewhere (tasks, mail), how to search it, and how a change is recorded — concept dated
with its evidence, a line in the branch's log entry (`okf-log.sh add`, never the frozen
root `log.md`), the gate.

Search: `okf search` is BM25 and misses paraphrases ("home phone" for a concept that says
"landline"). A local hybrid index — qmd with a multilingual embedding model, the bundle
as a collection with `index.md` and every `log.md` ignored — found three of the four questions
BM25 missed on the reference consumer; run both, they fail on different questions.

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
- **`code_refs` are repo-relative, narrow, and must exist.** They say where to look:
  directories or boundary files the concept governs, file paths only (no `path#Symbol`;
  `okf validate --drift` reads it as a missing path). Not `src/` on everything, which
  makes `--for-path` noise and puts a change hint on every hit.
- **The writing rule.** A concept holds what the code does not say: why, invariants,
  traps, conventions, how to behave, and where to look. It never restates what the code
  says (signatures, defaults, step lists, numbers, field lists); name where that lives.
  A fact that must be quoted from the code is a dated observation ("on 2026-10-15,
  `retry.ts` gave up after 3 attempts").
- **Comments and links inside comments count.** Search indexes comment text; okf
  resolves a link inside a comment. Annotations are replaced and deleted.
- **`index.md` and `log.md` are reserved at every level; `README.md` is not.**
- **Decisions: slug is permanent, file is never deleted.** In force → `status: stable`;
  superseded → `status: deprecated`, a `Superseded by` link, the new file links back, no
  `stale_after`. `--strict` rejects any other status word.
- **`state.md` is a one-line snapshot.** One line per item, ending with how far the claim
  reaches; "None known." when a list is empty. Per-item evidence goes to
  `state-evidence.md` under the same item, the story to the branch's log entry. The budget is the line,
  not the count: without an evidence file, the reference consumer's snapshot reached 58 KB.

## What OKF does not give you, said once

No code graph, no `impact`, and no check that a concept is still true. `code_refs` +
`--drift` tell you a path vanished; recall's change hint tells you a governed path
changed since the concept's last commit, and which commit was last. Whether the prose is
still *true* is read-repair's question, asked by the agent that relies on it, against
the code. The writing rule keeps that question rare: a concept that holds only what the
code does not say has little for a code change to falsify.

## Report

Give the user: the okf version; the validate line after scaffolding; the gate result
after population with every placeholder left and why; the decisions recorded; the
three search checks; the files to commit; and anything in `references/okf-quirks.md`
the run contradicted.
