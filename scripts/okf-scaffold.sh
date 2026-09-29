#!/bin/sh
# okf-scaffold.sh — lay down the fixed OKF v0.2 knowledge bundle in a repository.
#
#   okf-scaffold.sh [--name "Project Name"] [--profile code|wiki] [--force] [target-dir]
#
# --profile wiki lays down the bundle for a knowledge base that describes no code
# (reference/, playbooks/, decisions/, no project snapshot, no code_refs) and writes
# `.okf-profile` beside it, which the gate and recall read. Default: code.
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
profile=code
force=0
target="."
while [ $# -gt 0 ]; do
  case "$1" in
    --name) name="$2"; shift 2 ;;
    --name=*) name="${1#--name=}"; shift ;;
    --profile) [ $# -ge 2 ] || { echo "--profile needs a value (code or wiki)" >&2; exit 2; }; profile="$2"; shift 2 ;;
    --profile=*) profile="${1#--profile=}"; shift ;;
    --force) force=1; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) target="$1"; shift ;;
  esac
done

case "$profile" in
  code) ;;
  wiki) templates="$here/../skills/okf-setup/templates-wiki/knowledge" ;;
  *) echo "unknown profile: $profile (expected code or wiki)" >&2; exit 2 ;;
esac

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

# The profile file is read by the gate and recall and switches checks off, so the scaffold
# never lets it disagree with what is being laid down — refused here, before anything is
# written, so a refusal leaves nothing half-done behind.
declared=""
[ -f "$target/.okf-profile" ] && declared=$(tr -d '[:space:]' < "$target/.okf-profile")
if [ -n "$declared" ] && [ "$declared" != "$profile" ]; then
  echo "refusing: $target/.okf-profile declares '$declared', not '$profile'" >&2
  exit 1
fi
if [ "$profile" = wiki ]; then
  for marker in drift.lock .okf-drift-version knowledge/project/state.md; do
    if [ -e "$target/$marker" ]; then
      echo "refusing: $target/$marker says this is a code repository; a wiki profile would switch off its drift, snapshot and code_refs warnings" >&2
      exit 1
    fi
  done
fi

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

if [ "$profile" = wiki ]; then
  printf 'wiki\n' > "$target/.okf-profile"
  echo "  + wrote   .okf-profile (wiki)"
fi

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
if [ "$profile" = wiki ]; then
  echo "Next:"
  echo "  1. Add the categories this knowledge base needs (see knowledge/reference/index.md)."
  echo "  2. Write the first concepts; the gate FAILS on a bundle with none."
  echo "  3. Run the gate: okf-drift:okf-runtime in gate mode (pin >= v0.11.0 with okf-pin.sh)"
  echo "  4. Add a Knowledge base section to CLAUDE.md: see /okf-setup, Profile: wiki."
  exit 0
fi
echo "Next:"
echo "  1. Follow /okf-setup Step 3: preflight the plugin-only integration helper with"
echo "     an explicit published pin >= v0.7.0 (no consumer scripts). Instructions:"
echo "       $claude_section"
echo "  2. Invoke okf-drift:okf-runtime in gate mode — it FAILS until populated;"
echo "     verify that the pinned gate actually ran."
echo "  3. Populate with references/populate-prompt.md from the okf-setup skill."
