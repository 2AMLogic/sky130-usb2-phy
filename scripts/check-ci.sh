#!/usr/bin/env bash
# Runs this repo's actual verification suite (see verification/README.md).
# Backs the `check:ci` npm script -- replaces a stub that always exited 0.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STATUS=0

echo "== Layer 1/3: usbfs protocol reference + packet builders (pytest) =="
if ! python3 -m pytest verification/test_usbfs_model.py -v; then
  STATUS=1
fi

echo
echo "== Layer 2 + RTL: cocotb testbenches via klt functional-verification =="
if command -v klt >/dev/null 2>&1; then
  for request in verification/request-*.json; do
    echo "-- $request --"
    if ! klt functional-verification "$request" --format json; then
      echo "FAILED: $request" >&2
      STATUS=1
    fi
  done
else
  echo "WARNING: klt not found on PATH -- skipping cocotb/RTL testbenches" >&2
  echo "  (test_utmi_stub, test_usbfs_loopback, test_usb_rx, test_usb_tx)." >&2
  echo "  See docs/environment-setup.md to install the toolchain." >&2
fi

exit "$STATUS"
