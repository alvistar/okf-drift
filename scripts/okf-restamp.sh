#!/bin/sh
# okf-restamp.sh — re-stamp drift bindings and write their line in the log entry.
#
#   okf-restamp.sh [log options] <doc> <anchor> "<what you read>" [bundle]   one reviewed re-stamp
#   okf-restamp.sh --format-only [log options] [bundle]                      the mechanical sweep
#
# Run from the REPO ROOT (default bundle: knowledge). `<anchor>` is the identity the gate
# prints (`path#symbol` for a symbol anchor, never the bare path of one).
#
# The line goes into the branch's log entry, <bundle>/log/<date>-<slug>-<hex>/log.md,
# never into the root log.md. okf-log.sh finds or creates the entry (see its header for the
# rules) and writes it; the log options `--entry <path>`, `--slug <slug>` and `--base <ref>`
# are passed to it unchanged. When this script runs through the pinned launcher, okf-log.sh
# is run through it too ($OKF_DRIFT_SHIM), so it is checked against the same pin.
#
# REVIEWED: the anchor must be non-fresh in `drift check` right now; this runs
# `drift link <doc> <anchor> --doc-is-still-accurate` and adds ONE line under today's
# `## YYYY-MM-DD` heading in the branch's log entry naming the doc, the anchor, the last commit
# on the file and what you read. The re-stamp rule is unchanged — never re-stamp what you
# did not read — but the line that proves it is written here, not composed by hand. A
# concept you EDITED still gets its prose entry in the log; this line is for "still holds".
#
# --format-only: for every stale anchor in the bundle, find the version of the file the
# binding was signed against (the newest of the file's last $OKF_RESTAMP_DEPTH commits,
# default 40, whose drift signature equals the one in drift.lock — recomputed by `drift
# link` in a scratch repository, so no signature algorithm is restated here), and compare
# it with the working tree. The anchor is re-stamped, with no reading, only when:
#
#   * the file is in a language drift hashes RAW and whose indentation carries no
#     meaning: C, C++, Objective-C, Swift, Kotlin, C#, Dart;
#   * neither version holds a backslash-continued line or a multi-line, raw or verbatim
#     string (there, indentation is content);
#   * the two hold the same sequence of lines, blank ones included, each identical once
#     its leading and trailing whitespace is dropped. Nothing inside a line changes; no
#     line is added, removed, joined, split or moved.
#
# The line in the log entry is written BEFORE the links, and a failed link is taken back out of it (the
# entry gets its bytes back, or the folder this run created is removed): an
# interrupted run can leave a line for an anchor the gate still flags, never a re-stamp
# with no line.
#
# Everything else is listed as NEEDS READING and left stale. In particular NOTHING in a
# language drift parses (rs, py, ts/tsx, js/jsx, go, zig, java) is ever settled: drift
# already ignores formatting there, so what it flags changed a token, and a token change
# is not provably harmless without a parser — `(x,)` is a tuple and `(x)` is not,
# `x-- - y` is not `x - --y`, a swapped `from a import x` changes which `x` wins. An
# earlier draft that normalised whitespace, trailing commas and import order re-stamped
# all of those; tests/ keep them as cases that must stay unsettled. Shell, YAML, Makefiles
# and data files are never settled either: indentation can be syntax there, and so is
# Scala (Scala 3's braceless syntax; a blank line before a block in Scala 2). The
# second review added that, the C# `@$"` strings and blank lines as significant. The
# comparison is over the WHOLE file even for a symbol anchor, which only makes it
# stricter. All re-stamps of one sweep share one line in the log entry.
#
# --compare <path-as-bound> <old-file> <new-file> prints the sweep's verdict on two
# versions of a file, with no repository, drift or bundle involved.
#
# Needs sh, perl 5.14+ (JSON::PP is core), git, drift. Exit 0 = done (a sweep that
# leaves anchors needing reading is still 0), 1 = refused or a link failed, 2 = unusable.
set -u
die() { echo "okf-restamp: $*" >&2; exit 2; }
mode=one
# --entry/--slug/--base go to okf-log.sh unchanged; they come before the positionals.
log_entry=; log_slug=; log_base=
while :; do
  case "${1:-}" in
    --entry|--slug|--base)
      [ "$#" -ge 2 ] && [ -n "$2" ] || die "$1 needs a value"
      case "$1" in --entry) log_entry=$2 ;; --slug) log_slug=$2 ;; *) log_base=$2 ;; esac
      shift 2 ;;
    --format-only)
      [ "$mode" = one ] || die '--format-only given twice'
      mode=sweep; shift ;;
    *) break ;;
  esac
