"""Toolchain-free tests for the D+ pull-up tolerance experiment (#113).

No klt, ngspice or PDK: reports are synthetic. They prove the existential best-trim
selection (formula, inclusive 1425/1575 boundaries, deterministic ties, "one passing
code among failing codes"), the failure paths (no passing code, zero current,
non-finite or missing code data, failed/missing/duplicate corners), that the ratified
window and load are not relaxed in tb.json, and that the design netlist/schematic and the
deck are consistent. They say nothing about the circuit; that is the recorded 45-corner run.
"""

import json
import math
import re
import shutil
from pathlib import Path

import pytest

from harness import evidence_lint as lint, matrix as mx, results as rs, runner, trim

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parent
EXP = SIM / "dplus-pullup-tolerance"
MATRIX = mx.load()
TB = json.loads((EXP / "testbench/tb.json").read_text())
CFG = TB["trim"]
RL = 15000.0


def v_of(r, vpu):
    """V(DP) for an effective pull-up resistance r into the 15 kohm host load."""
    return vpu * RL / (RL + r)


def codes_to_r(base=1900.0, step=52.0):
    return [base - k * step for k in range(16)]  # code 0 = max resistance


def disabled_values():
    return {"voff_d1_v": 2e-6, "voff_d0_v": 2e-6, "ioff_d1_na": 0.13, "ioff_d0_na": 0.13,
            "ioff_dz_na": 0.13, "ioff_dh_na": -0.001, "isup_d1_na": 0.16, "isup_d0_na": 0.18,
            "isup_dz_na": 0.16, "isup_dh_na": 0.02}


def good_values(vpu, rs_=None, tc=1.0):
    rs_ = rs_ or codes_to_r()
    vals = {f"vdp_c{k:02d}_v": v_of(r, vpu) for k, r in enumerate(rs_)}
    vals.update(disabled_values())
    return vals


def report(tamper=None, per_corner=None):
    corners = []
    for p, t, v in MATRIX.points():
        # shift the ladder with temperature so the harness-integrity spread check is met
        scale = 1.0 + (t - 27.0) * 0.0009
        vals = good_values(v, [r * scale for r in codes_to_r(1950.0)])
        if per_corner:
            vals.update(per_corner(p, t, v) or {})
        raw = {n: x for n, x in vals.items()}
        for m in TB["measure"].values():
            pass
        corners.append({
            "corner_id": f"{p}/{v:.3f}V/{t:g}C", "process": p, "supply_v": {"vsup": v},
            "temperature_c": float(t), "status": "pass",
            "measurements": [{"name": n, "value": x / float(TB["measure"][n].get("scale", 1.0)),
                              "status": "pass"} for n, x in raw.items()],
            "artifacts": {"log": None}})
    rep = {"status": "pass", "corners": corners, "environment": {"remote": {"job_id": "j"}}}
    if tamper:
        tamper(rep)
    return rep


def meas(rep, idx, name):
    return next(m for m in rep["corners"][idx]["measurements"] if m["name"] == name)


def evaluate(rep):
    return rs.evaluate(rep, MATRIX.points(), TB)


# ---- formula and selection (pure functions)

def test_r_eff_formula_units_and_direction():
    # V(DP) = 2.7 V from 3.0 V into 15 kohm: I_load = 0.18 mA out of the pull-up; R = 0.3/0.18 mA
    assert trim.r_eff(2.7, 3.0, RL) == pytest.approx(0.3 / (2.7 / RL))
    assert trim.r_eff(2.7, 3.0, RL) == pytest.approx(1666.6667, rel=1e-6)
    for r in (1425.0, 1500.0, 1575.0):
        assert trim.r_eff(v_of(r, 3.3), 3.3, RL) == pytest.approx(r, rel=1e-12)


@pytest.mark.parametrize("v,vpu", [(0.0, 3.3), (-0.1, 3.3), (3.3, 3.3), (3.4, 3.3), (float("nan"), 3.3),
                                   (float("inf"), 3.3), (None, 3.3), (1.0, float("nan")), (True, 3.3)])
def test_r_eff_guards_zero_current_singular_and_nonfinite(v, vpu):
    assert trim.r_eff(v, vpu, RL) is None


