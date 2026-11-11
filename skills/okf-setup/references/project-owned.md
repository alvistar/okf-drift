# Project-owned items: the helper's notices

Read this when `okf-integrate.py` prints a `project-owned` line, or refuses an item as
customized. `PLUGIN_ROOT` and `REPO_ROOT` are as in the skill that sent you here.

## The mark

A managed item is a `CLAUDE.md` section (`Knowledge Bundle`, `Work Loop`), the gate
workflow (`knowledge.yml` or `knowledge.yaml`) or `CODING_STANDARDS.md`. The owner
declares one the project's own with a mark inside it, on the line after the section
heading or near the top of the file:

```
<!-- okf-drift: project-owned sha256=<64 hex> -->     Markdown: a CLAUDE.md section, CODING_STANDARDS.md
# okf-drift: project-owned sha256=<64 hex>            YAML: the gate workflow
```

`sha256` records the official text the project adapted. To get it, write the bare mark
(`<!-- okf-drift: project-owned -->`) and run the dry run: the helper refuses a mark with
no record and prints the full mark for the current official text. When the project
adapted an older official text, its digest is the name of a file in
`$PLUGIN_ROOT/skills/okf-setup/templates/official/` whose content is that text.

The mark is the owner's decision, made once. When the helper refuses an unmarked item as
customized, the choice belongs to the user: merge the official text in (the skill's own
refusal step), or mark the item project-owned. Add a mark only on the user's explicit
word.

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

The diff is the upstream change, not the project's adaptation. When the recorded text is
not in the plugin's archive, the notice says so and the diff shows the whole current
official text.

## Act on a moved official text

For each item with a `moved on` notice, in turn:

1. **Show** the user the upstream diff, as printed.
2. **Propose** the merge: read the project's version of the item and write out how each
   upstream hunk lands in it — taken as is, adapted to the project's wording, or left
   out with the reason. Show the result as a diff of the project's file.
3. **Ask** for consent to that merge. The user may accept, amend or refuse it.
4. **On consent**, edit the item as agreed and replace its mark with the `<new mark>`
   the notice printed. Run the helper's dry run again: the item prints `skipped` with no
   `moved on` notice.
5. **Without consent**, leave the file byte-for-byte as it is, mark included, and tell
   the user the item still adapts an older official text; the notice returns on every
   run until a merge.

The step is done when every `moved on` item is either merged with consent and its mark
refreshed, or left untouched and named in the skill's report.
