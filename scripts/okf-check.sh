#!/bin/sh
# okf-check.sh — the knowledge gate `okf validate` alone is not.
#
#   okf-check.sh [bundle-dir]        (default: knowledge)      exit 0 = clean
#
# Measured on okf v0.6.0: `okf validate --strict --drift --stale` exits non-zero for a
# missing `type`, a broken link, an orphan (a concept with no links in OR out), a status
# outside draft|stable|deprecated, a bare-string `sources` item and a `stale_after` that is
# today or earlier — and for nothing else. A dead `code_refs` path and a concept missing
# from its parent index are WARNINGS that leave the exit code at 0 even under --strict;
# index descriptions are never compared. So this script:
#
#   1. runs okf's gate and treats its warning list as fatal;
#   2. checks every index row resolves to a concept, is unique, and carries the concept's
#      description verbatim — and every concept has a row in its category index;
#   3. checks frontmatter the tool ignores: one-line description, ISO last_updated and
#      stale_after, and for decisions/ an ISO date, a link to a concept outside
#      decisions/, and a "Superseded by" link when status is deprecated (the status
#      vocabulary itself, draft|stable|deprecated, okf --strict does enforce);
#   4. fails on leftover template material: HTML comments (search indexes them), the
#      population placeholders, and a section with no content;
#   5. checks the reserved files: root okf_version; log.md frozen (its marker the last
#      line, the history above it unchanged — else it names /okf-migrate or the log entry
#      to write instead) and every log entry's `## ` heading a bare ISO date; project/state.md's three lists,
#      and warns on a state item long enough to be evidence — and, over every concept, on
#      a `stale_after` that falls within the next OKF_REVIEW_WINDOW_DAYS days (default
#      30): the day it arrives, step 1 fails it, so the review is better done before;
#   6. fails while a `drift.lock` sits beside the bundle: drift is no longer used
#      (docs/adr/0002-drop-drift-code-is-the-source-of-truth.md), and a leftover lock
#      means the repository has not run /okf-migrate.
#
# A concept with empty `code_refs` is grouped into one `warn` line: `okf search
# --for-path <file>` can never return it.
#
# Other warnings (do not fail): an okf version other than the one measured. The runtime
# skill and standalone CI bootstrap call the pinned launcher; no consumer copy is needed.
# Run it from the repository root: code_refs are rooted there.
# Needs sh, perl 5.14+ (JSON::PP is core) and okf.
set -u
shell_warns=0
bundle=${1:-knowledge}
[ -d "$bundle" ] || { echo "no bundle at $bundle" >&2; exit 2; }
command -v okf >/dev/null 2>&1 || { echo "okf not on PATH" >&2; exit 2; }

ver=$(okf version 2>/dev/null | head -1)
case "$ver" in
  *v0.6.0*) ;;
  *) shell_warns=$((shell_warns+1)); echo "warn  okf is '$ver'; this gate was measured against v0.6.0 — re-check references/okf-quirks.md" ;;
esac

