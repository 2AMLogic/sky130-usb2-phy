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

import json
import math

from . import pex_equivalence, results
from .pex_runner import Bench


def supply_v(unit: dict) -> float:
    return float(next(iter(unit["supply_v"].values())))


def _corner_checks(cid: str, vdd: float, raw: dict, thresholds: dict) -> list[dict]:
    """Render the receiver report in raw units, grading in the threshold bench's units."""
    rules = thresholds["checks"]
    meas = results.scaled_measurements(raw.items(), thresholds["measure"])
    rows = []

    def check(name, rule, label, value, bound):
        passed = name in meas and not results.rule_problems(name, rule, meas, vdd)
        if isinstance(value, float) and not math.isfinite(value):
            value = None  # JSON has no representation for infinity or NaN.
        rows.append(
            {
                "corner_id": cid,
                "check": label,
                "value": value,
                "verdict": "pass" if passed else "FAIL",
                "bound": bound,
            }
        )

    for name in ("vth_v", "vth_last_v"):
        rule = rules[name].copy()
        same = rule.pop("same_as", None)
        lo, hi = rule["gt"], rule["lt"]
        check(
            name,
            rule,
            f"{name} strictly inside ({lo}, {hi}) V",
            raw.get(name),
            f"{lo} V < x < {hi} V (exclusive)",
        )
        if same:
            other, tol = same["measure"], same.get("tol", 0.0)
            gap = abs(raw[name] - raw[other]) if name in meas and other in meas else None
            check(
                name,
                {"same_as": same},
                f"{name} equals {other} within {tol * 1000:g} mV",
                gap,
                f"|{name} - {other}| <= {tol:g} V",
            )

    for name in ("rxd_low_max_v", "rxd_at_vil_v", "rxd_high_min_v", "rxd_at_vih_v"):
        rule = rules[name]
        op, limit = ("<=", rule["max"]) if "max" in rule else (">=", rule["min"])
        check(name, rule, f"{name} {op} {limit:g}*VDD", raw.get(name), f"{op} {limit * vdd:g} V")

    name = "isup_ua"
    rule = rules[name]
    lo, hi = rule["min"], rule["max"]
    scale = thresholds["measure"][name].get("scale", 1.0)
    check(
        name,
        rule,
        f"{name} in [{lo:g}, {hi:g}] uA (raw A)",
        raw.get(name),
        f"[{lo / scale:g}, {hi / scale:g}] A",
    )
    return rows


def grade_extracted(cfg: Bench, envelope: dict, tb: dict) -> dict:
    """The bench's own checks, evaluated on the extracted leg per corner (the
    supply-relative criteria klt pex cannot declare in one request)."""
    extracted = {(r.get("corner_id"), r.get("spec_row")): r.get("extracted_value")
                 for r in envelope.get("delta") or []}
    # The reference belongs to <threshold bench>/corners/<run>/report.json.
    thresholds = json.loads((cfg.reference_report.parents[2] / "testbench/tb.json").read_text())

    corners = {}
    all_pass = True
    for unit in tb["corners"]["units"]:
        cid = pex_equivalence.unit_corner_id(unit)
        vdd = supply_v(unit)
        raw = {m["name"]: extracted.get((cid, m["name"])) for m in tb["measurements"]}
        rows = _corner_checks(cid, vdd, raw, thresholds)
        corners[cid] = {"supply_v": vdd, "checks": rows}
        all_pass = all_pass and all(r["verdict"] == "pass" for r in rows)
    return {"leaf": cfg.leaf, "leg": "extracted", "all_pass": all_pass, "corners": corners}


def summarize(grading: dict) -> list[str]:
    """The receivers' end-of-run grading line (`Bench.summarize`)."""
    return [f"extracted-leg grading: {'PASS' if grading['all_pass'] else 'FAIL'} "
            f"({sum(len(c['checks']) for c in grading['corners'].values())} checks)"]
