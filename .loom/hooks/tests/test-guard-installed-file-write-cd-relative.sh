#!/usr/bin/env bash
# Regression test for the `loom:installed-file-write` guard (issue #87)
#
# Tracks upstream: rjwalters/loom#9154 (the guard lives in Loom's `defaults/`
# tree; this repo carries resync-refreshed copies — see "WHY NO LOCAL GUARD FIX"
# below). When that upstream fix reaches this repo via a `chore: resync
# installed Loom surfaces` commit, this file reports XPASS and exits 2.
#
# Usage: ./.loom/hooks/tests/test-guard-installed-file-write-cd-relative.sh
#
# WHAT THIS COVERS
# ----------------
# A false DENY in the `loom:installed-file-write` category of
# `.loom/hooks/guard-loom-workflow.sh` (decision logic in
# `.loom/scripts/lib/installed-file-guard.sh`).
#
# `guard-loom-workflow.sh:1879` normalizes every write target extracted by
# `loom_bash_write_targets()` with `loom_ifw_normalize_abs "$IFW_TARGET" "$CWD"`,
# where `$CWD` is the PreToolUse payload's `.cwd` — the tool call's cwd BEFORE
# any in-command `cd` runs. An in-command `cd` is not tracked, so a command
# shaped like
#
#     cd <scratch-dir> && cp <src> .loom/hooks/foo.sh
#
# has its RELATIVE destination resolved back onto the starting cwd. When that
# starting cwd is itself a Loom-managed consumer checkout — the normal case for
# an agent working in this repo — the destination is mis-resolved onto the real
# repo's `.loom/hooks/` and DENIED at catastrophic tier, even though the write
# lands entirely inside an isolated throwaway directory.
#
# `installed-file-guard.sh:279-287` documents the untracked-`cd` case in a
# "Known, ACCEPTED limitations — every one of them fails toward PERMISSIVE (a
# missed deny, never a false one)" block. That claim is INACCURATE for this
# case: it is a false DENY, not a missed deny. Correcting that comment and
# (optionally) teaching the normalizer about a literal same-command `cd` prefix
# is an UPSTREAM change — see "WHY NO LOCAL GUARD FIX" below.
#
# XFAIL POLICY (read before "fixing" a failure here)
# --------------------------------------------------
# The cases in the ALLOW-DESIRED group below assert the behavior the guard
# SHOULD have. They do not hold today, so they are reported as `XFAIL`
# (expected failure) and do NOT fail the suite: a permanently-red test file is
# indistinguishable from a real breakage and gets ignored. The DENY-REQUIRED
# group is the part that must never regress, and a failure there IS a hard
# failure.
#
# Exit codes:
#   0 — everything as expected (DENY-REQUIRED all pass, XFAILs still failing)
#   1 — a genuine FAILURE: a DENY-REQUIRED case stopped denying, or the fixture
#       sanity check broke. Investigate immediately.
#   2 — ACTION REQUIRED: an XFAIL case unexpectedly PASSED (`XPASS`). The
#       upstream fix (rjwalters/loom#9154) has reached this repo via a `chore:
#       resync installed Loom surfaces` commit. Promote that case to a hard
#       assertion (swap `xfail_allow` for `assert_allow`) and delete this note.
#
# WHY NO LOCAL GUARD FIX (issue #87, `.loom/docs/repo-owned-files.md`)
# -------------------------------------------------------------------
# `.loom/hooks/guard-loom-workflow.sh` and
# `.loom/scripts/lib/installed-file-guard.sh` are vendored, resync-refreshed
# copies of `rjwalters/loom`'s `defaults/` tree. Per
# `.loom/docs/repo-owned-files.md` § "Before you hand-edit an installed file,
# stop" a bug there has exactly two valid dispositions — upstream it, or pin it
# and own the divergence. This repo takes the UPSTREAM route for the guard
# itself: a pin cannot protect a file Loom *does* ship from an `install.sh
# --confirm-reinstall` / `loom update` re-copy (same doc, § "When you do and do
# not need it"), and freezing a core guard library locally would also block
# every FUTURE upstream guard fix from reaching this repo. The bug is therefore
# reported at rjwalters/loom#9154, and only THIS test file is pinned in
# `.loom/resync-ignore` — it is repo-owned and upstream ships no counterpart.
#
# NOTE ON `defaults/`: do NOT model new tests on
# `.loom/hooks/tests/test-guard-loom-workspace.sh`, which resolves its hook as
# `$REPO_ROOT/defaults/hooks/...`; this consumer repo has no `defaults/` tree.
# This file follows the working consumer-repo pattern from
# `test-guard-destructive-generic-interpreter-heredoc.sh`: copy the INSTALLED
# `.loom/` paths into an isolated temp git tree.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-loom-workflow.sh"
SRC_IFW_LIB="$REPO_ROOT/.loom/scripts/lib/installed-file-guard.sh"
SRC_CFG_LIB="$REPO_ROOT/.loom/scripts/lib/config-resolver.sh"

