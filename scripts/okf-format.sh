#!/bin/sh
# okf-format.sh — move a bundle's files to OKF v0.3, the edits that need no judgement.
#
#   okf-format.sh [bundle-dir]     (default: knowledge)     run from the REPO ROOT
#
# OKF v0.3 §6 resolves a path field without a leading `/` from the folder of the file that
# holds it. This plugin's bundles wrote a repository file in `sources[].resource` (and
# `resource`) from the repository root (`resource: docs/x.md`), which v0.3 reads as
# `knowledge/<dir>/docs/x.md`. So this:
#
#   okf_version    sets `okf_version: "0.3"` in the root index.md frontmatter;
#   resource       rewrites a `resource:` value that names no file from the concept's folder
#                  but names one from the repository root into the path relative to the
#                  concept (`../../docs/x.md`), quoting kept;
#   superseded_by  adds `superseded_by: /decisions/<x>.md` under `status: deprecated` on a
#                  decision whose body says `Superseded by [..](/decisions/<x>.md)`.
#
# What it does NOT touch: `title:` and `description:` of the root index (they need the
# owner's words; it says when they are missing), a URL, a `/` path, a value with a space (a
# descriptor, not a path), a value that resolves already, one whose first segment is not at
# the repository root or is also a folder of the bundle (the gate names it), and log files. Each file is
# written beside itself and renamed into place. One line per change; idempotent.
#
# Needs sh and perl 5.14+. Exit 0 = done, 2 = unusable.
set -u
bundle=${1:-knowledge}
[ -d "$bundle" ] || { echo "okf-format: no bundle at $bundle (run from the repository root)" >&2; exit 2; }
[ -f "$bundle/index.md" ] || { echo "okf-format: no root index.md in $bundle" >&2; exit 2; }
exec perl - "$bundle" <<'PERL'
use strict; use warnings;
use File::Find; use File::Basename; use File::Spec; use Cwd qw(abs_path getcwd);
my ($bundle) = @ARGV;
$bundle =~ s{/+\z}{} if $bundle =~ m{[^/]};
my $repo = abs_path(getcwd());
sub slurp { my $f = shift; open my $h, '<:raw', $f or die "$f: $!"; local $/; my $c = <$h>; defined $c ? $c : '' }
sub inside_repo { my $p = shift; defined $p && ($p eq $repo || index($p, "$repo/") == 0) }
sub spew {
  my ($f, $text) = @_;
  my $dest = -l $f ? abs_path($f) : $f;
  defined $dest or die "$f: cannot resolve the link\n";
  inside_repo(abs_path($dest)) or die "$f: links outside the repository; not rewritten\n";
  my $tmp = "$dest.okf-format.$$";
  my $mode = (stat $dest)[2] & 07777;
  open my $out, '>:raw', $tmp or die "$tmp: $!";
  print $out $text or die "$tmp: $!";
  close $out or die "$tmp: $!";
  chmod $mode, $tmp or die "$tmp: $!";
  rename $tmp, $dest or die "$dest: $!";
}

# The root index.
my $root = "$bundle/index.md";
my $t = slurp($root);
# A root that opens a frontmatter this script cannot read (CRLF line endings, no closing
# `---`) would get a second one stacked above it: refuse instead.
if ($t =~ /\A---[ \t]*\r?\n/ && $t !~ /\A---\n(.*?)\n---\n/s) {
  print STDERR "okf-format: $root: its frontmatter is not LF line endings closed by `---`; normalise the line endings (or close it), then rerun\n";
  exit 2;
}
my $nt = $t;
if ($nt =~ /\A---\n(.*?)\n---\n/s) {
  my $fm = $1; my $new = $fm;
  $new =~ s/^okf_version:.*$/okf_version: "0.3"/m or $new = qq(okf_version: "0.3"\n$new);
  $nt =~ s/\A---\n\Q$fm\E\n---\n/---\n$new\n---\n/ if $new ne $fm;
} else {
  $nt = qq(---\nokf_version: "0.3"\n---\n$nt);
}
if ($nt ne $t) { spew($root, $nt); print "okf-format: $root: okf_version \"0.3\"\n" }
my ($rfm) = $nt =~ /\A---\n(.*?)\n---\n/s;
for my $k (qw(title description)) {
  print "okf-format: $root: no $k: yet — write it in the root frontmatter (OKF v0.3 §8.1)\n" unless $rfm =~ /^$k:\s*\S/m;
}

# Concepts.
my @files;
find({ no_chdir => 1, wanted => sub {
  if (-d && $File::Find::name ne $bundle && ($File::Find::name eq "$bundle/log" || m{/\.[^/]*$})) { $File::Find::prune = 1; return }
  push @files, $File::Find::name if -f && m{\.md$} && !m{(?:^|/)(?:index|log)\.md$};
}}, $bundle);
for my $f (sort @files) {
  my $text = slurp($f);
  my ($fm, $rest) = $text =~ /\A---\n(.*?)\n---\n(.*)\z/s or next;
  my $dir = dirname($f);
  my @changes; my $cur = ''; my @lines;
  for my $line (split /\n/, $fm, -1) {
    $cur = $1 if $line =~ /^([A-Za-z_][\w-]*):/;
    # Only `resource:` on top, or inside a `sources` item: never an extension's own key.
    # A comment after an unquoted value is set aside and put back unchanged.
    my $comment = $line =~ s/^(\s*(?:-\s+)?resource:\s*(?:"[^"\n]*"|'[^'\n]*'|[^"'\s][^\n]*?))(\s+#.*)\z/$1/ ? $2 : '';
    if ((($cur eq 'resource' && $line =~ /^resource:/) || ($cur eq 'sources' && $line !~ /^sources:/))
        && $line =~ /^(\s*(?:-\s+)?resource:\s*)(["']?)([^"'\n]+?)\2(\s*)$/) {
      my ($pre, $q, $v, $post) = ($1, $2, $3, $4);
      (my $p = $v) =~ s/[?#].*\z//s;
      (my $d = $p) =~ s/%([0-9A-Fa-f]{2})/chr(hex $1)/ge;
      # Known by its first segment at the repository root, so a file the checkout lacks
      # (a submodule not fetched) is rewritten too, the same in every checkout.
      my ($first) = split m{/}, $d;
      if ($v !~ m{^[A-Za-z][A-Za-z0-9+.-]*:} && $v !~ m{^/} && $v !~ /\s/ && length $p
          && !-e "$dir/$d" && defined $first && $first !~ /^\.\.?\z/ && -e $first
          && !-e "$dir/$first" && !-e "$bundle/$first" && inside_repo(abs_path($first))) {
        my $out = File::Spec->abs2rel(File::Spec->rel2abs($p), abs_path($dir)) . substr($v, length $p);
        push @changes, "resource $v -> $out";
        $line = "$pre$q$out$q$post";
      }
    }
    push @lines, $line . $comment;
  }
  my $new = join "\n", @lines;
  if ($new =~ /^status:\s*deprecated\s*$/m && $new !~ /^superseded_by:/m
      && $rest =~ /Superseded by\s*\[[^\]]+\]\((\/decisions\/[^)\s]+\.md)\)/i) {
    my $to = $1;
    $new =~ s/^(status:\s*deprecated\s*)$/$1\nsuperseded_by: $to/m;
    push @changes, "superseded_by $to";
  }
  next unless @changes;
  spew($f, "---\n$new\n---\n$rest");
  print "okf-format: $f: $_\n" for @changes;
}
PERL
