# Managed items: explain the run, ask the user, the project-owned mark

Read this before the first question of an `okf-integrate.py` run, and when the helper
prints a `project-owned` line or refuses an item as customized. `PLUGIN_ROOT` and
`REPO_ROOT` are as in the skill that sent you here.

## The managed items

okf-drift manages four things in a repository. Name each by its role when you speak to
the user:

| Item | Role |
|---|---|
| the `Knowledge Bundle` and `Work Loop` sections of `CLAUDE.md` (two items) | what every agent reads about the bundle and about the work loop |
| the gate workflow, `.github/workflows/knowledge.yml` (or `knowledge.yaml`) | the CI job that checks the bundle on every PR |
| `CODING_STANDARDS.md` | where a code reviewer finds the rules |
| the pin, `.okf-drift-version` | the okf-drift release the repository runs |

The helper updates a managed item by itself only while the item holds an **official
text**, one that okf-drift itself shipped. An item the project changed is **customized**:
the helper stops on it rather than overwrite the project's changes.

## Plain words

Speak to the user in their language, with these words. The helper's own terms stay in the
commands you run and in your own checks; a progress line names the file and what you do
to it ("I add the line that marks the gate workflow as the project's").

| Helper term | Say to the user |
|---|---|
| the helper, `okf-integrate.py` | okf-drift |
| official text | okf-drift's vX.Y.Z text |
| customized | the project changed this file |
| refusal, `merge explicitly` | okf-drift stopped on this file, to keep the project's changes |
| mark, project-owned | a comment line that says the file belongs to the project |
| base, digest, `sha256=` | the okf-drift version the project started from |
| skipped | okf-drift leaves the file as it is |
| upstream change, `moved on` | what okf-drift changed in its own text |
| bare mark, dry run | what they found (the base, the files okf-drift would write) |

## Explain the run

Explain the run once per session, before the first question, covering every part of the
skill that runs the helper in this session. In a few sentences:

1. **The move.** The pin goes from vA.B.C to vX.Y.Z, so CI, the local gate and recall
   run that release's scripts. On a first install, the repository starts at vX.Y.Z. When
   the pin stays (a part that only installs a file), say it stays at vA.B.C and that
   the run adds or updates files of that same release.
2. **What the release brings**, when the pin moves: two or three lines from the
   sections of `$PLUGIN_ROOT/CHANGELOG.md` between the two tags.
3. **The managed items**, each with its role from the table above.
4. **What happens to them.** okf-drift updates by itself each item that holds its own
   text. For each item the project changed, you ask, one item per question. Each answer
   is applied when the user gives it: the mark or the merge goes into the file then. The
   files okf-drift writes by itself, and the pin, wait for the user's final OK.

## Ask about an item

Ask about one item per question: each section of `CLAUDE.md` is its own item. Before you
ask, find the item's base without touching the project's file, as **The mark** says. The
question gives, in this order:

1. **The role**, in one sentence, from the table above.
2. **Why okf-drift stopped**: it updates a managed file only while the file holds its own
   text, so it never overwrites the project's changes. For an item the project already
   marked, see **Act on a moved official text** instead.
