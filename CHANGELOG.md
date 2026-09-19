# Changelog

All notable changes to this project are documented here.

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with three segments.
`VERSION` at the repository root is the single source of truth; the release workflow
refuses a tag that disagrees with it or with `.claude-plugin/plugin.json`.

## [0.9.0] - 2026-09-19

### Fixed

- Integration recognises the outgoing v0.8.0–v0.8.2 `Work Loop` body digest
  (`dfacead5b7d2…`). A consumer's CLAUDE section is accepted when its body equals the
  current template verbatim **or** its digest is listed, so without this entry the
  template change below would refuse every official 0.8.2 consumer as "customized; merge
  explicitly". The `SECTIONS` comments now name the release range each digest covers, and
  a launcher case upgrades an official v0.8.2 `CLAUDE.md` with the current template.
- The integration helper no longer parses concept frontmatter with a strict YAML parser.
  okf accepts a `description:` whose value starts with an unquoted backtick — 12 concepts
  on the reference consumer carry one — and PyYAML raises `while scanning for the next
  token` on it, so `check_bindings` aborted with exit 2 before any CLAUDE.md logic and a
  bundle that passes the gate could not be integrated at all. The helper needs only
  `code_refs`, and now reads it with the same line rule the bootstrap and the gate use.
  Pre-existing since 0.7.0. The script no longer imports PyYAML, so the `uvx --with
  pyyaml` prefix is gone from every invocation in the README and `/okf-setup`.
- The gate's and recall's re-stamp target is the anchor's `identity`, not its `path`.
  drift's JSON carries the two separately and `drift link` takes the identity, so for a
  stale **symbol** anchor the printed repair used to create a second, whole-file binding
  and leave the symbol one exactly as stale as it was. Both are now shell-quoted with
  single quotes (a doc path can hold a space; an identity always holds a `#`), and the
  gate's "drifted from" line names the identity too.
- Blame is labelled as what it is. drift computes it with `git log -1 -- <file>`, so the
  commit it names is the **last commit to touch the file**, not necessarily the one that
  moved the ground under the concept — and once a file has drifted, any later unrelated
  commit to it takes that place and the real cause stops being mentioned anywhere. The
  gate and recall now print `last commit touching this file (not necessarily the cause):
  …`; `/okf-read` says to read the working tree and staged changes first and treat the
  commit as a lead; `okf-quirks.md` records both consequences. Recall's missing-subject
  fallback is aligned on the wording the gate and the skill already used,
  `(uncommitted change — nothing to blame yet)`.

### Added

- The Verify Checklist template carries a fixed first item: the knowledge gate ran with
  drift and is green, at the START of the work as a baseline and again at the end. A code
  change can stale a concept without touching `knowledge/`, so that directory is never
  "out of scope" for the gate. Measured: the gate's template-residue step still rejects
  the annotation beneath it and accepts the item.
