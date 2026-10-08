#!/bin/sh
# okf-recall.sh — search the knowledge bundle without serving a stale fact as a fact.
#
#   okf-recall.sh "<terms>" [bundle-dir]     (default bundle: knowledge)   run from REPO ROOT
#
# `okf search` ranks concepts by BM25 and knows nothing about whether they are still true.
# `drift check` knows which docs are bound to code that has changed since they were last
# believed, and who to blame, and knows nothing about relevance. This joins them on
# `<bundle>/<concept_id>.md` and prints every hit in rank order, a hit whose bound code
# moved after it was written marked STALE in place, with the anchor and the commit that
# moved it, so the agent reads the code before it quotes the prose.
#
# NO WORD IN THE OUTPUT MAY READ AS "VERIFIED". Each surviving hit carries three
# INDEPENDENT signals, all read from what already exists — nothing new in the frontmatter:
#
#   tracking   from drift's per-doc `anchors[]`: `N target(s) unchanged` when the concept
#              has anchors and drift calls the doc fresh, `no tracked target` when it has
#              none. It is an observation about the anchors, never about the prose, and it
#              says nothing about claims no anchor covers.
#   lifecycle  okf `status` from the concept's own frontmatter (`stable`/`deprecated`/
#              `draft`), or `no status`. Measured on okf v0.6.0: `okf search --json` does
#              NOT emit `status` even when the frontmatter carries it, so this is read from
#              the file — the same read that already yields `last_updated`.
#   review     `stale_after` vs today: `review current`, `review due <date>` within the next
#              OKF_REVIEW_WINDOW_DAYS days (default 30, the gate's window), `review expired
#              <date>`, `review date invalid (<date>)` or `no review date`. Today is the
#              UTC date, as okf's is. A date equal to today is expired: okf --stale
#              fails a concept on its stale_after day, not the day after.
#
# A stale or broken doc is marked STALE in place of the tracking signal, regardless of
# the other two. It used to be WITHHELD in a separate block. Measured over the reference
# consumers' sessions: of ~84 recalls, 5 withheld anything, and in each the concept was
# still worth reading beside the code; the CI gate keeps `main` fresh, so a stale hit
# appears only mid-branch, where the agent is usually the one who moved the code.
#
# Without drift — no `drift` on PATH, or no `drift.lock` at the repository root — recall
# still searches, says so in one line at the top, and labels every hit `drift not run`.
# It used to exit 2, which turned a missing binary into no recall at all. A drift that
# RAN and failed (exit > 1, no JSON, an incomplete report) is still exit 2: that is a
# broken detector, not an absent one.
#
# The one exception is a bundle declared `wiki` in `.okf-profile` at the repository root
# and carrying no drift.lock: it describes no code, so there is nothing for drift to
# check. Recall then runs without the join and says so on every hit ("not drift-tracked")
# instead of implying a freshness nobody measured. The review signal still applies.
#
# Measured on drift v0.10.1 (2026-09-16) and okf v0.6.0 (2026-10-08):
#   * `okf search --json` is an ARRAY of {concept_id, title, type, description, score,
#     tags, matched_on, inbound, scope, origin, priority, ...}. There is no `path`; the doc
#     path is `<bundle>/<concept_id>.md`.
#   * since okf v0.5.0 search defaults to `--scope all`: concepts under ~/.okf (or
#     OKF_USER_DIR), /etc/okf and .okf/vendor/ join the results with ids like
#     `user:notes/x`, which have no file in the bundle and no drift verdict — measured, one
#     such hit made recall refuse everything. Recall searches `--scope project` only (and,
#     on an okf older than v0.5.0, which has neither the flag nor the other scopes, plainly).
#   * `drift check --format json` covers EVERY .md in the repository, not only the bundle,
#     so the join is on the path, not on position. A doc with no anchors is `fresh`,
#     including a concept whose `code_refs` are all non-code paths.
#   * per-doc `result` is `fresh` | `stale` | `broken`; `broken` is a dead markdown LINK,
#     which is just as good a reason to withhold a concept as a moved anchor. A stale
#     anchor carries `reason.code` and `blame {author, commit, date, subject}`.
#   * an okf root-relative link like `/project/stack.md` is not counted as a drift link at
#     all (measured: `links_total` stayed 0), so the bundle's own link style never shows
#     up here as broken.
#
# Needs sh, perl 5.14+ (JSON::PP is core), okf, drift. Exit 0 with results, 2 unusable.
set -u
terms=${1:-}
bundle=${2:-knowledge}
[ -n "$terms" ] || { echo "usage: okf-recall.sh \"<terms>\" [bundle-dir]" >&2; exit 2; }
[ -d "$bundle" ] || { echo "no bundle at $bundle (run from the repository root)" >&2; exit 2; }
command -v okf   >/dev/null 2>&1 || { echo "okf not on PATH" >&2; exit 2; }
profile=code
if [ -f .okf-profile ]; then
  profile=$(tr -d '[:space:]' < .okf-profile)
  case "$profile" in
    code|wiki) ;;
    *) echo "okf-recall: .okf-profile says '$profile'; expected 'code' or 'wiki'" >&2; exit 2 ;;
  esac
