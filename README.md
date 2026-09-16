# okf-drift

A Claude Code plugin: project memory as an [OKF v0.2](https://github.com/okf-memory/okf-agent-memory)
bundle, with content-level drift on top.

A knowledge bundle's failure mode is not being empty. It is being confidently wrong — a
concept written six weeks ago, indexed, well-linked, top of the search results, and
describing a function that was rewritten last Tuesday. `okf` can tell you a governed path
**vanished**; it cannot tell you the path **changed**, which is how a concept actually goes
wrong. [`drift`](https://drift.fp.dev) closes that with a content signature per
(concept, path) pair. This plugin is the layout, the plumbing that joins the two tools, and
the gate for everything `okf validate` was measured not to check.

Every claim in these skills was measured against a running binary — okf v0.3.0, drift
v0.10.1, mex 0.8.2, on 2026-09-16 — not read from documentation. Where a measurement
contradicted the docs, the measurement is what is written down, and
`skills/okf-setup/references/okf-quirks.md` says which. Re-measure after an upgrade before
trusting a green validation.

## The four skills

| Skill | What it does |
|---|---|
| `/okf-setup` | Lays the bundle down in a repo that has none: a fixed layout that validates `--strict` from the first commit, the population and resync prompts, the `CLAUDE.md` sections, the gate, the drift bootstrap, and the CI job. |
| `/okf-migrate` | Builds the same bundle from an existing [mex](https://github.com/mex-memory/mex) scaffold, resolving every `grounds_to` and inline `mex://` anchor to a path **while the graph still exists**. |
| `/okf-write` | Records into the bundle: a decision, a playbook, a surgical concept edit, the state snapshot; binds every new `code_refs` path; re-stamps a reviewed binding — never silently. |
| `/okf-read` | Recalls from it: `okf search` joined with `drift check`, withholding any concept whose bound code moved after it was written, with the commit to blame. |

All four are **manual trigger only** — they run when you type the slash command.

## The two halves that make it work

**The gate** (`scripts/okf-check.sh`) is the six steps `okf validate --strict --drift --stale`
does not do: its own warning list treated as fatal (a dead `code_refs` path is a warning at
exit 0), index rows that resolve and carry the concept's description verbatim in both
directions, the frontmatter okf carries but ignores, template residue, the reserved files,
and the drift join. It runs in the Work Loop and as a blocking CI job, because the PR that
makes a concept stale is almost always one that touches only code.

**The re-stamp rule** (`/okf-write` step 3): the agent may re-stamp a drift binding, and may
never re-stamp one silently. `drift link … --doc-is-still-accurate` is a claim that a
human-readable statement survived a code change, and it leaves no trace anywhere except a
changed hex signature — so it is always paired with a dated line in `knowledge/log.md`
naming what was checked against what. Without that line the plugin degrades into a tool that
silences its own alarm.

## Install

From the marketplace, if you have `alvistar/alvistar-skills` added:

```
/plugin install okf-drift@alvistar-skills
```

Or point Claude Code straight at this repository:

```
claude plugin marketplace add alvistar/okf-drift
```

Runtime dependencies, installed separately and pinned by the CI template to the versions
everything here was measured against:

```sh
go install github.com/okf-memory/okf-agent-memory/cmd/okf@v0.3.0   # okf v0.3.0
curl -fsSL https://drift.fp.dev/install.sh | sh -s -- --version v0.10.1
```

## What a consumer repository carries

CI, the Work Loop and `/okf-read` all call the gate and the recall script from the
repository, so neither may depend on this plugin being installed. Since 0.5.0 that is a
**pinned fetch**, not a copy:

```
.okf-drift-version        one line: v0.5.0
scripts/okf-shim.sh       resolves and caches a script at that tag
scripts/okf-check.sh      two lines: exec "$(dirname "$0")/okf-shim.sh" okf-check.sh "$@"
scripts/okf-recall.sh     two lines, likewise
drift.lock                shared state, exactly like the bundle
.github/workflows/knowledge.yml   runs scripts/okf-check.sh knowledge on every PR and on push to main
```

A vendored copy of the gate drifts from the plugin silently and nothing in either
repository can see that it has. A pinned one moves only when `.okf-drift-version` moves,
and that is a one-line diff a reviewer can read. Upgrading a consumer repo is editing that
line.

The shim looks for `$OKF_DRIFT_ROOT/scripts/<name>` first, so a local checkout of this
repository overrides the pin while the plugin is being developed. Otherwise it fetches once
into `${XDG_CACHE_HOME:-$HOME/.cache}/okf-drift/<tag>/` and re-uses it. A download that
404s, arrives empty, or does not start with `#!` is fatal — running nothing must never look
like a clean gate.

## Repository layout

```
.claude-plugin/plugin.json          the plugin manifest; its version tracks VERSION
scripts/okf-scaffold.sh             the fixed bundle, laid down and validated
scripts/okf-check.sh                the gate, six steps
scripts/okf-recall.sh               search joined with drift; withholds what it cannot vouch for
scripts/okf-drift-bootstrap.sh      one drift link per code_refs entry
scripts/okf-migrate.py              inventory / resolve / convert, for a mex scaffold
scripts/okf-shim.sh                 what a consumer repo installs instead of a copy of the above
skills/okf-{setup,migrate,write,read}/SKILL.md
skills/okf-setup/templates/         the bundle, the CLAUDE.md sections, the CI workflow
skills/okf-setup/references/        okf-quirks.md and the population/resync prompts
```

## Versioning

Three-segment semver. `VERSION` at the root is the single source of truth;
`.claude-plugin/plugin.json` must agree with it, and `.github/workflows/release.yml`
fails a tag that disagrees with either. Releases are tag-driven: push `vX.Y.Z` and the
workflow publishes the matching `CHANGELOG.md` section.