- The CLAUDE template's Context step gains an impact check — `drift check --changed
  <path> --format json` for every path the task plans to touch, reported as candidates
  that may alarm together with every planned path no concept covers — and a baseline gate
  run whose output is kept, so an alarm already present is inherited rather than blamed on
  the change. Verify names the gate as the checklist's first item.
- `/okf-write` Step 2 gains "Where the anchor goes": anchor the claim's whole dependency
  set rather than the deepest call — the entry point when routing or defaults live there,
  every implementation the prose cites in every language, a whole file for an unsupported
  language — and a claim of absence, exclusivity or count is watched by no anchor at all,
  so it is removed, written as a dated measurement, or proved by a lane the concept names.
  `okf-quirks.md` gains the wrapper-with-policy consequence behind it.
- `/okf-read` and the CLAUDE template say when recall beats grep: recall answers what is
  WRITTEN about an area and what was observed about it; Grep and LSP find code.
- Recall gives every surviving hit **three independent signals** in place of the single
  word `fresh`: `N target(s) unchanged` or `no tracked target` (from drift's per-doc
  `anchors[]`), the concept's own `status` or `no status`, and `review current` /
  `review expired <date>` / `no review date` from `stale_after` against today. A paragraph
  after the hit list says what they do and do not mean, the header no longer says "fresh",
  and `/okf-read` carries the contract: no word in the output may be read as "verified" —
  `targets unchanged` is an observation about the anchors, not a statement about the prose,
  and it says nothing about claims the anchors do not cover. Measured on okf v0.3.0:
  `okf search --json` does **not** emit `status` even for a concept whose frontmatter
  carries it, so recall reads it from the file, by the same read that already yielded
  `last_updated`. The WITHHELD block still wins: a stale concept never reaches the hit
  list, deprecated or not.
- `OKF_REQUIRE_TRACKING=<glob>[,<glob>...]` makes the coverage warning FATAL for the
  concepts it matches — shell globs over the concept path relative to the bundle, `*`
  stopping at a `/` and `**` crossing one, and the failure names the glob. Unset, the
  default, leaves coverage a warning. Documented in `/okf-runtime` and the README.
- A green gate must mean the detector ran. On a repository that has **adopted** drift —
  `.okf-drift-version` and `drift.lock` both present at the bundle's parent — a missing
  `drift` binary is now a FAIL, and so is a `drift --version` that disagrees with the
  version pinned in `.github/workflows/knowledge.yml`. A repository that never adopted
  drift keeps exactly today's warning. Without this a worker without drift gets two green
  local runs and a red CI.
- `/okf-write` Step 0's table gains the superseded row — `status: deprecated`, a
  `Superseded by` link, and the successor written — a rule that existed only inside the
  decision-format paragraph.
- Plugin CI drives one scratch repo through the whole loop with the **real** pinned okf
  and drift: the three signals, a deprecated concept with an expired review date, a moved
  symbol anchor withheld, the gate's printed re-stamp command executed, and the lock
  holding exactly one binding for that doc afterwards. The stubbed selftests cannot prove
  parser compatibility; this step can.

### Changed

- Non-code paths take no *automatic* binding, but a hand `drift link` on one is a
  **deliberate** content anchor and stays valid: when a claim's truth lives in a workflow
  trigger, a Kconfig value or a fixture's shape, hand-link it and accept that a reformat
  will alarm, or restate the claim as a dated observation. The bootstrap now prints
  `held-non-code <doc> -> <target> (deliberate content anchor — kept)` with no `drift
  unlink` command beside it; that hint moved to its header comment. Setup, write, migrate,
  the CLAUDE template, the populate prompt, quirks and the README carry the same sentence.
- The resync prompt re-reads by hand every concept the gate reports with no tracked
  target: nothing checked it, and `git log -- <its code_refs>` is vacuous on empty
  `code_refs`, so neither existing check ever flags it.
- The README's integration notes record the one manual upgrade step: integration never
  writes `knowledge/project/conventions.md`, so an existing consumer adds the checklist
  item itself.
- The gate's 29 identical `code_refs is empty` warnings become **two grouped lines from
  two sources**, because they were two questions and one of them was answering for both:
  `N concept(s) with no tracked target (no drift anchor; nothing checks them)` computed
  from drift's report, and `N concept(s) with empty code_refs (okf search --for-path
  cannot find them)` computed from `code_refs` as before. A concept with non-code
  `code_refs` and no anchor is coverage-warned and not discoverability-warned; a concept
  with a hand anchor and empty `code_refs` is the reverse; both were misreported.
  `project/state.md` stays exempt from both, and when drift did not run nothing is said
  about coverage at all.

### Known gaps

- **Coverage is a warning by default.** A concept that nothing checks does not fail the
  gate unless a consumer opts in with `OKF_REQUIRE_TRACKING`. Making it fatal by default
  would fail every bundle that has not finished binding — 29 concepts on the bundle this
  release was measured against. Coverage is also computed from step 6's report, so neither
  the warning nor the opt-in fatal can fire on a repository where drift did not run.
- **Blame is `git log -1 -- <file>`, and this release only labels it.** It still names the
  last commit to touch the file rather than the commit that moved the anchored
  declaration; an unrelated later commit to the same file displaces the real cause
  entirely. Finding the causing commit is drift's to fix, and is filed there.
- **Removing a binding from `drift.lock` is only sometimes visible.** Nothing compares the
  lock against what a concept claims to be watching, so deleting a `[[bindings]]` entry by
  hand is not reported as a removal. The acceptance comparison on 2026-09-19 measured what
  this release does catch: when the deleted entry was the concept's LAST binding, the
  coverage warning names it (29 → 30 untracked concepts on the reference consumer), and
  `OKF_REQUIRE_TRACKING` makes that fatal. What stays silent is a concept that keeps at
  least one other binding — three anchors down to one loses coverage with every check
  green — and any repository where drift did not run, since coverage is computed from the
  drift report. The gate still notices only the opposite direction on its own: a binding
  whose DOC no longer exists.

## [0.8.2] - 2026-09-17

### Fixed

- The drift bootstrap now treats a code path as already bound when the same concept holds
  either the whole file or a `path#Symbol` binding, so reruns do not add duplicate
  whole-file bindings after symbol-level narrowing.
