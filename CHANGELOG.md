# Changelog

All notable changes to this project are documented here.

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with three segments.
`VERSION` at the repository root is the single source of truth; the release workflow
refuses a tag that disagrees with it or with `.claude-plugin/plugin.json`.

## [Unreleased]

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

[Unreleased]: https://github.com/alvistar/okf-drift/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/alvistar/okf-drift/releases/tag/v0.4.0
