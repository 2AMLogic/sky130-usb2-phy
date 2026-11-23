"""The single-ended receivers' extracted-leg grading over the shared leaf pex runner.

sim/se-receiver-dp-pex/run.py (D+, se_receiver_dp) and sim/se-receiver-dm-pex/run.py
(D-, se_receiver_dm) are thin entry points over sim/harness/pex_runner.py, the one
post-layout (klt pex) runner behind every leaf pex bench (klt pex submission, the
schematic-leg equivalence gate against the leaf's committed record, netlist-snapshot
freeze, evidence staging; see that module and sim/README.md). What the two receiver
benches take from here is the one part of their pex flow that is specific to them:
`grade_extracted`, the extracted-leg grading both leaves share, and `summarize`,
its end-of-run report line. Regression tests in sim/tests/test_pex_runner.py.

The receivers' requests differ from the other leaves' in one respect. The committed
bench's 8th measurement `vref_v` (`.meas dc ... FIND v(xrx.vref)`) is NOT in either
request: it probes a node inside the DUT by name, and the extracted netlist renames
internal nets to synthesized hub names, so the row errors the whole envelope on the
extracted leg (klt pex `no_such_vector`, 2AMLogic/klayout-tools#6990; discovered by
run 20261121-000805, whose schematic leg did reproduce the committed vref_v at both
corners). It is the bench's own sanity probe, not a spec row; the equivalence gate
therefore covers 7 of the committed record's 8 measurements (14 rows per leaf, not
16).

grading.json evaluates the EXTRACTED leg per corner against the same criteria the
committed bench grades (strict (0.8 V, 2.0 V) crossing window, single crossing,
supply-relative output levels, supply current): klt pex grades only the request's
declared supply-absolute limits, so the supply-relative checks are evaluated here,
per corner, from the delta rows.
"""

from __future__ import annotations

from . import pex_equivalence
from .pex_runner import Bench


def supply_v(unit: dict) -> float:
    return float(next(iter(unit["supply_v"].values())))


def grade_extracted(cfg: Bench, envelope: dict, tb: dict) -> dict:
    """The bench's own checks, evaluated on the extracted leg per corner (the
    supply-relative criteria klt pex cannot declare in one request)."""
    extracted = {(r.get("corner_id"), r.get("spec_row")): r.get("extracted_value")
                 for r in envelope.get("delta") or []}

    def check(cid, name, value, ok, bound):
        return {"corner_id": cid, "check": name, "value": value,
                "verdict": "pass" if (value is not None and ok(value)) else "FAIL",
                "bound": bound}

    corners = {}
    all_pass = True
    for unit in tb["corners"]["units"]:
        cid = pex_equivalence.unit_corner_id(unit)
        vdd = supply_v(unit)
        rows = []

        def v(name):
            return extracted.get((cid, name))

        for name in ("vth_v", "vth_last_v"):
            rows.append(check(cid, f"{name} strictly inside (0.8, 2.0) V", v(name),
                              lambda x: 0.8 < x < 2.0, "0.8 V < x < 2.0 V (exclusive)"))
        rows.append(check(cid, "vth_last_v equals vth_v within one 1 mV step",
                          None if v("vth_v") is None or v("vth_last_v") is None
                          else abs(v("vth_last_v") - v("vth_v")),
                          lambda x: x <= 0.001, "|vth_last_v - vth_v| <= 0.001 V"))
        rows.append(check(cid, "rxd_low_max_v <= 0.1*VDD", v("rxd_low_max_v"),
                          lambda x: x <= 0.1 * vdd, f"<= {0.1 * vdd:g} V"))
        rows.append(check(cid, "rxd_at_vil_v <= 0.1*VDD", v("rxd_at_vil_v"),
                          lambda x: x <= 0.1 * vdd, f"<= {0.1 * vdd:g} V"))
        rows.append(check(cid, "rxd_high_min_v >= 0.9*VDD", v("rxd_high_min_v"),
                          lambda x: x >= 0.9 * vdd, f">= {0.9 * vdd:g} V"))
        rows.append(check(cid, "rxd_at_vih_v >= 0.9*VDD", v("rxd_at_vih_v"),
                          lambda x: x >= 0.9 * vdd, f">= {0.9 * vdd:g} V"))
        rows.append(check(cid, "isup_ua in [1, 500] uA (raw A)", v("isup_ua"),
                          lambda x: 1e-06 <= x <= 5e-04, "[1e-06, 5e-04] A"))
        corners[cid] = {"supply_v": vdd, "checks": rows}
        all_pass = all_pass and all(r["verdict"] == "pass" for r in rows)
    return {"leaf": cfg.leaf, "leg": "extracted", "all_pass": all_pass, "corners": corners}


def summarize(grading: dict) -> list[str]:
    """The receivers' end-of-run grading line (`Bench.summarize`)."""
    return [f"extracted-leg grading: {'PASS' if grading['all_pass'] else 'FAIL'} "
            f"({sum(len(c['checks']) for c in grading['corners'].values())} checks)"]