3. **The differences**, in plain words, in two groups, each said even when empty ("the
   project changed nothing else"; "okf-drift's text has not changed since"):
   - **what the project changed**, from the `diff` of the base against the project's
     item: a mark keeps it;
   - **what okf-drift changed since**, from the `diff` of the base against the current
     official text: a merge brings it in.
   A line the project replaced counts only in the first group, even when okf-drift
   changed it too.
4. **The mark**, the first time it comes up in the run: a comment line in the file that
   tells okf-drift the item is the project's, so okf-drift leaves it as it is. It records
   which okf-drift version the project started from, so a later upgrade can show what
   okf-drift changed in its own text and propose to bring it in.
5. **Each option** from the table below that applies to the item, with what the file
   becomes now and what happens at the next upgrade. Recommend one and say why.

### The options

This table is the one list of options. The steps that ask point here.

| Option | Items | What you do | The file now | At the next upgrade |
|---|---|---|---|---|
| **Mark it as the project's** | every item but the pin | add the mark with the confirmed base (**The mark**) | stays as it is, plus the mark line | okf-drift leaves it as it is; when its own text changed, you show what changed and propose to bring it in |
| **Merge and mark**, when the second group is not empty | a `CLAUDE.md` section, the gate workflow | rebuild the item from the current official text and put back each of the project's changes, show the diff, then add the mark with the current official text's digest | okf-drift's new lines come in, the project's changes stay, plus the mark line | as for the mark |
| **Add okf-drift's text** | `CODING_STANDARDS.md` | paste `$PLUGIN_ROOT/skills/okf-setup/templates/CODING_STANDARDS.md` into the project's file verbatim, where its reader will see it; the project's rules stay | the project's rules plus okf-drift's text; no mark | okf-drift accepts the file while it holds that text; when a release changes it, the question comes back |
| **Use okf-drift's vX.Y.Z text** | a `CLAUDE.md` section, the gate workflow | replace the item with the current official text | okf-drift's text; the project's changes are gone | okf-drift updates it by itself |
| **Defer the upgrade** | every item, in `/okf-migrate` Part 4 only | write nothing more; the run stops before the final OK | as it is; answers already applied stay | the same question comes back |

A worked example, for a gate workflow the project gave its own runner, permissions and
timeout:

> **The gate workflow** (`.github/workflows/knowledge.yaml`) is the CI job that checks
> the knowledge bundle on every PR. okf-drift stopped on it because the project changed
> it: okf-drift updates a file by itself only while it holds okf-drift's own text, so it
> never overwrites the project's changes.
>
> - **What the project changed** (a mark keeps it): the job runs on the project's
>   `self-hosted` runner, has write permission on pull requests, and stops after 20
>   minutes instead of 10.
> - **What okf-drift changed since** (a merge brings it in): nothing; the project
>   started from okf-drift's v0.19.0 text.
>
> A mark is a comment line at the top of the file that says the file belongs to the
> project: okf-drift then leaves it as it is. It also records which okf-drift version the
> project started from, so a later upgrade can show what okf-drift changed in its own
> text and propose to bring it in.
>
> - **Mark it as the project's (recommended):** the file stays as it is, plus the mark
>   line. At the next upgrade okf-drift leaves it as it is, and shows any change to its
>   own text for you to accept or refuse.
> - **Use okf-drift's v0.19.0 text:** the job loses its own runner, permissions and
>   timeout. At the next upgrade okf-drift updates it by itself.
> - **Defer the upgrade:** nothing more changes and the pin stays at v0.18.0.

## The mark

The owner declares a managed item (all but the pin) the project's own with a mark inside
it, on the line after the section heading or near the top of the file:

```
<!-- okf-drift: project-owned sha256=<64 hex> -->     Markdown: a CLAUDE.md section, CODING_STANDARDS.md
# okf-drift: project-owned sha256=<64 hex>            YAML: the gate workflow
```

`sha256` records the official text the project adapted: the base. A wrong base hides
every upstream change made since the real one. Find it in a scratch copy, so the
project's file stays as it is until the user answers:

1. Copy the repository's working tree to a scratch directory
   (`rsync -a --exclude .git "$REPO_ROOT/" "$SCRATCH/"`). In the copy, write the bare
   mark (`<!-- okf-drift: project-owned -->`, or `# okf-drift: project-owned` in YAML)
   inside each customized item, and run the same dry run with `--repo-root "$SCRATCH"`.
   The helper refuses the first bare mark and prints the mark for that item's closest
   official text. Put that mark in the copy in place of the bare one and run again, until
   no bare mark is refused.
2. Confirm each base before you use it: `diff` the project's item against
   `$PLUGIN_ROOT/skills/okf-setup/templates/official/<digest>`, the archived official
   text. The project's own changes are the only differences. When they are not, try the
   item's other official texts (the same directory, one file per digest; the item's
   digests are in `scripts/okf-integrate.py`) and pick the one the project was adapted
   from. Ask the user when two fit. Every official `CLAUDE.md` text names the gate
   `.github/workflows/knowledge.yml`: in a repository whose gate is `knowledge.yaml`,
   that name is no change of the project's, and the helper maps it back before it
   compares a section, so the mark records the archived text as it is.

Write a mark into the project's file only after the user chooses an option that adds one.
The helper refuses a mark whose digest is not one of the item's own official texts, so a
mark that lands in the wrong section (above the next heading instead of below its own)
is caught. Put a section's mark on the line after its heading.

A kept item must not run a legacy wrapper under `scripts/` (`okf-check.sh`,
`okf-recall.sh`, `okf-shim.sh`) that the same run removes: the helper refuses with `<item>: project-owned
and still runs <script>`. Show the user that line and the item's current official text;
the item moves to the runtime launcher on the user's word, then the run goes on.

The mark is the owner's decision, made once, on the user's explicit word: when the helper
refuses an unmarked item as customized, ask as **Ask about an item** says.

## The notices

For a marked item the helper never compares or writes it, and carries on with every
other item. It prints:

```
<item>: project-owned, skipped
```

and, only when the official text changed since the recorded one:

```
<item>: official text moved on since the project adapted it; upstream diff follows; after a merge the user agreed to, record `<new mark>`
--- official sha256=<recorded>
+++ official sha256=<current>
<unified diff of the two OFFICIAL texts>
```

The diff is the upstream change, not the project's adaptation.

## Act on a moved official text

For each item with a `moved on` notice, in turn:

1. **Show** the user the upstream diff, as printed.
2. **Propose** the merge: read the project's version of the item and write out how each
   upstream hunk lands in it — taken as is, adapted to the project's wording, or left
   out with the reason. Show the result as a diff of the project's file.
3. **Ask** for consent to that merge, as **Ask about an item** says, with point 2
   reading instead: the project marked this file as its own, so okf-drift left it as it
   is and carried on with the rest; okf-drift's own text changed since the version the
   project started from. The upstream diff is the second group. The user may accept,
   amend or refuse the merge; a refusal leaves the file as it is, and the proposal comes
   back at the next upgrade.
4. **On consent**, edit the item as agreed and replace its mark with the `<new mark>`
   the notice printed. Run the helper's dry run again: the item prints `skipped` with no
   `moved on` notice.
5. **Without consent**, leave the file byte-for-byte as it is, mark included, and tell
   the user the item still adapts an older official text; the notice returns on every
   run until a merge.

The step is done when every `moved on` item is either merged with consent and its mark
refreshed, or left untouched and named in the skill's report.