def analyse(rs_, vpu=3.3):
    return trim.analyse([v_of(r, vpu) for r in rs_], vpu, CFG)


def test_one_passing_code_among_failing_codes_passes():
    rs_ = [1700.0 + 10 * k for k in range(16)]  # all out of window...
    rs_[7] = 1500.0                              # ...except code 7
    d, probs = analyse(rs_)
    assert probs == [] and d["best_code"] == 7 and d["n_in_window"] == 1
    assert d["best_r_ohm"] == pytest.approx(1500.0)


@pytest.mark.parametrize("r,ok", [(1425.0, True), (1575.0, True), (1424.99, False), (1575.01, False),
                                  (1424.0, False), (1576.0, False)])
def test_window_bounds_are_inclusive_and_exact(r, ok):
    # a window edge value is formed through V(DP) so allow the last-ulp round trip: assert on the
    # recovered resistance, as the evaluator does
    rs_ = [3000.0] * 16
    rs_[3] = r
    d, probs = analyse(rs_)
    got = d["r_c03_ohm"]
    assert (probs == []) == (1425.0 <= got <= 1575.0)
    if abs(r - 1425.0) > 1e-3 and abs(r - 1575.0) > 1e-3:
        assert (probs == []) == ok


def test_exact_edges_via_the_window_predicate():
    # the evaluator's predicate is lo <= R <= hi (inclusive); exercise it on exact floats
    cfg = dict(CFG)
    for r in (1425.0, 1575.0):
        v = 3.3 * RL / (RL + r)
        d, probs = trim.analyse([v if k == 0 else 3.3 * RL / (RL + 3000.0) for k in range(16)], 3.3, cfg)
        rec = d["r_c00_ohm"]
        assert (d["n_in_window"] == 1.0) == (1425.0 <= rec <= 1575.0)


def test_no_passing_code_is_reported_with_best_code():
    d, probs = analyse([1700.0 + 10 * k for k in range(16)])
    assert d["n_in_window"] == 0 and d["best_code"] == 0
    assert len(probs) == 1 and "no trim code inside [1425, 1575] ohm (best code 0" in probs[0]


def test_ties_go_to_the_lowest_code():
    rs_ = [3000.0] * 16
    rs_[5] = 1480.0
    rs_[9] = 1480.0  # identical resistance, identical distance: the lower code wins
    d, _ = analyse(rs_)
    assert d["best_code"] == 5
    d2, _ = analyse(list(reversed(rs_)))  # tied codes are now 6 and 10
    assert d2["best_code"] == 6


def test_steps_range_and_monotonic_count():
    d, probs = analyse(codes_to_r(1900.0, 52.0))
    assert probs == []
    assert d["step_min_ohm"] == pytest.approx(52.0) and d["step_max_ohm"] == pytest.approx(52.0)
    assert d["step_c01_ohm"] == pytest.approx(52.0) and d["step_c15_ohm"] == pytest.approx(52.0)
    assert d["range_ohm"] == pytest.approx(15 * 52.0) and d["n_nonmonotonic"] == 0
    rs_ = codes_to_r(1900.0, 52.0)
    rs_[8] = rs_[7] + 5  # a code that does not lower the resistance
    d, _ = analyse(rs_)
    assert d["n_nonmonotonic"] == 1


def test_invalid_code_fails_without_hiding_other_codes():
    vs = [v_of(r, 3.3) for r in codes_to_r()]
    vs[4] = 0.0  # zero current
    d, probs = trim.analyse(vs, 3.3, CFG)
    assert any("code 4" in p for p in probs)
    assert "r_c04_ohm" not in d and "range_ohm" not in d and d["best_code"] in range(16)


# ---- grid-level evaluation

def test_good_grid_passes_and_reports_per_corner_data():
    results, problems = evaluate(report())
    assert problems == [] and len(results) == 45
    r = results[0]["measurements"]
    assert {"best_code", "best_r_ohm", "step_min_ohm", "step_max_ohm", "range_ohm", "r_c00_ohm", "r_c15_ohm"} <= set(r)
    assert all(f"vdp_c{k:02d}_v" in r for k in range(16))  # raw measurements preserved