# okf v0.6.0 refuses a bundle root that resolves outside the directory holding it — a
# `knowledge -> /elsewhere` symlink — with no JSON, which step 1 would only report as "no
# JSON". Name the cause here instead. (v0.3.0 loaded the same link as an EMPTY bundle.)
real_bundle=$(CDPATH= cd -P -- "$bundle" 2>/dev/null && pwd) || { echo "okf-check: cannot resolve $bundle" >&2; exit 2; }
real_parent=$(CDPATH= cd -P -- "$(dirname "$bundle")" 2>/dev/null && pwd) || { echo "okf-check: cannot resolve the parent of $bundle" >&2; exit 2; }
case "$real_bundle/" in
  "${real_parent%/}"/*) ;;
  *) echo "FAIL  $bundle resolves to $real_bundle, outside $real_parent — okf v0.6.0 refuses a bundle root that leaves its parent directory; move the bundle into the repository instead of linking it"; exit 1 ;;
esac

json=$(okf validate "$bundle" --strict --drift --stale --json)
okf_status=$?

parent=$(dirname "$bundle")

# The profile says what the bundle describes. `code` (the default, no file) is a software
# repository: concepts govern code paths and a state snapshot is expected. `wiki` is a
# bundle that describes no code — a personal or company knowledge base — where `code_refs`
# is meaningless and a project snapshot does not exist. Declared by `.okf-profile` beside the bundle, one word. Anything else fails closed:
# a misspelt profile silently falling back to `code` would bury a wiki in warnings, and one
# falling back to `wiki` would switch off the checks a code repository relies on.
profile=code
if [ -f "$parent/.okf-profile" ]; then
  profile=$(tr -d '[:space:]' < "$parent/.okf-profile")
  case "$profile" in
    code|wiki) ;;
    *) echo "okf-check: $parent/.okf-profile says '$profile'; expected 'code' or 'wiki'" >&2; exit 2 ;;
  esac
fi
# okf's JSON reaches perl through a FILE, never argv. Linux caps a SINGLE argument at
# MAX_ARG_STRLEN (131072 bytes) independently of ARG_MAX, and a large bundle's report
# passes that (a drift report on ~48 anchors measured 183806 bytes). macOS has no comparable
# per-argument cap, so this only ever fails in Linux CI, as `exec: perl: Argument list too
# long`, exit 126 — a green local run proves nothing about it.
#
# No `exec`: the EXIT trap has to survive to remove the directory, and exec would replace
# the shell before it fires. The exit code is forwarded by hand instead.
tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-check.XXXXXX") || { echo "okf-check: cannot create a temp dir" >&2; exit 2; }
trap 'rm -rf "$tmp"' EXIT INT TERM
printf '%s' "$json" > "$tmp/okf.json" || exit 2

perl - "$bundle" "$tmp/okf.json" "$parent" "$okf_status" "$profile" "$shell_warns" "$( [ -f "$parent/drift.lock" ] && echo 1 || echo 0 )" <<'PERL'
use strict; use warnings; use utf8;
use JSON::PP; use File::Find; use File::Basename; use Time::Local qw(timegm); use Digest::SHA qw(sha256_hex);
binmode STDOUT, ':utf8';
my ($bundle, $json_file, $parent, $okf_status, $profile, $shell_warns, $has_lock) = @ARGV;
# A wiki is relieved of the code-only expectations: the snapshot and code_refs.
my $wiki = ($profile // 'code') eq 'wiki';
# Read as raw bytes and decode explicitly: decode_json expects UTF-8 octets, and a
# ':utf8' read would hand it characters instead.
sub slurp_raw { my $f=shift; open my $h,'<:raw',$f or die "$f: $!"; local $/; my $c=<$h>; defined $c ? $c : '' }
my $json       = slurp_raw($json_file);
my $fail = 0;
sub bad  { $fail = 1; print "FAIL  @_\n" }
my $warnings = $shell_warns // 0;
sub warnl{ $warnings++; print "warn  @_\n" }
sub slurp{ my $f=shift; open my $h,'<:utf8',$f or die "$f: $!"; local $/; <$h> }
my $ISO = qr/^\d{4}-\d{2}-\d{2}$/;
my $STATE_ITEM_MAX = 300;
# The snapshot and its evidence are prose about the project, not about code: they are
# expected to carry no code_refs, and warning about them every run
# teaches skimming.
my $EXEMPT = qr{^project/state(?:-evidence)?\.md$};
my (@no_code_refs, @open_questions, @review_due);
# Review notice. okf --stale fails a concept ON its stale_after date (measured on v0.6.0:
# `stale_after 2026-10-08 <= 2026-10-08`), so the useful moment to hear about it is before.
# Scaffolds stamp every concept with the same +3 months, so without notice a bundle's whole
# review lands as one red gate on one day.
my $REVIEW_WINDOW = length($ENV{OKF_REVIEW_WINDOW_DAYS} // '') ? $ENV{OKF_REVIEW_WINDOW_DAYS} : 30;   # set-but-empty (a CI var) = default
if ($REVIEW_WINDOW !~ /^\d+$/) { print "FAIL  OKF_REVIEW_WINDOW_DAYS='$REVIEW_WINDOW' is not a whole number of days\n"; exit 2 }
# okf decides staleness on the UTC date (measured on v0.6.0 under TZ=Pacific/Kiritimati), so
# the window counts from the same day; local time would disagree with the gate each evening.
my $today_days = do { my @t = gmtime; int(timegm(0, 0, 0, $t[3], $t[4], $t[5] + 1900) / 86400) };
# An open question written into a concept — a claim the writer could not confirm. Not a
# template placeholder (those FAIL below): a real bundle carries some, and they must stay
# visible rather than pass silently. English and Italian spellings.
my $OPEN_QUESTION = qr/\[(?:TO VERIFY|DA VERIFICARE)\]/;

# One `warn` line per diagnostic, not one per concept: 29 identical lines are read as
# noise. The list is
# capped too: the same names reprinted on every run were ~500 lines across the reference
# consumers' sessions, read and ignored each time. OKF_VERBOSE=1 prints them all.
my $GROUP_MAX = 8;
sub grouped {
  my ($label, @members) = @_;
  return unless @members;
  my $head = sprintf("%d concept(s) %s: ", scalar @members, $label);
  my $more = 0;
  if (!$ENV{OKF_VERBOSE} && @members > $GROUP_MAX) {
    $more = @members - $GROUP_MAX;
    @members = (sort @members)[0 .. $GROUP_MAX - 1];
  }
  my $indent = '        ';
  my @lines; my $line = ''; my $prefix = length("warn  ") + length($head);
  for my $m (sort @members) {
    my $piece = length($line) ? ", $m" : $m;
    if (length($line) && $prefix + length($line) + length($piece) > 100) {
      push @lines, "$line,"; $line = $m; $prefix = length($indent);
    }
    else { $line .= $piece }
  }
  push @lines, $line if length $line;
  push @lines, "… and $more more (OKF_VERBOSE=1 lists them)" if $more;
  warnl($head . shift @lines);
  print "$indent$_\n" for @lines;
}

# 1. okf's own verdict, warnings included.
my $v = eval { decode_json($json) };
if (!$v) {
  bad("okf validate produced no JSON (run it without --json for the findings)");
  exit 2;
}
else {
  for my $e (@{ $v->{errors} || [] })        { bad("okf validate error: $e") }
  for my $g (@{ $v->{gate_findings} || [] }) { bad("okf validate gate: $g") }
  for my $w (@{ $v->{warnings} || [] })      { bad("okf validate warning (fatal here): $w") }
  for my $l (@{ $v->{broken_links} || [] })  { bad("okf validate broken link: ".(ref $l ? join(' ', map { "$_=$l->{$_}" } sort keys %$l) : $l)) }
  for my $o (@{ $v->{orphans} || [] })       { bad("okf validate orphan: $o") }
  bad("okf validate: gate failed for a reason not listed above — run `okf validate $bundle --strict --drift --stale`") if !$v->{gate_passed} && !$fail;
  bad("okf validate: not conformant") unless $v->{is_conformant};
}

# 2. Reserved files.
my $root = slurp("$bundle/index.md");
bad("index.md: missing okf_version: \"0.2\"") unless $root =~ /^okf_version:\s*"0\.2"/m;
bad("log.md: missing") unless -f "$bundle/log.md";
# The frozen log and the log entries (docs/adr/0001-log-entries-as-reserved-log-files.md).
# The root log.md ends with okf-log.sh's marker, which hashes every byte above it (LF line
# endings, so a CRLF checkout of the same history passes). No new line goes there on any
# day; it goes in the branch's log entry, which okf-log.sh finds or creates. This gate
# never looks for that entry (no branch discovery here): it names the form and the writer.
my $ENTRY_FORM = "$bundle/log/<YYYY-MM-DD>-<slug>-<4 hex>/log.md";
my $USE_ENTRY  = "write new lines in this branch's log entry, $ENTRY_FORM, with `okf-log.sh add $bundle '<line>'`";
if (-f "$bundle/log.md") {
  my $t = slurp_raw("$bundle/log.md");
  my @m;
  while ($t =~ /^<!-- okf-log frozen (\d{4}-\d{2}-\d{2}) sha256:([0-9a-f]{64}) -->[ \t]*\r?$/mg) { @m = ($-[0], $+[0], $1, $2) }
  if (!@m) {
    bad("log.md: not frozen (no okf-log marker): this bundle predates log entries — run /okf-migrate, which freezes log.md and creates log/");
  } else {
    my ($start, $end, $date, $hash) = @m;
    bad("log.md: text below the marker — the frozen-log marker must be the last line; $USE_ENTRY") if substr($t, $end) =~ /\S/;
    (my $above = substr($t, 0, $start)) =~ s/\r\n/\n/g;
    bad("log.md: the history frozen on $date changed (its sha256 no longer matches the marker) — log.md is frozen; "
      . "$USE_ENTRY. A deliberate fix to old history: `okf-log.sh split --refreeze $bundle`") if sha256_hex($above) ne $hash;
  }
}
# Every `## ` heading in a log entry is a bare ISO date, as in the old log; one inside a
# fenced example or an HTML comment is not a heading (the writer skips those too).
for my $entry (sort glob("\Q$bundle\E/log/*/log.md")) {
  my $t = slurp($entry);
  my @skip;
  while ($t =~ /(<!--.*?-->|^[ \t]*```.*?^[ \t]*```[^\n]*$)/smg) { push @skip, [$-[0], $+[0]] }
  while ($t =~ /^## ([^\n]*?)\r?$/mg) {
    my ($pos, $h) = ($-[0], $1);
    next if grep { $pos >= $_->[0] && $pos < $_->[1] } @skip;
    bad("$entry: `## $h` is not a bare ISO date heading (## YYYY-MM-DD)") unless $h =~ /^\d{4}-\d{2}-\d{2}[ \t]*$/;
  }
}