done
if [ "$mode" = sweep ]; then
  [ "$#" -le 1 ] || die 'usage: okf-restamp.sh --format-only [--entry <path>] [--slug <slug>] [--base <ref>] [bundle]'
  bundle=${1:-knowledge}
elif [ "${1:-}" = --compare ]; then
  [ -z "$log_entry$log_slug$log_base" ] || die '--compare takes no --entry, --slug or --base'
  [ "$#" -eq 4 ] || die 'usage: okf-restamp.sh --compare <path-as-bound> <old-file> <new-file>'
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-restamp.XXXXXX") || die 'mktemp failed'
  trap 'rm -rf "$tmp"' EXIT
  mode=compare; note=$2; doc=$3; anchor=$4; bundle=.
else
  [ "$#" -ge 3 ] || die 'usage: okf-restamp.sh [--entry <path>] [--slug <slug>] [--base <ref>] <doc> <anchor> "<what you read>" [bundle] | --format-only [bundle]'
  doc=$1; anchor=$2; note=$3; bundle=${4:-knowledge}
fi
if [ "$mode" != compare ]; then
  [ -d "$bundle" ] || die "no bundle at $bundle (run from the repository root)"
  command -v drift >/dev/null 2>&1 || die 'drift not on PATH'
  [ -f drift.lock ] || die 'no drift.lock at the repository root'
  top=$(git rev-parse --show-toplevel 2>/dev/null) || die 'not a git repository'
  [ "$top" = "$(pwd -P)" ] || die "run from the repository root ($top)"
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-restamp.XXXXXX") || die 'mktemp failed'
  trap 'rm -rf "$tmp"' EXIT
  drift check --format json >| "$tmp/check.json"
  [ -s "$tmp/check.json" ] || die 'drift check produced no JSON'
fi
trap 'exit 2' INT TERM

# The log entry is written by okf-log.sh: through the pinned launcher when this run came
# through it (so the writer is fetched and checked against the same pin), else beside us.
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
perl - "$mode" "$bundle" "$tmp" "$(date +%F)" "${OKF_RESTAMP_DEPTH:-40}" "${doc:-}" "${anchor:-}" "${note:-}" \
  "${OKF_DRIFT_SHIM:-}" "$here" "${top:-}" "$log_entry" "$log_slug" "$log_base" <<'PERL'
use strict; use warnings; use utf8;
use JSON::PP;
binmode STDOUT, ':utf8'; binmode STDERR, ':utf8';
my ($mode, $bundle, $tmp, $today, $depth, $doc, $anchor, $note,
    $shim, $here, $top, $o_entry, $o_slug, $o_base) = @ARGV;
