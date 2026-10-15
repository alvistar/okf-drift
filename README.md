# okf-drift

A Claude Code plugin: project memory as an [OKF v0.2](https://github.com/okf-memory/okf-agent-memory)
bundle, kept honest by the code it describes.

A knowledge bundle's failure mode is not being empty. It is being confidently wrong — a
concept written six weeks ago, indexed, well-linked, top of the search results, and
describing a function that was rewritten last Tuesday. This plugin's answer is that the
**code is the source of truth**: the bundle holds what the code does not say, and a
concept that contradicts the code is fixed by whoever finds it. The plugin is the layout,
the plumbing around `okf`, and the gate for everything `okf validate` was measured not to
check. (Its name is historical: until 0.15.0 it bound concepts to code with
[`drift`](https://drift.fp.dev); `docs/adr/0002-drop-drift-code-is-the-source-of-truth.md`
records why that went.)

Every claim about `okf` in these skills was measured against a running binary — okf
v0.6.0 on 2026-10-08 — not read from documentation. Where a measurement contradicted the
docs, the measurement is what is written down, and
`skills/okf-setup/references/okf-quirks.md` says which. Re-measure after an upgrade before
trusting a green validation.

## Skills

| Skill | What it does |
|---|---|
| `/okf-setup` | Lays the bundle down in a repo that has none: a fixed layout that validates `--strict` from the first commit, the population and resync prompts, the `CLAUDE.md` sections, the gate and the CI job. |
| `/okf-write` | Records into the bundle: a decision, a playbook, a surgical concept edit, the state snapshot and its evidence, each to the writing rule; logs the change in the branch's log entry; keeps index rows and `last_updated` with `okf-tidy.sh`. |
| `/okf-migrate` | Brings an older bundle up to date: splits the log (freezes the root `log.md`, creates `log/`) and drops drift (deletes `drift.lock`, updates the CI workflow and the `CLAUDE.md` sections, and on request reviews the concepts against the writing rule). Idempotent, works on both profiles, commits nothing. |
| `/okf-read` | Recalls from it: `okf search` with each hit's `status · review` and, when the code under its `code_refs` changed after the concept's last commit, a change hint. |

All four are **manual trigger only** — they run when you type the slash command.
The fifth, `okf-runtime`, is model-invocable for the Work Loop: pinned gate and recall
only, never setup, pin upgrades or bundle writes.

## How the bundle stays true

**The writing rule.** A concept holds what the code does not say: why, invariants, traps,
conventions, how to behave, and where to look (`code_refs`). It never restates what the
code says — signatures, defaults, step lists, numbers, field lists — because that copy is
what goes wrong when the code moves. A fact that must be quoted from the code is a dated
observation. The population and resync prompts and `/okf-write` all apply it.

**The change hint.** Recall prints, under a hit, `code changed since this concept: N
commit(s) on <paths> (last <sha> <date> "<subject>")` when commits touched the concept's
`code_refs` after the concept's last commit. It is counted from the commit, not from
`last_updated`, which cannot order two commits of one day. It is a place to look, never a
verdict and never an exit code.

**Read-repair.** When a concept an agent relies on contradicts the code, the code wins:
the agent fixes the concept with an ordinary `/okf-write` edit if the session writes the
repository, and says so in its answer otherwise. No field records the check, and the
branch's log entry records only the edit.

**The gate** (`scripts/okf-check.sh`) is the six steps `okf validate --strict --drift
--stale` does not do: its own warning list treated as fatal (a dead `code_refs` path is a
warning at exit 0), index rows that resolve and carry the concept's description verbatim
in both directions, the frontmatter okf carries but ignores, template residue, the
reserved files, and a leftover `drift.lock`, which fails the gate with `drift.lock found:
drift is no longer used, run /okf-migrate`. (`--drift` there is okf's own flag: a check
that every `code_refs` path still exists.) It runs in the Work Loop and as a blocking CI
job. It checks structure and review dates; whether a concept is still true is
read-repair's question.

## Log entries

Every PR used to write the bundle's `log.md`, so merging one PR conflicted every other open
PR (5 of 8 branch merges on the reference consumer, 2026-10-12; `merge=union` does not help,
because GitHub still reports the PR as conflicting). Since 0.14.0:

- **The root `knowledge/log.md` is the frozen log.** It keeps the history written before
  the split, a pointer to `log/`, and a marker line with the split date and the sha256 of
  every byte above it. Nothing writes it again. The gate fails any change to that history
  and names the log entry to use instead; `okf-log.sh split --refreeze` re-hashes it after
  a deliberate fix.
- **Each branch writes one log entry**, `knowledge/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`,
  with the same `## YYYY-MM-DD` headings, newest first. The one writer is
  `okf-log.sh add`: `/okf-write` and the scaffold both go through it. It
  reuses the entry this branch already added (compared against `origin/HEAD`, or
  `--base`), and refuses rather than guess on a detached HEAD, the default branch, more
  than one candidate or a shallow clone (`--slug` and `--entry` settle it). okf treats the
  nested `log.md` as reserved, so an entry is never a concept or a search hit; the gate
  checks its headings.
- **`/okf-migrate`** moves an existing bundle to this layout. New bundles from
  `/okf-setup` start split.

## Profiles

`code` (the default) is everything above. `wiki` is for a knowledge base that describes no
code — personal admin, a small company's facts and procedures: `okf-scaffold.sh --profile
wiki` writes `.okf-profile`, and the gate then stops asking for a project snapshot and
`code_refs`, while every structural check stays. See `/okf-setup`, *Profile:
wiki*.

## Install

From the marketplace, if you have `alvistar/alvistar-skills` added:

```
/plugin install okf-drift@alvistar-skills
```

Or point Claude Code straight at this repository:

```
claude plugin marketplace add alvistar/okf-drift
```

Runtime dependency, installed separately and pinned by the CI template to the version
everything here was measured against:

```sh
go install github.com/okf-memory/okf-agent-memory/cmd/okf@v0.6.0   # okf v0.6.0, needs Go 1.26+
```

## What a consumer repository carries

The repository carries **data and integration, no OKF scripts**:

```
.okf-drift-version                tag and SHA-256 digests, from the release asset
knowledge/                       the bundle
CLAUDE.md                        managed Knowledge Bundle / Work Loop instructions
.github/workflows/knowledge.yml   standalone verified bootstrap, PR + push to main
```

A `wiki` consumer (see **Profiles**) carries `knowledge/`, `.okf-profile` and, to run the
gate through `okf-runtime`, a `.okf-drift-version` pinned at v0.15.0 or later (v0.11.0 is
the first that knows the wiki profile, v0.14.0 the first with the split log the scaffold
writes, v0.15.0 the first without drift).

Local sessions invoke `okf-drift:okf-runtime`. It resolves the launcher from the
absolute skill directory supplied by the host, two levels up, and calls:

```sh
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-check.sh knowledge
sh "$PLUGIN_ROOT/scripts/okf-shim.sh" --repo-root "$REPO_ROOT" okf-recall.sh "<terms>" knowledge
```

`PLUGIN_ROOT` and `REPO_ROOT` above are explicitly resolved absolute paths, not
assumed environment variables. No versioned cache path is saved in project files.
Updating the installed plugin does **not** update the project's pinned runtime.

The gate reports a concept with empty `code_refs` as a warning: `okf search --for-path`
can never return it, and recall never gives it a change hint. The list prints at most 8
names and a count; `OKF_VERBOSE=1` lists them all.

okf fails a concept on its `stale_after` day, so the gate warns about every concept due
within the next 30 days (`OKF_REVIEW_WINDOW_DAYS`; a value that is not a whole number
exits 2), and recall labels it `review due <date>`. Both judge the date in UTC, as okf
does. An impossible `stale_after` (`2026-13-01`) fails the gate, and a bundle root that
resolves outside its parent directory (a `knowledge -> /elsewhere` symlink) fails it
before okf runs.

### Compatibility and the lockfile

**First compatible release: v0.7.0.**
Wrapper-free adoption requires that release or a later compatible one and its
published `SHA256SUMS` asset. The `CLAUDE.md` sections and CI workflow installed today
describe the v0.15.0 gate and recall: pin v0.15.0 or later. Tests use fixture releases so future unpublished
source remains testable.

Line 1 of `.okf-drift-version` is `vMAJOR.MINOR.PATCH`; remaining lines are
`<64 lowercase hex digits>  <script basename>`. Generate it with the plugin's
`okf-pin.sh`, which downloads the release's `SHA256SUMS` asset via gh or curl:

```sh
sh "$PLUGIN_ROOT/scripts/okf-pin.sh" v0.7.0 "$REPO_ROOT"
```

This is an explicit upgrade, not a startup action. Pin generation rejects malformed
or duplicate hashes and requires shim, gate and recall hashes.
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
workflow retains PR/main-only triggers, the pinned okf install and its explicit
version/presence preflight. Digest verification covers plugin scripts, not okf itself,
which `go install` fetches at its pinned tag.

### Integration conversion

The plugin-only `scripts/okf-integrate.py` is shared by setup and migration. It needs
Python 3.11+ and no third-party packages. For a fresh integration or conversion of existing wrappers:

```sh
python3 "$PLUGIN_ROOT/scripts/okf-integrate.py" \
  --repo-root "$REPO_ROOT" --tag v0.15.0 --dry-run
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
- `code_refs`, including directory/glob references, are checked before deletion. A
  candidate a concept governs blocks conversion; the bundle is not edited.
- `knowledge/` is read only and remains byte-for-byte unchanged; a leftover
  `drift.lock` is `/okf-migrate`'s to delete, not the helper's.
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
scripts/okf-recall.sh               search with status · review per hit and the change hint
scripts/okf-log.sh                  the one writer of a branch's log entry (add); split freezes the root log.md
scripts/okf-tidy.sh                 index rows and last_updated, the bookkeeping that needs no judgement
scripts/okf-shim.sh                 sole root-aware, content-pinned launcher (plugin/CI/legacy)
scripts/okf-integrate.py            conservative plugin-only integration install/conversion
scripts/okf-launcher-selftest.py    offline fixture-release launcher/CI/conversion contracts
scripts/okf-pin.sh                  writes a consumer repo's .okf-drift-version from a release's SHA256SUMS
scripts/okf-shim-selftest.sh        the shim's regression test, run by CI against a real tag
skills/okf-{setup,migrate,write,read,runtime}/SKILL.md
skills/okf-setup/templates/         the bundle, the CLAUDE.md sections, the CI workflow
skills/okf-setup/templates-wiki/    the wiki-profile bundle (okf-scaffold.sh --profile wiki)
skills/okf-setup/references/        okf-quirks.md and the population/resync prompts
```

## Versioning

Three-segment semver. `VERSION` at the root is the single source of truth;
`.claude-plugin/plugin.json` must agree with it, and `.github/workflows/release.yml`
fails a tag that disagrees with either. Releases are tag-driven: push `vX.Y.Z` and the
workflow publishes the matching `CHANGELOG.md` section.
