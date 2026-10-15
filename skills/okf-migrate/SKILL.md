---
name: okf-migrate
disable-model-invocation: true
description: |
  Bring an existing OKF bundle and its integration up to date, in two independent parts.
  Split the log: freeze the root `log.md` (the history stays, a marker hashes it) and
  create `log/`, where each branch writes its own log entry (`okf-log.sh split`). Drop
  drift: delete `drift.lock`, take the drift steps out of the CI workflow and the
  CLAUDE.md knowledge section, and on request review every concept against the writing
  rule. Works on both profiles (code and wiki). Safe to run twice; nothing commits.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-migrate.

  Trigger on: "/okf-migrate", "split the log", "freeze log.md", "migrate the bundle to
  log entries", "the gate says run /okf-migrate", "the gate says drift.lock found",
  "drop drift".
---

# /okf-migrate — bring an older bundle up to date

Two parts, each idempotent, each run only when its sign is present:

| Sign | Part |
|---|---|
| the root `log.md` has no `<!-- okf-log frozen … -->` marker; the gate says `log.md: not frozen` | **Part 1 — Split the log** |
| a `drift.lock` at the repository root; the gate says `drift.lock found` | **Part 2 — Drop drift** |

Check both signs first and say which parts apply. Run Part 1 before Part 2 when both do.

Set `PLUGIN_ROOT` to two directories above this skill's absolute base directory supplied
by the host. **Every command runs from the target repository root.** Nothing here
commits, pushes or opens a PR.

The bundle is `knowledge/` unless the repository keeps it elsewhere (the CLAUDE.md
knowledge section names it). It must hold a root `log.md`. If it does not, stop: the
bundle is incomplete, and `/okf-setup` is the job, not this one.

# Part 1 — Split the log

Every PR used to write the bundle's root `log.md`, so merging one PR conflicted every
other open PR. Now each branch writes its own **log entry**,
`<bundle>/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`, and the root `log.md` becomes the
**frozen log**: it keeps the history written before the split, points to `log/`, and
ends with a marker that carries the split date and the sha256 of the history. The gate
fails on any change to that history. See `docs/adr/0001-log-entries-as-reserved-log-files.md`
in the plugin.

This part makes that move for a bundle that predates it. The gate and `okf-log.sh add`
(which `/okf-write` uses) refuse an unmigrated bundle and name this skill. A bundle made
by `/okf-setup` starts split and does not need it.

## Step 1.1 — Split

```bash
sh "${PLUGIN_ROOT}/scripts/okf-log.sh" split knowledge
```

What it does:

- appends a short pointer to `log/` and, as the last line, the marker
  `<!-- okf-log frozen <YYYY-MM-DD> sha256:<hex> -->`. The hash covers every byte above
  the marker line, with line endings normalized to LF, so a CRLF checkout of the same
  history still passes;
- keeps every byte already in `log.md` as it was;
- creates `<bundle>/log/`.

Read its output:

- `froze …` — done. Go to Step 1.2.
- `… is already frozen …; nothing to do` — the bundle was split before. Nothing changed.
  If it also warns that the history changed since it was frozen, someone edited old
  history. Ask the user whether that edit is deliberate. Only if it is, re-hash it:
  `sh "${PLUGIN_ROOT}/scripts/okf-log.sh" split --refreeze knowledge`. Otherwise restore
  `log.md` from git and move the new lines into a log entry.
- `text below the marker …` (exit 1) — a line was added after the split. Move it into the
  branch's log entry (`okf-log.sh add knowledge '<line>'`), delete it from `log.md`, and
  run the split again.

## Step 1.2 — Check

```bash
git diff -- knowledge/log.md
```

The diff must only ADD lines at the end of the file. A changed or removed line means
something else wrote the file: stop and tell the user.

Then run the gate through `okf-drift:okf-runtime` (gate mode). It must not report
`log.md: not frozen`. `drift.lock found` is Part 2's job. Other findings are not this
skill's job. Report them, but do not fix them here.

## Step 1.3 — Hand back

Tell the user:

- the bundle is split; `log/` holds no entry yet, so git does not show the empty folder
  (the first `okf-log.sh add` creates the branch's entry);
- from now on every new line goes into the branch's log entry through `okf-log.sh add`
  (`/okf-write` does this). Nothing writes the root `log.md` again;
- `merge=union` on `log.md` in `.gitattributes`, and any workflow that union-merges the
  log, are no longer needed. This skill does not edit them; the user removes them;
- commit `log.md` together with the pin bump and the rest of the upgrade.

# Part 2 — Drop drift

okf-drift v0.15.0 removed the drift tool: no `drift.lock`, no bindings, no re-stamp, no
drift step in the gate. The code is the source of truth; the bundle holds what the code
does not say, and a concept found wrong while relied on is fixed as an ordinary edit
(read-repair). See `docs/adr/0002-drop-drift-code-is-the-source-of-truth.md` in the
plugin. A gate pinned to v0.15.0 or newer fails while `drift.lock` exists, and names this
skill.

There is no script for this part: you make each change, and you show the user every
change to `CLAUDE.md` and to the workflow before writing it. `okf validate --drift` is
okf's own check for dead `code_refs` paths, not the removed tool: leave it wherever it
appears.

## Step 2.1 — Delete the lock

```bash
git rm drift.lock
```

When it is untracked, `rm drift.lock`. Already gone: nothing to do. Delete nothing else
in the bundle: `code_refs` stay, as the place each concept says to look.

## Step 2.2 — Update the integration and the pin

Three files carry the old integration: the `## Knowledge Bundle` and `## Work Loop`
sections of `CLAUDE.md`, the CI workflow `.github/workflows/knowledge.yml` (or
`knowledge.yaml`), and the pin `.okf-drift-version`. The plugin's integration helper
rewrites all three when the sections and the workflow match a known official version.
Preview it first:

```bash
python3 "$PLUGIN_ROOT/scripts/okf-integrate.py" --repo-root "$REPO_ROOT" --tag v0.15.0 --dry-run
```

`REPO_ROOT` is the absolute target repository root. Use the newest released tag at or
above v0.15.0 in place of `v0.15.0`. The preview prints a `write …` line per file it
would change and writes nothing. When it exits 0, show the user, before anything is
written, what each named file becomes: for `CLAUDE.md`, a diff of its `Knowledge Bundle`
and `Work Loop` sections against the template's
(`$PLUGIN_ROOT/skills/okf-setup/templates/CLAUDE-knowledge-section.md`); for the workflow,
`diff -u` against `$PLUGIN_ROOT/skills/okf-setup/templates/knowledge.yml`; for the pin,
the new tag. Wait for an OK, then run the same command without `--dry-run`.

When it refuses with `customized … section; merge explicitly` or `customized workflow;
merge explicitly`, it wrote nothing, the pin included. The repository changed an official
text, and the merge is yours:

1. Read the new texts: `$PLUGIN_ROOT/skills/okf-setup/templates/CLAUDE-knowledge-section.md`
   and `$PLUGIN_ROOT/skills/okf-setup/templates/knowledge.yml`.
2. In `CLAUDE.md`, replace the `Knowledge Bundle` and `Work Loop` sections with the
   template's, then put back each of the repository's own additions that does not depend
   on drift. Leave the `Navigation` section as it is.
3. In the workflow, remove the drift install, its version pin and the drift version
   check, and any step that runs drift (`drift check`, `drift link`, a bootstrap, a lock
   merge). Keep the repository's own steps, triggers and names. Compare with the template
   for the gate step itself.
4. Show the user the full diff of both files and wait for an OK before writing.
5. Re-pin alone: `sh "$PLUGIN_ROOT/scripts/okf-pin.sh" v0.15.0 "$REPO_ROOT"` (same tag
   rule as above). Never write `.okf-drift-version` by hand.

Elsewhere in the repository — another workflow, a pre-commit hook, `.gitattributes`, a
contributor doc — search for `drift` and list each hit for the user. Change only what
they confirm.

## Step 2.3 — Check

Run the gate through `okf-drift:okf-runtime` (gate mode). It must not report `drift.lock
found`, and it must run the pinned v0.15.0 gate, not the old one. Other findings are not
this part's job. Report them.

## Step 2.4 — Review the concepts (on request)

Ask the user whether to review the existing concepts now. It is optional and can be done
later; it reads every concept, so say how many there are.

The writing rule, which `/okf-write` now applies to every concept: a concept never
restates what the code already says — signatures, defaults, step lists, numbers, field
lists. It names where the fact lives (`code_refs`, and the path or symbol in the prose)
and holds what the code does not say: why, invariants, traps met, conventions, how to
behave. A fact that must be quoted from the code is a dated observation ("on
2026-09-28, …").

For each concept, read it with the code it names and propose one of:

- **keep**: it already follows the rule;
- **cut**: remove the sentences that restate the code, when the rest still stands;
- **rewrite**: restate it as where to look plus why, keeping every invariant, trap and
  reason, and the `description:` in step;
- **correct**: the code contradicts it; the code wins.

Show the proposal per concept, before writing anything. Apply only what the user accepts,
then follow `/okf-write`: one line per change in the branch's log entry
(`okf-log.sh add`), `okf-tidy.sh`, and the gate.

## Step 2.5 — Hand back

Tell the user what changed: the lock deleted, each file the helper or the hand merge
wrote, the new pin, the drift references found elsewhere and what was done with each,
and the concepts reviewed. Commit these together as the drift removal. Running this part
again on a repository with no `drift.lock`, current integration and a v0.15.0 pin
changes nothing.