utf8::decode($_) for $doc, $anchor, $note;
sub unusable { print STDERR "okf-restamp: @_\n"; exit 2 }
# It reaches a shell command below; anything but a count is refused, not interpolated.
unusable("OKF_RESTAMP_DEPTH must be a whole number of commits (got '$depth')") unless $depth =~ /\A[1-9][0-9]{0,4}\z/;
sub slurp_raw { my $f = shift; open my $h, '<:raw', $f or return undef; local $/; my $c = <$h>; $c // '' }
sub q1 { my $s = shift; $s =~ s/'/'\\''/g; "'$s'" }
# drift reports repo-relative paths: `./knowledge/` and `knowledge` must name the same thing.
$bundle =~ s{^(?:\./)+}{}; $bundle =~ s{/+\z}{};

# --compare <path> <old-file> <new-file>: the sweep's verdict on two versions of a file,
# with no repository, drift or bundle involved. For tests, and for asking "would the sweep
# settle this?" before trusting it.
if ($mode eq 'compare') {
  my $old = slurp_raw($doc) // unusable("$doc: unreadable");
  my $new = slurp_raw($anchor) // unusable("$anchor: unreadable");
  my $kind = classify($note, $old, $new);
  print defined $kind ? "format-only: $kind\n" : "differs\n";
  exit 0;
}

my $chk = eval { decode_json(slurp_raw("$tmp/check.json")) };
unusable("drift check produced no valid docs array") unless ref $chk eq 'HASH' && ref $chk->{docs} eq 'ARRAY';

# Every non-fresh anchor of a bundle doc: [doc, identity, path, reason, blame].
my @stale;
for my $d (@{ $chk->{docs} }) {
  my $p = $d->{path} // next;
  next unless $p =~ m{^\Q$bundle\E/};
  for my $a (@{ $d->{anchors} || [] }) {
    next if ($a->{result} // '') eq 'fresh';
    push @stale, [$p, $a->{identity} // $a->{path}, $a->{path}, $a->{reason}{code} // '', $a->{blame} || {}];
  }
}

sub link_accurate {
  my ($d, $t) = @_;
  my $out = `drift link @{[q1($d)]} @{[q1($t)]} --doc-is-still-accurate 2>&1`;
  return ($? == 0, $out);
}

# The branch's log entry, resolved ONCE per run by `okf-log.sh path` (which prints the
# base ref it used), then written only through `okf-log.sh add --entry` with that exact
# path: the restore after a failed link puts back the bytes it had, or removes the folder
# this run created. okf-log.sh inserts under today's heading, newest first.
my @LOG = $shim ne '' ? ('sh', $shim, '--repo-root', $top, 'okf-log.sh') : ('sh', "$here/okf-log.sh");
my ($entry, $entry_before, @entry_new_dirs);
sub bytes { my $s = shift; utf8::encode($s); $s }
sub run_log {   # stdout of okf-log.sh; its stderr passes through; its refusal is ours
  my @args = map { bytes($_) } @_;
  open my $h, '-|', @LOG, @args or unusable("cannot run okf-log.sh: $!");
  local $/; my $out = <$h> // ''; close $h;
  if ($?) { my $c = $? >> 8; exit($c == 1 ? 1 : 2) }
  utf8::decode($out); $out =~ s/\n\z//;
  return $out;
}
sub resolve_entry {
  return if defined $entry;
  my @opt = ((length $o_entry ? ('--entry', $o_entry) : ()),
             (length $o_slug ? ('--slug', $o_slug) : ()),
             (length $o_base ? ('--base', $o_base) : ()));
  $entry = run_log('path', @opt, $bundle);
  unusable("okf-log.sh printed no entry path") unless length $entry;
  $entry_before = slurp_raw($entry);
  (my $dir = $entry) =~ s{/log\.md\z}{};
  (my $logdir = $dir) =~ s{/[^/]+\z}{};
  @entry_new_dirs = grep { !-d $_ } ($dir, $logdir);
}
sub log_line {
  my $line = shift;
  resolve_entry();
  # --slug again, so a --slug entry is written as one (no branch comment).
  run_log('add', '--entry', $entry, (length $o_slug ? ('--slug', $o_slug) : ()), $bundle, $line);
}
sub restore_log {
  if (defined $entry_before) {
    open my $h, '>:raw', "$entry.tmp" or unusable("$entry.tmp: $!");
    print $h $entry_before; close $h or unusable("$entry.tmp: $!");
    rename "$entry.tmp", $entry or unusable("$entry: $!");
  } else {
    unlink $entry;
    rmdir $_ for @entry_new_dirs;   # only folders this run created, and only when empty
  }
}
# Whether the bundle can take a log entry at all (an unmigrated one cannot: refused,
# naming /okf-migrate) is okf-log.sh's call alone, asked before anything is linked and
# even when nothing will be settled. The probe names an entry by its form only, so no
# lookup runs, no branch rule applies and nothing is written.
run_log('path', '--entry', "$bundle/log/$today-probe-0000/log.md", $bundle);
sub rel { my $p = shift; $p =~ s{^\Q$bundle\E/}{}; $p }
sub blamed {
  my $b = shift;
  my $c = substr($b->{commit} // '', 0, 8);
  return $c ? "$c \"" . ($b->{subject} // '') . "\"" : 'uncommitted change';
}

if ($mode eq 'one') {
  (my $want = $doc) =~ s{^\./}{};
  unusable("$want: no such file") unless -f $want;
  my ($hit) = grep { $_->[0] eq $want && $_->[1] eq $anchor } @stale;
  unless ($hit) {
    my @same = map { grep { ($_->{identity} // '') eq $anchor } @{ $_->{anchors} || [] } }
               grep { ($_->{path} // '') eq $want } @{ $chk->{docs} };
    if (@same && !grep { ($_->{result} // '') ne 'fresh' } @same) {
      print "okf-restamp: $want <- $anchor is fresh; nothing to re-stamp, nothing logged\n"; exit 0;
    }
    if (@same) { print STDERR "okf-restamp: $want is not under the bundle '$bundle'; pass the bundle it belongs to\n"; exit 1 }
    print STDERR "okf-restamp: drift holds no binding $want <- $anchor (use the identity the gate printed: path#symbol for a symbol anchor)\n";
    exit 1;
  }
  (my $n = $note) =~ s/\s+/ /g; $n =~ s/^ | $//g;
  if (length($n) < 12) {
    print STDERR "okf-restamp: say what you read against what (\"$n\" is not that); nothing re-stamped\n";
    exit 1;
  }
  # The line first: an interrupted run may leave a line with no re-stamp behind it (the
  # gate still flags the anchor), never a re-stamp with no line.
  log_line("* STILL ACCURATE, re-stamped `" . rel($want) . "` <- `$anchor` (last commit on the file: " . blamed($hit->[4]) . "): $n");
  my ($ok, $out) = link_accurate($want, $anchor);
  unless ($ok) { restore_log(); $out =~ s/\s+$//; print STDERR "okf-restamp: drift link failed: $out\n"; exit 1 }
  print "re-stamped $want <- $anchor; logged in $entry under $today\n";
  exit 0;
}

# ---- --format-only -------------------------------------------------------------------
# The lock's signature for each (doc, target).
my %sig;
{
  my $lock = slurp_raw('drift.lock') // unusable('drift.lock unreadable');
  my ($d, $t);
  for (split /\n/, $lock) {
    if    (/^\s*doc\s*=\s*"(.*)"/)    { $d = $1; undef $t }
    elsif (/^\s*target\s*=\s*"(.*)"/) { $t = $1 }
    elsif (/^\s*sig\s*=\s*"(.*)"/ && defined $d && defined $t) { $sig{"$d\t$t"} = $1 }
  }
}

# drift parses these with tree-sitter and already ignores their formatting, so anything it
# flags in them changed a token — and no rule short of a parser can prove a token change
# harmless (`(x,)` is a tuple, `(x)` is not; `x-- - y` is not `x - --y`). Never settled here.
our $PARSED; BEGIN { $PARSED = qr/\.(?:rs|py|pyi|ts|tsx|js|jsx|go|zig|java)$/ }
# drift hashes these raw. In them a line's indentation and its trailing whitespace carry no
# meaning — outside a multi-line string or a backslash continuation, which classify()
# refuses outright. Every other extension (shell, YAML, Makefiles, data) is never settled:
# there, indentation can be syntax. Scala is out too: Scala 3's braceless syntax makes
# indentation syntax, and in Scala 2 a blank line separates a call from a following block.
our $FREEFORM; BEGIN { $FREEFORM = qr/\.(?:c|h|cc|cpp|cxx|hh|hpp|hxx|m|mm|swift|kt|kts|cs|dart)$/ }

# Formatting-only means: the same sequence of lines, blank ones included, each identical
# once its leading and trailing whitespace is dropped. Nothing inside a line may change,
# and no line may be added, removed, joined, split or moved — so no token can fuse, move
# into a comment, leave a preprocessor line, or detach a block from the call before it.
sub classify {
  my ($path, $old, $new) = @_;
  return 'identical' if $old eq $new;
  return undef if $path =~ $PARSED || $path !~ $FREEFORM;
  for ($old, $new) {
    return undef if /\\[ \t\r]*$/m;                   # a continued line: its indentation can be string content
    return undef if /"""|'''|R"[^(\s]{0,16}\(|@\$?"|\$@"/;   # multi-line, raw and verbatim strings (C# @", @$", $@")
  }
  my $lines = sub { [ map { my $l = $_; $l =~ s/^[ \t]+//; $l =~ s/[ \t\r]+$//; $l } split /\n/, shift, -1 ] };
  my ($a, $b) = ($lines->($old), $lines->($new));
  return undef unless @$a == @$b;
  for my $i (0 .. $#$a) { return undef unless $a->[$i] eq $b->[$i] }
  return 'indentation or trailing whitespace';
}

# The signature `drift link` gives this content, computed in a throwaway repository.
my $oracle_n = 0;
sub signature_of {
  my ($doc_path, $target, $content) = @_;
  (my $file = $target) =~ s/#.*//;
  for ($doc_path, $file) { return undef if m{^/} || m{(?:^|/)\.\.(?:/|\z)} }   # stays inside the scratch repo
  my $dir = "$tmp/oracle" . $oracle_n++;
  mkdir $dir or return undef;
  system("git", "init", "-q", $dir) == 0 or return undef;
  for ([$doc_path, "# oracle\n"], [$file, $content]) {
    my ($rel, $body) = @$_;
    my $p = "$dir/$rel"; (my $parent = $p) =~ s{/[^/]+$}{};
    system("mkdir", "-p", $parent) == 0 or return undef;
    open my $h, '>:raw', $p or return undef; print $h $body; close $h;
  }
  my $o = `cd @{[q1($dir)]} && drift link @{[q1($doc_path)]} @{[q1($target)]} 2>&1`;
  my $lock = slurp_raw("$dir/drift.lock") // return undef;
  my ($s) = $lock =~ /^\s*sig\s*=\s*"([^"]*)"/m;
  system("rm", "-rf", $dir);
  return $s;
}

my (@done, @read, %docs_done, %baseline);
for my $s (@stale) {
  my ($d, $id, $path, $reason, $b) = @$s;
  if ($reason ne 'changed_after_baseline') { push @read, "$d <- $id ($reason)"; next }
  # Decided by the language alone: no baseline search, no scratch repositories.
  if ($path =~ $PARSED || $path !~ $FREEFORM) { push @read, "$d <- $id (a language the sweep never settles)"; next }
  my $want = $sig{"$d\t$id"};
  unless (defined $want) { push @read, "$d <- $id (no signature in drift.lock)"; next }
  my $cur = slurp_raw($path);
  unless (defined $cur) { push @read, "$d <- $id (file unreadable)"; next }
  my @commits = split /\n/, `git log --format=%H -n $depth -- @{[q1($path)]} 2>/dev/null`;
  my ($base, $base_c);
  # A reformat flags every concept bound to the file: find each signed version once.
  my $memo = $baseline{"$id\t$want"};
  ($base, $base_c) = @$memo if $memo;
  for my $c ($memo ? () : @commits) {
    my $old = `git show @{[q1("$c:$path")]} 2>/dev/null`;
    next if $?;
    my $got = signature_of($d, $id, $old);
    if (defined $got && $got eq $want) { ($base, $base_c) = ($old, $c); $baseline{"$id\t$want"} = [$old, $c]; last }
  }
  unless (defined $base) { push @read, "$d <- $id (signed version not among the file's last $depth commits)"; next }
  my $kind = classify($path, $base, $cur);
  unless (defined $kind) { push @read, "$d <- $id (content changed since " . substr($base_c, 0, 8) . ")"; next }
  push @done, [$d, $id, $kind, substr($base_c, 0, 8)];
}

# Log, then link: an interrupted sweep may leave the line claiming an anchor the gate still
# flags, never a re-stamp with no line. A link that fails is taken out of the line again.
my $sweep_line = sub {
  my %kinds; $kinds{$_->[2]}++ for @done;
  %docs_done = map { $_->[0] => 1 } @done;
  sprintf("* FORMAT-ONLY, re-stamped mechanically by `okf-restamp.sh --format-only` (%s): %d anchor(s) across %d concept(s), each compared with the version it was signed against: %s",
    join(', ', map { "$_ $kinds{$_}" } sort keys %kinds), scalar @done, scalar keys %docs_done,
    join('; ', map { "`" . rel($_->[0]) . "` <- `$_->[1]` ($_->[2], since $_->[3])" } @done));
};
if (@done) {
  log_line($sweep_line->());
  my @linked;
  for my $e (@done) {
    my ($ok, $out) = link_accurate($e->[0], $e->[1]);
    if ($ok) { push @linked, $e } else { $out =~ s/\s+$//; push @read, "$e->[0] <- $e->[1] (drift link failed: $out)" }
  }
  if (@linked != @done) {
    restore_log();
    @done = @linked;
    log_line($sweep_line->()) if @done;
  }
}

if (@done) {
  print "re-stamped  $_->[0] <- $_->[1]  ($_->[2], signed at $_->[3])\n" for @done;
}
print "needs reading  $_\n" for @read;
printf "%d re-stamped as format-only%s, %d left for reading\n", scalar @done, (@done ? " (one line in $entry)" : ''), scalar @read;
exit 0;
PERL
