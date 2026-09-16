#!/bin/sh
# okf-pin.sh <tag> [repo-root] — write a consumer repo's .okf-drift-version from the
# SHA256SUMS asset of that release. Run it in the consumer repo, never write the file by
# hand: a hand-copied digest is a digest of whatever you happened to download.
#
#   "${CLAUDE_PLUGIN_ROOT}/scripts/okf-pin.sh" v0.6.0
set -eu
tag=${1:?usage: okf-pin.sh <tag> [repo-root]}
root=${2:-.}
tmp=$(mktemp "${TMPDIR:-/tmp}/okf-pin-XXXXXX") || { echo "okf-pin: mktemp failed" >&2; exit 2; }
trap 'rm -f "$tmp"' EXIT
if ! { command -v gh >/dev/null 2>&1 &&
       gh release download "$tag" -R alvistar/okf-drift -p SHA256SUMS -O "$tmp" --clobber >/dev/null 2>&1; }; then
  url="https://github.com/alvistar/okf-drift/releases/download/$tag/SHA256SUMS"
  curl -fsSL "$url" -o "$tmp" || { echo "okf-pin: cannot fetch $url" >&2; exit 2; }
fi
[ -s "$tmp" ] || { echo "okf-pin: SHA256SUMS for $tag is empty" >&2; exit 2; }
grep -q '^[0-9a-f]\{64\}  okf-check\.sh$' "$tmp" ||
  { echo "okf-pin: SHA256SUMS for $tag has no 'okf-check.sh' line" >&2; exit 2; }
{ printf '%s\n' "$tag"; cat "$tmp"; } > "$root/.okf-drift-version"
echo "okf-pin: $root/.okf-drift-version pinned to $tag, $(grep -c . "$tmp") script(s)"
