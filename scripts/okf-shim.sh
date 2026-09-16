#!/bin/sh
# okf-shim.sh — run an okf-drift script at the tag pinned in .okf-drift-version.
#
#   okf-shim.sh <script-name> [args...]        e.g. okf-shim.sh okf-check.sh knowledge
#
# Copy this and a two-line wrapper per script into the consumer repo, instead of copying
# the scripts themselves: a vendored gate drifts from the plugin silently, a pinned one
# moves only when .okf-drift-version does. Resolution order: $OKF_DRIFT_ROOT (a local
# plugin checkout, for developing the plugin itself), then a cache keyed by the tag,
# fetched once from raw.githubusercontent.com. A 404 is fatal — running nothing must
# never look like a clean gate.
set -eu
name=${1:?usage: okf-shim.sh <script-name> [args...]}
shift
root=$(cd "$(dirname "$0")/.." && pwd)
if [ -n "${OKF_DRIFT_ROOT:-}" ] && [ -x "$OKF_DRIFT_ROOT/scripts/$name" ]; then
  exec "$OKF_DRIFT_ROOT/scripts/$name" "$@"
fi
[ -f "$root/.okf-drift-version" ] || { echo "okf-shim: no $root/.okf-drift-version" >&2; exit 2; }
ver=$(sed -e 's/[[:space:]]*$//' -e '/^$/d' "$root/.okf-drift-version" | head -1)
[ -n "$ver" ] || { echo "okf-shim: $root/.okf-drift-version is empty" >&2; exit 2; }
cached="${XDG_CACHE_HOME:-$HOME/.cache}/okf-drift/$ver/$name"
if [ ! -x "$cached" ]; then
  url="https://raw.githubusercontent.com/alvistar/okf-drift/$ver/scripts/$name"
  mkdir -p "$(dirname "$cached")"
  curl -fsSL "$url" -o "$cached.part" || { rm -f "$cached.part"; echo "okf-shim: cannot fetch $url" >&2; exit 2; }
  head -1 "$cached.part" | grep -q '^#!' || { rm -f "$cached.part"; echo "okf-shim: $url is empty or not a script" >&2; exit 2; }
  chmod +x "$cached.part" && mv "$cached.part" "$cached"
fi
exec "$cached" "$@"
