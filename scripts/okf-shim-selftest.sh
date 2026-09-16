#!/bin/sh
# okf-shim-selftest.sh [tag] — four things a consumer repo's gate must do, run against a
# REAL tag so the fetch is real. Each was a measured defect before 0.6.0:
#
#   (a) a truncated cached script is rejected — 2 lines of a 221-line script used to be
#       accepted ("first line starts with #!"), cached forever, and the gate exited 0
#       having checked nothing: silently green.
#   (b) a cached script with one byte changed is rejected.
#   (c) a lockfile whose sha256 disagrees with the tag's real content is rejected on
#       download — a tag can be moved, so the tag alone pins nothing.
#   (d) the happy path still fetches, verifies, caches and runs the gate.
#
# SHIM=path/to/okf-shim.sh overrides which shim is under test (default scripts/okf-shim.sh).
set -eu
TAG=${1:-v0.5.1}
SHIM=${SHIM:-scripts/okf-shim.sh}
raw="https://raw.githubusercontent.com/alvistar/okf-drift/$TAG/scripts"
if command -v shasum >/dev/null 2>&1; then hash_of() { shasum -a 256 "$1" | cut -d' ' -f1; }
else hash_of() { sha256sum "$1" | cut -d' ' -f1; }; fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl -fsSL "$raw/okf-check.sh" -o "$work/real" || { echo "selftest: cannot fetch $raw/okf-check.sh" >&2; exit 1; }
good=$(hash_of "$work/real")
echo "selftest: okf-check.sh at $TAG is sha256 $good"

repo="$work/repo"
fixture() {  # $1 = the sha256 to pin
  rm -rf "$repo"; mkdir -p "$repo/scripts"
  cp "$SHIM" "$repo/scripts/okf-shim.sh"
  printf '#!/bin/sh\nexec "$(dirname "$0")/okf-shim.sh" okf-check.sh "$@"\n' > "$repo/scripts/okf-check.sh"
  chmod +x "$repo/scripts/okf-shim.sh" "$repo/scripts/okf-check.sh"
  printf '%s\n%s  okf-check.sh\n' "$TAG" "$1" > "$repo/.okf-drift-version"
}
# No bundle is present, so the gate's own "no bundle at knowledge" is the ONLY evidence it
# ran, and its absence the only evidence it did not.
run() { ( cd "$repo" && XDG_CACHE_HOME="$repo/cache" ./scripts/okf-check.sh knowledge ) >"$work/out" 2>&1 && echo 0 || echo $?; }
ran()    { grep -q 'no bundle at knowledge' "$work/out"; }
fail()   { echo "FAIL $*" >&2; sed 's/^/    | /' "$work/out" >&2; exit 1; }
cache="$repo/cache/okf-drift/$TAG/okf-check.sh"

# (d) happy path
fixture "$good"
rc=$(run)
ran || fail "(d) the gate did not run (rc=$rc)"
[ -x "$cache" ] || fail "(d) nothing was cached at $cache"
echo "ok (d) happy path — fetched, hash-verified, cached, and the gate ran"

# (a) truncated cache
head -2 "$cache" > "$work/trunc" && cp "$work/trunc" "$cache" && chmod +x "$cache"
rc=$(run)
[ "$rc" = 2 ] || fail "(a) a truncated cached script gave rc=$rc, want 2"
grep -q 'is damaged' "$work/out" || fail "(a) no expected-vs-found line"
if ran; then fail "(a) the gate ran on a truncated script"; fi
echo "ok (a) a truncated cached script is rejected with exit 2, and the gate does not run"

# (b) one byte changed in the cache
fixture "$good"; rc=$(run); ran || fail "(b) setup: the gate did not run (rc=$rc)"
printf 'X' | dd of="$cache" bs=1 seek=120 conv=notrunc status=none 2>/dev/null ||
  printf 'X' | dd of="$cache" bs=1 seek=120 conv=notrunc 2>/dev/null
rc=$(run)
[ "$rc" = 2 ] || fail "(b) a one-byte-changed cached script gave rc=$rc, want 2"
grep -q 'is damaged' "$work/out" || fail "(b) no expected-vs-found line"
if ran; then fail "(b) the gate ran on a modified script"; fi
echo "ok (b) a cached script with one byte changed is rejected with exit 2"

# (c) a lockfile that disagrees with the tag's real content, on a cold cache
fixture "0000000000000000000000000000000000000000000000000000000000000000"
rc=$(run)
[ "$rc" = 2 ] || fail "(c) a wrong pin gave rc=$rc, want 2"
grep -q "sha256 expected 0000" "$work/out" || fail "(c) no expected-vs-found line"
if ran; then fail "(c) the gate ran on an unverified download"; fi
[ ! -e "$cache" ] || fail "(c) an unverified download was cached"
echo "ok (c) a lockfile disagreeing with the tag's content is rejected on download"

# A lockfile with a tag but no pin line for the requested script is an error, not a fetch.
fixture "$good"; printf '%s\n' "$TAG" > "$repo/.okf-drift-version"
rc=$(run)
[ "$rc" = 2 ] || fail "(e) an unpinned script gave rc=$rc, want 2"
grep -q 'pins no sha256' "$work/out" || fail "(e) no explanation"
echo "ok (e) a lockfile with no pin line for the script is an error"

echo "selftest: all checks passed against $TAG using $SHIM"
