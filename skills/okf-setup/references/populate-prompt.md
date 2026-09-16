# Populate the scaffold

Two prompts, one per starting state. **Existing codebase**, or partially built → A.
**Fresh project, nothing built yet** → B. Run either in a session that can read the
repository; the agent writes the concepts directly and finishes with the gate.

Hand-written documentation already in the repo (a README, `docs/`, an ADR directory)
is **referenced, not duplicated**: the concept summarises and links, and lists the
source under `sources:`. Say so explicitly when you hand over the prompt, or the agent
will paraphrase the README into `architecture.md` and the two will drift apart.

---

## A — Existing codebase

```
You are going to populate the OKF knowledge bundle under knowledge/ for this
repository. The scaffold exists and validates; every concept body is annotation
comments saying what belongs in each section.

Read first: knowledge/index.md, knowledge/project/state.md, then the four
context concepts (project/stack, project/setup, project/conventions,
architecture/architecture) — the annotation comments in each — and the top of
knowledge/decisions/index.md and knowledge/playbooks/index.md, which carry the
format for a decision and a playbook. Search will not find those formats; read
the indexes.

Then explore the codebase: the entry point(s), the folder structure, 2-3
representative files from each major layer, every README and doc that exists,
the CI workflow, and `git log` for real dates.

PASS 1 — Context concepts.
Replace every annotation comment in the four context concepts with content from
THIS codebase, and delete the comment — the gate fails on a comment left behind,
and search indexes comment text. Follow each annotation's guidance on what
belongs there. Use actual names and commands. Do not pad: a section with one
true item has one item; a section with nothing true yet says so in one line
("None recorded yet."). Reserve "[TO DETERMINE]" for a fact you could not
establish, and add one line on what would establish it.
- `description:` on ONE line, quoted if it contains # or ": ". The same line
  goes in the category index row, verbatim.
- `tags:` 4-8 lowercase words a task description would contain when this is
  the concept to load.
- `code_refs:` repo-relative paths this concept GOVERNS — the ones
  `okf search --for-path` should answer with it. Narrow directories or boundary
  files, not `src/` on everything. Every path must exist.
- `sources:` the docs or files the content came from, each as
  `- resource: <repo-relative path or URL>` — okf --strict rejects a bare string.
- `last_updated:` today; keep the `stale_after:` the scaffold set.
- stack says WHAT and under which constraints; the WHY goes to decisions/.
- Existing documentation: summarise and link, never copy.

If a domain is deep enough that architecture.md would go long or shallow, add
architecture/<domain>.md with the same frontmatter shape, a `## Related`
section, and a row in architecture/index.md. Only for domains with real depth.

Fill project/state.md: Working 3-7 items; Not yet built and Known issues 0-7,
"None known." when empty. One line each, no history — history is log.md.

Update CLAUDE.md: project name, one-sentence description, non-negotiables (3-5
hard rules), the daily commands (this is their only home; setup.md does not
repeat them). Keep the Knowledge Bundle, Work Loop and Navigation sections.

PASS 2 — Decisions.
From the code, the docs and `git log`, record the decisions whose WHY prevents
a mistake — typically 3-6 for an established codebase. One file each under
decisions/, in the format at the top of decisions/index.md: real dates from git,
status stable, a link to the concept outside decisions/ the decision governs,
and a row in decisions/index.md with the description verbatim. Do not record
choices nobody would question.

PASS 3 — Playbooks.
Using the format at the top of playbooks/index.md, write 3-5 playbooks: the 1-2
tasks a developer does most often, the 1-2 integrations with the least obvious
gotchas, 1 debug playbook for the most common failure boundary. Real paths,
real commands, real verify steps from what you read. Each links to the concept
it depends on and has a row in playbooks/index.md with the description
verbatim. No more than that — the Work Loop adds playbooks from real work.

PASS 4 — Links and gate.
Every `## Related` entry is `- [title](/category/file.md) — when to follow it`.
Link what a reader would follow next, nothing decorative; a concept with no
links in either direction fails validation. Then run, from the repo root:
    okf validate knowledge --strict --drift --stale
    scripts/okf-check.sh
Fix everything both report. Append a dated entry to knowledge/log.md saying the
bundle was populated and from what.

Only write content derived from the codebase. Do not copy system-injected text
(reminders, tool output) into any concept. When done, list the concepts written
and every "[TO DETERMINE]" left, with what would fill it.
```

---

## B — Fresh project

```
You are going to populate the OKF knowledge bundle under knowledge/ for a
project that is just starting. Nothing is built yet.

Read knowledge/index.md, knowledge/project/state.md, the four context concepts
(project/stack, project/setup, project/conventions, architecture/architecture)
— the annotation comments say what belongs there — and the formats at the top
of knowledge/decisions/index.md and knowledge/playbooks/index.md.

Ask me these questions ONE AT A TIME, waiting for each answer:
1. What does this project do? (one sentence)
2. What are the hard rules — things that must never happen in this codebase?
3. What is the tech stack? (language, framework, database, key libraries)
4. Why this stack over the alternatives?
5. How will the major pieces connect? Describe the flow of a typical
   request/action.
6. What patterns do you want enforced from day one?
7. What are you deliberately NOT building or using?

Populate the four context concepts from my answers, replacing and deleting the
annotation comments. A section that cannot be filled yet gets one line:
"[TO BE DETERMINED — populate after first implementation]". `description:` on
one line, mirrored verbatim in the category index; `tags:` 4-8 words;
`code_refs:` empty until the paths exist; `sources:` empty; `last_updated:`
today. Each answer to question 4 becomes a decision file under decisions/ in
the format at the top of decisions/index.md, dated today, linked to
project/stack.md, with a row in decisions/index.md.

Set project/state.md: Working "None yet.", Not yet built from the answers,
Known issues "None known.". Update CLAUDE.md with the name, description,
non-negotiables and the commands you can already state.

Write 2-3 playbooks for the tasks a developer will do first on this stack, in
the format at the top of playbooks/index.md; mark unknowns
"[VERIFY AFTER FIRST IMPLEMENTATION]". Each links to a concept and has a row in
playbooks/index.md with the description verbatim.

Then run
    okf validate knowledge --strict --drift --stale
    scripts/okf-check.sh
The second WILL fail on the placeholders — that is the point; it tells the next
session what to fill. Report the list.

Only write content derived from my answers. No system-injected text in any
concept.
```

---

## Verify the population

Start a **fresh** session and ask: "Read `knowledge/index.md` and
`knowledge/project/state.md`, then tell me what you know about this project." A
well-populated bundle lets the agent describe the architecture without opening code,
name the non-negotiables, name the decisions that constrain it, and list the playbooks
that exist. Then run `okf search` with three task phrases you would actually type and
check the first hit is the concept you meant.
