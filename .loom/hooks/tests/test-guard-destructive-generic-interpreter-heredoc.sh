#!/usr/bin/env bash
# Regression test for .loom/hooks/guard-destructive-generic.sh (issue #16)
#
# Usage: ./.loom/hooks/tests/test-guard-destructive-generic-interpreter-heredoc.sh
#
# Covers a `worktree-write-confinement` false positive: is_interpreter_opener()
# (shared by mask_heredoc_bodies_selective(), consulted by
# extract_write_targets()'s catastrophic-tier write-confinement scan) used to
# lump shell interpreters (bash/sh/zsh/dash/ksh/eval/source/.) together with
# non-shell script interpreters (python/perl/ruby/node) into one "leave the
# heredoc body visible to the scan" bucket. Because a python3/perl/ruby/node
# heredoc body was never masked, ordinary bit-shift (`>>`, `>>=`) or
# comparison (`>`, `<`) operators in that body were misread as shell
# append-redirection / redirection and denied at catastrophic tier, even
# though the body performs no file I/O at all.
#
# This test verifies:
#   1. The reported false positive (`python3 <<'EOF'` with `>>=`) -> ALLOW
#   2. The sibling false positive (bare `>` comparison in python/perl/ruby/
#      node heredocs) -> ALLOW
#   3. A genuinely dangerous shell-interpreter-fed heredoc with a real
#      destructive write outside the worktree still -> DENY (confirms the
#      fix did not weaken shell-heredoc protection)
#   4. A `cat <<EOF ... EOF` inert-sink heredoc is unaffected (still ALLOW,
#      same as before this fix)
#   5. Edge cases: a dashed heredoc (`<<-'EOF'`) and a wrapper-prefixed
#      interpreter (`timeout 30 python3 <<'EOF'`) are still classified
#      correctly into the non-shell bucket
#
# NOTE ON `defaults/` (curator caveat, verified 2026-08-07): several existing
# files under .loom/hooks/tests/ resolve their source-of-truth hook as
# `$REPO_ROOT/defaults/hooks/...`. This consumer repo has no `defaults/` tree
# (it is a resynced/installed-only Loom deployment), so that pattern fails
# immediately at the `cp` step here. This test instead copies the REAL
# installed/consumer-repo path, `$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh`,
# into an isolated temp git tree so the hook's REPO_ROOT/HOOK_ERROR_LOG/
# worktree-confinement logic resolve there. Exit 0 = all pass, 1 = fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"

PASS=0
FAIL=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

if [[ ! -f "$SRC_HOOK" ]]; then
    echo "ERROR: $SRC_HOOK not found" >&2
    exit 1
fi

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
# Canonicalize to defeat the macOS /tmp -> /private/tmp symlink, so the cwd
# we feed the hook matches the repo root git resolves via `rev-parse`.
TMPROOT=$(cd "$TMPROOT" && pwd -P)
git init -q "$TMPROOT"
mkdir -p "$TMPROOT/.loom/hooks"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-destructive-generic.sh"
HOOK="$TMPROOT/.loom/hooks/guard-destructive-generic.sh"

# --- Fixture: one managed worktree at $TMPROOT/.loom/worktrees/issue-1 -----
# This is what puts "worktree isolation in play" (_wt_isolation_in_play): the
# worktree-write-confinement scan only ever fires a deny when a managed
# worktree actually exists somewhere in the repo. Running from $TMPROOT
# itself (the main checkout root, outside that worktree) is what lets a
# relative write target resolve "into the main checkout" and trip the deny.
mkdir -p "$TMPROOT/.loom/worktrees/issue-1/src"
cat > "$TMPROOT/.loom/worktrees/issue-1/.loom-managed" <<'EOF'
# Loom-managed worktree marker
EOF
touch "$TMPROOT/CLAUDE.md"

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

make_input() {
    local cmd="$1"
    jq -n --arg cmd "$cmd" --arg cwd "$TMPROOT" '{tool_input: {command: $cmd}, cwd: $cwd}'
}

