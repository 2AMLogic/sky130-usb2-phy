#!/usr/bin/env bash
# Resolve the base ref the evidence lints are enforced against. Backs the
# "Resolve the append-only base ref" step of the `flow-records` job in
# .github/workflows/ci.yml; the resolved value becomes FLOW_LINT_BASE_REF,
# which .github/scripts/lint.sh forwards to both lints' --base-ref.
#
# Inputs come from the workflow step's `env:` block (the same two-expression
# plumbing sky130-comparator#332 uses), so nothing here interpolates GitHub
# context expressions directly:
#
#   EVENT    -- github.event_name: pull_request | push | merge_group
#   BASE_REF -- github.base_ref                     (pull_request)
#   BEFORE   -- github.event.before                 (push)
#   MG_BASE  -- github.event.merge_group.base_sha   (merge_group)
#
# Behavior per event:
#   pull_request -- fetch origin/"$BASE_REF" and use "origin/$BASE_REF", as
#                   the inline step always did.
#   push         -- "$BEFORE", falling back to HEAD~1 when unset (the first
#                   push of a branch), as before.
#   merge_group  -- "$MG_BASE", REQUIRED and required to resolve to a commit
#                   in this checkout (`git cat-file -e`). github.base_ref and
#                   github.event.before are both empty on a merge_group run,
#                   so falling through to the push fallback would silently
#                   mis-base a multi-PR group at the group head's first
#                   parent -- an unverified pass, the exact failure mode the
#                   append-only lint exists to prevent. A missing or
#                   unavailable base therefore fails the step instead.
#
# The value is appended to $GITHUB_ENV when that is set (CI) and echoed to
# stdout either way, so local runs and the selftests
# (flow/tests/test_resolve_base_ref.py) can read it without a GITHUB_ENV.
set -uo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

case "${EVENT:-}" in
  pull_request)
    [ -n "${BASE_REF:-}" ] \
      || fail "pull_request event with an empty github.base_ref"
    git fetch --no-tags origin "$BASE_REF" \
      || fail "git fetch --no-tags origin $BASE_REF failed"
    REF="origin/$BASE_REF"
    ;;
  push)
    REF="${BEFORE:-HEAD~1}"
    ;;
  merge_group)
    [ -n "${MG_BASE:-}" ] \
      || fail "merge_group event with an empty merge_group.base_sha -- the append-only base cannot be resolved; refusing to fall back to HEAD~1 or origin/main, which would mis-base the group"
    git cat-file -e "${MG_BASE}^{commit}" 2>/dev/null \
      || fail "merge_group base sha $MG_BASE is not available in this checkout (fetch full history); refusing to mis-base the append-only lint"
    REF="$MG_BASE"
    ;;
  *)
    fail "unsupported event '${EVENT:-<unset>}' -- set EVENT to pull_request, push or merge_group"
    ;;
esac

if [ -n "${GITHUB_ENV:-}" ]; then
  echo "FLOW_LINT_BASE_REF=$REF" >> "$GITHUB_ENV"
fi
echo "FLOW_LINT_BASE_REF=$REF"
