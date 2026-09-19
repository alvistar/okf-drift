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

## Skills

| Skill | What it does |
|---|---|
| `/okf-setup` | Lays the bundle down in a repo that has none: a fixed layout that validates `--strict` from the first commit, the population and resync prompts, the `CLAUDE.md` sections, the gate, the drift bootstrap, and the CI job. |
| `/okf-migrate` | Builds the same bundle from an existing [mex](https://github.com/mex-memory/mex) scaffold, resolving every `grounds_to` and inline `mex://` anchor to a path **while the graph still exists**. |
| `/okf-write` | Records into the bundle: a decision, a playbook, a surgical concept edit, the state snapshot; binds every new **code** `code_refs` path; non-code paths take no *automatic* binding, so a claim whose truth lives in one is hand-linked or restated as a dated observation; re-stamps a reviewed binding — never silently. |
| `/okf-read` | Recalls from it: `okf search` joined with `drift check`, withholding any concept whose bound code moved after it was written, with the commit to blame. |

All four are **manual trigger only** — they run when you type the slash command.
The fifth, `okf-runtime`, is model-invocable for the Work Loop: pinned gate and
freshness-checked recall only, never setup, pin upgrades or binding writes.

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

The repository carries **data and integration, no OKF scripts**:

```
.okf-drift-version                tag and SHA-256 digests, from the release asset
knowledge/                       the bundle
drift.lock                      shared bindings (at repository root)
CLAUDE.md                        managed Knowledge Bundle / Work Loop instructions
.github/workflows/knowledge.yml   standalone verified bootstrap, PR + push to main
```

Local sessions invoke `okf-drift:okf-runtime`. It resolves the launcher from the
absolute skill directory supplied by the host, two levels up, and calls:

```sh
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-check.sh knowledge
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-recall.sh "<terms>" knowledge
```

`PLUGIN_ROOT` and `REPO_ROOT` above are explicitly resolved absolute paths, not
assumed environment variables. No versioned cache path is saved in project files.
Updating the installed plugin does **not** update the project's pinned runtime.

### Compatibility and the lockfile

**First compatible release: v0.7.0.**
Wrapper-free adoption requires that release or a later compatible one and its
published `SHA256SUMS` asset. Tests use fixture releases so future unpublished
source remains testable.

Line 1 of `.okf-drift-version` is `vMAJOR.MINOR.PATCH`; remaining lines are
`<64 lowercase hex digits>  <script basename>`. Generate it with the plugin's
`okf-pin.sh`, which downloads the release's `SHA256SUMS` asset via gh or curl:

```sh
sh "$PLUGIN_ROOT/scripts/okf-pin.sh" v0.7.0 "$REPO_ROOT"
```

This is an explicit upgrade, not a startup action. Pin generation rejects malformed
or duplicate hashes and requires shim, gate, recall and drift-bootstrap hashes.
It stages a validated file before replacing the pin. Never hand-copy digests.
Older pins remain usable through their legacy wrappers, but the root-aware
integration diagnoses them and requires an explicit upgrade; it never runs the
installed plugin runtime as a fallback.

### Launcher resolution and cache

One launcher, `scripts/okf-shim.sh`, with this consumer-root precedence:

1. `--repo-root <path>`;
2. legacy `<consumer>/scripts/okf-shim.sh` location, only if its parent carries a pin;
3. the Git root of the calling cwd (including subdirectories/worktrees).

The runtime always executes with cwd at the chosen root. Arguments and status are
forwarded. An unrelated cwd needs the explicit flag. Paths with spaces are supported.

`OKF_DRIFT_ROOT` is a **visible development-only bypass** pointing at a local plugin
checkout. It bypasses content verification intentionally; an invalid override is an
error. CI unsets it. Otherwise scripts come only from the pinned tag, downloaded to
unique temporary files and atomically cached beneath
`${XDG_CACHE_HOME:-$HOME/.cache}/okf-drift/<tag>/`. Cold downloads and warm cache
entries are both verified against the project's digest on every run. Missing,
empty, damaged, unpinned or unfetchable scripts fail before execution. Independent
worktrees can share the cache without sharing partial downloads.

### Standalone bootstrap

Without an installed plugin, use the **`pinned runtime gate` shell block in
`skills/okf-setup/templates/knowledge.yml`**, installed verbatim at
`.github/workflows/knowledge.yml`. Run that block from the consumer checkout; it
is the single authoritative bootstrap recipe. It needs Git, sh, curl and a SHA-256
tool. It downloads the pinned shim to a temporary directory, verifies the shim's
pinned digest **before execution**, then calls it with the explicit checkout root.
No plugin installation, local machine path, consumer script or download from main.
For standalone recall, change only the last line to:

```sh
sh "$tmp/okf-shim.sh" --repo-root "$root" okf-recall.sh "<terms>" knowledge
```

Keep the preceding validation and cleanup steps unchanged. Missing plugin means an
explicit diagnostic and this bootstrap, never an unverified search fallback. The
workflow retains full Git history, PR/main-only triggers, pinned okf/drift installs
and their explicit version/presence preflight. Digest verification covers plugin
scripts, not the separately downloaded drift installer.

### Integration conversion

The plugin-only `scripts/okf-integrate.py` is shared by setup and migration. It needs
Python 3.11+ and PyYAML. For a fresh integration or conversion of existing wrappers:

```sh
uvx --with pyyaml python3 "$PLUGIN_ROOT/scripts/okf-integrate.py" \
  --repo-root "$REPO_ROOT" --tag v0.7.0 --dry-run
# Review, then repeat without --dry-run. Omit --tag to preserve a compatible pin.
```

The dry run may fetch the release checksum asset into a temporary directory, but
writes nothing to the consumer. The apply preflights every candidate before writes:

- Legacy check/recall wrappers must match the exact generated two-line or commented
  three-line content. Shims must hash to an official v0.5.0–v0.6.2 source version,
  independently of the current pin. All other scripts are left alone.
- Only exact official legacy/current workflow content is replaced. Only exact
  template Knowledge Bundle / Work Loop sections are replaced; other sections and
  any existing Navigation (including required read order) remain byte-for-byte.
- Symlinks (including candidate parent directories), customized/unknown files,
  duplicate managed headings and invalid pins are blockers naming the file.
- `code_refs` and drift binding targets, including directory/glob references, are
  checked before deletion. Bound candidates block conversion; no re-stamp is made.
- `knowledge/` and `drift.lock` are read only and remain byte-for-byte unchanged.
  Historical operational references are reported, not rewritten; the new CLAUDE
  section makes them non-authoritative. No scaffold, population or log update runs.

Integration never touches `knowledge/project/conventions.md`, so a consumer that
already has a bundle does **not** get the Verify Checklist's first item — the knowledge
gate, at the baseline and again at the end — from an upgrade. Add it by hand, from
`skills/okf-setup/templates/knowledge/project/conventions.md`.

The second application makes no changes. Customized integrations need an explicit
human merge rather than force/overwrite flags. Candidates are rechecked before
apply to detect edits during downloads; apply uses atomic file replacement, **not a
multi-file transaction**. Avoid concurrent consumer edits; filesystem failure during
apply can leave a partial integration (rerun after correcting it, review the diff).

## Repository layout

```
.claude-plugin/plugin.json          the plugin manifest; its version tracks VERSION
scripts/okf-scaffold.sh             the fixed bundle, laid down and validated
scripts/okf-check.sh                the gate, six steps
scripts/okf-recall.sh               search joined with drift; withholds what it cannot vouch for
scripts/okf-drift-bootstrap.sh      one drift link per code `code_refs` entry; a hand binding on a non-code path is kept
scripts/okf-migrate.py              inventory / resolve / convert, for a mex scaffold
scripts/okf-shim.sh                 sole root-aware, content-pinned launcher (plugin/CI/legacy)
scripts/okf-integrate.py            conservative plugin-only integration install/conversion
scripts/okf-launcher-selftest.py    offline fixture-release launcher/CI/conversion contracts
scripts/okf-pin.sh                  writes a consumer repo's .okf-drift-version from a release's SHA256SUMS
scripts/okf-shim-selftest.sh        the shim's regression test, run by CI against a real tag
skills/okf-{setup,migrate,write,read,runtime}/SKILL.md
skills/okf-setup/templates/         the bundle, the CLAUDE.md sections, the CI workflow
skills/okf-setup/references/        okf-quirks.md and the population/resync prompts
```

## Versioning

Three-segment semver. `VERSION` at the root is the single source of truth;
`.claude-plugin/plugin.json` must agree with it, and `.github/workflows/release.yml`
fails a tag that disagrees with either. Releases are tag-driven: push `vX.Y.Z` and the
workflow publishes the matching `CHANGELOG.md` section.
