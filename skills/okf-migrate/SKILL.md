---
name: okf-migrate
disable-model-invocation: true
description: |
  Move an existing OKF bundle to the split log layout: freeze the root `log.md` (the
  history stays, a marker hashes it) and create `log/`, where each branch writes its own
  log entry from then on. Runs `okf-log.sh split`; writes nothing else in the bundle.
  Works on both profiles (code and wiki). Safe to run twice: on a bundle that is already
  split it changes nothing.

  MANUAL TRIGGER ONLY: invoke only when the user types /okf-migrate.

  Trigger on: "/okf-migrate", "split the log", "freeze log.md", "migrate the bundle to
  log entries", "the gate says run /okf-migrate".
---

# /okf-migrate — freeze `log.md`, write log entries from now on

Every PR used to write the bundle's root `log.md`, so merging one PR conflicted every
other open PR. Now each branch writes its own **log entry**,
`<bundle>/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`, and the root `log.md` becomes the
**frozen log**: it keeps the history written before the split, points to `log/`, and
ends with a marker that carries the split date and the sha256 of the history. The gate
fails on any change to that history. See `docs/adr/0001-log-entries-as-reserved-log-files.md`
in the plugin.

This skill makes that move for a bundle that predates it. The gate, `okf-log.sh add`
(which `/okf-write` uses) and `okf-restamp.sh` all refuse an unmigrated bundle and name
this skill. A bundle made by `/okf-setup` starts split and does not need it.

Set `PLUGIN_ROOT` to two directories above this skill's absolute base directory supplied
by the host. **Every command runs from the target repository root.** Nothing here
commits, pushes or opens a PR.

## Step 1 — Find the bundle

The bundle is `knowledge/` unless the repository keeps it elsewhere (the CLAUDE.md
knowledge section names it). It must hold a root `log.md`. If it does not, stop: the
bundle is incomplete, and `/okf-setup` is the job, not this one.

## Step 2 — Split

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

- `froze …` — done. Go to Step 3.
- `… is already frozen …; nothing to do` — the bundle was split before. Nothing changed.
  If it also warns that the history changed since it was frozen, someone edited old
  history. Ask the user whether that edit is deliberate. Only if it is, re-hash it:
  `sh "${PLUGIN_ROOT}/scripts/okf-log.sh" split --refreeze knowledge`. Otherwise restore
  `log.md` from git and move the new lines into a log entry.
- `text below the marker …` (exit 1) — a line was added after the split. Move it into the
  branch's log entry (`okf-log.sh add knowledge '<line>'`), delete it from `log.md`, and
  run the split again.

## Step 3 — Check

```bash
git diff -- knowledge/log.md
```

The diff must only ADD lines at the end of the file. A changed or removed line means
something else wrote the file: stop and tell the user.

Then run the gate through `okf-drift:okf-runtime` (gate mode). It must not report
`log.md: not frozen`. Other findings are not this skill's job. Report them, but do not
fix them here.

## Step 4 — Hand back

Tell the user:

- the bundle is split; `log/` holds no entry yet, so git does not show the empty folder
  (the first `okf-log.sh add` creates the branch's entry);
- from now on every new line goes into the branch's log entry through `okf-log.sh add`
  (`/okf-write` and `okf-restamp.sh` do this). Nothing writes the root `log.md` again;
- `merge=union` on `log.md` in `.gitattributes`, and any workflow that union-merges the
  log, are no longer needed. This skill does not edit them; the user removes them;
- commit `log.md` together with the pin bump and the rest of the upgrade.
