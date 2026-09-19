# Resync the bundle

OKF has no drift detector for prose: `okf validate --drift` checks that `code_refs`
paths still exist, nothing more (`references/okf-quirks.md`). Staleness is what you
declare with `stale_after:` and what `last_updated:` lets you infer from `git log`.
So a resync is an agent task, run when:

- `okf-drift:okf-runtime in gate mode` or `okf validate --drift --stale` reports anything;
- `git log --since=<last_updated> -- <code_refs paths>` is non-empty for a concept;
- a session found a concept wrong and did not fix it on the spot;
- on a cadence, e.g. before a release.

## Quick check, zero tokens

```bash
okf validate knowledge --strict --drift --stale      # broken links, orphans, dead paths, expired reviews
# Invoke okf-drift:okf-runtime in gate mode for indexes, frontmatter, residue and drift.
for f in $(grep -rl '^code_refs:' knowledge --include='*.md'); do
  since=$(awk '/^last_updated:/{print $2; exit}' "$f" | tr -d "'\"")
  paths=$(awk '/^code_refs:/{f=1;next} f&&/^- /{print $2} f&&!/^- /{exit}' "$f")
  [ -n "$paths" ] && n=$(git log --oneline --since="$since" -- $paths | wc -l | tr -d ' ') && [ "$n" -gt 0 ] \
    && echo "$f: $n commit(s) under its code_refs since $since"
done
```

The loop is the closest thing to mex's grounding drift that OKF affords: not "the
symbol's body changed" but "something under the paths this concept governs changed
since the concept was last touched". Coarser, and honest about it. It is also why
`code_refs` should be narrow: a concept governing `src/` is hot on every commit.

## The prompt

```
You are going to resync the OKF knowledge bundle under knowledge/ with the
codebase. The bundle may be out of date; the checks below say where to look.

First read knowledge/index.md and knowledge/project/state.md. Then run, from
the repo root, and keep the output:
    okf validate knowledge --strict --drift --stale
    okf-drift:okf-runtime in gate mode
and, for every concept with code_refs, `git log --oneline --since=<its
last_updated> -- <its code_refs paths>`.

For each concept that is flagged, or whose paths have commits since its
last_updated, or that I name below:
1. Compare its claims to the actual code. Read the code; do not trust the prose.
2. Fix what is wrong SURGICALLY — edit the sentence, do not rewrite the file.
3. A decision that no longer holds is not edited: set status: deprecated, add
   "Superseded by [title](/decisions/<new>.md)" under ## Related, and write the
   new decision as its own file, linked back. Both stay.
4. If a code_refs path moved, point it at the new path; if the thing it
   governed is gone, remove the path and the sentence that relied on it.
5. Bump last_updated. If you actually reviewed the whole concept, advance
   stale_after too — otherwise a reviewed concept stays expired. If the
   description changed, change the same line in its index row.
6. Refresh project/state.md if what is working / not built / broken has moved.
   Keep it a snapshot; put the story in log.md.

Every concept the gate reports with no tracked target is re-read against the
repository by hand during this resync: nothing checked it, and `git log -- <its
code_refs>` is vacuous on empty code_refs, so it is never flagged by either check
above.

Playbooks: run the Steps of each flagged playbook mentally against the current
code. A command that no longer exists, a path that moved, a gotcha that was
fixed — update or delete. A playbook nobody could follow is worse than none.

Then re-run both checks until clean, and append a dated entry to
knowledge/log.md: which concepts changed and why, one line each.

Do not touch a concept the checks and the git log leave alone unless I named
it. Report: concepts changed, concepts confirmed unchanged, and anything you
could not verify from the code.

Concepts I want looked at regardless: [none | list]
```
