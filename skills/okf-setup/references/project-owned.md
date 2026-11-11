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
commands you run and in your own checks.

| Helper term | Say to the user |
|---|---|
| official text | the text okf-drift ships in vX.Y.Z |
| customized | the project changed this file |
| refusal, `merge explicitly` | the helper stopped on this file, to keep the project's changes |
| mark, project-owned | a comment line that says the file belongs to the project |
| base, digest, `sha256=` | the official version the project started from |
| bare mark | (your own step: name what it found, never the step) |

## Explain the run

After the first dry run and before any question, tell the user in a few sentences:

1. **The move.** The pin goes from vA.B.C to vX.Y.Z, so CI, the local gate and recall
   run that release's scripts. On a first install, say the repository starts at vX.Y.Z.
2. **What the release brings.** Two or three lines from the sections of
   `$PLUGIN_ROOT/CHANGELOG.md` between the two tags.
3. **The managed items**, each with its role from the table above.
4. **What happens to them.** The helper updates by itself each item that holds an
   official text. For each file the project changed, you ask, one file at a time.
   Nothing is written before the user's final OK.

## Ask about an item

Ask about one item per question: each section of `CLAUDE.md` is its own item. The
question gives, in this order:

1. **The role**, in one sentence, from the table above.
2. **Why the helper stopped**: it updates a managed file only while the file holds an
   official text, so it never overwrites the project's changes.
3. **The differences**, in plain words, in two groups, each said even when empty ("the
   project changed nothing else"; "the official text adds nothing the project lacks"):
   - what the project changed: a mark keeps it;
   - what the official text has that the project lacks: a merge brings it in.
   Read both from your `diff` of the item against its closest official text, found
   before you ask as **The mark** says, steps 1 and 2.
4. **The mark**, the first time it comes up in the run: a comment line in the file that
   tells okf-drift the item is the project's, so the helper skips it. It records which
   official version the project started from, so a later upgrade can show what changed
   upstream and propose a merge.
5. **Each option**, with what the file becomes now and what happens at the next
   upgrade. The step that sent you names the options that apply; for a refused
   customized item they are:

   | Option | The file now | At the next upgrade |
   |---|---|---|
   | **Mark** | stays as it is, plus the mark line | skipped; when the official text changed, you show the upstream change and propose a merge |
   | **Merge and mark**, when the second group is not empty | the official text's new lines come in, the project's changes stay, plus the mark line | as for Mark |
   | **Take the official text** | the official text; the project's changes are gone | the helper updates it by itself |
   | **Defer the upgrade** | nothing is written, the pin stays | the same question comes back |

   For `CODING_STANDARDS.md` the merge pastes the generated text into the project's file
   and needs no mark: the helper accepts the file while it holds that text, and asks
   again when a release changes it.

Recommend one option and say why. Each progress line says what you do to which file in
the same plain words: "I add the line that marks the gate workflow as the project's",
not "applying the bare marks".

A worked example, for a gate workflow the project gave its own runner, permissions and
timeout:

> **The gate workflow** (`.github/workflows/knowledge.yaml`) is the CI job that checks
> the knowledge bundle on every PR. The helper stopped on it because the project changed
> it, and the helper updates a file by itself only while it holds the text okf-drift
> ships, so that it never overwrites the project's changes.
>
> - **What the project changed** (a mark keeps it): the job runs on the project's own
>   runner, has write permission on pull requests, and stops after 10 minutes.
> - **What v0.19.0 has that the project lacks** (a merge brings it in): nothing; the
>   project started from the v0.19.0 text.
>
> A mark is a comment line at the top of the file that says the file belongs to the
> project: okf-drift then leaves it alone. It also records which okf-drift version the
> project started from, so a later upgrade can show what changed in okf-drift's own text
> and propose to bring it in.
>
> - **Mark (recommended):** the file stays as it is, plus the mark line. At the next
>   upgrade okf-drift leaves it alone, and shows any change to its own text for you to
>   accept or refuse.
> - **Take the official text:** the job loses its own runner, permissions and timeout.
>   At the next upgrade the helper updates it by itself.
> - **Defer the upgrade:** nothing changes and the pin stays at v0.18.0.

## The mark

The owner declares a managed item (all but the pin) the project's own with a mark inside
it, on the line after the section heading or near the top of the file:

```
<!-- okf-drift: project-owned sha256=<64 hex> -->     Markdown: a CLAUDE.md section, CODING_STANDARDS.md
# okf-drift: project-owned sha256=<64 hex>            YAML: the gate workflow
```

`sha256` records the official text the project adapted: the base. A wrong base hides
every upstream change made since the real one. To find it:

1. Write the bare mark (`<!-- okf-drift: project-owned -->`) inside the item and run the
   dry run. The helper refuses it and prints the mark for the item's closest official
   text.
2. Confirm that base before you record it: `diff` the project's item against
   `$PLUGIN_ROOT/skills/okf-setup/templates/official/<digest>`, the archived official
   text. The project's own additions are the only differences. When they are not, try the
   item's other official texts (the same directory, one file per digest; the item's
   digests are in `scripts/okf-integrate.py`) and pick the one the project was adapted
   from. Ask the user when two fit.

The helper refuses a mark whose digest is not one of the item's own official texts, so a
mark that lands in the wrong section (above the next heading instead of below its own)
is caught. Put a section's mark on the line after its heading.

A kept item must not run a legacy wrapper under `scripts/` (`okf-check.sh`,
`okf-recall.sh`, `okf-shim.sh`) that the same run removes: the helper refuses with `<item>: project-owned
and still runs <script>`. Show the user that line and the item's current official text;
the item moves to the runtime launcher on the user's word, then the run goes on.

The mark is the owner's decision, made once. When the helper refuses an unmarked item as
customized, the choice belongs to the user, asked as **Ask about an item** says. Add a
mark only on the user's explicit word.

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
3. **Ask** for consent to that merge, as **Ask about an item** says: the upstream diff
   is the second group of differences. The user may accept, amend or refuse it.
4. **On consent**, edit the item as agreed and replace its mark with the `<new mark>`
   the notice printed. Run the helper's dry run again: the item prints `skipped` with no
   `moved on` notice.
5. **Without consent**, leave the file byte-for-byte as it is, mark included, and tell
   the user the item still adapts an older official text; the notice returns on every
   run until a merge.

The step is done when every `moved on` item is either merged with consent and its mark
refreshed, or left untouched and named in the skill's report.