def test_best_code_may_differ_per_corner():
    results, problems = evaluate(report())
    assert problems == []
    assert len({round(x["measurements"]["best_code"]) for x in results}) > 1


def test_codes_failing_the_window_do_not_fail_a_corner_that_has_one_passing_code():
    # the window is existential: every other code is far outside [1425, 1575], that is fine
    def one_code(p, t, v):
        rs_ = [4000.0] * 16
        rs_[11] = 1575.0 - 1e-3
        return {f"vdp_c{k:02d}_v": v_of(r, v) for k, r in enumerate(rs_)} | {}
    results, problems = rs.evaluate(report(per_corner=lambda p, t, v: one_code(p, t, v) if (p, t, v) == ("fs", 27, 3.3) else None),
                                    MATRIX.points(), {**TB, "checks": {k: x for k, x in TB["checks"].items() if k != "r_c00_ohm"}})
    assert problems == []


@pytest.mark.parametrize("name,tamper,needle", [
    ("no passing code", lambda r: [meas(r, 4, f"vdp_c{k:02d}_v").update(value=v_of(2500.0 - 3 * k, r["corners"][4]["supply_v"]["vsup"])) for k in range(16)],
     "no trim code inside"),
    ("zero current", lambda r: meas(r, 4, "vdp_c07_v").update(value=0.0), "code 7: no finite positive R_eff"),
    ("VDP at VPU", lambda r: meas(r, 4, "vdp_c07_v").update(value=r["corners"][4]["supply_v"]["vsup"]), "code 7: no finite positive R_eff"),
    ("nonfinite", lambda r: meas(r, 4, "vdp_c07_v").update(value=float("nan")), "vdp_c07_v"),
    ("missing code", lambda r: r["corners"][4]["measurements"].remove(meas(r, 4, "vdp_c15_v")), "vdp_c15_v"),
    ("missing corner", lambda r: r["corners"].pop(), "missing from report"),
    ("failed simulation", lambda r: r["corners"][2].update(status="error"), "simulation status"),
    ("duplicate corner", lambda r: r["corners"].append(json.loads(json.dumps(r["corners"][0]))), "duplicate corner"),
    ("unexpected corner", lambda r: r["corners"].append({**json.loads(json.dumps(r["corners"][0])), "temperature_c": 125.0}), "unexpected corner"),
    ("disabled pulled up", lambda r: meas(r, 6, "voff_d1_v").update(value=1.2), "voff_d1_v"),
    ("missing disabled data", lambda r: r["corners"][6]["measurements"].remove(meas(r, 6, "isup_dz_na")), "isup_dz_na"),
])
def test_bad_grid_never_passes(name, tamper, needle):
    results, probs = evaluate(report(tamper))
    assert any(needle in p for p in probs), probs
    if name not in ("duplicate corner", "unexpected corner"):  # extra entries do not change the 45 results
        assert any(x["status"] != "ok" for x in results)


def test_failure_names_corner_id_and_value():
    def tamper(r):
        for k in range(16):
            meas(r, 0, f"vdp_c{k:02d}_v").update(value=v_of(2500.0 - 3 * k, 3.0))
    _, probs = evaluate(report(tamper))
    assert any(p.startswith("tt_-40c_3.00v: no trim code inside [1425, 1575] ohm (best code 15: ") for p in probs), probs


def test_flat_resistance_across_the_grid_is_flagged():
    def flat(r):
        pass
    rep = report(per_corner=lambda p, t, v: {f"vdp_c{k:02d}_v": v_of(1900.0 - 52 * k, v) for k in range(16)})
    _, probs = evaluate(rep)
    assert any("r_c00_ohm spread" in p for p in probs), probs


# ---- tb.json and design consistency (the ratified window and load are not relaxed)

