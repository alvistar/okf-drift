#!/bin/sh
# okf-recall.sh — search the knowledge bundle, and say where the code moved under a hit.
#
#   okf-recall.sh "<terms>" [bundle-dir]     (default bundle: knowledge)   run from REPO ROOT
#
# `okf search` ranks concepts by BM25 and knows nothing about whether they are still true.
# The code is the source of truth (docs/adr/0002-drop-drift-code-is-the-source-of-truth.md):
# this prints every hit in rank order with two signals read from its frontmatter, and, when
# the code under its `code_refs` changed after the concept's last commit, a CHANGE HINT
# naming how many commits and the last one. The hint obliges nobody to do anything: it
# says where to read the code before relying on the concept.
#
#   lifecycle  okf `status` from the concept's own frontmatter (`stable`/`deprecated`/
#              `draft`), or `no status`. Measured on okf v0.6.0: `okf search --json` does
#              NOT emit `status` even when the frontmatter carries it, so this is read from
#              the file.
#   review     `stale_after` vs today: `review current`, `review due <date>` within the next
#              OKF_REVIEW_WINDOW_DAYS days (default 30, the gate's window), `review expired
#              <date>`, `review date invalid (<date>)` or `no review date`. Today is the
#              UTC date, as okf's is. A date equal to today is expired: okf --stale
#              fails a concept on its stale_after day, not the day after.
#   hint       `git rev-list --count <concept's last commit>..HEAD -- <code_refs>`. Counted
#              from the concept's last COMMIT, not from `last_updated`: a date cannot order
#              two commits made the same day. No hint when the count is 0, when the concept
#              has no `code_refs` or no commit, or outside a git work tree. A cosmetic
#              commit to the concept resets it; accepted (ADR 0002).
#
# Measured on okf v0.6.0 (2026-10-08):
#   * `okf search --json` is an ARRAY of {concept_id, title, type, description, score,
#     tags, matched_on, inbound, scope, origin, priority, ...}. There is no `path`; the doc
#     path is `<bundle>/<concept_id>.md`.
#   * since okf v0.5.0 search defaults to `--scope all`: concepts under ~/.okf (or
#     OKF_USER_DIR), /etc/okf and .okf/vendor/ join the results with ids like
#     `user:notes/x`, which have no file in the bundle. Recall searches `--scope project`
#     only (and, on an okf older than v0.5.0, which has neither the flag nor the other
#     scopes, plainly).
#
# Needs sh, perl 5.14+ (JSON::PP is core), okf; git for the hint. Exit 0 with results,
# 2 unusable.
set -u
terms=${1:-}
bundle=${2:-knowledge}
[ -n "$terms" ] || { echo "usage: okf-recall.sh \"<terms>\" [bundle-dir]" >&2; exit 2; }
[ -d "$bundle" ] || { echo "no bundle at $bundle (run from the repository root)" >&2; exit 2; }
command -v okf   >/dev/null 2>&1 || { echo "okf not on PATH" >&2; exit 2; }
if [ -f .okf-profile ]; then
  profile=$(tr -d '[:space:]' < .okf-profile)
  case "$profile" in
    code|wiki) ;;
    *) echo "okf-recall: .okf-profile says '$profile'; expected 'code' or 'wiki'" >&2; exit 2 ;;
  esac
fi
in_git=0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && in_git=1

# Keep payloads out of argv (Linux's per-argument limit is 131072 bytes), just as
# the gate does. Failed searches are not an empty result set; preserve stderr.
tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-recall.XXXXXX") || exit 2
trap 'rm -rf "$tmp"' EXIT
trap 'exit 2' INT TERM
# --scope arrived in okf v0.5.0; v0.3.0 rejects the flag ("flag provided but not defined")
# and has no other scope to leak in. Ask the binary rather than parse its version.
scope=''
okf search --help 2>&1 | grep -q -- '-scope' && scope='--scope project'
# shellcheck disable=SC2086
okf search "$terms" "$bundle" $scope --json > "$tmp/search.json" || { echo "okf-recall: okf search failed" >&2; exit 2; }

