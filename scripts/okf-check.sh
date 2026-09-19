#!/bin/sh
# okf-check.sh — the knowledge gate `okf validate` alone is not.
#
#   okf-check.sh [bundle-dir]        (default: knowledge)      exit 0 = clean
#
# Measured on okf v0.3.0: `okf validate --strict --drift --stale` exits non-zero for a
# missing `type`, a broken link, an orphan (a concept with no links in OR out) and an
# expired `stale_after` — and for nothing else. A dead `code_refs` path is a WARNING that
# leaves the exit code at 0 even under --strict. Indexes are never read. So this script:
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
#   5. checks the reserved files: root okf_version, log.md, project/state.md's three lists;
#   6. runs `drift check --format json` from the bundle's parent and fails on any doc in
#      the bundle that is not `fresh` — an anchor whose code changed after the concept was
#      last believed (with the commit to blame) or a dead markdown link. A non-zero drift
#      status with findings only outside the bundle is noted and tolerated; a non-zero
#      status with no stale/broken findings is an execution failure. Content-level drift
#      is the one thing `code_refs` cannot give you: okf tells you a path VANISHED,
#      drift tells you it CHANGED. Bindings come from `okf-drift-bootstrap.sh` for code
#      `code_refs` entries; non-code paths take no *automatic* binding, but a hand
#      `drift link` on one is a deliberate content anchor and stays valid. A concept
#      reviewed against a change is re-stamped with
#      `drift link '<doc>' '<anchor identity>' --doc-is-still-accurate` and a line in
#      log.md — the IDENTITY (`path#symbol` for a symbol anchor), never the bare path,
#      which would create a second, whole-file binding and leave the stale one stale.
#
# TWO SEPARATE DIAGNOSTICS, because they are two different questions and one of them used
# to answer for both:
#
#   coverage         from drift's report — a concept with NO anchor at all. Nothing checks
#                    it; a green gate says nothing about it. Grouped into one `warn` line.
#   discoverability  from `code_refs` — a concept `okf search --for-path <file>` can never
#                    return. Grouped into a second `warn` line.
#
# A concept with non-code `code_refs` and no anchor is coverage-warned and not
# discoverability-warned; a concept with a hand anchor and empty `code_refs` is the
# reverse. Coverage is a warning by default: making it fatal would fail every bundle that
# has not finished binding. `OKF_REQUIRE_TRACKING=<glob>[,<glob>...]` (a shell glob over
# the concept path relative to the bundle, e.g. `architecture/*`) makes it FATAL for that
# subset. Unset, the default, is warning-only. Coverage is computed from step 6's report,
# so neither the warning nor the opt-in fatal can fire when drift did not run.
#
# A GREEN GATE MUST MEAN THE DETECTOR RAN. On a repo that has NOT adopted drift — neither
# `.okf-drift-version` nor `drift.lock` at the bundle's parent — a missing `drift` or a
# missing lock is a warning, and the gate keeps working. On a repo that HAS adopted it
# (both files present), a missing `drift` binary is FATAL, and so is a `drift --version`
# that disagrees with the version pinned in `.github/workflows/knowledge.yml` (or the same
# file named `.yaml`); otherwise a worker without drift gets two green local runs and a
# red CI.
#
# Other warnings (do not fail): an okf version other than the one measured. The runtime
# skill and standalone CI bootstrap call the pinned launcher; no consumer copy is needed.
# Run it from the repository root: code_refs and drift.lock are both rooted there.
# Needs sh, perl 5.14+ (JSON::PP is core) and okf; drift is optional.
set -u
bundle=${1:-knowledge}
[ -d "$bundle" ] || { echo "no bundle at $bundle" >&2; exit 2; }
command -v okf >/dev/null 2>&1 || { echo "okf not on PATH" >&2; exit 2; }

ver=$(okf version 2>/dev/null | head -1)
case "$ver" in
  *v0.3.0*) ;;
  *) echo "warn  okf is '$ver'; this gate was measured against v0.3.0 — re-check references/okf-quirks.md" ;;
esac

json=$(okf validate "$bundle" --strict --drift --stale --json)
okf_status=$?
drift_status=0

# Step 6's input. Empty string = "not adopted here", which is a warning, not a failure —
# unless this repository has adopted drift, in which case a detector that did not run is
# a gate that certifies nothing. `adoption_error` carries that verdict to perl so the
# other five steps still report before it fails.
drift_json=""
adoption_error=""
parent=$(dirname "$bundle")
adopted=0
[ -f "$parent/.okf-drift-version" ] && [ -f "$parent/drift.lock" ] && adopted=1

