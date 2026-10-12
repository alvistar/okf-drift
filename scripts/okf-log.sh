#!/bin/sh
# okf-log.sh — the one writer of a branch's log entry.
#
#   okf-log.sh add  [--entry <path>] [--slug <slug>] [--base <ref>] <bundle> "<line>"
#   okf-log.sh path [--entry <path>] [--slug <slug>] [--base <ref>] <bundle>
#   okf-log.sh split [--refreeze] <bundle>
#
# Run from the REPO ROOT. A log entry is <bundle>/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md:
# the date the entry was created, the branch's slug (its last path segment, lowercased,
# every run of non-alphanumerics folded to `-`) and a random suffix, so `alice/fix` and
# `bob/fix` never share a folder. okf treats a nested `log.md` as reserved: not a concept,
# never searched (docs/adr/0001-log-entries-as-reserved-log-files.md).
#
# `add` inserts the line under today's `## YYYY-MM-DD` heading, newest first: on top of
# today's heading when the entry's first heading is today, else under a new heading above
# the first one. A `## ` inside a fenced example or an HTML comment is not a heading.
# `path` prints the entry `add` would write, without writing anything (a new entry gets
# its name here, so `add --entry <that path>` creates exactly it).
#
# Which entry:
#   1. `--entry <path>` wins (it must be <bundle>/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md).
#   2. Otherwise the base is `--base <ref>`, or `origin/HEAD`; the ref used is printed.
#   3. Candidates are the entries the branch added since the merge-base with the base,
#      committed, staged or untracked, whose slug is the branch's slug.
#   4. None: a new entry. One: that one. More: refused, pass --entry.
# Refused without `--slug`: a detached HEAD, the default branch, no git repository. Always
# refused: a missing base ref, shallow history (missing history is not "no entry yet").
# With `--slug` and no usable history (no repository, no base ref, a shallow clone) the
# candidates are the existing entries with that slug in the working tree.
#
# `add` and `path` refuse a bundle whose root log.md is not frozen yet: run /okf-migrate.
#
# `split` makes the root log.md the FROZEN LOG (/okf-migrate runs it): it appends a pointer
# to log/ and, as the last line, the marker
#     <!-- okf-log frozen <YYYY-MM-DD> sha256:<hex> -->
# carrying the split date and the sha256 of every byte above the marker line, line endings
# normalized to LF (a CRLF checkout of the same history hashes the same). The bytes already
# there are kept as they are, and log/ is created. On a log that is already frozen it
# changes nothing. `split --refreeze` re-hashes the history after a deliberate fix and
# keeps the split date. Both refuse when text sits below the marker: that text belongs in
# a log entry. The gate (okf-check.sh) checks the hash.
#
# Exit 0 = written (or printed), 1 = refused, nothing written, 2 = unusable.
set -u
die() { echo "okf-log: $*" >&2; exit 2; }
command -v perl >/dev/null 2>&1 || die 'perl not on PATH'
exec perl - "$(date +%F)" "$@" <<'PERL'
use strict; use warnings;
my $today = shift @ARGV;
sub unusable { print STDERR "okf-log: @_\n"; exit 2 }
sub refuse   { print STDERR "okf-log: @_\n"; exit 1 }
my $usage = 'usage: okf-log.sh add|path [--entry <path>] [--slug <slug>] [--base <ref>] <bundle> ["<line>"]'
          . ' | split [--refreeze] <bundle>';
my $cmd = shift(@ARGV) // unusable($usage);
unusable($usage) unless $cmd eq 'add' || $cmd eq 'path' || $cmd eq 'split';
my (%opt, @pos);
while (@ARGV) {
  my $a = shift @ARGV;
  if ($a eq '--refreeze' && $cmd eq 'split') { $opt{refreeze} = 1 }
  elsif ($a =~ /\A--(entry|slug|base)\z/ && $cmd ne 'split') { defined($opt{$1} = shift @ARGV) or unusable("$a needs a value") }
  elsif ($a =~ /\A--(entry|slug|base)=(.*)\z/s && $cmd ne 'split') { $opt{$1} = $2 }
  elsif ($a eq '--') { push @pos, @ARGV; last }
  elsif ($a =~ /\A--/) { unusable("unknown option $a") }
  else { push @pos, $a }
}
unusable($usage) unless @pos == ($cmd eq 'add' ? 2 : 1);
my ($bundle, $line) = @pos;
$bundle =~ s{\A(?:\./)+}{}; $bundle =~ s{(?<=.)/+\z}{};
-d $bundle or unusable("no bundle at $bundle (run from the repository root)");