- `#Symbol` entries in `code_refs` now fail fast with guidance to list the file in
  `code_refs` and put the symbol anchor in `drift.lock` via `drift link`.
- Runtime selftests cover both bootstrap regressions and sabotage-verify each fix.

## [0.8.1] - 2026-09-17

### Fixed

- The gate now distinguishes drift findings from execution errors: stale or broken
  markdown outside the knowledge bundle is reported as a note and does not fail the gate
  when every bundle concept is fresh, while a non-zero report with no findings remains
  fatal. Runtime selftests cover both paths and are sabotage-verified.

## [0.8.0] - 2026-09-17

### Added

- The drift bootstrap now binds only code `code_refs` paths from a fixed extension list;
  every governed path remains under okf's existence check. It reports `not-code` paths and
  existing non-code bindings as `held-non-code` with the exact manual `drift unlink` command.
- Offline runtime regression coverage exercises the code-only filter, all-non-code directory
  expansion, held non-code bindings, and the gate's acceptance of unbound paths.

### Changed

- Setup, migration, writing, reading, templates, quirks, the README and runtime headers now
  distinguish automatic code-content drift bindings from okf's existence-only checks for
  non-code paths. Integration accepts the official v0.7.0 Work Loop digest while updating it.

### Known gaps

- A data file whose content a concept describes needs a hand `drift link`; the bootstrap does
  not provide an environment override for its fixed code-extension list.
- Existing non-code bindings are reported, not removed; remove them explicitly with the
  printed `drift unlink` command.

## [0.7.0] - 2026-09-16

### Added

- Wrapper-free consumer integration: the model-invocable `okf-runtime` skill resolves
  its plugin launcher from the host-supplied skill directory for pinned gate/recall.
  The four existing skills remain manual-triggered. No cache-version paths or implicit
  plugin-root environment are stored in consumer instructions.
- Standalone consumer CI bootstrap verifies the pinned launcher before execution,
  requires **v0.7.0** or a later compatible release, and disables the development
  override. Consumer adoption uses the release's published SHA256SUMS asset.
- Plugin-only integration helper with all-candidate preflight, exact generated wrapper
  recognition and official historical shim/workflow hashes independent of the current
  pin. It preserves project navigation, refuses customized/symlinked/bound deletion
  candidates, reports historical operational references, and leaves every bundle/lock
  byte untouched. Reapplication is idempotent.
- Offline fixture-release contracts exercise launcher roots, pin validation, cache
  corruption/concurrent worktrees, the actual CI template without a plugin, skill
  resolution, and safe integration conversion. The existing runtime suite also runs
  through the pinned launcher.

### Changed

- The sole `okf-shim.sh` accepts `--repo-root`, retains legacy positional invocation,
  falls back to the cwd's Git root, and always executes at the selected consumer root.
  Development bypasses are explicit in diagnostics; normal launches still verify cold
  downloads and warm caches. Root-aware use diagnoses old incompatible pins.
- Pin generation validates unique well-formed hashes for all required runtime entries
  including the launcher and stages the file before replacement. Release checksum
  validation checks all four required entries. Gate/recall algorithms are unchanged.
- Setup, mex migration, writing/reading, templates and next-step diagnostics now point
  to the plugin runtime or standalone verified bootstrap, not consumer wrappers.

### Known gaps

- Integration apply uses atomic per-file replacement, not a multi-file transaction;
  avoid concurrent consumer edits and review/retry after filesystem failures. Unknown
  or customized integrations require an explicit human merge.
- SHA-256 pins cover plugin scripts, not the separate drift installer. The development
  override deliberately bypasses verification; gate degradation without adopted drift
  and recall's refusal without drift remain unchanged.

## [0.6.2] - 2026-09-16

### Fixed

- An installed, adopted drift checker that emits no JSON now fails the gate instead of
  reporting success with step 6 skipped. Nonzero validator/checker statuses cannot become
  a clean gate even when stdout contains a fresh-looking report; structured stale findings
  remain visible. Missing per-document verdicts and partial reports that omit a concept
  are no longer assumed fresh.
