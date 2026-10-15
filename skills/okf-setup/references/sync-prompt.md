# Resync the bundle

Nothing checks whether prose is still true of the code: `okf validate --drift` checks
that `code_refs` paths still exist, nothing more (`references/okf-quirks.md`). The code
is the source of truth, and an agent that relies on a wrong concept fixes it then
(read-repair). A review date is what you declare with `stale_after:`; where to look is
what the change hint shows: commits on a concept's `code_refs` since the concept's last
commit. So a resync is an agent task, run when:

- `okf-drift:okf-runtime in gate mode` or `okf validate --drift --stale` reports anything;
- a concept carries a change hint you have not read the code behind;
- a session found a concept wrong and did not fix it on the spot;
- on a cadence, e.g. before a release.

## Quick check, zero tokens

```bash
okf validate knowledge --strict --drift --stale      # broken links, orphans, dead paths, expired reviews
# Invoke okf-drift:okf-runtime in gate mode for indexes, frontmatter, residue and log.
for f in $(grep -rl '^code_refs:' knowledge --include='*.md'); do
  base=$(git log -1 --format=%H -- "$f")
  paths=$(awk '/^code_refs:/{f=1;next} f&&/^- /{print $2} f&&!/^- /{exit}' "$f")
  [ -n "$base" ] && [ -n "$paths" ] && n=$(git rev-list --count "$base"..HEAD -- $paths) && [ "$n" -gt 0 ] \
    && echo "$f: $n commit(s) under its code_refs since its last commit"
done
```

The loop is the change hint recall prints, for the whole bundle at once: not "the
symbol's body changed" but "something under the paths this concept governs changed
since the concept was last committed". Counted from the commit, not `last_updated`,
because a date cannot order two commits of one day. A hint is a place to look, not a
verdict: most code changes leave a concept that follows the writing rule true. It is
also why `code_refs` should be narrow: a concept governing `src/` is hinted on every
commit.

## The prompt

```
You are going to resync the OKF knowledge bundle under knowledge/ with the
codebase. The bundle may be out of date; the checks below say where to look.

First read knowledge/index.md and knowledge/project/state.md. Then run, from
the repo root, and keep the output:
    okf validate knowledge --strict --drift --stale
    okf-drift:okf-runtime in gate mode
and, for every concept with code_refs, `git log --oneline <the concept's last
commit>..HEAD -- <its code_refs paths>`.

For each concept that is flagged, or whose paths have commits since its last
commit, or that I name below:
1. Compare its claims to the actual code. Read the code; the code wins.
2. Fix what is wrong SURGICALLY — edit the sentence, do not rewrite the file.
   Apply the writing rule while there: a sentence that restates the code
   (a signature, a default, a step list, a number, a field list) becomes where
   to look and why, or a dated observation if it must be quoted.
3. A decision that no longer holds is not edited: set status: deprecated, add
   "Superseded by [title](/decisions/<new>.md)" under ## Related, and write the
   new decision as its own file, linked back. Both stay.
4. If a code_refs path moved, point it at the new path; if the thing it
   governed is gone, remove the path and the sentence that relied on it.
5. Bump last_updated. If you actually reviewed the whole concept, advance
   stale_after too — otherwise a reviewed concept stays expired. If the
   description changed, change the same line in its index row.
6. Refresh project/state.md if what is working / not built / broken has moved:
   one line per item, the evidence in project/state-evidence.md under the same
   item, the story in the branch's log entry.

Every concept the gate reports with empty code_refs is re-read against the
repository by hand during this resync: it never carries a change hint, so neither
check above can flag it.

Playbooks: run the Steps of each flagged playbook mentally against the current
code. A command that no longer exists, a path that moved, a gotcha that was
fixed — update or delete. A playbook nobody could follow is worse than none.

Then re-run both checks until clean, and log which concepts changed and why, one
line each, with `okf-log.sh add knowledge '<line>'` through the pinned launcher (as
/okf-write does). The lines go in this branch's log entry; knowledge/log.md is frozen.

Do not touch a concept the checks and the git log leave alone unless I named
it. Report: concepts changed, concepts confirmed unchanged, and anything you
could not verify from the code.

Concepts I want looked at regardless: [none | list]
```
