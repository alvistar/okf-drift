#!/bin/sh
# okf-tidy.sh — do the bundle's bookkeeping that needs no judgement.
#
#   okf-tidy.sh [bundle-dir]     (default: knowledge)     run from the REPO ROOT
#
# Two rules the gate enforces and an agent used to satisfy by hand, copying text:
#
#   index rows    every row in an `index.md` that links to a concept carries that
#                 concept's `description:` verbatim (rewritten when it does not), and a
#                 concept with no row in its category's `index.md` gets one, appended
#                 after the last row: `- [<title>](/<path>) — <description>`.
#   last_updated  every concept that differs from HEAD (modified, added or untracked) has
#                 `last_updated:` set to today.
#
# What it does NOT touch: `stale_after` (it means "I reviewed this against reality", a
# judgement), a concept with no one-line description (the gate names it), the order of
# rows, and anything outside the bundle. It prints one line per change and is idempotent.
#
# Needs sh, perl 5.14+, git. Exit 0 = done, 2 = unusable.
set -u
bundle=${1:-knowledge}
[ -d "$bundle" ] || { echo "okf-tidy: no bundle at $bundle (run from the repository root)" >&2; exit 2; }
git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "okf-tidy: not a git repository" >&2; exit 2; }
tmp=$(mktemp "${TMPDIR:-/tmp}/okf-tidy.XXXXXX") || exit 2
trap 'rm -f "$tmp"' EXIT
trap 'exit 2' INT TERM
# NUL-separated: without -z, git quotes a path holding a space or a non-ASCII byte, and
# that concept silently never matched.
git status --porcelain -z --untracked-files=all -- "$bundle" >| "$tmp" || exit 2

