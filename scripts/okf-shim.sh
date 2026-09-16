#!/bin/sh
# okf-shim.sh — run an okf-drift script at the tag AND sha256 pinned in .okf-drift-version.
#
#   okf-shim.sh <script-name> [args...]        e.g. okf-shim.sh okf-check.sh knowledge
#
# .okf-drift-version is a lockfile: line 1 is the tag, every other line is one
# `<sha256>  <name>` pair in `shasum -a 256` output format (so `shasum -c` reads it too).
# A tag is not fixed content — it can be moved — so the tag alone pins nothing. The
# content pin is the sha256, and it is re-checked on EVERY run, not only on download:
# a damaged cache must be an error, never a gate that silently checked nothing.
# $OKF_DRIFT_ROOT (a local plugin checkout, for developing the plugin itself) wins over
# the pin and is EXEMPT from the hash check by design — the file being edited cannot match.
set -eu
name=${1:?usage: okf-shim.sh <script-name> [args...]}
shift
root=$(cd "$(dirname "$0")/.." && pwd)
if [ -n "${OKF_DRIFT_ROOT:-}" ] && [ -x "$OKF_DRIFT_ROOT/scripts/$name" ]; then
  exec "$OKF_DRIFT_ROOT/scripts/$name" "$@"
fi
die() { echo "okf-shim: $*" >&2; exit 2; }
lock="$root/.okf-drift-version"
[ -s "$lock" ] || die "$lock is missing or empty"
ver=$(sed -e 's/[[:space:]]*$//' -e '/^$/d' "$lock" | head -1)
[ -n "$ver" ] || die "$lock has no tag on line 1"
want=$(awk -v n="$name" '$2 == n { print $1; exit }' "$lock")
[ -n "$want" ] || die "$lock pins no sha256 for $name — expected a '<sha256>  $name' line"
if command -v shasum >/dev/null 2>&1; then   sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
elif command -v sha256sum >/dev/null 2>&1; then sha() { sha256sum "$1" | cut -d' ' -f1; }
else die "neither shasum nor sha256sum is available; $name cannot be verified"; fi
cached="${XDG_CACHE_HOME:-$HOME/.cache}/okf-drift/$ver/$name"
if [ ! -f "$cached" ]; then
  url="https://raw.githubusercontent.com/alvistar/okf-drift/$ver/scripts/$name"
  mkdir -p "$(dirname "$cached")"
  # A unique temp file, not a fixed "$cached.part": several worktrees of the same repo
  # run their first gate concurrently and would otherwise write one another's download.
  tmp=$(mktemp "$(dirname "$cached")/.$name.XXXXXX") || die "mktemp failed under $(dirname "$cached")"
  curl -fsSL "$url" -o "$tmp" || { rm -f "$tmp"; die "cannot fetch $url"; }
  [ -s "$tmp" ] || { rm -f "$tmp"; die "$url arrived empty"; }
  got=$(sha "$tmp")
  [ "$got" = "$want" ] || { rm -f "$tmp"; die "$name at $ver: sha256 expected $want, downloaded $got"; }
  chmod +x "$tmp" && mv "$tmp" "$cached"
fi
got=$(sha "$cached")
[ "$got" = "$want" ] || die "cached $cached is damaged: sha256 expected $want, found $got"
[ -x "$cached" ] || chmod +x "$cached"
exec "$cached" "$@"