# The drift version this repository's own workflow installs, when it pins one. Read from
# the `drift` line so the okf pin beside it is never mistaken for it; absent file or
# absent pin means the check is skipped in silence. BOTH extensions are looked for: the
# template ships `.yml`, but a repository whose every other workflow is `.yaml` renames
# it, and with a single hardcoded name that rename silently disabled this whole check —
# the only symptom being a version comparison that never ran.
pinned_drift=""
workflow=""
for candidate in "$parent/.github/workflows/knowledge.yml" "$parent/.github/workflows/knowledge.yaml"; do
  [ -f "$candidate" ] || continue
  workflow=$candidate
  break
done
if [ -n "$workflow" ]; then
  pinned_drift=$(grep drift "$workflow" 2>/dev/null \
    | sed -n 's/.*--version \(v\{0,1\}[0-9][0-9.]*\).*/\1/p' | head -1)
fi

if ! command -v drift >/dev/null 2>&1; then
  if [ "$adopted" = 1 ]; then
    adoption_error="this repository adopted drift ($parent/.okf-drift-version and $parent/drift.lock are both present) but \`drift\` is not on PATH — step 6 (content drift) did not run, so a pass here would certify nothing was checked; install the pinned drift"
  else
    echo "warn  drift not on PATH — step 6 (content drift) did not run; \`code_refs\` can only tell you a path vanished, not that it changed"
  fi
elif [ ! -f "$parent/drift.lock" ]; then
  echo "warn  no drift.lock in $parent — step 6 (content drift) did not run; use /okf-setup for the explicit pinned drift bootstrap"
else
  if [ -n "$pinned_drift" ]; then
    have_drift=$(drift --version 2>/dev/null | awk 'NR==1{print $NF}')
    if [ "${pinned_drift#v}" != "${have_drift#v}" ]; then
      adoption_error="drift on PATH is '$have_drift' but $workflow pins '$pinned_drift' — the local gate and CI are running different detectors; install the pinned version"
    fi
  fi
  drift_json=$( (cd "$parent" && drift check --format json) )
  drift_status=$?
  # An adopted checker failing at runtime is not the optional, unadopted case.
  [ -n "$drift_json" ] || { echo "okf-check: drift check produced no JSON (exit $drift_status)" >&2; exit 2; }
fi

# Both blobs reach perl through FILES, never argv. Linux caps a SINGLE argument at
# MAX_ARG_STRLEN (131072 bytes) independently of ARG_MAX, and `drift check --format json`
# passes that on a bundle of ~48 anchors (measured: 183806 bytes). macOS has no comparable
# per-argument cap, so this only ever fails in Linux CI, as `exec: perl: Argument list too
# long`, exit 126 — a green local run proves nothing about it.
#
# No `exec`: the EXIT trap has to survive to remove the directory, and exec would replace
# the shell before it fires. The exit code is forwarded by hand instead.
tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-check.XXXXXX") || { echo "okf-check: cannot create a temp dir" >&2; exit 2; }
trap 'rm -rf "$tmp"' EXIT INT TERM
printf '%s' "$json" > "$tmp/okf.json" || exit 2
printf '%s' "$drift_json" > "$tmp/drift.json" || exit 2

perl - "$bundle" "$tmp/okf.json" "$tmp/drift.json" "$parent" "$okf_status" "$drift_status" "$adoption_error" <<'PERL'
use strict; use warnings; use utf8;
use JSON::PP; use File::Find; use File::Basename;
binmode STDOUT, ':utf8';
my ($bundle, $json_file, $drift_file, $parent, $okf_status, $drift_status, $adoption_error) = @ARGV;
# Read as raw bytes and decode explicitly: decode_json expects UTF-8 octets, and a
# ':utf8' read would hand it characters instead.
sub slurp_raw { my $f=shift; open my $h,'<:raw',$f or die "$f: $!"; local $/; my $c=<$h>; defined $c ? $c : '' }
my $json       = slurp_raw($json_file);
my $drift_json = slurp_raw($drift_file);
my $fail = 0;
sub bad  { $fail = 1; print "FAIL  @_\n" }
sub warnl{ print "warn  @_\n" }
# A doc path may hold spaces; an anchor identity always holds a `#`. Single quotes make
# the printed command copy-pasteable in either case.
sub shq  { my $s = shift; $s =~ s/'/'\\''/g; "'$s'" }
sub slurp{ my $f=shift; open my $h,'<:utf8',$f or die "$f: $!"; local $/; <$h> }
my $ISO = qr/^\d{4}-\d{2}-\d{2}$/;
# The snapshot is prose about the project, not about code: it is expected to carry
# neither code_refs nor an anchor, and warning about it every run teaches skimming.
my $EXEMPT = qr{^project/state\.md$};
my (@no_code_refs, @no_anchor);

