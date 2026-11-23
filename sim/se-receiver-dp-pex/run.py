#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the se_receiver_dp leaf. See sim/README.md.

Entry point only: the flow itself (klt pex submission, the schematic-leg
equivalence gate against this leaf's committed record, netlist-snapshot freeze,
evidence staging) is the one shared leaf runner, sim/harness/pex_runner.py,
behind every leaf pex bench; the extracted-leg grading both receivers share is
sim/harness/se_receiver_pex.py. The per-leaf facts this bench owns:

- leaf/layout: se_receiver_dp (layout/analog/se_receiver_dp/se_receiver_dp.gds)
- deck: testbench/se_rx_dp_pex_tb.spice; pin-order DUT shim:
  testbench/se_receiver_dp_pex_dut.spice
- committed schematic reference: sim/se-receiver-dp-thresholds/corners/
  20261020-205102-ea63f5c/report.json (the D+ 225-point resistor-set record)

    python3 sim/se-receiver-dp-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/se-receiver-dp-pex/run.py              # batch run, equivalence gate, staging
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness.pex_runner import Bench, main  # noqa: E402
from harness.se_receiver_pex import grade_extracted, summarize  # noqa: E402

BENCH = Bench(
    leaf="se_receiver_dp",
    bench="se-receiver-dp-pex",
    polarity="D+",
    deck="se_rx_dp_pex_tb.spice",
    shim="se_receiver_dp_pex_dut.spice",
    reference_report=REPO / ("sim/se-receiver-dp-thresholds/corners/"
                             "20261020-205102-ea63f5c/report.json"),
    grade_extracted=grade_extracted,
    summarize=summarize,
)

if __name__ == "__main__":
    raise SystemExit(main(BENCH))
