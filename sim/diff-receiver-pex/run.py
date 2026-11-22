#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the differential_receiver leaf. See sim/README.md.

Entry point only: the flow itself (klt pex submission, the schematic-leg
equivalence gate against this leaf's committed record, netlist-snapshot freeze,
evidence staging) is the one shared leaf runner, sim/harness/pex_runner.py,
behind every leaf pex bench; the gate is the shared exact-pair check in
sim/harness/pex_equivalence.py. This bench supplies no extracted-leg grading: a
run writes equivalence.json only. The per-leaf facts this bench owns:

- leaf/layout: differential_receiver
  (layout/analog/differential_receiver/differential_receiver.gds)
- request: testbench/tb.json, the sensitivity bench re-run at tt_27c_3.30v and
  at sf_100c_3.00v, the binding corner of the committed 45-point schematic
  record (18 measurements x 3 common-mode points -> 36 equivalence rows)
- deck: testbench/diff_receiver_pex_tb.spice; pin-order DUT shim:
  testbench/differential_receiver_pex_dut.spice
- committed schematic reference: sim/diff-receiver-sensitivity/corners/
  20261020-172719-ca4a45a/report.json

    python3 sim/diff-receiver-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/diff-receiver-pex/run.py              # batch run, equivalence gate, staging

Evidence is staged for `python3 sim/run_store_evidence.py diff-receiver-pex
<stage-dir>`.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness.pex_runner import Bench, main  # noqa: E402

BENCH = Bench(
    leaf="differential_receiver",
    bench="diff-receiver-pex",
    deck="diff_receiver_pex_tb.spice",
    shim="differential_receiver_pex_dut.spice",
    reference_report=REPO / "sim/diff-receiver-sensitivity/corners/20261020-172719-ca4a45a/report.json",
)

if __name__ == "__main__":
    raise SystemExit(main(BENCH))