sub slurp_raw { my $f = shift; open my $h, '<:raw', $f or return undef; local $/; my $c = <$h>; $c // '' }
sub write_raw {
  my ($f, $t) = @_;
  open my $h, '>:raw', "$f.tmp" or unusable("$f.tmp: $!");
  print $h $t; close $h or unusable("$f.tmp: $!");
  rename "$f.tmp", $f or unusable("$f: $!");
}
# The frozen log. The marker is the LAST line matching MARKER; `$+[0]` ends it.
my $MARKER = qr/^<!-- okf-log frozen (\d{4}-\d{2}-\d{2}) sha256:([0-9a-f]{64}) -->[ \t]*\r?$/m;
my $root_log = "$bundle/log.md";
sub find_marker {   # (start of the marker line, end of it, date, hash) or ()
  my $t = shift; my @m;
  while ($t =~ /$MARKER/g) { @m = ($-[0], $+[0], $1, $2) }
  return @m;
}
sub history_hash { require Digest::SHA; (my $h = shift) =~ s/\r\n/\n/g; Digest::SHA::sha256_hex($h) }

if ($cmd eq 'split') {
  -f $root_log or refuse("no $root_log to freeze");
  my $t = slurp_raw($root_log) // unusable("$root_log unreadable");
  my ($start, $end, $date, $hash) = find_marker($t);
  if (!defined $start) {
    refuse("$root_log is not frozen yet: run `okf-log.sh split $bundle` (no --refreeze) first") if $opt{refreeze};
    my $eol = $t =~ /\r\n/ ? "\r\n" : "\n";
    my $sep = $t !~ /\S/ ? '' : $t =~ /$eol$eol\z/ ? '' : $t =~ /\n\z/ ? $eol : "$eol$eol";
    my $above = $t . $sep
      . "New log entries live in `log/`, one folder per branch (`log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md`),$eol"
      . "written with `okf-log.sh add`. Everything above the marker below is frozen: the gate fails$eol"
      . "on any change to it (a deliberate fix is re-hashed with `okf-log.sh split --refreeze`).$eol$eol";
    -d "$bundle/log" or mkdir "$bundle/log" or unusable("$bundle/log: $!");
    write_raw($root_log, $above . "<!-- okf-log frozen $today sha256:" . history_hash($above) . " -->$eol");
    print "froze $root_log on $today; new log entries go in $bundle/log/\n";
    exit 0;
  }
  refuse("text below the marker in $root_log: move it into a log entry (okf-log.sh add $bundle '<line>'), "
       . "then delete it from $root_log") if substr($t, $end) =~ /\S/;
  my $now = history_hash(substr($t, 0, $start));
  -d "$bundle/log" or mkdir "$bundle/log" or unusable("$bundle/log: $!");
  if (!$opt{refreeze}) {
    print "$root_log is already frozen (split on $date); nothing to do\n";
    print STDERR "okf-log: the history above the marker changed since it was frozen: "
               . "if the change is deliberate, `okf-log.sh split --refreeze $bundle`\n" if $now ne $hash;
    exit 0;
  }
  if ($now eq $hash) { print "$root_log: the history is unchanged; nothing to re-hash\n"; exit 0 }
  my $marker = substr($t, $start, $end - $start);
  $marker =~ s/sha256:[0-9a-f]{64}/sha256:$now/;
  write_raw($root_log, substr($t, 0, $start) . $marker . substr($t, $end));
  print "re-froze $root_log (split on $date): the marker now hashes the corrected history\n";
  exit 0;
}
if (-f $root_log && !find_marker(slurp_raw($root_log) // '')) {
  refuse("$root_log is not frozen yet, so there is nowhere to write a log entry: run /okf-migrate "
       . "(it runs `okf-log.sh split $bundle`) first");
}
if ($cmd eq 'add') {
  $line =~ s/\s+\z//;
  refuse('nothing to log: the line is empty') unless $line =~ /\S/;
}

my $NAME = qr/(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9a-f]{4})/;
sub slugify { my $s = lc shift; $s =~ s/[^a-z0-9]+/-/g; $s =~ s/\A-+|-+\z//g; $s }
sub git {   # stdout of a git command, undef when it fails; stderr dropped
  my $pid = open my $h, '-|';
  return undef unless defined $pid;
  if (!$pid) { open STDERR, '>', '/dev/null'; exec 'git', @_; exit 127 }
  local $/; my $o = <$h>; close $h or return undef;
  $o //= ''; $o =~ s/\n\z//; return $o;
}

my $entry;
if (defined $opt{entry}) {
  ($entry = $opt{entry}) =~ s{\A(?:\./)+}{};
  refuse("--entry must be $bundle/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md (got '$opt{entry}')")
    unless $entry =~ m{\A\Q$bundle\E/log/$NAME/log\.md\z};
} else {
  my $slug;
  if (defined $opt{slug}) {
    $slug = slugify($opt{slug});
    refuse("--slug '$opt{slug}' has no letter or digit") unless length $slug;
  }
  my $in_git = (git('rev-parse', '--is-inside-work-tree') // '') eq 'true';
  my $base = $opt{base} // 'origin/HEAD';
  my ($mb, $why_not, $shallow);
  if (!$in_git) {
    refuse('not a git repository: pass --slug <slug> (or --entry <path>) to name the entry') unless defined $slug;
    $why_not = 'not a git repository';
  } else {
    my $branch = git('symbolic-ref', '-q', '--short', 'HEAD');
    if (!defined $slug) {
      refuse('HEAD is detached: pass --slug <slug> (or --entry <path>) to name the entry') unless defined $branch;
    }
    my $base_sha = git('rev-parse', '-q', '--verify', "$base^{commit}");
    if (!defined $base_sha) {
      $why_not = "base ref $base not found";
    } elsif ((git('rev-parse', '--is-shallow-repository') // '') eq 'true') {
      ($why_not, $shallow) = ('the history is shallow', 1);
    } else {
      $mb = git('merge-base', 'HEAD', $base_sha);
      $why_not = "no merge-base between HEAD and $base" unless defined $mb && length $mb;
    }
    if (!defined $slug) {
      # The default branch: what the base names (origin/HEAD -> origin/main -> main).
      my %default;
      for my $ref ($base, 'origin/HEAD') {
        my $full = git('rev-parse', '-q', '--symbolic-full-name', $ref) // next;
        $default{$1} = 1 if $full =~ m{\Arefs/(?:heads|remotes/[^/]+)/(.+)\z} && $1 ne 'HEAD';
      }
      refuse("on the default branch $branch: pass --slug <slug> (or --entry <path>) to name the entry")
        if $default{$branch};
      if (defined $why_not) {
        refuse("$why_not: the entry this branch added cannot be found. Fetch the full history "
             . "(git fetch --unshallow), or pass --base <ref>, --slug <slug> or --entry <path>")
          if $shallow;
        refuse("$why_not: pass --base <ref> (default origin/HEAD; `git remote set-head origin -a` sets it), "
             . "or --slug <slug> or --entry <path>");
      }
      $slug = slugify((split m{/}, $branch)[-1]);
      refuse("the branch name '$branch' gives no slug: pass --slug <slug>") unless length $slug;
    }
  }
  my @cand;
  if (defined $mb && !defined $why_not) {
    print STDERR "okf-log: base $base (merge-base " . substr($mb, 0, 8) . ")\n";
    my %seen;
    for my $out (git('diff', '--name-only', '--relative', '--diff-filter=A', $mb, '--', "$bundle/log"),
                 git('diff', '--cached', '--name-only', '--relative', '--diff-filter=A', $mb, '--', "$bundle/log"),
                 git('ls-files', '--others', '--exclude-standard', '--', "$bundle/log")) {
      unusable('git could not list the entries this branch added') unless defined $out;
      for (split /\n/, $out) {
        next unless m{(?:\A|/)log/($NAME)/log\.md\z};
        my ($name, $s) = ($1, $3);
        next unless $s eq $slug;
        my $p = "$bundle/log/$name/log.md";
        push @cand, $p if -f $p && !$seen{$p}++;
      }
    }
  } else {
    print STDERR "okf-log: $why_not; using the working tree's entries named '$slug'\n";
    for my $p (sort glob("\Q$bundle\E/log/*/log.md")) {
      push @cand, $p if $p =~ m{/log/$NAME/log\.md\z} && $2 eq $slug;
    }
  }
  if (@cand > 1) {
    refuse("more than one entry could be this branch's: " . join(', ', sort @cand) . "; pass --entry <path>");
  } elsif (@cand) {
    $entry = $cand[0];
  } else {
    for (1 .. 64) {
      my $hex;
      if (open my $r, '<:raw', '/dev/urandom') { read $r, my $b, 2; $hex = unpack 'H4', $b }
      else { $hex = sprintf '%04x', int rand 65536 }
      my $p = "$bundle/log/$today-$slug-$hex/log.md";
      unless (-e "$bundle/log/$today-$slug-$hex") { $entry = $p; last }
    }
    unusable('could not name a new entry') unless defined $entry;
  }
}

if ($cmd eq 'path') { print "$entry\n"; exit 0 }

my $t;
if (-e $entry) {
  $t = slurp_raw($entry) // unusable("$entry unreadable");
} else {
  (my $dir = $entry) =~ s{/log\.md\z}{};
  (my $logdir = $dir) =~ s{/[^/]+\z}{};
  for ($logdir, $dir) { -d $_ or mkdir $_ or unusable("$_: $!") }
  $t = '';
}
my @skip;
while ($t =~ /(<!--.*?-->|^[ \t]*```.*?^[ \t]*```[^\n]*$)/smg) { push @skip, [$-[0], $+[0]] }
my ($at, $is_today);
while ($t =~ /^## ([^\n]*)$/mg) {
  my ($pos, $h) = ($-[0], $1);
  next if grep { $pos >= $_->[0] && $pos < $_->[1] } @skip;
  ($at, $is_today) = ($pos, $h =~ /^\Q$today\E[ \t]*$/ ? 1 : 0);
  last;
}
if    ($t !~ /\S/)     { $t = "## $today\n$line\n" }
elsif (!defined $at)   { $t =~ s/\n*\z/\n\n## $today\n$line\n/ }
elsif ($is_today)      { my $eol = index($t, "\n", $at); if ($eol < 0) { $t .= "\n$line\n" } else { substr($t, $eol + 1, 0) = "$line\n" } }
else                   { substr($t, $at, 0) = "## $today\n$line\n\n" }
write_raw($entry, $t);
print "logged in $entry under $today\n";
exit 0;
PERL
