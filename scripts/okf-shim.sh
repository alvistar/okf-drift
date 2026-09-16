#!/bin/sh
# okf-shim.sh — run an okf-drift script at the tag AND sha256 pinned in .okf-drift-version.
#
#   sh okf-shim.sh [--repo-root <path>] <script-name> [args...]
# Root: explicit flag, legacy scripts/ location with a pin, then cwd's Git root.
# The runtime always runs at that root; root-aware use requires a v0.7.0+ pin.
#
# .okf-drift-version is a lockfile: line 1 is the tag, every other line is one
# `<sha256>  <name>` pair in `shasum -a 256` output format (so `shasum -c` reads it too).
# A tag is not fixed content — it can be moved — so the tag alone pins nothing. The
# content pin is the sha256, and it is re-checked on EVERY run, not only on download:
# a damaged cache must be an error, never a gate that silently checked nothing.
# $OKF_DRIFT_ROOT (a local plugin checkout, for developing the plugin itself) wins over
# the pin and is EXEMPT from the hash check by design — the file being edited cannot match.
set -eu
die() { echo "okf-shim: $*" >&2; exit 2; }
root=''
root_aware=0
if [ "${1:-}" = --repo-root ]; then
  [ "$#" -ge 2 ] && [ -n "$2" ] || die '--repo-root needs a directory'
  root=$2
  root_aware=1
  shift 2
fi
[ "$#" -ge 1 ] || die 'usage: okf-shim.sh [--repo-root <path>] <script-name> [args...]'
name=$1
shift
case "$name" in okf-*.sh|okf-*.py) ;; *) die "invalid script name: $name" ;; esac
case "$name" in */*|*..*) die "invalid script name: $name" ;; esac
if [ -z "$root" ]; then
  legacy=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
  if [ "$(basename "$(dirname "$0")")" = scripts ] && [ -f "$legacy/.okf-drift-version" ]; then
    root=$legacy
  else
    root=$(git rev-parse --show-toplevel 2>/dev/null) || die 'no Git root; pass --repo-root <path>'
    root_aware=1
  fi
fi
root=$(CDPATH= cd -- "$root" && pwd) || die "cannot enter repository: $root"
# Resolve a relative development override before changing cwd.
if [ -n "${OKF_DRIFT_ROOT:-}" ]; then
  dev=$(CDPATH= cd -- "$OKF_DRIFT_ROOT" && pwd) || die 'invalid OKF_DRIFT_ROOT'
  [ -x "$dev/scripts/$name" ] || die "OKF_DRIFT_ROOT has no executable scripts/$name"
  echo "okf-shim: development override $dev (pin verification bypassed)" >&2
  cd "$root"
  exec "$dev/scripts/$name" "$@"
fi
cd "$root"
lock="$root/.okf-drift-version"
[ -s "$lock" ] || die "$lock is missing or empty"
ver=$(sed -n '1p' "$lock")
printf '%s\n' "$ver" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$' || die "$lock has no valid vMAJOR.MINOR.PATCH tag on line 1"
if [ "$root_aware" -eq 1 ]; then
  printf '%s\n' "$ver" | awk -F. '{ sub(/^v/, "", $1); exit !($1+0 > 0 || $2+0 >= 7) }' ||
    die 'root-aware integration requires v0.7.0 or newer; upgrade explicitly with okf-pin.sh after publication'
fi
want=$(awk -v n="$name" '
  NR > 1 && $2 == n {
    count++; if (NF != 2 || length($1) != 64 || $1 ~ /[^0-9a-f]/) bad=1
    digest=$1
  }
  END { if (count != 1 || bad) exit 1; print digest }
' "$lock") || die "$lock needs exactly one valid sha256 for $name"
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
