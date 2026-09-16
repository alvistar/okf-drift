#!/bin/sh
# okf-scaffold.sh — lay down the fixed OKF v0.2 knowledge bundle in a repository.
#
#   okf-scaffold.sh [--name "Project Name"] [--force] [target-dir]
#
# Copies the templates next to this script into <target-dir>/knowledge/, substituting
# {{PROJECT_NAME}}, {{DATE}}, {{STALE_3M}} and {{STALE_6M}}, and runs
# `okf validate --strict --drift` on the result. Refuses to touch an existing knowledge/
# unless --force is given, and even then only adds files it does not find — it never
# overwrites a concept you may have populated.
#
# It does NOT edit CLAUDE.md: the section to merge is printed at the end.
set -eu

# This script lives at <plugin>/scripts/; the templates belong to the okf-setup skill.
here=$(cd "$(dirname "$0")" && pwd)
templates="$here/../skills/okf-setup/templates/knowledge"
claude_section="$here/../skills/okf-setup/templates/CLAUDE-knowledge-section.md"

name=""
force=0
target="."
while [ $# -gt 0 ]; do
  case "$1" in
    --name) name="$2"; shift 2 ;;
    --name=*) name="${1#--name=}"; shift ;;
    --force) force=1; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) target="$1"; shift ;;
  esac
done

target=$(cd "$target" && pwd)
bundle="$target/knowledge"
[ -n "$name" ] || name=$(basename "$target")
date=$(date +%Y-%m-%d)
# BSD date (macOS) takes -v, GNU date takes -d.
plus_months() {
  date -v+"$1"m +%Y-%m-%d 2>/dev/null || date -d "+$1 months" +%Y-%m-%d
}
stale3=$(plus_months 3)
stale6=$(plus_months 6)

if [ -e "$bundle" ] && [ "$force" -eq 0 ]; then
  echo "refusing: $bundle already exists (use --force to add only the missing files)" >&2
  exit 1
fi

# Walk the template tree; copy each file with substitution unless it already exists.
(cd "$templates" && find . -type f -name '*.md' | sort) | while IFS= read -r rel; do
  rel=${rel#./}
  dest="$bundle/$rel"
  if [ -e "$dest" ]; then
    echo "  = kept    knowledge/$rel"
    continue
  fi
  mkdir -p "$(dirname "$dest")"
  # sed's delimiter is | so a name containing / is safe; one containing | is not.
  sed -e "s|{{PROJECT_NAME}}|$name|g" -e "s|{{DATE}}|$date|g" \
      -e "s|{{STALE_3M}}|$stale3|g" -e "s|{{STALE_6M}}|$stale6|g" \
      "$templates/$rel" > "$dest"
  echo "  + created knowledge/$rel"
done

echo
if command -v okf >/dev/null 2>&1; then
  echo "okf $(okf version 2>/dev/null | head -1)"
  (cd "$target" && okf validate knowledge --strict --drift) || {
    echo "validation FAILED — the scaffold should validate clean before population; report this" >&2
    exit 1
  }
else
  echo "okf is not on PATH — install it (go install github.com/okf-memory/okf-agent-memory/cmd/okf@latest)" >&2
  echo "and run: okf validate knowledge --strict --drift" >&2
fi

echo
echo "Next:"
echo "  1. Merge this into $target/CLAUDE.md (keep any existing identity/commands section):"
echo "       $claude_section"
echo "  2. Copy the gate into the repo and run it — it FAILS until the bundle is populated:"
echo "       cp $here/okf-check.sh $target/scripts/okf-check.sh"
echo "  3. Populate with references/populate-prompt.md from the okf-setup skill."