fi
nodrift=0
# Both places a lock could sit: the root (where recall runs drift) and beside the bundle
# (where the gate looks). Either one means something was bound, so the join stays on.
[ "$profile" = wiki ] && [ ! -f drift.lock ] && [ ! -f "$(dirname "$bundle")/drift.lock" ] && nodrift=1
nodrift_why=''
if [ "$nodrift" = 0 ]; then
  if ! command -v drift >/dev/null 2>&1; then
    nodrift=2; nodrift_why='drift is not on PATH'
  elif [ ! -f drift.lock ]; then
    nodrift=2; nodrift_why='there is no drift.lock at the repository root'
  fi
fi

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
if [ "$nodrift" != 0 ]; then
  printf '%s' '{"docs":[]}' > "$tmp/drift.json"
  drift_status=0
else
  drift check --format json > "$tmp/drift.json"
  drift_status=$?
fi

perl - "$bundle" "$terms" "$tmp/search.json" "$tmp/drift.json" "$drift_status" "$(date -u +%F)" "$nodrift" "$nodrift_why" <<'PERL'
use strict; use warnings; use utf8;
use JSON::PP; use Cwd qw(abs_path); use File::Spec; use Time::Local qw(timegm);
binmode STDOUT, ':utf8';
my ($bundle, $terms, $search_file, $check_file, $drift_status, $today, $nodrift, $nodrift_why) = @ARGV;
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
my $chk = eval { decode_json(slurp_raw($check_file)) };
unusable("drift check produced no valid docs array") unless ref $chk eq 'HASH' && ref $chk->{docs} eq 'ARRAY';
# drift exits 1 for stale/broken findings. Retain those findings, but an unrelated
# execution failure or an inconsistent exit-1/fresh report is never trustworthy.
unusable("drift check exited $drift_status") if $drift_status > 1;
for my $d (@{ $chk->{docs} }) {
  unusable("drift check returned an invalid doc") unless ref $d eq 'HASH' && defined $d->{path};
}
unusable("drift check exited 1 without stale or broken findings")
  if $drift_status == 1 && !grep { ($_->{result} // '') =~ /^(stale|broken)$/ } @{ $chk->{docs} };
# drift runs from the repository root. Normalize equivalent bundle spellings to
# that same namespace; an unknown join must fail below, never imply freshness.
$bundle = File::Spec->abs2rel(abs_path($bundle), abs_path('.'));

# path => doc entry, for the bundle only.
my %doc;
for my $d (@{ $chk->{docs} || [] }) {
  next unless ($d->{path} // '') =~ m{^\Q$bundle\E/};
  $doc{ $d->{path} } = $d;
}

# One read of the concept's frontmatter serves all three of last_updated, status and
# stale_after. Scalar keys only: a list value (tags, code_refs) is not wanted here.
sub frontmatter {
  my $f = shift;
  open my $h, '<:utf8', $f or return { _missing => 1 };
  local $/; my $t = <$h>; close $h;
  my ($fm) = $t =~ /\A---\n(.*?)\n---\n/s or return { _no_frontmatter => 1 };
  my %k;
  for my $line (split /\n/, $fm) {
    next unless $line =~ /^([A-Za-z_]+):[ \t]*(\S.*?)\s*$/;
    my ($key, $val) = ($1, $2);
    $val =~ s/^(["'])(.*)\1$/$2/;
    $k{$key} = $val;
  }
  return \%k;
}
sub last_updated {
  my $fm = shift;
  return '(no file)'        if $fm->{_missing};
  return '(no frontmatter)' if $fm->{_no_frontmatter};
  return length($fm->{last_updated} // '') ? $fm->{last_updated} : '(none)';
}
# The three signals, in the fixed order tracking · lifecycle · review.
sub signals {
  my ($d, $fm) = @_;
  my $n = scalar @{ $d->{anchors} || [] };
  # A `fresh` doc's anchors are all fresh (drift reports a doc as the worst of its
  # anchors), so a count is the whole of what was observed.
  my $tracking = $d->{_nodrift} ? ($nodrift == 2 ? 'drift not run' : 'not drift-tracked (wiki)')
               : $d->{result} eq 'broken' && !(grep { ($_->{result} // '') ne 'fresh' } @{ $d->{anchors} || [] })
                 ? 'BROKEN LINK: it points at a file that does not exist'
               : $d->{result} ne 'fresh' ? 'STALE: code moved after it was written'
               : $n ? sprintf("%d target%s unchanged", $n, $n == 1 ? '' : 's')
                    : 'no tracked target';
  my $status = length($fm->{status} // '') ? $fm->{status} : 'no status';
  my $sa = $fm->{stale_after} // '';
  my $days = day_number($sa);
  my $review = !length $sa                              ? 'no review date'
             : !defined $days                           ? "review date invalid ($sa)"
             : $days <= day_number($today)                ? "review expired $sa"
             : $days <= day_number($today) + $REVIEW_WINDOW ? "review due $sa"
             :                                              'review current';
  return "$tracking · $status · $review";
}

my @rows;
for my $h (@$hits) {
  unusable("okf search returned a hit without a concept_id")
    unless ref $h eq 'HASH' && defined $h->{concept_id} && !ref $h->{concept_id} && length $h->{concept_id};
  my $id   = $h->{concept_id};
  my $path = "$bundle/$id.md";
  my $d    = $nodrift ? { result => 'fresh', anchors => [], _nodrift => 1 } : $doc{$path};
  # Unbound concepts still receive an explicit fresh verdict from drift. Missing
  # or unknown verdicts indicate an incomplete report, not permission to quote.
  unusable("no valid drift verdict for $path; refusing all search results")
    unless $d && ($d->{result} // '') =~ /^(fresh|stale|broken)$/;
  push @rows, [$h, $d];
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

if ($nodrift == 2) {
  print "warn  drift did not run ($nodrift_why): nothing below was checked against the code\n\n";
}
if (!@$hits) {
  print "no concept in $bundle matches \"$terms\"\n";
  exit 0;
}

my $stale = grep { $_->[1]{result} ne 'fresh' } @rows;
printf "%d hit(s) for \"%s\" in %s%s\n\n", scalar @rows, $terms, $bundle,
  $stale ? " — $stale STALE" : '';
for my $e (@rows) {
  my ($h, $d) = @$e;
  my $path = "$bundle/" . $h->{concept_id} . ".md";
  my $fm = frontmatter($path);
  print head_line($h), "   ", signals($d, $fm), "\n";
  print wrapped($h->{description}, '      '), "\n";
  if ($d->{result} ne 'fresh') {
    printf "      last_updated %s; the code under it moved since:\n", last_updated($fm);
    for my $a (@{ $d->{anchors} || [] }) {
      next if ($a->{result} // '') eq 'fresh';
      my $b = $a->{blame} || {};
      my $c = substr($b->{commit} // '', 0, 8);
      my $date = ($b->{date} // ''); $date =~ s/T.*//;
      # `identity` is the canonical handle `drift link` takes (`path#symbol` for a symbol
      # anchor); `path` alone would name a DIFFERENT, whole-file binding.
      my $target = $a->{identity} // $a->{path} // '?';
      printf "        %s  [%s]\n", $target, $a->{reason}{code} // ($a->{result} // '?');
      # drift blames with `git log -1 -- <file>`: the last commit to TOUCH the file, which
      # is not necessarily the one that moved the ground. Label it as what it is.
      printf "          last commit touching this file (not necessarily the cause): %s %s %s (%s)\n",
        $c || '-', $date || '-', $b->{subject} // '(uncommitted change — nothing to blame yet)', $b->{author} // '-';
    }
    for my $l (@{ $d->{links} || [] }) {
      next if ($l->{result} // '') ne 'broken';
      printf "        broken link at line %s: %s\n", $l->{line} // '?', $l->{target} // '?';
    }
  }
  print "\n";
}
my $fresh = @rows - $stale;
if ($fresh && $nodrift == 1) {
  print <<'NOTE';
"not drift-tracked" means this wiki bundle binds no code, so nothing checked these
concepts against anything: they are as current as their last_updated. "review expired"
means the writer's own review date has passed. A deprecated concept is history.
NOTE
}
elsif ($fresh) {
  print <<'NOTE';
"targets unchanged" means the code under the anchors did not move. It does not mean the
prose is right, and it says nothing about claims the anchors do not cover. "no tracked
target" means nothing was checked. A deprecated concept is history: read its successor.
NOTE
}
if ($stale) {
  print <<'NOTE';
STALE means the code a concept is bound to changed after the concept was last believed.
Read that code before you rely on the concept; quote it only for what the code confirms.
If it still holds, re-stamp it (/okf-write); if it does not, fix it there.
NOTE
}
exit 0;
PERL
rc=$?
exit "$rc"
