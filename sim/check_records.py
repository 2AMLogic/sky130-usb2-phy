#!/usr/bin/env python3
"""Analog evidence-record lint (stdlib + git only).

    python3 sim/check_records.py --base-ref origin/main
    python3 sim/check_records.py --no-append-only        # format/coverage only

See sim/harness/evidence_lint.py and sim/README.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness.evidence_lint import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