- Recall normalizes relative, dotted and absolute bundle paths into drift's repository-root
  namespace. Missing or unknown verdicts fail closed before any search result is printed,
  rather than promoting stale or unchecked concepts to fresh.
- Failed searches and malformed search/check reports no longer look like a successful empty
  search. Recall preserves dependency diagnostics and distinguishes drift's exit-1 findings
  from execution errors.
- Recall, like the gate, passes JSON to Perl through private temporary files, not command
  arguments. Large search and drift reports no longer hit Linux's per-argument size limit;
  temporary files are removed on success, failure and handled termination.

### Added

- Offline runtime regression tests exercise process failures, malformed and missing verdicts,
  equivalent bundle paths, valid empty searches, and reports larger than 131 KB. CI runs them
  alongside the existing checksum selftest and gate size/path regressions.

### Known gaps

- The gate still warns when drift is not installed or no lock exists, for repositories that
  have not adopted it. CI consumers must retain their explicit dependency/version preflight.
- Digest verification protects the fetched plugin scripts, not the separate mutable drift
  installer; `OKF_DRIFT_ROOT` remains an intentional local-development bypass.

## [0.6.1] - 2026-09-16

Two defects, both found on the first CI run after a consumer repo adopted the gate, and
both invisible on a developer machine. Neither could have been caught by anything ci.yml
ran before this release, so each now has a regression test.

1. **The gate died on Linux once the bundle grew.** `okf-check.sh` collected
   `okf validate --json` and `drift check --format json` into shell variables and passed
   both to perl as ARGUMENTS. Linux caps a single argument at `MAX_ARG_STRLEN` — 131072
   bytes, 32 pages — independently of `ARG_MAX`. Measured on a 27-document, 48-anchor
   bundle: `drift check` emitted 183806 bytes, 1.4x the cap, and `execve` refused with
   `E2BIG`. The gate died as `okf-check.sh: 60: exec: perl: Argument list too long`, exit
   126. macOS has no comparable per-argument cap, so the gate was green on every developer
   machine and red on the first CI run. Bisected in an alpine container: 131071 bytes pass,
   131072 fail.
2. **An absolute bundle path silently skipped step 6.** `drift check` runs from the
   bundle's parent and reports paths relative to it. Step 6 filtered those against
   `$bundle`, which holds only while `$bundle` is a plain relative name from the repo root.
   Given `/abs/path/knowledge`, or `../knowledge` from a subdirectory, no drift path could
   match: every doc was skipped and the gate printed `0 doc(s) / 0 drift anchor(s) fresh`
   and exited 0 over a bundle whose concepts were genuinely stale. Measured with two
   concepts drifted: `okf-check.sh knowledge` reported 2 FAIL and exit 1, while
   `okf-check.sh /abs/path/knowledge` reported ok and exit 0. Steps 1 to 5 were unaffected
   throughout — frontmatter, indexes and template residue were still checked — so this was
   never "the gate checks nothing"; it was the gate silently dropping the one step it
   exists for.

### Fixed

- **Both JSON blobs reach perl through files.** They are written into an `mktemp -d`
  directory and perl receives the PATHS. `exec` is dropped so the EXIT trap survives to
  remove the directory; perl's status is forwarded by hand instead. Perl reads them with an
  explicit `:raw` slurp rather than the existing `:utf8` one, because `decode_json` expects
  UTF-8 octets and a `:utf8` read would hand it characters.
- **Step 6 matches `basename($bundle)`,** the bundle's name within the parent drift runs
  from, at both comparison sites: the doc filter and the anchor count. Fixing only the
  first made the absolute form report `27 doc(s)` with `0 anchors`, which is how the second
  site was found.

### Added

- **A gate that checked nothing can no longer report freshness.** When drift returns JSON
  and the bundle has concepts but not one doc matched, that is now a FAIL naming both
  sides, instead of a pass. Defence in depth for a failure that was silent rather than
  loud.
- **A regression test per defect in `ci.yml`.** A stub drift emitting 296176 bytes, and a
  stub reporting only docs outside the bundle. The second doubles as the positive control
  for the guard above: without a case where zero docs match, the guard could ship inert.
  Both were sabotage-verified in an alpine container — each fails against 0.6.0 and passes
  against 0.6.1 — and both were extracted from the YAML and executed before release,
  because a CI step that has never run is not a test.


