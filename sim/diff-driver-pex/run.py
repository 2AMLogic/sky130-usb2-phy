#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the differential_driver leaf. See sim/README.md.

Submits the two committed driver benches restructured for `klt pex` -- the static
bench (testbench/tb-static.json: rows 6-04 VOH, 6-05 VOL, 6-08 output resistance)
and the signal-quality bench (testbench/tb-sq.json: rows 6-06 rise/fall + matching,
6-07 crossover, the decision-record 0008 crossover load) -- each at tt_27c_3.30v
plus its binding corners, against the committed leaf GDS. Each run checks the
schematic leg of its report against that bench's committed 45-point record
(20261020-194710-ca4a45a static, 20261020-181618-ca4a45a signal quality) and
stages an evidence directory for `python3 sim/run_store_evidence.py
diff-driver-pex <stage-dir>`.

    python3 sim/diff-driver-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/diff-driver-pex/run.py              # batch runs, equivalence gates, staging
    python3 sim/diff-driver-pex/run.py --bench static    # one bench only

The corner sets are deliberate subsets, not the frozen 45-point matrix (each
bench's binding corner set is derived from its committed record: the corner whose
ratified-row value sits closest to a bound): static = tt + fs_-40c_3.60v (VOH
6-04 binding: voh 3.5929 V vs the 3.6 V bound) + sf_-40c_3.60v (VOL 6-05 and
output-resistance 6-08 binding: vol 0.0690 V, rout_low 29.418 ohm vs the 28 ohm
bound); signal quality = tt + fs_100c_3.60v (crossover 6-07 binding: vcross
1.9933 V vs the 2.0 V bound) + sf_-40c_3.60v (matching 6-06 binding: trf ratio
1.0772 vs the 1.1 bound) + fs_100c_3.00v (matching 6-06 binding: trf ratio
0.9278 vs the 0.9 bound). The full 45-point post-layout runs are named as
follow-up.

The shared runner checks each requested (corner, measurement) pair against the
committed reference. A combined run finishes both benches and returns the first
nonzero exit code. Each bench keeps its own run id suffix for staged evidence
and append-only netlist snapshots.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness.pex_runner import Bench, main  # noqa: E402

BENCHES = (
    Bench(
        leaf="differential_driver", bench="diff-driver-pex", variant="static",
        deck="driver_static_pex_tb.spice", shim="differential_driver_pex_dut.spice",
        reference_report=REPO / "sim/driver-static/corners/20261020-194710-ca4a45a/report.json",
        check_nonzero_envelope=True,
    ),
    Bench(
        leaf="differential_driver", bench="diff-driver-pex", variant="sq",
        deck="driver_sq_pex_tb.spice", shim="differential_driver_pex_dut.spice",
        reference_report=REPO / "sim/driver-signal-quality/corners/20261020-181618-ca4a45a/report.json",
        check_nonzero_envelope=True,
    ),
)

if __name__ == "__main__":
    raise SystemExit(main(BENCHES))
