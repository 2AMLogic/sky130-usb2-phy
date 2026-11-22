#!/usr/bin/env python3
"""Run the physical checks for layout/analog/differential_receiver (issue #167).

    python3 layout/analog/differential_receiver/run_checks.py            # run, write reports
    python3 layout/analog/differential_receiver/run_checks.py --record   # also mint the record

The checks, reports and record are produced by the shared runner
layout/analog/run_checks_common.py; this file holds only what is specific to this leaf.
Reports and records stay in this leaf and flow/analog-layout-differential_receiver/.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from run_checks_common import LeafConfig, main  # noqa: E402

CONFIG = LeafConfig(
    here=HERE,
    block="differential_receiver",
    issue=167,
    supply_nets=("VDD", "VSS"),
    claim_subject="the first analog leaf's",
    bulk_note_tail=(
        " -- the runset's MOS4 and resistor-with-bulk "
        "device classes carry B / W -- so the 11 matched devices include their bulk nets."
    ),
    doc=__doc__,
    inputs_after_common=["layout/analog/gen_se_receiver.py"],
)


if __name__ == "__main__":
    sys.exit(main(CONFIG))
