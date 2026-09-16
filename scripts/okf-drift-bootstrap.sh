#!/bin/sh
# okf-drift-bootstrap.sh — give every `code_refs:` entry in an OKF bundle a drift binding.
#
#   okf-drift-bootstrap.sh [bundle-dir]     (default: knowledge)     run from the REPO ROOT
#
# `okf` knows which paths a concept governs (`code_refs:`); `drift` knows when a path has
# changed since the doc was last believed (`drift.lock`). Nothing connects them, so this
# does: one `drift link <bundle>/<concept>.md <path>` per entry, writing the repo-root
# `drift.lock` that `okf-check.sh` step 6 and `okf-recall.sh` then read.
#
# Measured on drift v0.10.1 (2026-09-16); each branch below exists because of one of these:
#
#   * `drift link` on a binding the lock ALREADY holds exits 1 with "refused: target
#     changed since last link" — even when `drift check` calls that same binding fresh.
#     So a re-run must skip what the lock holds rather than relink it. That, not a flag
#     on drift, is what makes this script idempotent.
#   * a DIRECTORY target is rejected — `error: ReadFailed`, exit 1 — because drift signs
#     file content. A directory `code_ref` is expanded here into the files git tracks
#     under it, and skipped loudly past $OKF_DRIFT_MAX_DIR_FILES (default 20) so that one
#     broad `src/` does not put hundreds of permanently-hot anchors in the lock. The fix
#     for a skip is to narrow the code_ref, not to raise the limit.
#   * a target that does not exist is rejected: "error: target not found: <path>".
#     `okf validate --drift` calls the same path a warning at exit 0; okf-check.sh fails
#     on it. Here it is a FAIL line and a non-zero exit.
#
# Needs sh, perl 5.14+ (core), git, drift. Does not need okf.
# Exit 0 = every code_ref is bound; 1 = at least one could not be.
set -u
bundle=${1:-knowledge}
max_dir=${OKF_DRIFT_MAX_DIR_FILES:-20}

[ -d "$bundle" ] || { echo "no bundle at $bundle (run from the repository root)" >&2; exit 2; }
command -v drift >/dev/null 2>&1 || { echo "drift not on PATH — install it before the drift phase" >&2; exit 2; }
top=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not a git repository — drift blames commits" >&2; exit 2; }
[ "$top" = "$(pwd -P)" ] || { echo "run from the repository root ($top); drift.lock and every path in it are rooted there" >&2; exit 2; }

tmp=$(mktemp "${TMPDIR:-/tmp}/okf-drift-XXXXXX") || exit 2
trap 'rm -f "$tmp" "$tmp.have"' EXIT INT TERM

# Every (doc, target) pair the bundle asks for, tab-separated, deduplicated, in order.
perl - "$bundle" >|"$tmp" <<'PERL'
use strict; use warnings; use utf8;
use File::Find;
binmode STDOUT, ':utf8';
my ($bundle) = @ARGV;
my @concepts;
find({ no_chdir=>1, wanted=>sub {
  return unless -f && /\.md$/;
  (my $rel = $File::Find::name) =~ s{^\Q$bundle\E/}{};
  return if $rel =~ m{(^|/)(index|log)\.md$};        # reserved at every level
  push @concepts, $rel;
}}, $bundle);
my %seen;
for my $rel (sort @concepts) {
  open my $h, '<:utf8', "$bundle/$rel" or next;
  local $/; my $text = <$h>; close $h;
  my ($fm) = $text =~ /\A---\n(.*?)\n---\n/s or next;
  my $in = 0;
  for my $line (split /\n/, $fm) {
    if    ($line =~ /^code_refs:\s*$/) { $in = 1; next }
    elsif ($line =~ /^[A-Za-z_]+:/)    { $in = 0; next }
    next unless $in;
    next unless $line =~ /^\s*-\s+(.+?)\s*$/;        # list items may sit at zero indent
    my $p = $1; $p =~ s/^(["'])(.*)\1$/$2/;
    next if $seen{"$bundle/$rel\t$p"}++;
    print "$bundle/$rel\t$p\n";
  }
}
PERL

[ -s "$tmp" ] || { echo "no code_refs in $bundle — nothing to bind"; exit 0; }

# Bindings the lock already holds, "doc<TAB>target" per line.
perl -ne '
  if    (/^\s*doc\s*=\s*"(.*)"/)                  { $d = $1 }
  elsif (/^\s*target\s*=\s*"(.*)"/ && defined $d) { print "$d\t$1\n"; undef $d }
' drift.lock 2>/dev/null >|"$tmp.have" || :
[ -f "$tmp.have" ] || : >|"$tmp.have"

TAB=$(printf '\t')
linked=0; skipped=0; failed=0; concepts=0; lastdoc=

link_one() {   # link_one <doc> <target>
  if grep -qxF "$1$TAB$2" "$tmp.have"; then
    echo "skip  $1 -> $2 (already in drift.lock)"
    skipped=$((skipped + 1))
    return 0
  fi
  if out=$(drift link "$1" "$2" 2>&1); then
    echo "link  $1 -> $2"
    linked=$((linked + 1))
  else
    echo "FAIL  $1 -> $2: $(printf '%s' "$out" | tr -d '\r' | tr '\n' ' ')"
    failed=$((failed + 1))
  fi
}

while IFS="$TAB" read -r doc target; do
  [ -n "${target:-}" ] || continue
  [ "$doc" = "$lastdoc" ] || { concepts=$((concepts + 1)); lastdoc=$doc; }
  if [ -d "$target" ]; then
    n=$(git ls-files -- "$target" | grep -c . || true)
    if [ "$n" -eq 0 ]; then
      echo "FAIL  $doc -> $target (a directory with nothing tracked under it)"
      failed=$((failed + 1)); continue
    fi
    if [ "$n" -gt "$max_dir" ]; then
      echo "skip  $doc -> $target ($n tracked files > OKF_DRIFT_MAX_DIR_FILES=$max_dir — narrow the code_ref)"
      skipped=$((skipped + 1)); continue
    fi
    echo "      $doc -> $target is a directory; drift binds file content — expanding to $n file(s)"
    while read -r f; do
      [ -n "$f" ] || continue
      link_one "$doc" "$f"
    done <<EOF
$(git ls-files -- "$target")
EOF
    continue
  fi
  link_one "$doc" "$target"
done < "$tmp"

held=$(grep -c '^[[:space:]]*target[[:space:]]*=' drift.lock 2>/dev/null || echo 0)
echo "----"
echo "$concepts concept(s) with code_refs: $linked linked, $skipped skipped, $failed failed; drift.lock holds $held binding(s)"
# drift check's exit code covers EVERY markdown file under the working directory, so an
# unrelated broken link elsewhere in the repo fails it while the bundle is perfectly fresh
# (measured on ai-review: 32 broken links in docs/ and .claude/rules/, 0 in the bundle).
# Judge the bundle, the way okf-check.sh step 6 does.
if drift check --format json 2>/dev/null | perl -0777 -ne '
  use JSON::PP; my $d = eval { decode_json($_) } or exit 2;
  my $b = shift @ARGV;
  for my $x (@{ $d->{docs} || [] }) {
    next unless ($x->{path} // "") =~ m{^\Q$b\E/};
    exit 1 unless ($x->{result} // "fresh") eq "fresh";
  }
  exit 0' -- "$bundle"; then
  echo "drift check: pass — every bound path is at the content the concept was written against"
else
  echo "drift check: FAIL — run \`drift check\` for the detail (a binding written now should be fresh)"
fi
[ "$failed" -eq 0 ]
