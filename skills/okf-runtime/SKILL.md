---
name: okf-runtime
description: |
  Run the pinned OKF gate for a repository's Verify/Grow loop, or recall knowledge
  with the mandatory drift join during Context. Model-invocable, read-only with
  respect to the consumer integration, bundle and bindings. Use when project
  instructions request the OKF gate or freshness-checked knowledge recall.
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
**v0.7.0**. An older/missing/malformed pin is a blocker, never an implicit upgrade.
`OKF_DRIFT_ROOT` is a visible development-only bypass; use it only when explicitly
working on the runtime, never as a recovery from verification failure.

Report the command's status and diagnostics. A failing gate is not green; withheld
recall hits are not weaker facts. Read their bound code instead of quoting them.
If recall fails, stop: no bare-search fallback. The gate may warn when drift has
not been adopted; report that degraded result rather than claiming drift passed.

The gate warns, and does not fail, for a concept with no tracked target; a consumer
that wants a subset to be mandatory sets `OKF_REQUIRE_TRACKING=<glob>[,<glob>...]`
(shell globs over the concept path relative to the bundle, e.g. `architecture/*`),
which turns coverage into a FAIL for the paths it matches and names the glob.
On a repository that has ADOPTED drift — `.okf-drift-version` and `drift.lock` both
present — a missing `drift` binary, or one whose version disagrees with the pin in
`.github/workflows/knowledge.yml` (or that file renamed `.yaml`), is a FAIL rather
than a warning: a green gate has to mean the detector ran. Never work around that by uninstalling the pin.

## Scope and unavailable plugin

This skill only runs gate/recall. It never pins, installs/converts integration,
scaffolds, edits knowledge, bootstraps drift or re-stamps bindings. The four
existing setup/migrate/read/write skills retain their manual triggers.

If this skill or its launcher is unavailable, report the missing plugin explicitly.
The standalone alternative is the `pinned runtime gate` shell block in the
consumer's recognized `.github/workflows/knowledge.yml`, documented under
**Standalone bootstrap** in okf-drift's README. It verifies the pinned launcher
before running it. For recall, change only its final runtime name/arguments as
shown there. No fetch from main, unverified download or saved local-cache path.