## [0.6.0] - 2026-09-16

Three defects in the 0.5.x shim, all measured on a consumer repo with five worktrees on
2026-09-16. Each of them could leave a gate green that had checked nothing.

1. **A truncated download was accepted.** The only validation was "the first line starts
   with `#!`". Two lines of a 221-line `okf-check.sh` passed it, were cached, and the gate
   then exited 0 having checked nothing — silently green, and cached forever, because the
   cache key is the tag.
2. **The download went to a fixed `$cached.part`.** Five worktrees of the same repo running
   their first gate at once wrote one another's file, which could leave a damaged script
   that passed (1) and was then cached under the tag for good.
3. **A git tag is not fixed content.** A moved tag changes what is fetched while
   `.okf-drift-version` says the same thing. Nothing pinned the bytes.

### Changed

- **`.okf-drift-version` is a lockfile, not a tag.** Line 1 is still the tag; every other
  line is `<sha256>  <name>` in `sha256sum` output format, so `shasum -c` reads it. The
  filename is unchanged — consumer repos already carry it, and the shim tells a 0.5.x
  one-line file apart by finding no pin line for the script it was asked for.
- **`scripts/okf-shim.sh` pins by content.** It downloads to a unique `mktemp` file next to
  the cache (fixing 2), computes sha256 with `shasum -a 256` or `sha256sum`, and moves it
  into the cache only on a match (fixing 1 and 3). It then re-hashes the **cached** file on
  every later run: a cache damaged after the fact is an error, not a green gate. Every
  failure — a 404, an empty body, a digest mismatch on download or in cache, a missing or
  empty lockfile, a lockfile with no pin line for the requested script, or neither hashing
  tool on `PATH` — exits 2 with one line naming expected vs found.
  `$OKF_DRIFT_ROOT` still wins over the pin and is **exempt** from the hash check by
  design: the file being edited cannot match a published digest. The file says so.
- `.github/workflows/release.yml` computes `SHA256SUMS` over `scripts/*.sh` and
  `scripts/*.py` at the tag, asserts it is non-empty and mentions `okf-check.sh`, and
  attaches it to the GitHub Release.
- `/okf-setup` Step 3 and `/okf-migrate` Step 4 write the consumer lockfile **from that
  asset** and say never to write it by hand, with the exact `okf-pin.sh` and
  `gh release download` commands. `knowledge.yml`'s header says the fetched gate is
  digest-checked, and that a warm cache is re-verified rather than trusted.

### Added

- `scripts/okf-pin.sh <tag> [repo-root]` — writes a consumer repo's `.okf-drift-version`
  from that release's `SHA256SUMS` (via `gh`, falling back to the asset's URL). Refuses an
  empty asset or one with no `okf-check.sh` line.
- `scripts/okf-shim-selftest.sh [tag]` — the regression test, run by `ci.yml` against a
  real tag. Four properties, of which (a) and (b) fail against the 0.5.1 shim: a truncated
  cached script is rejected with exit 2 and the gate does not run; a cached script with one
  byte changed is rejected; a lockfile disagreeing with the tag's real content is rejected
  on download and nothing is cached; and the happy path still fetches, verifies, caches and
  runs the gate. It also checks that a lockfile with no pin line for the script is an error.
- `ci.yml` additionally proves `okf-pin.sh` writes a lockfile the shim accepts, against the
  newest release that carries the asset.

## [0.5.1] - 2026-09-16

### Changed

- Docs only: the two repositories the plugin was measured on are now called repo A (a Rust/Python/Swift protocol family) and repo B (a TypeScript monorepo); their names, one plan path and a few file paths and symbol names are gone from the skills, the quirks file, the templates and one script comment. Every measured number is unchanged. Scripts are byte-identical to 0.5.0 apart from that comment.

## [0.5.0] - 2026-09-16

### Changed

- **A consumer repository no longer vendors the scripts.** `/okf-setup` and `/okf-migrate`
  now install `scripts/okf-shim.sh` plus a `.okf-drift-version` holding a single tag, and
  write `scripts/okf-check.sh` and `scripts/okf-recall.sh` as two-line wrappers that
  `exec` the shim. A vendored copy drifts from the plugin silently and nothing in either
  repository can see that it has; a pinned one moves only when `.okf-drift-version` does,
  and the move is a one-line diff a reviewer can read.
