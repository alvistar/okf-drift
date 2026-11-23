#!/bin/sh
# okf-links.sh — rewrite a bundle's angle-bracket link destinations to the plain form.
#
#   okf-links.sh [bundle-dir]     (default: knowledge)     run from the REPO ROOT
#
# `[t](<../../docs/a.md>)` was the form this plugin recommended for a link to a repository
# file outside the bundle: okf v0.6.0 accepted it. okf v0.9.0 keeps the brackets in the
# path and reports the link broken (okf-agent-memory#69), so the gate now refuses it
# (docs/adr/0003-links-outside-the-bundle.md). This writes `[t](../../docs/a.md)` instead,
# a space or a parenthesis percent-encoded (`%20`, `%28`, `%29`; OKF v0.3 §6), in every concept.
#
# What it does NOT touch: `index.md` and `log.md` at any level (the frozen log's history is
# hashed), log entries, a fenced block or a code span (an example, not a link), and a link
# inside a code span, which the gate also refuses but whose fix needs a reader. One line
# per rewritten file; idempotent.
#
# Needs sh and perl 5.14+. Exit 0 = done, 2 = unusable.
set -u
bundle=${1:-knowledge}
[ -d "$bundle" ] || { echo "okf-links: no bundle at $bundle (run from the repository root)" >&2; exit 2; }
exec perl - "$bundle" <<'PERL'
use strict; use warnings;
use File::Find; use Cwd qw(abs_path);
my ($bundle) = @ARGV;
$bundle =~ s{/+\z}{} if $bundle =~ m{[^/]};   # `knowledge/` names the same bundle
# A bare destination ends at a space or an unbalanced `)`: percent-encode what would end it.
sub encode { my $d = shift; $d =~ s/([ ()])/sprintf('%%%02X', ord $1)/ge; $d }
my @files;
find({ no_chdir => 1, wanted => sub {
  # Dot-directories are tool state; only the bundle's own log/ holds log entries.
  if (-d && $File::Find::name ne $bundle && ($File::Find::name eq "$bundle/log" || m{/\.[^/]*$})) { $File::Find::prune = 1; return }
  push @files, $File::Find::name if -f && m{\.md$} && !m{(?:^|/)(?:index|log)\.md$};
}}, $bundle);
for my $f (sort @files) {
  open my $in, '<:raw', $f or die "$f: $!"; local $/; my $text = <$in>; close $in;
  # Split into fenced blocks (kept as they are) and the prose between them.
  my @parts = split /(^[ \t]*```.*?^[ \t]*```[^\n]*$)/sm, $text;
  my $n = 0;
  for my $i (0 .. $#parts) {
    next if $i % 2;
    # Inside the prose, keep code spans and rewrite only outside them. A span never
    # crosses a paragraph, so a lone backtick stays literal (as the gate reads it).
    my @out;
    for my $para (split /(\n[ \t]*\n)/, $parts[$i]) {
      my @bits = split /((?<!`)(`+)(?!`).*?(?<!`)\2(?!`))/s, $para;
      for (my $j = 0; $j < @bits; $j++) {
        if ($j % 3 == 0) {
          $bits[$j] =~ s{\]\(\s*<([^<>\n]*)>}{ $n++; "](" . encode($1) }ge;
          push @out, $bits[$j];
        } elsif ($j % 3 == 1) { push @out, $bits[$j] }
      }
    }
    $parts[$i] = join '', @out;
  }
  next unless $n;
  # Write beside the concept and rename over it, so a full disk never truncates it. A
  # symlinked concept is written at its target, so the link stays a link.
  my $dest = -l $f ? abs_path($f) : $f;
  defined $dest or die "$f: cannot resolve the link\n";
  my $tmp = "$dest.okf-links.$$";
  my $mode = (stat $dest)[2] & 07777;
  open my $out, '>:raw', $tmp or die "$tmp: $!";
  print $out join('', @parts) or die "$tmp: $!";
  close $out or die "$tmp: $!";
  chmod $mode, $tmp or die "$tmp: $!";
  rename $tmp, $dest or die "$dest: $!";
  print "okf-links: $f: $n link(s) rewritten\n";
}
PERL