# Collect concepts and indexes.
my (@concepts, @indexes);
find({ no_chdir=>1, wanted=>sub {
  return unless -f && /\.md$/;
  (my $rel = $File::Find::name) =~ s{^\Q$bundle\E/}{};
  if    ($rel =~ m{(^|/)index\.md$}) { push @indexes, $rel }
  elsif ($rel =~ m{(^|/)log\.md$})   { }
  else                               { push @concepts, $rel }
}}, $bundle);
@concepts = sort @concepts; @indexes = sort @indexes;
# An empty bundle passes every per-concept check vacuously. A fresh scaffold must not.
bad("no concept in $bundle yet — populate it before a green gate means anything") unless @concepts;

# 3. Frontmatter and body of each concept.
my %desc;                       # rel => description
for my $rel (@concepts) {
  my $text = slurp("$bundle/$rel");
  my ($fm, $body) = $text =~ /\A---\n(.*?)\n---\n(.*)\z/s;
  unless (defined $fm) { bad("$rel: no frontmatter"); next }
  my %f; my @code_refs; my $cur='';
  for my $line (split /\n/, $fm) {
    next if $line =~ /^\s*#/ or $line =~ /^\s*$/;
    if ($line =~ /^([A-Za-z_]+):\s*(.*)$/) { $cur=$1; my $val=$2; $val =~ s/^(["'])(.*)\1$/$2/; $f{$cur}=$val; $f{"_multi_$cur"}=1 if $val =~ /^[>|]/ }
    elsif ($line =~ /^\s*-\s*(.+)$/)     { push @code_refs, $1 if $cur eq 'code_refs'; $f{"_list_$cur"}=1 }
    elsif ($line =~ /^\s+\S/)            { $f{"_multi_$cur"}=1 }
  }
  bad("$rel: no type:")        unless length($f{type}//'');
  if (!length($f{description}//'') or $f{"_multi_description"}) { bad("$rel: description: must be present and on ONE line (quote it if it holds # or ': ')") }
  else { $desc{$rel} = $f{description} }
  bad("$rel: last_updated: must be an ISO date (got '".($f{last_updated}//'')."')") unless ($f{last_updated}//'') =~ $ISO;
  bad("$rel: stale_after: must be an ISO date") if exists $f{stale_after} && $f{stale_after} !~ $ISO;
  if (($f{stale_after} // '') =~ /^(\d{4})-(\d{2})-(\d{2})$/) {
    # okf compares these dates as text, so an impossible one never expires: name it here.
    # Years below 1000 are refused because Time::Local reads them as offsets from 1900.
    my $t = $1 >= 1000 ? eval { timegm(0, 0, 0, $3, $2 - 1, $1) } : undef;
    if (!defined $t) { bad("$rel: stale_after: $f{stale_after} is not a real date") }
    else {
      my $days = int($t / 86400) - $today_days;
      push @review_due, "$rel ($f{stale_after})" if $days > 0 && $days <= $REVIEW_WINDOW;
    }
  }
  push @no_code_refs, $rel unless @code_refs or $rel =~ $EXEMPT or $wiki;
  # Fence-stripped, so a playbook that shows the marker as an example is not flagged.
  (my $unfenced = $body) =~ s/^(?:[ \t]*)```.*?^(?:[ \t]*)```[^\n]*$//smg;
  push @open_questions, $rel if $unfenced =~ $OPEN_QUESTION;
  bad("$rel: HTML comment left in a concept — replace the annotation, search indexes comment text") if $text =~ /<!--/;
  bad("$rel: unfilled placeholder") if $text =~ /\[TO DETERMINE\]|\[TO BE DETERMINED|\[VERIFY AFTER|\[Project Name\]|\{\{[A-Z_0-9]+\}\}/;
  # Two views of the body. `$masked` keeps a fenced block as a single opaque token, so a
  # section whose whole content is a command block still counts as content and a `#` line
  # inside an example is not mistaken for a heading. `$nb` drops fences entirely, so a
  # link inside an example is not mistaken for a real outbound link.
  (my $masked = $body) =~ s/^(?:[ \t]*)```.*?^(?:[ \t]*)```[^\n]*$/FENCED CODE BLOCK/smg;
  (my $nb     = $body) =~ s/^(?:[ \t]*)```.*?^(?:[ \t]*)```[^\n]*$//smg;
  # A heading followed only by a deeper heading is a container, not an empty section.
  my @parts = split /^(?=#{1,6} )/m, $masked;
  for my $i (0..$#parts) {
    next unless $parts[$i] =~ /^(#{1,6}) ([^\n]*)\n(.*)\z/s;
    my ($lvl,$h,$c) = (length $1, $2, $3);
    next if $c =~ /\S/;
    my $next_lvl = ($i < $#parts && $parts[$i+1] =~ /^(#{1,6}) /) ? length $1 : 0;
    bad("$rel: section '$h' is empty") unless $next_lvl > $lvl;
  }
  # Links out of the body.
  my @links = $nb =~ /\]\((\/[^)\s]+\.md)(?:#[^)]*)?\)/g;
  if ($rel =~ m{^decisions/}) {
    bad("$rel: decisions need date: as an ISO date") unless ($f{date}//'') =~ $ISO;
    # okf --strict itself enforces draft|stable|deprecated; this names the rule when it fires.
    bad("$rel: status: must be stable (in force), deprecated (superseded) or draft (got '".($f{status}//'')."')") unless ($f{status}//'') =~ /^(draft|stable|deprecated)$/;
    bad("$rel: a decision must link to at least one concept outside decisions/ (an island of decisions passes okf validate)") unless grep { !m{^/decisions/} } @links;
    bad("$rel: deprecated but no 'Superseded by' link to another decision") if ($f{status}//'') eq 'deprecated' && $nb !~ /Superseded by\s*\[[^\]]+\]\(\/decisions\/[^)]+\.md\)/i;
    bad("$rel: a deprecated decision takes no stale_after") if ($f{status}//'') eq 'deprecated' && exists $f{stale_after};
  }
}

# 4. Indexes both ways.
my %rows_for;                   # index rel => [ [path, desc], ... ]
for my $idx (@indexes) {
  my $t = slurp("$bundle/$idx");
  $t =~ s/<!--.*?-->//sg; $t =~ s/```.*?```//sg;
  my (%seen);
  while ($t =~ /^- \[([^\]]+)\]\((\/[^)\s]+)\) — (.*)$/mg) {
    my ($title,$path,$d) = ($1,$2,$3);
    (my $target = $path) =~ s{^/}{};
    bad("$idx: duplicate row for $path") if $seen{$path}++;
    push @{$rows_for{$idx}}, $target;
    if ($target =~ m{(^|/)index\.md$}) { bad("$idx: row links to missing index $path") unless -f "$bundle/$target"; next }
    if (!exists $desc{$target}) { bad("$idx: row links to missing concept $path") unless -f "$bundle/$target"; next }
    bad("$idx: row for $path carries a description that is not the concept's:\n        index:   $d\n        concept: $desc{$target}") if $d ne $desc{$target};
  }
}
for my $rel (@concepts) {
  my $dir = dirname($rel); my $cat = $dir eq '.' ? 'index.md' : "$dir/index.md";
  if (!-f "$bundle/$cat") { bad("$rel: category has no $cat"); next }
  bad("$rel: not listed in $cat") unless grep { $_ eq $rel } @{ $rows_for{$cat} || [] };
}

# 5. State snapshot shape.
if (-f "$bundle/project/state.md") {
  my $s = slurp("$bundle/project/state.md");
  for my $h ('Working', 'Not yet built', 'Known issues') { bad("project/state.md: missing the '**$h:**' list") unless $s =~ /^\*\*\Q$h\E:\*\*/m }
  # The snapshot is read at the start of every session, so its cost is paid on every turn
  # after. A long item is evidence that has nowhere else to go: it belongs in
  # project/state-evidence.md. A warning, because a line's length is a judgement.
  my @long = grep { length($_) > $STATE_ITEM_MAX } ($s =~ /^- (.*)$/mg);
  warnl(sprintf("project/state.md: %d item(s) over %d characters — keep the line, move the evidence to project/state-evidence.md", scalar @long, $STATE_ITEM_MAX)) if @long;
} elsif (!$wiki) { warnl("project/state.md: absent — the session bootstrap has no snapshot to read") }

# 6. A leftover drift.lock: drift is gone (ADR 0002), and the lock means /okf-migrate
# has not run here.
bad("drift.lock found: drift is no longer used, run /okf-migrate") if $has_lock;

grouped("with empty code_refs (okf search --for-path cannot find them)", @no_code_refs);
grouped("with an open question ([TO VERIFY] / [DA VERIFICARE]) — confirm or remove", @open_questions);
grouped("due for review within $REVIEW_WINDOW days (stale_after; the gate fails on the day) — review now, then move the date", @review_due);

# Never erase a failed subprocess status.
bad("okf validate exited $okf_status") if $okf_status && !$fail;
print "ok    $bundle: okf gate passed with ".($warnings ? "$warnings warning(s) above" : "no warnings").", indexes consistent both ways, frontmatter complete, no template residue\n" unless $fail;
exit $fail;
PERL
rc=$?
exit "$rc"