# Prints "<exit_code>|<stdout>". Always run from $TMPROOT (the main checkout
# root, matching the stdin cwd) so REPO_ROOT/_WT_MAIN_ROOT resolve there.
run_hook() {
    local cmd="$1"
    local exit_code=0 output
    output=$(cd "$TMPROOT" && bash "$HOOK" < <(make_input "$cmd") 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

assert_allow() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    local decision
    decision=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    if [[ "$code" == "0" && "$decision" != "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected allow, got exit=$code output=$out)"
    fi
}

assert_deny() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    local decision
    decision=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    if [[ "$decision" == "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected permissionDecision=deny, got: $out)"
    fi
}

echo "=== guard-destructive-generic.sh interpreter-heredoc tests (#16) ==="

# (1) Original reported false positive: python3 heredoc with `>>=` / bare `>>`
CMD1='python3 << '"'"'EOF'"'"'
reg = 0x1F
reg >>= 1
byte = 0xFF
shifted = (byte >> 1)
print(reg, shifted)
EOF'
result=$(run_hook "$CMD1")
assert_allow "(1) python3 heredoc with >>=/bare >> bit-shift -> allow" "$result"

# (2) Sibling false positive: bare `>` / `<` comparison operators
CMD2='python3 << '"'"'EOF'"'"'
reg = 0x100
if reg > 0xFF:
    print("big")
if reg < 0x200:
    print("small")
EOF'
result=$(run_hook "$CMD2")
assert_allow "(2) python3 heredoc with bare >/< comparison -> allow" "$result"

# (2b) Same sibling case in perl
CMD2B='perl << '"'"'EOF'"'"'
my $reg = 0x100;
if ($reg > 0xFF) { print "big\n"; }
EOF'
result=$(run_hook "$CMD2B")
assert_allow "(2b) perl heredoc with bare > comparison -> allow" "$result"

# (2c) Same sibling case in node/nodejs
CMD2C='node << '"'"'EOF'"'"'
let reg = 0x100;
if (reg > 0xFF) { console.log("big"); }
EOF'
result=$(run_hook "$CMD2C")
assert_allow "(2c) node heredoc with bare > comparison -> allow" "$result"

# (3) Non-shell interpreter class coverage: ruby heredoc with >>/>>=
CMD3='ruby << '"'"'EOF'"'"'
x = 5
x >>= 1
puts x
EOF'
result=$(run_hook "$CMD3")
assert_allow "(3) ruby heredoc with >>= bit-shift -> allow" "$result"

# (4) Genuinely dangerous case: shell-interpreter-fed heredoc with a real
# destructive write resolving outside the worktree (into the main checkout
# root) must still DENY at catastrophic tier -- confirms the fix does not
# reopen the #4178/#5351 worktree-write-confinement protection.
CMD4='bash << '"'"'EOF'"'"'
echo pwned > CLAUDE.md
EOF'
result=$(run_hook "$CMD4")
assert_deny "(4) bash heredoc with real write outside worktree -> deny" "$result"

# (5) cat <<EOF ... EOF inert-sink heredoc is unaffected (pre-existing
# #4914/#5000/#5181 masking behavior unchanged by this fix).
CMD5='cat << '"'"'EOF'"'"'
reg >>= 1
if reg > 0xFF: pass
EOF'
result=$(run_hook "$CMD5")
assert_allow "(5) cat heredoc (inert sink) with >>/> text -> allow (unchanged)" "$result"

# (6) Edge case: dashed heredoc form (<<-'EOF') with python
CMD6='python3 <<-'"'"'EOF'"'"'
	reg = 1
	reg >>= 1
	print(reg)
	EOF'
result=$(run_hook "$CMD6")
assert_allow "(6) python3 dashed heredoc (<<-) with >>= -> allow" "$result"

# (7) Edge case: interpreter invoked via a wrapper (timeout 30 python3 <<EOF)
CMD7='timeout 30 python3 << '"'"'EOF'"'"'
reg = 1
reg >>= 1
print(reg)
EOF'
result=$(run_hook "$CMD7")
assert_allow "(7) timeout-wrapped python3 heredoc with >>= -> allow" "$result"

echo ""
echo "Tests run: $TOTAL, Passed: $PASS, Failed: $FAIL"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