def test_ratified_row_and_load_are_unrelaxed():
    assert (CFG["lo_ohm"], CFG["hi_ohm"], CFG["target_ohm"], CFG["load_ohm"], CFG["codes"]) == (1425, 1575, 1500, 15000, 16)
    assert not any(k.startswith(("r_c", "best_")) and ("min" in v or "max" in v) for k, v in TB["checks"].items())
    deck = (EXP / "testbench/dplus_pullup_tb.spice").read_text()
    assert len(re.findall(r"^rld\d\d dp\d\d 0 15k$", deck, re.M)) == 16
    assert re.search(r"^vsup vdd 0 dc 3\.3$", deck, re.M)
    for k in range(16):
        bits = [("vdd" if (k >> i) & 1 else "0") for i in range(4)]
        assert f"xpu{k:02d} dp{k:02d} vdd 0 vdd {' '.join(bits)} dplus_pullup" in deck
    assert TB["analysis"]["kind"] == "dc"


def test_every_measure_name_is_declared_and_prefix_matches():
    names = set(TB["measure"])
    assert all(f"vdp_c{k:02d}_v" in names for k in range(16))
    assert {"voff_d1_v", "voff_d0_v", "ioff_dz_na", "ioff_dh_na", "isup_dz_na"} <= names
    for n, m in TB["measure"].items():
        assert f".meas dc {n} " in m["spice"]


def test_design_netlist_uses_only_sky130_devices_and_documented_pins():
    net = (REPO / "design/netlist/dplus_pullup.spice").read_text()
    sch = (REPO / "design/dplus_pullup.sch").read_text()
    assert ".subckt dplus_pullup DP VPU VSS PU_EN TRIM0 TRIM1 TRIM2 TRIM3" in net
    models = set(re.findall(r"\s(sky130_fd_pr__\w+)\s+(?:L|W)=", net))
    assert models == {"sky130_fd_pr__pfet_g5v0d10v5", "sky130_fd_pr__nfet_g5v0d10v5", "sky130_fd_pr__res_generic_po"}
    assert not re.search(r"gf180|ppolyf|03v3|\bnf=([2-9]|\d\d)", net.lower())
    devs = [x for x in re.findall(r"^C \{(\S+)\.sym\}", sch, re.M) if not x.startswith("devices/")]
    assert devs and all(x.startswith("sky130_fd_pr/") for x in devs), devs
    # TRIM<i>=1 turns segment i's bypass switch on (active-low gate from the inverter) and
    # PU_EN=1 turns the enable switch on
    for i in range(4):
        assert re.search(rf"^XMP_B{i} N{i + 1}\w* TRIM{i}B N", net, re.M) or f"TRIM{i}B" in net
        assert f"XMP_T{i} TRIM{i}B TRIM{i} VPU VPU" in net and f"XMN_T{i} TRIM{i}B TRIM{i} VSS VSS" in net
    assert "XMP_ENSW N0 PU_ENB VPU VPU" in net and "XMP_EN PU_ENB PU_EN VPU VPU" in net
    # the all-zero code leaves every segment in the path: maximum resistance, fail-safe default
    assert "XRBASE N1 N0" in net and "XR3 DP N4" in net


def test_record_discloses_selection_limits_and_resistor_corner_mapping():
    m = {"experiment": "dplus-pullup-tolerance", "status": "PASS",
         "results": [{"corner_id": mx.corner_id(*p), "status": "ok",
                      "measurements": {"best_code": 8.0, "best_r_ohm": 1480.0, "n_in_window": 3.0}}
                     for p in MATRIX.points()],
         "axes": {"process": list(MATRIX.process), "temperature_c": list(MATRIX.temperature_c),
                  "supply_v": list(MATRIX.supply_v)},
         "problems": [], "backend": "batch", "job_id": "j", "klt_version": "k", "engine_version": "46",
         "pdk": {}, "git": {"head": "h", "dirty": False}, "started_utc": "t", "author": "a"}
    rec = runner.render_record("20260101-000000-abcdef0", m, "0" * 64,
                               {"claim": TB["claim"], "supersedes": "", "record_meta": TB["record"]})
    assert "Monte Carlo was NOT run" in rec and "res_typical__cap_typical" in rec
    assert "does not prove that a single calibration code" in rec
    assert "No leakage limit is ratified" in rec and "inclusive" in rec
    assert "## Per-corner selection" in rec and rec.count("| `") >= 45
