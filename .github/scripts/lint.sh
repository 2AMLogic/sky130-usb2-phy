#!/usr/bin/env bash
# Backs `npm run lint`, and the `flow-records` job in .github/workflows/ci.yml.
#
# This is the *evidence* lint: it checks that this repo's committed
# digital-flow evidence records are well-formed, append-only, fresh, and not
# claiming anything they did not measure. It is deliberately toolchain-free --
# no klt, no PDK, no OpenROAD, no simulator -- so it runs on every PR in
# seconds, whether or not the heavy `check:ci` suite's toolchain provisioned.
#
# The analog (sim/) evidence lint rides along: sim/check_records.py enforces
# the append-only analog evidence under sim/ against the same base ref, and
# sim/tests/ are its (and the harness') toolchain-free self-tests. Neither
# submits a simulation job.
#
# It is NOT a substitute for `npm run check:ci` (the real functional
# verification suite, scripts/check-ci.sh), and it does not re-run the physical
# flow. Re-running the flow is `flow/run_flow.py`, which needs the full
# toolchain; see flow/README.md.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

STATUS=0

# Let CI pass an explicit base ref (a shallow clone has no origin/main).
BASE_REF="${FLOW_LINT_BASE_REF:-origin/main}"

echo "== Evidence-record lint: flow/check_records.py =="
if ! python3 flow/check_records.py --base-ref "$BASE_REF"; then
  STATUS=1
fi

echo
echo "== Analog evidence lint: sim/check_records.py =="
if ! python3 sim/check_records.py --base-ref "$BASE_REF"; then
  STATUS=1
fi

echo
echo "== Evidence-record lint self-tests: flow/tests/ + sim/tests/ =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found" >&2
  exit 1
fi
if python3 -c "import pytest" >/dev/null 2>&1; then
  if ! python3 -m pytest flow/tests sim/tests -q -p no:cacheprovider; then
    STATUS=1
  fi
else
  echo "ERROR: pytest is not installed -- the lint's own self-tests cannot run." >&2
  echo "  python3 -m pip install pytest   (see docs/environment-setup.md)" >&2
  STATUS=1
fi

echo
if [ "$STATUS" -eq 0 ]; then
  echo "lint: OK"
else
  echo "lint: FAILED" >&2
fi
exit "$STATUS"
