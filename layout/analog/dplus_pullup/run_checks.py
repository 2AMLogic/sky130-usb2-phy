#!/usr/bin/env python3
"""Run the physical checks for layout/analog/dplus_pullup (issue #222).

    python3 layout/analog/dplus_pullup/run_checks.py            # run, write reports
    python3 layout/analog/dplus_pullup/run_checks.py --record   # also mint the record

The five steps, the reports and the record are produced by the shared runner
layout/analog/run_checks_common.py; this file holds only what is specific to this leaf.
Reports and records stay in this leaf and flow/analog-layout-dplus_pullup/.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from run_checks_common import LeafConfig, main  # noqa: E402

CONFIG = LeafConfig(
    here=HERE,
    block="dplus_pullup",
    issue=222,
    supply_nets=("VPU", "VSS"),
    claim_subject="the dplus_pullup leaf's",
    bulk_note_tail=(
        " for the MOS4 device classes (which carry B); "
        "res_generic_po is a two-terminal resistor with no bulk terminal."
    ),
    doc=__doc__,
)


if __name__ == "__main__":
    sys.exit(main(CONFIG))
