---
name: okf-runtime
description: |
  Run the pinned OKF gate for a repository's Verify/Grow loop, or recall knowledge
  with its change hint during Context. Model-invocable, read-only with respect to the
  consumer integration and bundle. Use when project instructions request the OKF gate
  or knowledge recall.
---

# Pinned gate and recall

1. Respect the project's required read order. Identify the consumer repository,
   using its explicit supplied root or `git rev-parse --show-toplevel` from its cwd.
2. Resolve the plugin from **this skill's absolute base directory supplied by the
   host when it loaded the skill**, two directories up. Substitute that actual path
   for `SKILL_DIR` below; never guess a cache version or assume `CLAUDE_PLUGIN_ROOT`
   exists in the shell. `REPO_ROOT` is the consumer, not the plugin checkout.
3. Choose gate (default) or recall. Execute the relevant command with quoted paths
   and arguments. This gate example is directly executable after substitution:

```sh
set -eu
SKILL_DIR='<host-supplied absolute skill directory>'
REPO_ROOT='<absolute consumer root>'
PLUGIN_ROOT=$(CDPATH= cd -- "$SKILL_DIR/../.." && pwd)
[ -f "$PLUGIN_ROOT/scripts/okf-shim.sh" ] || { printf '%s\n' 'okf-runtime: plugin launcher missing; use the documented pinned CI bootstrap' >&2; exit 2; }
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-check.sh knowledge
```

For recall, replace only the last line with:

```sh
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-recall.sh "<terms>" knowledge
```

The launcher enters the consumer root and selects runtime bytes solely through its
`.okf-drift-version`, not the installed plugin's version. Minimum compatible pin:
**v0.7.0** (**v0.11.0** for a bundle declared `wiki` in `.okf-profile`). An older/missing/malformed pin is a blocker, never an implicit upgrade.
`OKF_DRIFT_ROOT` is a visible development-only bypass; use it only when explicitly
working on the runtime, never as a recovery from verification failure.

Report the command's status and diagnostics. A failing gate is not green. If recall
exits 2, stop: no bare-search fallback.

A recall hit may carry a **change hint**, `code changed since this concept: N commit(s)
on <paths> (last …)`: commits touched its `code_refs` after the concept's last commit. It
is informative only, never an exit code, and does not make the concept wrong. The code is
the source of truth: before relying on a concept's content, read the code it points at,
starting where a hint names. When a concept you rely on contradicts the code, the code
wins (**read-repair**): if the session already writes the repository, fix the concept
with an ordinary `/okf-write` edit; otherwise say so in the answer. A concept merely
listed in the results owes nothing. A bundle declared `wiki` in `.okf-profile` carries no
`code_refs`, so its hits carry no hint.

The gate fails while a `drift.lock` sits at the repository root (`drift.lock found:
drift is no longer used, run /okf-migrate`): drift was removed in v0.15.0
(`docs/adr/0002-drop-drift-code-is-the-source-of-truth.md`). Report it and point to
`/okf-migrate`; this skill does not delete the lock. `okf validate --drift`, which the
gate runs, is okf's own check for dead `code_refs` paths and is unrelated to the removed
tool. A concept with empty `code_refs` is one grouped `warn` line, never a FAIL.

## When to run the gate

The gate reads the whole bundle every time. Run it where its answer changes what you
do next, not after every edit:

- **Once as a baseline**, before touching anything, and keep the output: an alarm
  present then is inherited, not yours.
- **Once before pushing.** CI runs the same gate on every PR and on push to `main`,
  and only the branch head merges, so a green gate on an intermediate commit buys
  nothing a green gate before the push does not.
- **On a FAIL, fix every finding it named, then re-run once.** Re-running after each
  single fix prints the same report again. The reference consumer's heaviest sessions
  ran the gate 57–60 times, 13–17 of them FAILs inside such a loop.

Mid-work, to learn which concepts govern a path you are about to change, ask for that
path alone (`okf search --for-path <path>`); the gate answers for the bundle, not the
path.

## Scope and unavailable plugin

This skill only runs gate/recall. It never pins, installs/converts integration,
scaffolds or edits knowledge — `okf-tidy.sh` and `okf-log.sh` belong to `/okf-write`,
deleting `drift.lock` to `/okf-migrate`. `/okf-write` is model-invocable: load it for
the Grow step and for read-repair. setup, migrate and read keep their manual triggers.

If this skill or its launcher is unavailable, report the missing plugin explicitly.
The standalone alternative is the `pinned runtime gate` shell block in the
consumer's recognized `.github/workflows/knowledge.yml`, documented under
**Standalone bootstrap** in okf-drift's README. It verifies the pinned launcher
before running it. For recall, change only its final runtime name/arguments as
shown there. No fetch from main, unverified download or saved local-cache path.