PASS=0
FAIL=0
XFAIL=0
XPASS=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

for f in "$SRC_HOOK" "$SRC_IFW_LIB"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: $f not found" >&2
        exit 1
    fi
done
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required by this test" >&2
    exit 1
fi

# --- Fixtures --------------------------------------------------------------
# TMPROOT      a Loom CONSUMER checkout (has .loom/config.json, no
#              defaults/.claude/commands/loom/) — stands in for this repo, and
#              is the `cwd` every case below reports in its PreToolUse payload.
# SCRATCH      a bare throwaway dir that is NOT a Loom install — stands in for
#              the `mktemp -d` fixture dir an agent cd's into.
# SCRATCH_LOOM a throwaway dir that IS itself a Loom consumer install — the
#              control proving a cd-aware fix must still deny there.
TMPBASE="$(mktemp -d)"
trap 'rm -rf "$TMPBASE"' EXIT
# Canonicalize to defeat a /tmp -> /private/tmp symlink, so the cwd we feed the
# hook matches what `git rev-parse --show-toplevel` reports inside it.
TMPBASE=$(cd "$TMPBASE" && pwd -P)

TMPROOT="$TMPBASE/consumer-repo"
SCRATCH="$TMPBASE/scratch-plain"
SCRATCH_LOOM="$TMPBASE/scratch-loom-install"

mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib"
git init -q "$TMPROOT"
printf '%s\n' '{}' > "$TMPROOT/.loom/config.json"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-loom-workflow.sh"
cp "$SRC_IFW_LIB" "$TMPROOT/.loom/scripts/lib/installed-file-guard.sh"
[[ -f "$SRC_CFG_LIB" ]] && cp "$SRC_CFG_LIB" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-loom-workflow.sh"
HOOK="$TMPROOT/.loom/hooks/guard-loom-workflow.sh"

# A pinned path inside the fixture, to prove ALLOW is reachable at all here.
printf '%s\n' 'hooks/repo-owned-pinned.sh' > "$TMPROOT/.loom/resync-ignore"

# Payload source file every `cp` case copies FROM (never written to).
SRC_FILE="$TMPBASE/payload.sh"
printf '%s\n' '#!/bin/sh' > "$SRC_FILE"

mkdir -p "$SCRATCH/.loom/hooks"
git init -q "$SCRATCH"

mkdir -p "$SCRATCH_LOOM/.loom/hooks"
git init -q "$SCRATCH_LOOM"
printf '%s\n' '{}' > "$SCRATCH_LOOM/.loom/config.json"

