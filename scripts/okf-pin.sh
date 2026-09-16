#!/bin/sh
# okf-pin.sh <tag> [repo-root] — write a consumer repo's .okf-drift-version from the
# SHA256SUMS asset of that release. Run it in the consumer repo, never write the file by
# hand: a hand-copied digest is a digest of whatever you happened to download.
#
#   sh "$PLUGIN_ROOT/scripts/okf-pin.sh" v0.7.0 "$REPO_ROOT"
# Resolve PLUGIN_ROOT from the host-supplied skill directory; it is not implicit.
set -eu
tag=${1:?usage: okf-pin.sh <tag> [repo-root]}
root=${2:-.}
die() { echo "okf-pin: $*" >&2; exit 2; }
printf '%s\n' "$tag" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$' || die 'expected vMAJOR.MINOR.PATCH tag'
[ ! -L "$root/.okf-drift-version" ] || die "$root/.okf-drift-version is a symlink"
tmp=$(mktemp "${TMPDIR:-/tmp}/okf-pin-XXXXXX") || { echo "okf-pin: mktemp failed" >&2; exit 2; }
trap 'rm -f "$tmp"' EXIT
if ! { command -v gh >/dev/null 2>&1 &&
       gh release download "$tag" -R alvistar/okf-drift -p SHA256SUMS -O "$tmp" --clobber >/dev/null 2>&1; }; then
  url="https://github.com/alvistar/okf-drift/releases/download/$tag/SHA256SUMS"
  curl -fsSL "$url" -o "$tmp" || { echo "okf-pin: cannot fetch $url" >&2; exit 2; }
fi
[ -s "$tmp" ] || { echo "okf-pin: SHA256SUMS for $tag is empty" >&2; exit 2; }
awk '
  NF != 2 || length($1) != 64 || $1 ~ /[^0-9a-f]/ || $2 !~ /^okf-[a-z0-9-]+\.(sh|py)$/ { bad=1 }
  { if (seen[$2]++) bad=1 }
  END { if (bad || !seen["okf-shim.sh"] || !seen["okf-check.sh"] ||
            !seen["okf-recall.sh"] || !seen["okf-drift-bootstrap.sh"]) exit 1 }
' "$tmp" || die "SHA256SUMS for $tag needs unique valid hashes including shim, check, recall and drift-bootstrap"
# Stage alongside the destination so a failed download/validation never truncates its pin.
staged=$(mktemp "$root/.okf-drift-version.XXXXXX") || die "cannot stage pin in $root"
trap 'rm -f "$tmp" "$staged"' EXIT
{ printf '%s\n' "$tag"; cat "$tmp"; } >| "$staged"
mv "$staged" "$root/.okf-drift-version"
echo "okf-pin: $root/.okf-drift-version pinned to $tag, $(grep -c . "$tmp") script(s)"
