#!/usr/bin/env python3
"""okf-migrate.py — mechanical half of a mex → OKF migration, straight into the okf-drift layout.

    uvx --with pyyaml python3 okf-migrate.py inventory  --mex .mex
    uvx --with pyyaml python3 okf-migrate.py resolve    --mex .mex --map map.json          # needs `mex` + a built graph
    uvx --with pyyaml python3 okf-migrate.py convert    --mex .mex --out knowledge --templates <plugin>/skills/okf-setup/templates/knowledge \
                                                        --name "Project" [--map map.json]

What it does, and does not:
  * reads frontmatter with a real YAML parser (PyYAML) but WRITES it by hand, one key per
    line, description on ONE line, quoted when needed — PyYAML's dumper folds long strings
    and that fold is what truncated 22 descriptions in the first migration (okf reads a
    description to the end of its first line);
  * name→title, triggers→tags, edges→`## Related`, grounds_to→code_refs (through the map),
    inline `[text](mex://kind:id)`→`` `text` `` (+ path when resolved);
  * context/{stack,setup,conventions} → project/, context/decisions.md → one file per
    decision under decisions/, every other context/* → architecture/, patterns/* →
    playbooks/ (README/INDEX dropped: the format guide comes from the plugin templates),
    ROUTER's "Current Project State" → project/state.md;
  * writes the four category indexes and the root index in the plugin's shape, and a
    dated log.md entry with the full node→path provenance table;
  * never deletes .mex, never touches CLAUDE.md, .gitignore, orca.yaml or any file outside
    --out. Those are the skill's steps, done by a reader.
Bodies are preserved verbatim apart from the mex:// rewrite. Anything it could not map
is printed as NOTE and written into log.md — nothing is silently dropped.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

TODAY = dt.date.today().isoformat()
ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
YM = re.compile(r"\b(\d{4}-\d{2})\b")
MEX_LINK = re.compile(r"\[([^\]]+)\]\(mex://([a-z]+):([0-9a-f]+)\)")
MEX_BARE = re.compile(r"mex://([a-z]+):([0-9a-f]+)")
STATE_DESC = "What is working, what is not yet built, and what is known to be broken — a snapshot, not a history."

notes: list[str] = []


def note(msg: str) -> None:
    notes.append(msg)
    print(f"NOTE  {msg}")


# ---------- reading ----------

def split(text: str) -> tuple[dict[str, Any], str, bool]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        raise ValueError("frontmatter never closes")
    data = yaml.safe_load("".join(lines[1:close])) or {}
    return data, "".join(lines[close + 1:]), True


def one_line(s: Any) -> str:
    return " ".join(str(s).split())


# ---------- writing (by hand: no folding, ever) ----------

def yq(s: str) -> str:
    """Quote a scalar iff YAML or a naive parser could misread it."""
    if s == "" or s[0] in "[{&*!|>'\"%@`-?:" or ": " in s or " #" in s or s.endswith(":") or s.lower() in {"yes", "no", "true", "false", "null", "~"}:
        return "'" + s.replace("'", "''") + "'"
    return s


def frontmatter(d: dict[str, Any]) -> str:
    order = ["type", "title", "description", "status", "date", "tags", "sources", "code_refs", "last_updated", "stale_after"]
    out = ["---"]
    for k in order:
        if k not in d:
            continue
        v = d[k]
        if isinstance(v, list):
            out.append(f"{k}: []" if not v else f"{k}:")
            for x in v:
                if isinstance(x, dict):            # sources: okf --strict wants {resource: path}
                    first, *rest = x.items()
                    out.append(f"- {first[0]}: {yq(str(first[1]))}")
                    out.extend(f"  {kk}: {yq(str(vv))}" for kk, vv in rest)
                else:
                    out.append(f"- {yq(str(x))}")
        else:
            out.append(f"{k}: {yq(str(v))}")
    out.append("---")
    return "\n".join(out) + "\n"


def write(path: Path, fm: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = body.lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"
    path.write_text(frontmatter(fm) + "\n" + body)


def plus_months(n: int) -> str:
    d = dt.date.today()
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return dt.date(y, m, min(d.day, 28)).isoformat()


def iso_date(raw: Any, where: str) -> str:
    s = str(raw or "")
    if m := ISO.search(s):
        return m.group(1)
    if m := YM.search(s):
        note(f"{where}: date '{s}' has no day — using {m.group(1)}-01")
        return f"{m.group(1)}-01"
    note(f"{where}: no usable date in '{s}' — using today")
    return TODAY


def slugify(title: str) -> str:
    s = re.sub(r"[`*_]", "", title).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "decision"


# ---------- mapping ----------

def new_path(old: str, decisions_note: bool = True) -> str | None:
    """Old scaffold-relative target → new bundle-absolute path, or None if it has no concept."""
    old = old.strip().lstrip("./")
    if old.startswith("context/"):
        f = old[len("context/"):]
        if f == "decisions.md":
            return None                       # split into decisions/*; no single concept
        return f"/project/{f}" if f in {"stack.md", "setup.md", "conventions.md"} else f"/architecture/{f}"
    if old.startswith("patterns/"):
        f = old[len("patterns/"):]
        if f in {"README.md", "INDEX.md"}:
            return None                       # format guide lives in playbooks/index.md now
        return f"/playbooks/{f}"
    if old in {"ROUTER.md", "AGENTS.md"}:
        return "/project/state.md" if old == "ROUTER.md" else None
    return None


# ---------- commands ----------

def cmd_inventory(mex: Path) -> None:
    docs = sorted(p for p in mex.rglob("*.md"))
    print(f"documents: {len(docs)}")
    body_only, groundings, anchors, folded = [], 0, 0, []
    for p in docs:
        t = p.read_text()
        d, body, has = split(t)
        if not has:
            body_only.append(str(p.relative_to(mex)))
            continue
        groundings += len(d.get("grounds_to") or [])
        anchors += len(MEX_BARE.findall(body))
        desc = d.get("description")
        raw = re.search(r"^description:\s*(.*)$", t, re.M)
        if raw and desc and one_line(desc) != raw.group(1).strip().strip("'\"") and "\n" in str(desc):
            folded.append(str(p.relative_to(mex)))
    print(f"body-only (no frontmatter): {body_only}")
    print(f"grounds_to entries: {groundings}   inline mex:// anchors in prose: {anchors}")
    dec = mex / "context/decisions.md"
    if dec.exists():
        txt = dec.read_text()
        print(f"decisions: {len(re.findall(r'^### ', txt, re.M))} entries, {len(re.findall(r'Superseded', txt))} mention supersession")
    st = subprocess.run(["mex", "graph", "status"], capture_output=True, text=True)
    print("mex graph status:", (st.stdout or st.stderr).strip().splitlines()[0] if (st.stdout or st.stderr) else "mex not on PATH")
    print("graph is REQUIRED for `resolve`: without it every grounds_to and mex:// anchor is lost. Build it first (deps installed, `mex graph rebuild`).")


def resolve_node(kind: str, nid: str) -> dict[str, Any]:
    r = subprocess.run(["mex", "graph", "get", f"{kind}:{nid}", "--detail", "source"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if m.get("type") == "source" and m.get("filePath"):
            # Measured on mex 0.8.2: the `source` record has NO `name`/`symbol` field, so the
            # symbol has to come out of the first line of the matching range's content. It is
            # what `/okf-migrate` step 6 narrows drift anchors from, so losing it costs the
            # whole symbol-level binding pass.
            sym = line_no = None
            for rg in m.get("ranges") or []:
                if f"{kind}:{nid}" not in (rg.get("nodeIds") or []):
                    continue
                first = (rg.get("content") or "").splitlines()[:1]
                if not first:
                    continue
                head = re.sub(r"^\s*\d+:\s*", "", first[0])
                mm = re.search(r"(?:function|class|const|let|var|def|fn|struct|enum|trait)\s+([A-Za-z_$][\w$]*)", head) \
                     or re.match(r"(?:export\s+)?(?:async\s+)?([A-Za-z_$][\w$]*)\s*[(:=]", head)
                if mm:
                    sym, line_no = mm.group(1), rg.get("startLine")
                    break
            return {"path": m["filePath"], "symbol": sym, "line": line_no}
    return {"path": None, "error": r.stderr.strip() or f"mex exited {r.returncode} without a source record"}


def cmd_resolve(mex: Path, out: Path) -> None:
    ids: dict[str, dict[str, Any]] = {}
    for p in sorted(mex.rglob("*.md")):
        d, body, has = split(p.read_text())
        rel = str(p.relative_to(mex))
        if has:
            for g in d.get("grounds_to") or []:
                n = str(g.get("node", ""))
                if ":" in n:
                    ids.setdefault(n, {"docs": []})["docs"].append(rel)
        for kind, nid in MEX_BARE.findall(body):
            ids.setdefault(f"{kind}:{nid}", {"docs": []})["docs"].append(rel)
    for n, entry in ids.items():
        kind, nid = n.split(":", 1)
        entry.update(resolve_node(kind, nid))
        print(f"{'ok  ' if entry.get('path') else 'MISS'} {n} -> {entry.get('path') or entry.get('error')}")
    out.write_text(json.dumps(ids, indent=2, ensure_ascii=False) + "\n")
    miss = sum(1 for e in ids.values() if not e.get("path"))
    print(f"resolved {len(ids) - miss}/{len(ids)} node ids -> {out}")


MD_LINK = re.compile(r"\[([^\]]*)\]\((?!<)([^)\s]+\.md(?:#[^)\s]*)?)\)")


def rewrite_outbound_links(body: str, new_path: str, where: str, sources: list[str]) -> str:
    """okf validates every `[t](x.md)` as a concept link; a relative one that leaves the
    bundle is 'broken'. Measured escape: the angle-bracket destination `[t](<x.md>)` is
    ignored by okf and still a link everywhere else. Record the target under sources."""
    depth = new_path.strip("/").count("/")            # segments below the bundle root

    def repl(m: re.Match) -> str:
        text, target = m.group(1), m.group(2)
        path_only = target.split("#", 1)[0]
        ups = 0
        p = path_only
        while p.startswith("../"):
            ups += 1
            p = p[3:]
        if ups <= depth:                               # stays inside the bundle: a concept link, leave it
            return m.group(0)
        repo_rel = p                                   # what remains after climbing out of the bundle
        if {"resource": repo_rel} not in sources:
            sources.append({"resource": repo_rel})     # okf --strict: each source is {resource: …}
        note(f"{where}: link to '{repo_rel}' leaves the bundle — kept as an angle-bracket link and listed under sources")
        return f"[{text}](<{target}>)"
    return MD_LINK.sub(repl, body)


def rewrite_anchors(body: str, mapping: dict[str, Any], where: str, refs: list[str]) -> str:
    def repl(m: re.Match) -> str:
        text, kind, nid = m.group(1), m.group(2), m.group(3)
        e = mapping.get(f"{kind}:{nid}") or {}
        if e.get("path"):
            if e["path"] not in refs:
                refs.append(e["path"])
            return f"{text} (`{e['path']}`)"
        note(f"{where}: inline anchor {kind}:{nid} ('{text}') unresolved — kept as plain text")
        return text
    body = MEX_LINK.sub(repl, body)
    return MEX_BARE.sub(lambda m: (note(f"{where}: bare mex://{m.group(1)}:{m.group(2)} removed"), "")[1], body)


def base_fm(d: dict[str, Any], typ: str, where: str, mapping: dict[str, Any], body: str, new_path_of: str = "/x/x.md") -> tuple[dict[str, Any], str]:
    title = d.get("title") or d.get("name") or where
    desc = one_line(d.get("description") or "")
    if not desc:
        note(f"{where}: no description — fill it before the gate")
        desc = "[TO DETERMINE]"
    tags: list[str] = []
    for t in d.get("triggers") or d.get("tags") or []:
        t = str(t).lower().strip()
        if t and t not in tags:
            tags.append(t)
    refs: list[str] = []
    for g in d.get("grounds_to") or []:
        e = mapping.get(str(g.get("node", ""))) or {}
        if e.get("path") and e["path"] not in refs:
            refs.append(e["path"])
    body = rewrite_anchors(body, mapping, where, refs)
    sources: list[dict[str, str]] = []
    body = rewrite_outbound_links(body, new_path_of, where, sources)
    fm = {"type": typ, "title": str(title), "description": desc}
    if tags:
        fm["tags"] = tags
    fm["sources"] = sources
    fm["code_refs"] = refs
    lu = d.get("last_updated")
    fm["last_updated"] = ISO.search(str(lu)).group(1) if lu and ISO.search(str(lu)) else TODAY
    return fm, body


def related_section(edges: list[dict[str, Any]], where: str, titles: dict[str, str]) -> str:
    rows = []
    for e in edges or []:
        tgt = new_path(str(e.get("target", "")))
        if tgt is None:
            note(f"{where}: edge to '{e.get('target')}' has no concept in the new layout — dropped (index/format-guide/decision-log targets are not links)")
            continue
        rows.append(f"- [{titles.get(tgt, Path(tgt).stem)}]({tgt}) — {one_line(e.get('condition', ''))}")
    return ("\n## Related\n\n" + "\n".join(rows) + "\n") if rows else ""


def split_decisions(text: str) -> list[dict[str, Any]]:
    _, body, _ = split(text)
    parts = re.split(r"^### ", body, flags=re.M)[1:]
    out = []
    for p in parts:
        title, _, rest = p.partition("\n")
        fields: dict[str, str] = {}
        for k in ("Date", "Status", "Decision"):
            if m := re.search(rf"^\*\*{k}:\*\*\s*(.*)$", rest, re.M):
                fields[k] = m.group(1).strip()
        out.append({"title": title.strip(), "body": rest.strip("\n"), **fields})
    return out


def cmd_convert(mex: Path, out: Path, templates: Path, name: str, mapping: dict[str, Any]) -> None:
    if out.exists():
        sys.exit(f"refusing: {out} exists")
    titles: dict[str, str] = {}
    docs: list[tuple[Path, str, dict[str, Any], str]] = []   # (old, newpath, data, body)

    # pass 1: collect concepts and their new paths/titles
    for p in sorted((mex / "context").glob("*.md")) + sorted((mex / "patterns").glob("*.md")):
        rel = p.relative_to(mex).as_posix()
        np_ = new_path(rel)
        if np_ is None:
            continue
        d, body, has = split(p.read_text())
        if not has:
            note(f"{rel}: no frontmatter — skipped (only README/INDEX are expected body-only)")
            continue
        titles[np_] = str(d.get("title") or d.get("name") or p.stem)
        docs.append((p, np_, d, body))
    titles["/project/state.md"] = "state"

    # decisions
    dec_file = mex / "context/decisions.md"
    decisions: list[dict[str, Any]] = split_decisions(dec_file.read_text()) if dec_file.exists() else []
    dec_edges = (split(dec_file.read_text())[0].get("edges") if dec_file.exists() else []) or []
    slugs = {d["title"]: slugify(d["title"]) for d in decisions}
    for d in decisions:
        titles[f"/decisions/{slugs[d['title']]}.md"] = d["title"]

    # pass 2: write concepts
    for p, np_, d, body in docs:
        rel = p.relative_to(mex).as_posix()
        typ = "Playbook" if np_.startswith("/playbooks/") else "Reference"
        fm, body = base_fm(d, typ, rel, mapping, body, np_)
        body = body.rstrip("\n") + "\n" + related_section(d.get("edges") or [], rel, titles)
        write(out / np_.lstrip("/"), fm, body)
        print(f"wrote {np_}  <- {rel}")

    # decisions, one per file
    for d in decisions:
        where = f"context/decisions.md ### {d['title']}"
        slug = slugs[d["title"]]
        status_raw = d.get("Status", "Active")
        deprecated = "supersed" in status_raw.lower()
        refs: list[str] = []
        dsources: list[dict[str, str]] = []
        body = rewrite_anchors(d["body"], mapping, where, refs)
        body = rewrite_outbound_links(body, f"/decisions/{slug}.md", where, dsources)
        desc = one_line(re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", d.get("Decision", "")) or d["title"])
        fm: dict[str, Any] = {"type": "Decision", "title": d["title"], "description": desc,
                              "status": "deprecated" if deprecated else "stable",
                              "date": iso_date(d.get("Date"), where), "tags": [], "sources": dsources,
                              "code_refs": refs, "last_updated": TODAY}
        rel_rows = []
        if deprecated:
            m = re.search(r"superseded by\s*[\"“']?(.+?)[\"”']?\s*$", status_raw, re.I)
            target = slugs.get(m.group(1).strip()) if m else None
            if target:
                rel_rows.append(f"- Superseded by [{m.group(1).strip()}](/decisions/{target}.md)")
            else:
                note(f"{where}: status '{status_raw}' names a superseding decision that is not an entry — write it as its own file and link it, or the gate fails")
        for e in dec_edges:
            tgt = new_path(str(e.get("target", "")))
            if tgt:
                rel_rows.append(f"- [{titles.get(tgt, Path(tgt).stem)}]({tgt}) — {one_line(e.get('condition', ''))}")
        if not any(not r.startswith("- Superseded") for r in rel_rows):
            rel_rows.append("- [architecture](/architecture/architecture.md) — the structure this decision shapes")
            note(f"{where}: no non-decision edge inherited — linked to architecture; repoint it")
        write(out / "decisions" / f"{slug}.md", fm, f"# {d['title']}\n\n{body}\n\n## Related\n\n" + "\n".join(rel_rows) + "\n")
        print(f"wrote /decisions/{slug}.md  ({fm['status']}, {fm['date']})")
    # back-links for supersession
    for f in (out / "decisions").glob("*.md") if decisions else []:
        t = f.read_text()
        for m in re.finditer(r"Superseded by \[([^\]]+)\]\(/decisions/([^)]+)\.md\)", t):
            new = out / "decisions" / f"{m.group(2)}.md"
            if new.exists() and f"/decisions/{f.stem}.md" not in new.read_text():
                new.write_text(new.read_text().rstrip("\n") + f"\n- Supersedes [{titles.get('/decisions/' + f.stem + '.md', f.stem)}](/decisions/{f.stem}.md)\n")

    # state from ROUTER
    router = mex / "ROUTER.md"
    state_body = "**Working:**\n- [TO DETERMINE]\n\n**Not yet built:**\n- [TO DETERMINE]\n\n**Known issues:**\n- [TO DETERMINE]\n"
    if router.exists():
        _, rb, _ = split(router.read_text())
        if m := re.search(r"^## Current Project State\s*\n(.*?)(?=^## )", rb, re.M | re.S):
            state_body = re.sub(r"<!--.*?-->\s*", "", m.group(1), flags=re.S).strip("\n") + "\n"
            n_lines = len(state_body.splitlines())
            if n_lines > 30:
                note(f"ROUTER.md: Current Project State is {n_lines} lines — it is a snapshot (3-7 items per list); move the narrative to log.md")
        else:
            note("ROUTER.md: no 'Current Project State' section found — state.md carries placeholders")
        note("ROUTER.md: the Behavioural Contract is policy — it goes to CLAUDE.md as the plugin's Work Loop, not into the bundle")
    write(out / "project/state.md",
          {"type": "Reference", "title": "state", "description": STATE_DESC, "tags": ["state", "status", "known issues", "not yet built"],
           "sources": [], "code_refs": [], "last_updated": TODAY, "stale_after": plus_months(3)},
          f"# Current Project State\n\n{state_body}\n## Related\n\n- [architecture](/architecture/architecture.md) — the components these items belong to\n")
    for f, months in (("project/stack.md", 6), ("project/setup.md", 6)):
        fp = out / f
        if fp.exists():
            fp.write_text(fp.read_text().replace("\n---\n\n", f"\nstale_after: {plus_months(months)}\n---\n\n", 1))

    # indexes
    def rows(cat: str) -> list[str]:
        r = []
        for f in sorted((out / cat).glob("*.md")):
            if f.name == "index.md":
                continue
            d, _, _ = split(f.read_text())
            r.append(f"- [{d['title']}](/{cat}/{f.name}) — {d['description']}")
        return r
    (out / "project/index.md").write_text("# Project\n\n" + "\n".join(rows("project")) + "\n")
    (out / "architecture/index.md").write_text("# Architecture\n\n" + "\n".join(rows("architecture")) + "\n")
    for cat in ("decisions", "playbooks"):
        (out / cat).mkdir(exist_ok=True)
        head = (templates / cat / "index.md").read_text()
        (out / cat / "index.md").write_text(head.rstrip("\n") + "\n\n" + "\n".join(rows(cat)) + "\n")
    root = (templates / "index.md").read_text().replace("{{PROJECT_NAME}}", name)
    (out / "index.md").write_text(root)

    # log
    resolved = {k: v for k, v in mapping.items() if v.get("path")}
    unresolved = {k: v for k, v in mapping.items() if not v.get("path")}
    lines = [f"## {TODAY}", "",
             f"* **Migrated**: converted the mex scaffold under `{mex}` into this OKF bundle with okf-migrate.py — {len(docs)} context/pattern documents, {len(decisions)} decisions split into `decisions/`, ROUTER's project state into `project/state.md`.",
             f"* **Grounded**: {len(resolved)} mex node ids resolved to `code_refs`, {len(unresolved)} unresolved (recorded below; not fabricated)."]
    lines += [f"* **Note**: {n}" for n in notes]
    if mapping:
        lines += ["", "### mex node → path provenance", "", "| node | path or result | documents |", "|---|---|---|"]
        lines += [f"| `{k}` | `{v.get('path') or 'UNRESOLVED: ' + str(v.get('error'))}` | {', '.join(f'`{d}`' for d in v.get('docs', []))} |" for k, v in mapping.items()]
    (out / "log.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out}: {len(docs)} concepts + {len(decisions)} decisions + state; {len(notes)} notes in log.md")
    print("next: follow /okf-migrate's integration steps, then invoke okf-drift:okf-runtime in gate mode (CLAUDE.md, pin/workflow, .gitignore, references, drift bootstrap, rm .mex)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["inventory", "resolve", "convert"])
    ap.add_argument("--mex", type=Path, default=Path(".mex"))
    ap.add_argument("--out", type=Path, default=Path("knowledge"))
    ap.add_argument("--map", type=Path, default=None)
    ap.add_argument("--templates", type=Path, default=None)
    ap.add_argument("--name", default=Path.cwd().name)
    a = ap.parse_args()
    if a.command == "inventory":
        cmd_inventory(a.mex)
    elif a.command == "resolve":
        cmd_resolve(a.mex, a.map or Path("okf-migrate-map.json"))
    else:
        if not a.templates or not (a.templates / "index.md").exists():
            sys.exit("--templates must point at the plugin's skills/okf-setup/templates/knowledge")
        mapping = json.loads(a.map.read_text()) if a.map and a.map.exists() else {}
        if not mapping:
            note("no --map: every grounds_to and mex:// anchor is UNRESOLVED — run `resolve` first while mex and its graph still exist")
        cmd_convert(a.mex, a.out, a.templates, a.name, mapping)


if __name__ == "__main__":
    main()
