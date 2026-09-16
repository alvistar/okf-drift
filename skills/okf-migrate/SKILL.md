---
name: okf-migrate
description: |
  Migrate a mex scaffold (`.mex/`: ROUTER, AGENTS, context/, patterns/, grounds_to,
  mex:// anchors) into an OKF v0.2 bundle in the okf-drift layout, keeping every
  document, resolving every grounding to a path WHILE mex still exists, and finishing
  with the gate green and drift bootstrapped. Built from two real migrations; carries
  what they got wrong.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-migrate.

  Trigger on: "/okf-migrate", "migrate from mex", "convert .mex to okf", "leave mex",
  "mex to knowledge/".
---

# /okf-migrate — from `.mex/` to `knowledge/`, without losing anything

The fourth skill in the `okf-drift` plugin. `/okf-setup` is for a repo with no bundle;
this one is for a repo that has a mex scaffold and wants out. The mechanical half is
`${CLAUDE_PLUGIN_ROOT}/scripts/okf-migrate.py`; the rest is judgement, and the order
matters because **step 2 is only possible while mex and its graph are still there.**

**Every path below is relative to the target repository root**, and every command runs
from there. Nothing here pushes, opens a PR, or bumps a version.

## What the first migration got wrong, so this one does not

Measured on offline-payment-attestation (27 documents, 31 groundings) and ai-review
(20 documents, 34 groundings, 25 inline anchors):

- **PyYAML folded 22 long descriptions over two lines and okf reads a description to
  the end of its first line.** Half of each description vanished from search and the
  indexes, silently, and no check saw it for a day. The migrator writes frontmatter by
  hand, one line per key. Never round-trip a bundle through a YAML dumper.
- **PyYAML also ate an unquoted `#`** (`(issue #48); …` → `(issue`). Quote descriptions
  that carry `#` or `: `; the migrator does.
- **The plan's counts were wrong** (26 docs, 33 groundings, "README has frontmatter").
  Count with `inventory`, not from memory; `patterns/README.md` and `INDEX.md` are
  body-only.
- **`mex graph get` exits 0 with no source record** for some nodes (7 of 31). Those
  groundings are recorded as UNRESOLVED in `log.md`, with the node id, not invented.
- **Links from an index do not connect a concept**; two concepts were orphans until they
  got a `## Related` of their own. And a link *to* an `index.md` is a broken link.
- **The routing table, the session contract and the format guides were mex, not
  knowledge**; the layout conversion afterwards cost a second commit and 180 lines of
  state had to be put on a diet. The migrator writes the okf-drift layout directly.
- **Deleting a doc leaves its drift bindings in the lock.** Not a migration problem —
  bootstrap comes after the layout is final — but it is why drift is the last step.

## Step 0 — Inventory, and the one precondition

```bash
uvx --with pyyaml python3 "${CLAUDE_PLUGIN_ROOT}/scripts/okf-migrate.py" inventory --mex .mex
git grep -c '\.mex/' -- . ':!.mex' ':!docs/plans/'      # every file that names the old paths
mex graph status
```

Read the numbers back to the user: documents, body-only files, `grounds_to` entries,
inline `mex://` anchors, decisions and how many are superseded, files referencing
`.mex/` outside it.

**If `mex graph status` says `missing`, stop and build it before anything else.** Every
`grounds_to` and every inline `[symbol](mex://function:…)` is a node id that only the
graph can turn into a path; without it the migration keeps the prose and loses the
grounding. Building it is the user's call and the user's terminal for a TypeScript
repo (deps must be installed first — node ids depend on the compiler's rendered types,
see `mex-adopt`), ~60 s on 1 300 files:

```
Run this yourself, from <repo root>:   mex graph rebuild
```

Do not skip this because it is slow. The graph is deleted with `.mex/` at the end and
there is no second chance.

## Step 1 — Resolve every node id, while mex still exists

```bash
uvx --with pyyaml python3 "${CLAUDE_PLUGIN_ROOT}/scripts/okf-migrate.py" resolve --mex .mex --map okf-migrate-map.json
```

One `mex graph get <node> --detail source` per distinct id; prints `ok`/`MISS` per node
and the count. Keep the map file until the commit — it is the provenance. A `MISS` is
`matchedNodes: 1` with `returnedNodes: 0`: the graph knows the id and holds no source for
it, so it is not an error to fix now; it is a row in `log.md`.

**A MISS whose id also appears as an inline anchor can usually be recovered**, because the
anchor carries the label: `[`acceptSuggestionService()`](mex://function:89ea857d…)`. Grep
the codebase for that declaration, and if exactly one file declares it, write the path into
the map by hand and mark the row `RECOVERED by symbol name, not by the graph` in `log.md`.
That is verification, not invention — and on ai-review it saved 2 of 6 misses. A `MISS`
that appears only in a `grounds_to:` block has no label (mex records `node` and
`fingerprint`, nothing else) and stays unresolved.

## Step 2 — Convert

```bash
uvx --with pyyaml python3 "${CLAUDE_PLUGIN_ROOT}/scripts/okf-migrate.py" convert \
  --mex .mex --out knowledge --map okf-migrate-map.json \
  --templates "${CLAUDE_PLUGIN_ROOT}/skills/okf-setup/templates/knowledge" --name "<Project>"
```

What it writes, from what:

| mex | knowledge/ |
|---|---|
| `context/{stack,setup,conventions}.md` | `project/` — `type: Reference` |
| `context/decisions.md`, one `### ` entry each | `decisions/<slug>.md` — `type: Decision`, `status: stable` / `deprecated`, `date:` from the entry (a `2026-06` becomes `-01` and a NOTE) |
| every other `context/*.md` | `architecture/` |
| `patterns/*.md` | `playbooks/` — `type: Playbook`; `README.md`/`INDEX.md` dropped, the format guide comes from the templates |
| `ROUTER.md` → *Current Project State* | `project/state.md`, `stale_after` +3 months |
| `ROUTER.md` → *Behavioural Contract* | **not written** — it is `CLAUDE.md`'s Work Loop (Step 4) |
| `name`, `triggers`, `edges`, `grounds_to` | `title`, `tags`, `## Related` (targets remapped; edges to `INDEX.md`, `README.md` or `decisions.md` dropped with a NOTE — those are not concepts), `code_refs` (from the map) |
| `[text](mex://kind:id)` in prose | `` text (`path`) `` when resolved and the path added to `code_refs`; plain `text` + NOTE when not |
| `AGENTS.md`, `SETUP.md`, `SYNC.md`, `events/` | nothing — identity is in `CLAUDE.md`, the prompts are this skill, the event log is `log.md` |

It refuses an existing `knowledge/`, never touches `.mex/`, and prints every judgement
it could not make as `NOTE` — and writes the same notes plus the node→path table into
`knowledge/log.md`. **Read the notes.** The usual ones: an edge to `decisions.md` that
should now point at one specific decision; a superseded status naming a decision that
was never an entry (write it as its own file, or the gate fails on the `Superseded by`
rule); a state section far longer than a snapshot.

## Step 3 — Links that leave the bundle

okf validates **every** markdown link in a concept as a concept link. A relative link
to a repo document outside `knowledge/` — `[x](../../docs/incidents/foo.md)` — is a
broken link under `--strict`, and mex scaffolds are full of them (ai-review: 19).
Measured on okf v0.3.0: a relative `.md` link and a root-relative `/docs/x.md` are
broken; an **angle-bracket destination** `[text](<../../docs/foo.md>)` is not counted
at all, and neither is a non-`.md` target, an `https://` URL, or a reference-style
link. The angle form is still a link everywhere Markdown is rendered, so the migrator
rewrites every link it can prove leaves the bundle into that form and appends the
target to `sources:`. Check `okf validate knowledge --strict` for any it missed and
do the same by hand. Do not delete the reference: the concept's claim rests on that
document.

## Step 4 — Everything outside `knowledge/`

1. **`CLAUDE.md`**: replace the mex block (`## Code Graph`, the mex-agent template
   comment, `## Scaffold Growth`, `## Agent Logging`, `## Navigation`, and any prose
   paragraph that routes to `.mex/context/…`) with the three sections from
   `${CLAUDE_PLUGIN_ROOT}/skills/okf-setup/templates/CLAUDE-knowledge-section.md`
   (**Knowledge Bundle**, **Work Loop**, **Navigation**). Repoint any paragraph that
   named a context doc (`.mex/context/auth-model.md` → `knowledge/architecture/auth-model.md`).
   Keep identity, non-negotiables, commands untouched.
2. **`.gitignore`**: remove the `.mex/graph.db*` block.
3. **`orca.yaml`** (if present): remove the background `mex graph` build at worktree
   creation and any `.mex` shared path — a bundle is tracked Markdown, nothing to build.
3b. **Inside the bundle too.** The migrator rewrites *links*, not prose paths, and a mex
   scaffold is full of the latter: measured on ai-review, all five `patterns/` files ended
   in an **`## Update Scaffold`** checklist telling the agent to edit `.mex/ROUTER.md`,
   `.mex/context/` and `.mex/patterns/INDEX.md`, and four concepts cited a sibling as a bare
   `` `context/auth-model.md` ``. Sweep
   `grep -rn 'context/\|patterns/\|ROUTER\.md\|\.mex' knowledge/ | grep -v log.md`
   and fix both: replace the scaffold checklist with one matching `CLAUDE.md`'s Work Loop,
   and turn a prose citation into a real `[title](/category/slug.md)` link.
4. **Every other file from Step 0's `git grep`**: `TODOS.md`, `docs/reference/*`,
   `docs/agents/*`, `CONCEPTS.md`, READMEs, `.claude/rules/*` — repoint to the new
   path. Historical plan files under `docs/plans/` are left alone; a dated plan naming
   `.mex/` is a record, not a link.
5. Copy the gate and the recall script in: `${CLAUDE_PLUGIN_ROOT}/scripts/okf-check.sh`
   → `scripts/okf-check.sh`, `okf-recall.sh` likewise, executable.

6. **Step 3c of `/okf-setup`: the CI workflow.** Copy
   `${CLAUDE_PLUGIN_ROOT}/skills/okf-setup/templates/knowledge.yml` to
   `.github/workflows/knowledge.yml` and add its sentence to `CLAUDE.md`. Normally in the
   migration commit itself, so the PR the user ships already carries the gate. **Defer it
   to a follow-up commit after the migration lands** when there are other open branches:
   `pull_request` fires on every one of them, and a branch that has not yet merged the
   migration has no `knowledge/` — the job fails there for a reason that is not its
   author's.

Then `git grep -n '\.mex' -- . ':!docs/plans/' ':!knowledge/log.md'` must be empty
(the log's provenance table names the old paths on purpose).

## Step 5 — Gate, then diet

```bash
okf validate knowledge --strict --drift --stale
scripts/okf-check.sh knowledge
```

Expect failures of three kinds, in this order of effort: out-of-bundle links the
migrator could not prove (Step 3); `[TO DETERMINE]` where a document had no
description; and `project/state.md` over the snapshot rule — Working 3-7, Not yet
built 0-7, Known issues 0-7, one line each. The narrative that was in the ROUTER goes
to `log.md` as dated entries, every date and number kept. That last one is editorial
work, not mechanical; do it, do not skip it, and say what moved.

Three searches you would actually type must hit the concept you meant first.

## Step 6 — drift, then remove mex

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/okf-drift-bootstrap.sh" knowledge     # drift.lock from every code_refs
drift check --format json | head -20                                   # all fresh, by construction
git rm -r .mex && rm -rf .mex                                          # graph.db* was ignored; the wrapper stays
scripts/okf-check.sh knowledge                                         # step 6 now runs
```

Symbol-level anchors (`path#Symbol`) are worth it where the prose depends on one
declaration and the language is Go/Java/Python/Rust/TypeScript/Zig — the map file carries
the symbol name for each node, which is exactly the list to narrow from. Three things
measured on the ai-review migration, each of which costs the whole narrowing pass if you
assume otherwise:

- **mex's `source` record has no symbol NAME** (mex 0.8.2): `resolve` parses it out of the
  first line of the range's `content`. Before that fix every `symbol` in the map was `null`.
- **A bare name binds the first declaration of that name in the file** — check each one is
  unique in its file before linking it (`grep -c 'function <name>\b'`), and say which
  declaration you bound in `log.md` when it is not.
- **`.mjs` and `.cjs` refuse a `#Symbol` anchor**; `.ts` accepts one. Node-side scripts stay
  whole-file. See `okf-quirks.md`.

**Do not re-run `okf-drift-bootstrap.sh` after narrowing.** It skips a `(doc, target)` pair
the lock already holds, and `path#Symbol` is not the same pair as `path` — so a second run
re-adds every whole-file binding you just replaced (measured: 48 bindings became 67). If it
happens, `git checkout HEAD -- drift.lock`.

Do it after the commit, as its own change (`/okf-write` knows the rule: never re-stamp
silently).

`~/.local/bin/mex` (the pinned wrapper) is per machine, not per repo: leave it until
the last mex repo is gone.

## Step 7 — Commit

One commit, `chore: migrate the knowledge base from .mex/ to an OKF bundle at knowledge/`,
body: documents moved, decisions split, groundings resolved/unresolved, references
repointed, drift bindings. `knowledge/log.md` already carries the provenance table. Then
the user decides about `/ship`; a knowledge migration takes no version bump.

## Report

Inventory numbers vs what was written; groundings resolved / unresolved with the node
ids; every NOTE the migrator printed and what was done about it; lines moved from state
to log; the gate line; the search checks; the commit hash; and anything above that
turned out wrong when measured.
