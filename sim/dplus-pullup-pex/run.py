#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the dplus_pullup leaf. See sim/README.md.

Entry point plus this bench's own extracted-leg evaluator: the flow itself (klt
pex submission, the schematic-leg equivalence gate against this leaf's committed
record, netlist-snapshot freeze, evidence staging) is the one shared leaf runner,
sim/harness/pex_runner.py, behind every leaf pex bench; the gate is the shared
exact-pair check in sim/harness/pex_equivalence.py, which expects this bench's two
requested corners x 26 measurements = 52 rows. The per-leaf facts this bench owns:

- leaf/layout: dplus_pullup (layout/analog/dplus_pullup/dplus_pullup.gds)
- request: testbench/tb.json, the pull-up tolerance bench re-run at tt_27c_3.30v
  and at fs_hl_100c_3.00v, the binding corner of the committed 225-point
  resistor-set schematic record
- deck: testbench/dplus_pullup_pex_tb.spice; pin-order DUT shim:
  testbench/dplus_pullup_pex_dut.spice
- committed schematic reference: sim/dplus-pullup-tolerance/corners/
  20261020-174658-ca4a45a/report.json

    python3 sim/dplus-pullup-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/dplus-pullup-pex/run.py              # batch run, equivalence gate, staging

grading.json evaluates the EXTRACTED leg per corner with the committed bench's own
evaluator: the 16 code voltages go through sim/harness/trim.py (R_eff against the
15 kohm host load; the corner passes when every code yields a finite positive
R_eff and at least one lands inside the inclusive [1425, 1575] ohm window of the
ratified 'FS device D+ pull-up' row), the disabled-state D+ voltage keeps its
0.8 V bound, and the leakage/supply currents are recorded as engineering data (no
ratified limit). klt pex grades only the request's declared supply-absolute limits
(the two voff rows); the trim criterion is existential over codes within each
corner, which no per-row limit can express.

Evidence is staged for `python3 sim/run_store_evidence.py dplus-pullup-pex
<stage-dir>`.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness import pex_equivalence, trim  # noqa: E402
from harness.pex_runner import Bench, main  # noqa: E402

BENCH_TB = REPO / "sim/dplus-pullup-tolerance/testbench/tb.json"
CODES = 16


def grade_extracted(cfg: Bench, envelope: dict, tb: dict) -> dict:
    """The committed bench's own evaluator on the extracted leg, per corner."""
    extracted = {(r.get("corner_id"), r.get("spec_row")): r.get("extracted_value")
                 for r in envelope.get("delta") or []}
    trim_cfg = json.loads(BENCH_TB.read_text())["trim"]
    corners = {}
    all_pass = True
    for unit in tb["corners"]["units"]:
        cid = pex_equivalence.unit_corner_id(unit)
        vpu = float(next(iter(unit["supply_v"].values())))
        rows = []

        def v(name):
            return extracted.get((cid, name))

        for name in ("voff_d1_v", "voff_d0_v"):
            value = v(name)
            rows.append({"corner_id": cid, "check": f"{name} <= 0.8 V", "value": value,
                         "verdict": "pass" if (value is not None and value <= 0.8) else "FAIL",
                         "bound": "<= 0.8 V"})
        v_dp = [v(f"vdp_c{k:02d}_v") for k in range(CODES)]
        derived, problems = trim.analyse(v_dp, vpu, trim_cfg)
        in_window = int(derived.get("n_in_window", 0))
        best = None
        if "best_code" in derived:
            best = {"code": int(derived["best_code"]), "r_ohm": derived["best_r_ohm"],
                    "err_ohm": derived["best_err_ohm"]}
        rows.append({"corner_id": cid,
                     "check": "every code finite-positive and >= 1 code inside "
                              f"[{trim_cfg['lo_ohm']:g}, {trim_cfg['hi_ohm']:g}] ohm",
                     "value": {"n_in_window": in_window, "best": best},
                     "verdict": "pass" if not problems else "FAIL",
                     "bound": "trim.analyse over the 16 code voltages at the 15 kohm load"})
        corners[cid] = {"supply_v": vpu, "checks": rows, "trim_problems": problems,
                        "r_eff_ohm": {f"c{k:02d}": derived.get(f"r_c{k:02d}_ohm")
                                      for k in range(CODES)}}
        all_pass = all_pass and all(r["verdict"] == "pass" for r in rows)
    return {"leaf": cfg.leaf, "leg": "extracted", "all_pass": all_pass, "corners": corners}


def summarize(grading: dict) -> list[str]:
    """The per-corner trim summary (`Bench.summarize`): the trim verdict with the
    best code's R_eff, or the trim problems where no code yielded an R_eff."""
    lines = []
    for cid, c in grading["corners"].items():
        best = next((r["value"]["best"] for r in c["checks"]
                     if r["value"] and isinstance(r["value"], dict)
                     and r["value"].get("best") is not None), None)
        if best:
            verdict = "PASS" if c["checks"][-1]["verdict"] == "pass" else "FAIL"
            lines.append(f"extracted trim at {cid}: {verdict}"
                         f" (best code {best['code']}: {best['r_ohm']:.2f} ohm)")
        else:
            lines.append(f"extracted trim at {cid}: FAIL {c['trim_problems']}")
    return lines


BENCH = Bench(
    leaf="dplus_pullup",
    bench="dplus-pullup-pex",
    deck="dplus_pullup_pex_tb.spice",
    shim="dplus_pullup_pex_dut.spice",
    reference_report=REPO / "sim/dplus-pullup-tolerance/corners/20261020-174658-ca4a45a/report.json",
    grade_extracted=grade_extracted,
    summarize=summarize,
)

if __name__ == "__main__":
    raise SystemExit(main(BENCH))
