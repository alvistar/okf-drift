# Log entries are reserved `log.md` files, one folder per branch

Parallel PRs all wrote `knowledge/log.md`, so every merge conflicted every other open PR (5 of 8 branch merges in alvistar/ai-review on 2026-10-12; issue #13). Each branch now writes one log entry at `knowledge/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`, where the folder name is the index and nothing is generated, and the random suffix keeps two branches with the same last name segment (`alice/fix`, `bob/fix`) out of one folder; the root `log.md` becomes the frozen log, keeping the history before the split and a pointer to `log/`, and the gate refuses new dated headings under it. The folder-per-entry shape exists because okf (v0.6.0, measured) treats `log.md` as reserved at every level, so a nested one is neither a concept nor searched and passes `okf validate`, while okf does not check its headings, so `okf-check.sh` does.

## Considered Options

- **`log.d/<slug>.md` without front matter**: okf rejects it (`missing YAML frontmatter block`, NOT conformant).
- **Entries with front matter**: they become concepts, counted, orphan-checked and returned by recall.
- **Entries outside the bundle**: okf no longer sees the history, which leaves the bundle.
- **A generated `log.md` view**: every PR would rewrite it, bringing the conflict back.
- **`merge=union` on `log.md`**: fixes a local merge, but GitHub still reports the PR as conflicting.

## Consequences

The slug alone cannot tell a stacked branch from its parent (`bob/fix` on top of `alice/fix` sees alice's entry among the files it added since the merge-base). So an entry that `okf-log.sh` names from the branch records the full branch name in an HTML comment above its first heading, `<!-- okf-log branch: alice/fix -->`, and lookup reuses it only on that exact branch, whatever its slug. A renamed branch keeps its entry: a comment that records a former name of the branch (a `git branch -m` in its reflog) matches too, and the next `add` rewrites it to the new name; a comment that records a branch no ref names any more, with no rename in the reflog, refuses with the entry's path instead of creating a second entry in silence (issue #25). An entry without the comment (the setup entry, a `--slug` entry) is matched by its slug. okf ignores the comment, and the gate's heading check skips comments.

_Superseded by ADR 0002 (drift and `drift.lock` removed):_ `drift.lock` keeps drift's single-file layout: it conflicted in only 1 of the same 8 merges (two new docs at the same sorted position), and `okf-lock-merge` resolves that by merging bindings by (doc, target) and letting `drift check` judge the signatures.