pass()   { PASS=$((PASS + 1));   TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC}  %s\n" "$1"; }
fail()   { FAIL=$((FAIL + 1));   TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC}  %s\n" "$1"; }
xfail()  { XFAIL=$((XFAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${YELLOW}XFAIL${NC} %s\n" "$1"; }
xpass()  { XPASS=$((XPASS + 1)); TOTAL=$((TOTAL + 1)); printf "${YELLOW}XPASS${NC} %s\n" "$1"; }

make_input() {
    local cmd="$1" cwd="$2"
    jq -n --arg cmd "$cmd" --arg cwd "$cwd" '{tool_input: {command: $cmd}, cwd: $cwd}'
}

# Prints "<exit_code>|<stdout>".
#
# The ambient environment of a Loom-dispatched agent carries LOOM_FORCE_SCOPE
# and LOOM_GUARD_DECISION_LOG (see builder.md § "Your Environment Is Not a
# Clean Shell"); LOOM_GUARD_INSTALLED_FILE_WRITES would silently disable the
# very category under test. Strip all three so the result reflects the guard's
# factory-default behavior rather than the dispatcher's env.
run_hook() {
    local cmd="$1" cwd="${2:-$TMPROOT}"
    local exit_code=0 output
    output=$(cd "$cwd" && env -u LOOM_GUARD_INSTALLED_FILE_WRITES \
                              -u LOOM_GUARD_DECISION_LOG \
                              -u LOOM_FORCE_SCOPE \
                              bash "$HOOK" < <(make_input "$cmd" "$cwd") 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

decision_of() {
    printf '%s' "$1" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true
}

# is_allow "<code>|<output>" -> 0 when the hook allowed the command
is_allow() {
    local result="$1"
    local code="${result%%|*}" out="${result#*|}"
    [[ "$code" == "0" ]] || return 1
    [[ "$(decision_of "$out")" != "deny" ]]
}

assert_allow() {
    local desc="$1" result="$2"
    if is_allow "$result"; then pass "$desc"; else fail "$desc (expected allow, got: $result)"; fi
}

assert_deny() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    if [[ "$(decision_of "$out")" == "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected permissionDecision=deny, got: $out)"
    fi
}

# xfail_allow — the guard SHOULD allow this but currently denies (issue #87).
# A pass here is an XPASS, not a PASS: the fix landed and the case must be
# promoted to assert_allow.
xfail_allow() {
    local desc="$1" result="$2"
    if is_allow "$result"; then
        xpass "$desc -- guard now ALLOWS. Promote to assert_allow (see XFAIL POLICY)."
    else
        xfail "$desc -- still denied (known #87 false DENY)"
    fi
}

echo "=== loom:installed-file-write cd-then-relative-write tests (#87) ==="
echo "consumer fixture: $TMPROOT"
echo "scratch dir:      $SCRATCH"
echo

# --- Fixture sanity: ALLOW must be reachable in this fixture ---------------
# Without this, every XFAIL below could be explained by a broken fixture (a
# hook that denies unconditionally, or a mis-sourced library) rather than by
# the bug under test.
echo "-- fixture sanity --"
result=$(run_hook "cp $SRC_FILE $TMPROOT/.loom/hooks/repo-owned-pinned.sh")
assert_allow "(S1) absolute write to a path PINNED in .loom/resync-ignore -> allow" "$result"

result=$(run_hook "cp $SRC_FILE $SCRATCH/.loom/hooks/x.sh")
assert_allow "(S2) absolute write into a scratch dir that is not a Loom install -> allow" "$result"

# --- DENY-REQUIRED: the protection this category exists for ----------------
# Every case here resolves (or must be assumed to resolve) onto a real
# consumer install's managed path. None may ever start allowing, with or
# without a cd-aware refinement.
echo
echo "-- deny-required (must never regress) --"

result=$(run_hook "cp $SRC_FILE .loom/hooks/guard-loom-workflow.sh")
assert_deny "(D1) relative managed write, no cd at all -> deny" "$result"

result=$(run_hook "cd $TMPROOT && cp $SRC_FILE .loom/hooks/guard-loom-workflow.sh")
assert_deny "(D2) literal cd that lands back in the managed checkout -> deny" "$result"

result=$(run_hook "cd $SCRATCH_LOOM && cp $SRC_FILE .loom/hooks/x.sh")
assert_deny "(D3) literal cd into a dir that is ITSELF a Loom consumer install -> deny" "$result"

result=$(run_hook "cd $SCRATCH && cp $SRC_FILE $TMPROOT/.loom/hooks/x.sh")
assert_deny "(D4) cd into scratch but ABSOLUTE managed destination -> deny" "$result"

result=$(run_hook "cd $SCRATCH && echo pwned > $TMPROOT/.loom/scripts/lib/installed-file-guard.sh")
assert_deny "(D5) cd into scratch, absolute managed redirection target -> deny" "$result"

result=$(run_hook "cp $SRC_FILE .loom/hooks/" )
assert_deny "(D6) relative managed DIRECTORY destination, no cd -> deny" "$result"

# --- ALLOW-DESIRED (currently XFAIL): the #87 false DENY -------------------
# The write lands entirely inside a throwaway dir that is not a Loom install,
# so no resync can ever revert it and there is nothing for this category to
# protect. The guard denies anyway because it resolves the relative
# destination against the PRE-`cd` cwd.
echo
echo "-- allow-desired (known #87 false DENY; XFAIL until the upstream fix resyncs) --"

result=$(run_hook "cd $SCRATCH && cp $SRC_FILE .loom/hooks/guard-destructive-generic.sh")
xfail_allow "(A1) literal 'cd <scratch> &&' + relative cp into scratch's .loom/hooks" "$result"

result=$(run_hook "cd $SCRATCH; cp $SRC_FILE .loom/hooks/")
xfail_allow "(A2) literal 'cd <scratch>;' + relative cp to scratch dir destination" "$result"

result=$(run_hook "cd $SCRATCH && echo x > .loom/hooks/x.sh")
xfail_allow "(A3) literal 'cd <scratch> &&' + relative '>' redirection" "$result"

result=$(run_hook "cd $SCRATCH && tee .loom/hooks/x.sh < $SRC_FILE")
xfail_allow "(A4) literal 'cd <scratch> &&' + relative tee target" "$result"

# (A5) is the EXACT shape logged in .loom/logs/guard-decisions.log on
# 2026-09-23 and re-reproduced when #87 was filed: the cd target is a VARIABLE
# bound to `$(mktemp -d)` in the same command, not a literal path.
#
# Recommendation 2 in #87 (recognize a *literal* leading `cd <dir>` prefix)
# would NOT cover this shape — closing it needs the sibling precedent from
# `guard-destructive-generic.sh`'s rm-scope mktemp fast path, which proves a
# same-command `VAR=$(mktemp -d)` binding is /tmp-rooted. Kept as a separate
# case so the two refinements can be retired independently.
result=$(run_hook "WORK=\$(mktemp -d); cd \"\$WORK\"; git init -q; mkdir -p .loom/hooks
cp $SRC_FILE .loom/hooks/")
xfail_allow "(A5) logged shape: 'WORK=\$(mktemp -d); cd \"\$WORK\"' + relative cp" "$result"

echo
echo "Cases: $TOTAL  Passed: $PASS  Failed: $FAIL  XFail: $XFAIL  XPass: $XPASS"

if [[ $FAIL -gt 0 ]]; then
    echo "RESULT: FAILURE — a deny-required case or the fixture sanity check broke." >&2
    exit 1
fi
if [[ $XPASS -gt 0 ]]; then
    echo "RESULT: ACTION REQUIRED — $XPASS expected-failure case(s) now pass." >&2
    echo "  The upstream fix for #87 has reached this repo. Promote the XPASS case(s)" >&2
    echo "  from xfail_allow to assert_allow and delete the XFAIL POLICY note." >&2
    exit 2
fi
echo "RESULT: OK — deny-required behavior intact; $XFAIL known #87 false DENY(s) still open."