perl - "$bundle" "$terms" "$tmp/search.json" "$(date -u +%F)" "$in_git" <<'PERL'
use strict; use warnings; use utf8;
use JSON::PP; use Time::Local qw(timegm);
binmode STDOUT, ':utf8';
my ($bundle, $terms, $search_file, $today, $in_git) = @ARGV;
$bundle =~ s{/+$}{};
sub unusable { print STDERR "okf-recall: @_\n"; exit 2 }
my $REVIEW_WINDOW = length($ENV{OKF_REVIEW_WINDOW_DAYS} // '') ? $ENV{OKF_REVIEW_WINDOW_DAYS} : 30;
unusable("OKF_REVIEW_WINDOW_DAYS='$REVIEW_WINDOW' is not a whole number of days") unless $REVIEW_WINDOW =~ /^\d+$/;
# Days since the epoch for an ISO date; undef for anything else, an impossible date included.
sub day_number {
  my ($y, $m, $d) = ($_[0] // '') =~ /^(\d{4})-(\d{2})-(\d{2})$/ or return undef;
  return undef if $y < 1000;   # Time::Local reads a smaller year as an offset from 1900
  my $t = eval { timegm(0, 0, 0, $d, $m - 1, $y) };
  return defined $t ? int($t / 86400) : undef;
}
sub slurp_raw { my $f=shift; open my $h,'<:raw',$f or unusable("$f: $!"); local $/; my $c=<$h>; defined $c ? $c : '' }
my $hits = eval { decode_json(slurp_raw($search_file)) };
unusable("okf search produced no valid JSON array") unless ref $hits eq 'ARRAY';

# One read of the concept's frontmatter: status and stale_after as scalars, code_refs as
# a list (block `- path` items, indented or not, or an inline `[a, b]`). A `#symbol`
# fragment is cut off: git takes the file as the pathspec.
sub frontmatter {
  my $f = shift;
  open my $h, '<:utf8', $f or return {};
  local $/; my $t = <$h>; close $h;
  my ($fm) = $t =~ /\A---\n(.*?)\n---\n/s or return {};
  my (%k, @refs, $cur);
  for my $line (split /\n/, $fm) {
    if ($line =~ /^([A-Za-z_]+):[ \t]*(.*?)\s*$/) {
      ($cur, my $val) = ($1, $2);
      if ($cur eq 'code_refs' && $val =~ /^\[(.*)\]$/) { push @refs, split /\s*,\s*/, $1 }
      elsif (length $val) { $val =~ s/^(["'])(.*)\1$/$2/; $k{$cur} = $val }
    }
    elsif (($cur // '') eq 'code_refs' && $line =~ /^\s*-\s+(.*?)\s*$/) { push @refs, $1 }
  }
  my %seen;
  $k{code_refs} = [ grep { length && !$seen{$_}++ }
                    map { (my $r = $_) =~ s/^(["'])(.*)\1$/$2/; $r =~ s/#.*//; $r } @refs ];
  return \%k;
}
sub git_out {
  open my $h, '-|', 'git', @_ or return '';
  local $/; my $o = <$h>; close $h;
  return $? ? '' : ($o // '');
}
# The change hint, or undef: commits on code_refs after the concept's last commit.
sub change_hint {
  my ($path, $refs) = @_;
  return undef unless $in_git && @$refs;
  my $base = git_out('log', '-1', '--format=%H', '--', $path); chomp $base;
  return undef unless length $base;
  my $n = git_out('rev-list', '--count', "$base..HEAD", '--', @$refs); chomp $n;
  return undef unless $n =~ /^\d+$/ && $n > 0;
  my $last = git_out('log', '-1', '--date=short', '--format=%h %ad "%s"', "$base..HEAD", '--', @$refs);
  chomp $last;
  return sprintf("code changed since this concept: %d commit(s) on %s (last %s)", $n, join(', ', @$refs), $last);
}
sub signals {
  my $fm = shift;
  my $status = length($fm->{status} // '') ? $fm->{status} : 'no status';
  my $sa = $fm->{stale_after} // '';
  my $days = day_number($sa);
  my $review = !length $sa                              ? 'no review date'
             : !defined $days                           ? "review date invalid ($sa)"
             : $days <= day_number($today)                ? "review expired $sa"
             : $days <= day_number($today) + $REVIEW_WINDOW ? "review due $sa"
             :                                              'review current';
  return "$status · $review";
}
sub head_line {
  my $h = shift;
  sprintf("  %-44s %-10s %5.2f", $h->{concept_id}, $h->{type} // '?', $h->{score} // 0);
}
sub wrapped {
  my ($text, $indent) = @_;
  my @out; my $line = '';
  for my $w (split /\s+/, $text // '') {
    if (length($line) + length($w) + 1 > 92) { push @out, $line; $line = $w }
    else { $line = length($line) ? "$line $w" : $w }
  }
  push @out, $line if length $line;
  return join("\n", map { "$indent$_" } @out);
}

for my $h (@$hits) {
  unusable("okf search returned a hit without a concept_id")
    unless ref $h eq 'HASH' && defined $h->{concept_id} && !ref $h->{concept_id} && length $h->{concept_id};
}
if (!@$hits) {
  print "no concept in $bundle matches \"$terms\"\n";
  exit 0;
}
printf "%d hit(s) for \"%s\" in %s\n\n", scalar @$hits, $terms, $bundle;
my $hinted = 0;
for my $h (@$hits) {
  my $path = "$bundle/" . $h->{concept_id} . ".md";
  my $fm = frontmatter($path);
  print head_line($h), "   ", signals($fm), "\n";
  print wrapped($h->{description}, '      '), "\n";
  if (defined(my $hint = change_hint($path, $fm->{code_refs} || []))) {
    $hinted++;
    print "      $hint\n";
  }
  print "\n";
}
print "A deprecated concept is history: read its successor.\n";
printf <<'NOTE', $hinted if $hinted;
%d hit(s) with a change hint: code under their code_refs changed after the concept's
last commit. That does not make the concept wrong. If you rely on one, read that code
first: the code wins. If they disagree and this session writes the repository, fix the
concept with /okf-write; otherwise say so in your answer.
NOTE
exit 0;
PERL
rc=$?
exit "$rc"