- `skills/okf-setup/templates/knowledge.yml` says that the gate now needs network access
  on its first run in a job. The command CI runs is unchanged — `scripts/okf-check.sh
  knowledge` — and `curl` was already used by the step above it to install drift.

### Added

- `scripts/okf-shim.sh` — resolves a script in this order: `$OKF_DRIFT_ROOT/scripts/<name>`
  when that variable points at a local plugin checkout (so the plugin can be developed
  against a real repo without republishing), otherwise
  `${XDG_CACHE_HOME:-$HOME/.cache}/okf-drift/<tag>/<name>`, populated on first use from
  `raw.githubusercontent.com/alvistar/okf-drift/<tag>/scripts/<name>`. A download that
  404s, arrives empty, or does not start with `#!` is fatal: running nothing must never
  look like a clean gate.

## [0.4.0] - 2026-09-16

First release as a standalone repository. The history below was split out of a private
monorepo with `git subtree split`, so every commit under `0.4.0` predates this tag.

### Added

- `/okf-setup` — scaffolds a fixed OKF v0.2 bundle (`project/{state,stack,setup,conventions}`,
  `architecture/`, one concept per decision, one per playbook) that passes
  `okf validate --strict` before a word is written, plus the population and resync prompts
  and the `CLAUDE.md` Knowledge Bundle / Work Loop / Navigation sections.
- `scripts/okf-check.sh` — the six-step gate for what `okf validate` was measured *not* to
  check: its own warnings treated as failures, index rows resolved both ways with the
  concept's description verbatim, ISO `last_updated`/`stale_after`, decision
  `date`/`status`/supersession, no template residue, no empty sections, the reserved files,
  and the drift join. 21 mutations verified.
- The drift phase. `scripts/okf-drift-bootstrap.sh` writes one `drift link` per `code_refs`
  entry into a repo-root `drift.lock`; `scripts/okf-recall.sh` joins `okf search --json`
  with `drift check --format json` and **withholds** a concept whose bound code moved after
  it was written, with the commit to blame; gate step 6 fails on the same condition but only
  *warns* when there is no lock, so the gate keeps working in a repo that has not adopted
  drift. Recall refuses, the gate degrades — a skipped gate step is visible in the gate's
  own output, a missing check inside a recall is visible nowhere.
- `/okf-write` — the record half, with the rule that makes the alarm worth anything: the
  agent may re-stamp a binding with `drift link … --doc-is-still-accurate`, and may never do
  it silently. Every re-stamp is paired with a dated line in `knowledge/log.md`.
- `/okf-read` — recall through `okf-recall.sh`, and how to read a WITHHELD block (it is a
  refusal, not a weaker hit).
- `/okf-migrate` and `scripts/okf-migrate.py` — a mex scaffold (`.mex/`: ROUTER, context/,
  patterns/, `grounds_to`, `mex://` anchors) converted into this layout without losing a
  document or a grounding. Node ids are resolved through `mex graph get` while the graph
  still exists; frontmatter is written by hand, one line per key, because a YAML dumper's
  fold silently truncated 22 descriptions on the first migration.
- `skills/okf-setup/templates/knowledge.yml` — the gate as a blocking CI job, on every PR
  and on push to `main`. The PR that makes a concept stale is almost always one that touches
  only code, and nobody in that PR has a reason to run the gate. `fetch-depth: 0` because
  drift's blame reads `git log`; `okf version && drift --version` before the gate, because
  a failed install would otherwise leave the job green with step 6 silently skipped.
- `skills/okf-setup/references/okf-quirks.md` — everything measured on okf v0.3.0, drift
  v0.10.1 and mex 0.8.2 on 2026-09-16, including the three `drift link` refusals, the
  `#Symbol` anchor forms each language accepts, and the one fact the whole design rests on:
  editing a doc does **not** clear its staleness.

[Unreleased]: https://github.com/alvistar/okf-drift/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/alvistar/okf-drift/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/alvistar/okf-drift/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/alvistar/okf-drift/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/alvistar/okf-drift/compare/v0.6.2...v0.7.0
[0.6.2]: https://github.com/alvistar/okf-drift/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/alvistar/okf-drift/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/alvistar/okf-drift/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/alvistar/okf-drift/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/alvistar/okf-drift/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/alvistar/okf-drift/releases/tag/v0.4.0
