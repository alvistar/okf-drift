#!/bin/sh
# okf-recall.sh — search the knowledge bundle without serving a stale fact as a fact.
#
#   okf-recall.sh "<terms>" [bundle-dir]     (default bundle: knowledge)   run from REPO ROOT
#
# `okf search` ranks concepts by BM25 and knows nothing about whether they are still true.
# `drift check` knows which docs are bound to code that has changed since they were last
# believed, and who to blame, and knows nothing about relevance. This joins them on
# `<bundle>/<concept_id>.md` and splits the result in two: the hits that are still
# grounded, and a WITHHELD block for the ones that are not — with the commit that moved
# the ground under them, so the agent reads the code instead of the prose.
#
# Drift is a HARD DEPENDENCY here, by design. A recall that cannot tell a fact from a
# stale one is the thing this plugin exists to replace, so with no `drift.lock` at the
# repository root, or no `drift` on PATH, this exits 2 with one line rather than quietly
# degrading into a bare `okf search`. Bootstrap the lock with `okf-drift-bootstrap.sh`.
#
# Measured on drift v0.10.1 and okf v0.3.0 (2026-09-16):
#   * `okf search --json` is an ARRAY of {concept_id, title, type, description, score,
#     tags, code_refs, matched_on, inbound, ...}. There is no `path`; the doc path is
#     `<bundle>/<concept_id>.md`.
#   * `drift check --format json` covers EVERY .md in the repository, not only the bundle,
#     so the join is on the path, not on position. A doc with no anchors is `fresh`.
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
command -v drift >/dev/null 2>&1 || { echo "drift not on PATH — okf-recall needs it to tell a fact from a stale one; install drift or use \`okf search\` knowing it cannot" >&2; exit 2; }
[ -f drift.lock ] || { echo "no drift.lock at the repository root — okf-recall will not serve concepts it cannot check; run scripts/okf-drift-bootstrap.sh first" >&2; exit 2; }

# Keep payloads out of argv (Linux's per-argument limit is 131072 bytes), just as
# the gate does. Failed searches are not an empty result set; preserve stderr.
tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-recall.XXXXXX") || exit 2
trap 'rm -rf "$tmp"' EXIT
trap 'exit 2' INT TERM
okf search "$terms" "$bundle" --json > "$tmp/search.json" || { echo "okf-recall: okf search failed" >&2; exit 2; }
drift check --format json > "$tmp/drift.json"
drift_status=$?

perl - "$bundle" "$terms" "$tmp/search.json" "$tmp/drift.json" "$drift_status" <<'PERL'
use strict; use warnings; use utf8;
use JSON::PP; use Cwd qw(abs_path); use File::Spec;
binmode STDOUT, ':utf8';
my ($bundle, $terms, $search_file, $check_file, $drift_status) = @ARGV;
sub unusable { print STDERR "okf-recall: @_\n"; exit 2 }
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

sub last_updated {
  my $f = shift;
  open my $h, '<:utf8', $f or return '(no file)';
  local $/; my $t = <$h>; close $h;
  my ($fm) = $t =~ /\A---\n(.*?)\n---\n/s or return '(no frontmatter)';
  return $fm =~ /^last_updated:\s*(\S+)/m ? $1 : '(none)';
}

my (@fresh, @held);
for my $h (@$hits) {
  unusable("okf search returned a hit without a concept_id")
    unless ref $h eq 'HASH' && defined $h->{concept_id} && !ref $h->{concept_id} && length $h->{concept_id};
  my $id   = $h->{concept_id};
  my $path = "$bundle/$id.md";
  my $d    = $doc{$path};
  # Unbound concepts still receive an explicit fresh verdict from drift. Missing
  # or unknown verdicts indicate an incomplete report, not permission to quote.
  unusable("no valid drift verdict for $path; withholding all search results")
    unless $d && ($d->{result} // '') =~ /^(fresh|stale|broken)$/;
  if ($d->{result} ne 'fresh') { push @held, [$h, $d] }
  else                        { push @fresh, $h }
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

if (!@$hits) {
  print "no concept in $bundle matches \"$terms\"\n";
  exit 0;
}

printf "%d fresh hit(s) for \"%s\" in %s\n\n", scalar @fresh, $terms, $bundle;
for my $h (@fresh) {
  print head_line($h), "\n";
  print wrapped($h->{description}, '      '), "\n\n";
}
print "  (none — every match is withheld below)\n\n" unless @fresh;

exit 0 unless @held;

printf "WITHHELD — %d concept(s) matched, but the code under them moved after they were written.\n", scalar @held;
print  "Do not quote these as facts. Read the code they point at, or fix the concept with\n";
print  "/okf-write, which re-stamps the binding and logs that it did.\n\n";
for my $e (@held) {
  my ($h, $d) = @$e;
  my $path = "$bundle/" . $h->{concept_id} . ".md";
  print head_line($h), "   last_updated ", last_updated($path), "\n";
  print wrapped($h->{description}, '      '), "\n";
  for my $a (@{ $d->{anchors} || [] }) {
    next if ($a->{result} // '') eq 'fresh';
    my $b = $a->{blame} || {};
    my $c = substr($b->{commit} // '', 0, 8);
    my $date = ($b->{date} // ''); $date =~ s/T.*//;
    printf "      %s  [%s]\n", $a->{path} // $a->{identity} // '?', $a->{reason}{code} // ($a->{result} // '?');
    printf "          %-9s %-11s %s (%s)\n", $c || '-', $date || '-', $b->{subject} // '(uncommitted change — no commit to blame yet)', $b->{author} // '-';
  }
  for my $l (@{ $d->{links} || [] }) {
    next if ($l->{result} // '') ne 'broken';
    printf "      broken link at line %s: %s\n", $l->{line} // '?', $l->{target} // '?';
  }
  print "\n";
}
exit 0;
PERL
rc=$?
exit "$rc"