perl - "$bundle" "$(date +%F)" "$tmp" <<'PERL'
use strict; use warnings; use utf8;
use File::Find; use File::Basename; use File::Spec; use Cwd qw(abs_path);
binmode STDOUT, ':utf8';
my ($bundle, $today, $status_file) = @ARGV;
my $changed = do { open my $h, '<:raw', $status_file or die "okf-tidy: $status_file: $!\n"; local $/; <$h> // '' };
sub slurp { my $f = shift; open my $h, '<:utf8', $f or die "okf-tidy: $f: $!\n"; local $/; my $c = <$h>; $c // '' }
sub spew  { my ($f, $c) = @_; open my $h, '>:utf8', "$f.tmp" or die "okf-tidy: $f: $!\n"; print $h $c; close $h or die; rename "$f.tmp", $f or die "okf-tidy: $f: $!\n" }
# Every path below is relative to the repository root, the namespace git status speaks.
my $top = `git rev-parse --show-toplevel`; chomp $top;
my $bdir = File::Spec->abs2rel(abs_path($bundle), abs_path($top));
chdir $top or die "okf-tidy: $top: $!\n";
# File::Find yields bytes; a row and a printed line want characters.
sub chars { my $s = shift; utf8::decode($s); $s }

my (@concepts, @indexes);
find({ no_chdir => 1, wanted => sub {
  return unless -f && /\.md$/;
  (my $rel = $File::Find::name) =~ s{^\Q$bdir\E/}{};
  $rel = chars($rel);
  if    ($rel =~ m{(^|/)index\.md$}) { push @indexes, $rel }
  elsif ($rel =~ m{(^|/)log\.md$})   { }
  else                               { push @concepts, $rel }
}}, $bdir);
@concepts = sort @concepts;

my $n = 0;
# 1. last_updated on what changed. `XY path\0`, and a rename's old path follows as its own
# NUL-terminated field, which is skipped.
my %touched;
my @fields = split /\0/, $changed;
while (defined(my $f = shift @fields)) {
  my ($xy, $path) = $f =~ /^(..) (.*)\z/s or next;
  shift @fields if $xy =~ /[RC]/;
  $path = chars($path);
  $touched{$1} = 1 if $path =~ m{^\Q$bdir\E/(.+\.md)\z};
}
for my $rel (grep { $touched{$_} } @concepts) {
  my $f = "$bdir/$rel"; my $t = slurp($f);
  my ($fm) = $t =~ /\A---\n(.*?)\n---\n/s or next;
  my ($cur) = $fm =~ /^last_updated:[ \t]*["']?([^"'\n]*?)["']?[ \t]*$/m;
  next if defined $cur && $cur eq $today;
  my $new = $fm;
  if (defined $cur) { $new =~ s/^last_updated:.*$/last_updated: $today/m }
  else              { $new .= "\nlast_updated: $today" }
  $t =~ s/\A---\n\Q$fm\E\n---\n/---\n$new\n---\n/;
  spew($f, $t); $n++;
  print "last_updated  $rel -> $today\n";
}

# 2. Index rows. Read each concept's title and one-line description.
my (%desc, %title);
for my $rel (@concepts) {
  my ($fm) = slurp("$bdir/$rel") =~ /\A---\n(.*?)\n---\n/s or next;
  for my $k (qw(description title)) {
    my ($v) = $fm =~ /^$k:[ \t]*(\S.*?)[ \t]*$/m or next;
    next if $v =~ /^[>|]/;
    $v =~ s/^(["'])(.*)\1$/$2/;
    ($k eq 'description' ? $desc{$rel} : $title{$rel}) = $v;
  }
}
my %listed;
for my $idx (sort @indexes) {
  my $f = "$bdir/$idx"; my $t = slurp($f); my $orig = $t;
  # Rows inside an HTML comment or a fence are examples, not rows.
  my @skip;
  while ($t =~ /(<!--.*?-->|```.*?```)/sg) { push @skip, [$-[0], $+[0]] }
  $t =~ s{^(- \[[^\]]+\]\((/[^)\s]+)\) — )(.*)$}{
    my ($head, $path, $d, $at) = ($1, $2, $3, $-[0]);
    (my $target = $path) =~ s{^/}{};
    if (grep { $at >= $_->[0] && $at < $_->[1] } @skip) { "$head$d" }
    else {
      $listed{"$idx\t$target"} = 1;
      if (defined $desc{$target} && $d ne $desc{$target}) { $n++; print "index row     $idx: $path takes the concept's description\n"; "$head$desc{$target}" }
      else { "$head$d" }
    }
  }meg;
  spew($f, $t) if $t ne $orig;
}
for my $rel (@concepts) {
  next unless defined $desc{$rel};
  if ($rel =~ /\s/) {   # an index row cannot link to it; adding one would repeat every run
    print "skipped       $rel: a path holding whitespace cannot be an index row — rename it\n";
    next;
  }
  my $dir = dirname($rel); my $idx = $dir eq '.' ? 'index.md' : "$dir/index.md";
  next if $listed{"$idx\t$rel"};
  next unless -f "$bdir/$idx";       # a category with no index is the gate's to name
  my $title = $title{$rel} // (basename($rel, '.md') =~ s/-/ /gr);
  my $row = "- [$title](/$rel) — $desc{$rel}";
  my $t = slurp("$bdir/$idx");
  # The last REAL row: one inside an HTML comment or a fence is an example, and a row
  # added after it would land in the example, never count as listed, and repeat each run.
  my @skip;
  while ($t =~ /(<!--.*?-->|```.*?```)/sg) { push @skip, [$-[0], $+[0]] }
  my $last;
  while ($t =~ /^- \[[^\]]+\]\(\/[^)\s]+\) — .*$/mg) {
    my ($from, $to) = ($-[0], $+[0]);
    $last = $to unless grep { $from >= $_->[0] && $from < $_->[1] } @skip;
  }
  if (defined $last) { substr($t, $last, 0) = "\n$row" }
  else               { $t =~ s/\n*\z/\n\n$row\n/ }
  spew("$bdir/$idx", $t); $n++;
  print "index row     $idx: added /$rel\n";
}
print $n ? "okf-tidy: $n change(s) in $bundle\n" : "okf-tidy: nothing to do in $bundle\n";
PERL