# `OKF_REQUIRE_TRACKING=architecture/*,decisions/*` — a comma-separated list of shell
# globs over the concept path RELATIVE to the bundle. `*` and `?` stop at a `/` as they do
# in the shell; `**` crosses one. Unset (the default) leaves coverage a warning.
my @require_tracking = grep { length } split /\s*,\s*/, ($ENV{OKF_REQUIRE_TRACKING} // '');
sub glob_re {
  my $g = shift;
  my $re = '';
  while ($g =~ /\G(\*\*|\*|\?|[^*?]+)/gc) {
    my $t = $1;
    $re .= $t eq '**' ? '.*' : $t eq '*' ? '[^/]*' : $t eq '?' ? '[^/]' : quotemeta $t;
  }
  return qr/\A$re\z/;
}
my @require_re = map { [ $_, glob_re($_) ] } @require_tracking;
# One `warn` line per diagnostic, not one per concept: 29 identical lines are read as
# noise, and the two questions they used to conflate have different answers.
sub grouped {
  my ($label, @members) = @_;
  return unless @members;
  my $head = sprintf("%d concept(s) %s: ", scalar @members, $label);
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
  push @no_code_refs, $rel unless @code_refs or $rel =~ $EXEMPT;
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
} else { warnl("project/state.md: absent — the session bootstrap has no snapshot to read") }

# 6. Content drift: has the code a concept is bound to moved since the concept was written?
my $drift_note = "step 6 skipped (no drift.lock)";
my ($nonfresh, $outside_nonfresh) = (0, 0);
my $bundle_rel = '';
if (length $drift_json) {
  my $dc = eval { decode_json($drift_json) };
  if (!$dc) {
    bad("drift check produced no JSON — run `drift check --format json` from the bundle's parent");
    exit 2;
  }
  else {
    my $checked = 0;
    my (%checked_paths, %anchors_for);
    $bundle_rel = basename($bundle);
    for my $d (@{ $dc->{docs} || [] }) {
      my $r = $d->{result} // '';
      next unless $r eq 'stale' || $r eq 'broken';
      $nonfresh++;
      $outside_nonfresh++ unless ($d->{path} // '') =~ m{^\Q$bundle_rel\E/};
    }
    # drift runs from $parent and reports paths relative to it, so the prefix to match is
    # the bundle's name WITHIN $parent, never $bundle itself. Matching $bundle broke the
    # moment it was absolute or reached from a subdirectory: no drift path ever started
    # with /abs/path/knowledge/, every doc was skipped, and the gate printed
    # "0 doc(s) / 0 drift anchor(s) fresh" and exited 0 over a genuinely stale concept.
    # Measured: with two concepts stale, `okf-check.sh knowledge` reported 2 FAIL / exit 1
    # and `okf-check.sh /abs/path/knowledge` reported ok / exit 0.
    for my $d (@{ $dc->{docs} || [] }) {
      my $p = $d->{path} // next;
      next unless $p =~ m{^\Q$bundle_rel\E/};
      $checked++;
      $checked_paths{$p} = 1;
      # drift keeps evaluating a deleted doc's bindings from the lock alone and never
      # fails on it (measured: a `git rm`ed concept kept reporting fresh anchors).
      unless (-f "$parent/$p") {
        bad("$p: bound in drift.lock but the file no longer exists — `drift unlink $p <target>` for each of its targets, or re-link the targets to the concept that replaced it");
        next;
      }
      $anchors_for{$p} = scalar @{ $d->{anchors} || [] };
      my $r = $d->{result} // 'missing';
      next if $r eq 'fresh';
      for my $a (@{ $d->{anchors} || [] }) {
        next if ($a->{result} // '') eq 'fresh';
        my $b = $a->{blame} || {};
        my $c = substr($b->{commit} // '', 0, 8) || '-';
        my $date = $b->{date} // ''; $date =~ s/T.*//;
        # `identity` is the canonical anchor handle `drift link` takes — `path#symbol` for
        # a symbol anchor. Printing `path` alone repaired a DIFFERENT, whole-file binding
        # and left the stale symbol one exactly as it was.
        my $target = $a->{identity} // $a->{path} // '<target>';
        bad("$p: drifted from $target (".($a->{reason}{code} // $a->{result} // '?').")\n"
           # drift blames with `git log -1 -- <file>`: the last commit to TOUCH the file,
           # not necessarily the one that moved the ground under the concept.
           ."        last commit touching this file (not necessarily the cause): $c ".($date || '-')." ".($b->{subject} // '(uncommitted change — nothing to blame yet)')." (".($b->{author} // '-').")\n"
           ."        review the concept against the code, then: drift link ".shq($p)." ".shq($target)." --doc-is-still-accurate  + a dated line in $bundle/log.md");
      }
      for my $l (@{ $d->{links} || [] }) {
        next unless ($l->{result} // '') eq 'broken';
        bad("$p: broken link at line ".($l->{line} // '?').": ".($l->{target} // '?'));
      }
      # A non-fresh doc with neither a stale anchor nor a broken link: name it anyway.
      bad("$p: drift result '$r' with no anchor or link to point at — run `drift check`")
        unless grep { ($_->{result} // '') ne 'fresh' } @{ $d->{anchors} || [] },
               grep { ($_->{result} // '') eq 'broken' } @{ $d->{links} || [] };
    }
    # One matching index is not evidence that the concepts were checked. A partial
    # report must not silently certify a doc drift omitted from its output.
    for my $rel (@concepts) {
      bad("$bundle_rel/$rel: no drift verdict; step 6 did not check this concept")
        unless $checked_paths{"$bundle_rel/$rel"};
      # Coverage, over concepts only: index.md and log.md are reserved files that make no
      # claim about code, and the state snapshot is prose about the project.
      push @no_anchor, $rel unless $anchors_for{"$bundle_rel/$rel"} or $rel =~ $EXEMPT;
    }
    my $anchors = 0;
    $anchors += scalar @{ $_->{anchors} || [] } for grep { ($_->{path} // '') =~ m{^\Q$bundle_rel\E/} } @{ $dc->{docs} || [] };
    # A gate that checked nothing must never report freshness. If the bundle has concepts
    # and drift returned JSON, but not one doc matched, the two are talking about different
    # paths — the failure mode above — and that is a gate defect, not a clean bundle.
    if (!$checked && @concepts) {
      bad("step 6 matched none of drift's " . scalar(@{ $dc->{docs} || [] }) . " doc(s) against '$bundle_rel/' — "
        . "drift.lock and the bundle disagree about paths, so NO concept was drift-checked");
    }
    $drift_note = "$checked doc(s) / $anchors drift anchor(s) fresh";
  }
}

# Coverage (what nothing checks) and discoverability (what --for-path cannot find) are two
# questions with two answers. Coverage is only knowable when step 6 ran; when it did not,
# the "step 6 skipped" note above is the whole of what can honestly be said.
if (length $drift_json) {
  grouped("with no tracked target (no drift anchor; nothing checks them)", @no_anchor);
  for my $rel (@no_anchor) {
    for my $r (@require_re) {
      next unless $rel =~ $r->[1];
      bad("$rel: no tracked target, and OKF_REQUIRE_TRACKING='$r->[0]' makes that fatal for this path — `drift link $bundle_rel/$rel <the declaration the claim depends on>`, or restate the claim");
      last;
    }
  }
}
grouped("with empty code_refs (okf search --for-path cannot find them)", @no_code_refs);

# A repository that adopted drift and then ran the gate without it gets a FAIL, not a
# green run: the other five steps above are worth reporting first, so this lands here.
bad($adoption_error) if length $adoption_error;

# Keep structured stale diagnostics above, but never erase a failed subprocess status.
bad("okf validate exited $okf_status") if $okf_status && !$fail;
if ($drift_status && !$nonfresh && !$fail) {
  bad("drift check exited $drift_status");
} elsif ($drift_status && !$fail) {
  print "note  drift reports $outside_nonfresh non-fresh doc(s) outside $bundle_rel; not gated here\n";
}
print "ok    $bundle: okf gate passed with no warnings, indexes consistent both ways, frontmatter complete, no template residue, $drift_note\n" unless $fail;
exit $fail;
PERL
rc=$?
exit "$rc"
