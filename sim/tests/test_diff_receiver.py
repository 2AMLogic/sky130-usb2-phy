"""Toolchain-free tests for the differential-receiver experiment and the record metadata.

No klt, ngspice or PDK: reports are synthetic. These prove the *checks* reject bad
receivers (missing / non-finite measurements, wrong output polarity, out-of-bounds
thresholds) and that receiver records do not inherit the smoke disclaimer while
the smoke record prose stays unchanged. They say nothing about the circuit itself;
that is the recorded 45-corner run.
"""

import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from harness import evidence_lint as lint, matrix as mx, results as rs, runner

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parent
EXP = SIM / "diff-receiver-sensitivity"
TB = json.loads((EXP / "testbench/tb.json").read_text())
SMOKE_TB = json.loads((SIM / "smoke-inverter/testbench/tb.json").read_text())
MATRIX = mx.load()
CMS = {"0p80": 0.8, "1p65": 1.65, "2p50": 2.5}


def good_values(vdd):
    out = {}
    for tag in CMS:
        out[f"vth_cm{tag}_v"] = -0.02
        out[f"rxd_pos_min_cm{tag}_v"] = vdd
        out[f"rxd_neg_max_cm{tag}_v"] = 1e-9
        out[f"rxd_p200_cm{tag}_v"] = vdd
        out[f"rxd_m200_cm{tag}_v"] = 1e-9
        out[f"isup_ua_cm{tag}"] = -30e-6  # raw amps; the tb scale flips the sign convention
    return out


def report(tamper=None):
    corners = []
    for p, t, v in MATRIX.points():
        vals = good_values(v)
        corners.append({
            "corner_id": f"{p}/{v:.3f}V/{t:g}C", "process": p, "supply_v": {"vsup": v},
            "temperature_c": float(t), "status": "pass",
            "measurements": [{"name": n, "value": x * (-1.0 if n.startswith("isup") else 1.0), "status": "pass"}
                             for n, x in vals.items()],
            "artifacts": {"log": None}})
    rep = {"status": "pass", "corners": corners, "environment": {"remote": {"job_id": "j"}}}
    if tamper:
        tamper(rep)
    return rep


def meas(rep, idx, name):
    return next(m for m in rep["corners"][idx]["measurements"] if m["name"] == name)


def problems_of(tamper=None):
    return rs.evaluate(report(tamper), MATRIX.points(), TB)[1]


def test_all_135_pvt_cm_combinations_are_individually_named():
    names = set(TB["measure"])
    for tag in CMS:
        for stem in ("vth", "rxd_pos_min", "rxd_neg_max", "rxd_p200", "rxd_m200"):
            assert f"{stem}_cm{tag}_v" in names
        assert f"isup_ua_cm{tag}" in names
    assert all(n in TB["checks"] for n in names)
    # each of the three common-mode points is a distinct receiver instance driven at its own VCM
    deck = (EXP / "testbench" / TB["netlist"]).read_text()
    assert [float(x) for x in re.findall(r"^vcm\d+ cm\d+ 0 dc ([0-9.]+)", deck, re.M)] == list(CMS.values())
    assert len(rs.evaluate(report(), MATRIX.points(), TB)[0]) == 45


def test_good_grid_passes():
    assert problems_of() == []


@pytest.mark.parametrize("tamper,needle", [
    (lambda r: r["corners"][4]["measurements"].remove(meas(r, 4, "vth_cm1p65_v")), "vth_cm1p65_v"),
    (lambda r: meas(r, 4, "vth_cm0p80_v").update(value=float("nan")), "vth_cm0p80_v"),
    (lambda r: meas(r, 4, "rxd_pos_min_cm2p50_v").update(value=None), "rxd_pos_min_cm2p50_v"),
    (lambda r: meas(r, 7, "vth_cm2p50_v").update(value=0.25), "above max"),
    (lambda r: meas(r, 7, "vth_cm0p80_v").update(value=-0.21), "below min"),
    # wrong output polarity beyond the boundary: RXD stays low for VDIFF > +200 mV
    (lambda r: meas(r, 9, "rxd_pos_min_cm1p65_v").update(value=0.0), "rxd_pos_min_cm1p65_v"),
    # RXD stays high for VDIFF < -200 mV
    (lambda r: meas(r, 9, "rxd_neg_max_cm2p50_v").update(value=r["corners"][9]["supply_v"]["vsup"]), "rxd_neg_max_cm2p50_v"),
    # weak output level: 80 % of the rail is not a logic high for the 3.3 V domain
    (lambda r: meas(r, 9, "rxd_p200_cm0p80_v").update(value=0.8 * r["corners"][9]["supply_v"]["vsup"]), "rxd_p200_cm0p80_v"),
    (lambda r: r["corners"].pop(), "missing from report"),
    (lambda r: r["corners"][2].update(status="error"), "simulation status"),
])
def test_bad_receiver_never_passes(tamper, needle):
    probs = problems_of(tamper)
    assert any(needle in p for p in probs), probs


def test_failure_names_corner_and_common_mode_point():
    def tamper(r):
        meas(r, 0, "rxd_pos_min_cm2p50_v").update(value=0.1)
    probs = problems_of(tamper)
    assert any(p.startswith("tt_-40c_3.00v:") and "cm2p50" in p for p in probs), probs


def test_threshold_bound_is_the_ratified_200mv_without_relaxation():
    assert TB["checks"]["vth_cm0p80_v"] == {"min": -0.2, "max": 0.2}
    assert all(TB["checks"][f"vth_cm{t}_v"] == {"min": -0.2, "max": 0.2} for t in CMS)
    assert TB["analysis"]["args"] == "vd -0.4 0.4 0.001"


def test_design_netlist_uses_only_sky130_devices():
    net = (REPO / "design/netlist/differential_receiver.spice").read_text()
    sch = (REPO / "design/differential_receiver.sch").read_text()
    assert ".subckt differential_receiver VDD VSS DP DM RXD" in net
    models = set(re.findall(r"\s(\w*(?:fet|res)\w*)\s+(?:L|W)=", net))
    assert models and all(m.startswith("sky130_fd_pr__") for m in models), models
    assert "gf180" not in net.lower() and "03v3" not in net.replace("nfet_03v3_nvt", "")
    syms = re.findall(r"^C \{(\S+)\.sym\}", sch, re.M)
    devs = [x for x in syms if not x.startswith("devices/")]
    assert devs and all(x.startswith("sky130_fd_pr/") for x in devs), devs


# ---- record metadata ---------------------------------------------------------

def make_parts(tb, **kw):
    return {"claim": tb["claim"], "supersedes": "", "record_meta": tb.get("record") or {}, **kw}


def manifest(problems=(), status="FAIL"):
    pts = MATRIX.points()
    results = [{"corner_id": mx.corner_id(*p), "status": "ok",
                "measurements": {"vth_cm0p80_v": -0.02, "rxd_pos_min_cm0p80_v": p[2]}} for p in pts]
    return {"experiment": "diff-receiver-sensitivity", "status": status, "results": results,
            "axes": {"process": list(MATRIX.process), "temperature_c": list(MATRIX.temperature_c),
                     "supply_v": list(MATRIX.supply_v)},
            "problems": list(problems), "backend": "batch", "job_id": "j", "klt_version": "k",
            "engine_version": "46", "pdk": {}, "git": {"head": "h", "dirty": False},
            "started_utc": "t", "author": "a"}


def test_receiver_record_makes_no_smoke_claim_and_discloses_coverage():
    rec = runner.render_record("20260101-000000-abcdef0", manifest(), "0" * 64, make_parts(TB))
    assert "harness smoke deck" not in rec and "No design claim" not in rec
    assert "harness-only" not in rec
    assert "xschem export of design/differential_receiver.sch" in rec
    assert "Monte Carlo was NOT run" in rec
    assert "1 mV" in rec and "VDD/2" in rec and "DP = VCM + VDIFF/2" in rec
    assert "A FAIL record is evidence of failure" in rec


def test_receiver_record_lists_every_failure_not_just_five():
    probs = [f"tt_27c_3.30v: rxd_pos_min_cm{i}=0 below min 0.9" for i in range(12)]
    rec = runner.render_record("20260101-000000-abcdef0", manifest(probs), "0" * 64, make_parts(TB))
    for p in probs:
        assert f"- {p}" in rec
    assert "12 problem(s)" in rec


def test_smoke_record_prose_is_unchanged_by_default():
    rec = runner.render_record("20260101-000000-abcdef0", manifest(status="PASS"), "0" * 64,
                               {"claim": SMOKE_TB["claim"], "supersedes": ""})
    assert "schematic-level hand netlist (harness smoke deck); no layout, no PHY block" in rec
    assert "not applicable (deterministic operating-point corners, no Monte Carlo)" in rec
    assert "inside the harness-only bounds in tb.json" in rec
    assert rec.rstrip().endswith("No design claim: this record is harness evidence only.")
    assert "## Method" not in rec and "## Failures" not in rec
    # A committed smoke record has the same fixed prose (it was minted before this change).
    old = next((SIM / "smoke-inverter/records").glob("*.md")).read_text()
    for line in ("harness smoke deck", "No design claim: this record is harness evidence only."):
        assert line in old


SMOKE_RECORDS = sorted(p.stem for p in (SIM / "smoke-inverter/records").glob("*.md"))


def test_both_smoke_outcomes_are_committed():
    statuses = {json.loads((SIM / f"smoke-inverter/corners/{rid}/evidence.json").read_text())["status"]
                for rid in SMOKE_RECORDS}
    assert {"PASS", "FAIL"} <= statuses


@pytest.mark.parametrize("rid", SMOKE_RECORDS)
def test_committed_smoke_record_rerenders_byte_identical(rid):
    """Re-render each committed smoke record from its own evidence; the default prose must not drift."""
    cdir = SIM / "smoke-inverter/corners" / rid
    mbytes = (cdir / "evidence.json").read_bytes()
    tb = json.loads((cdir / "tb.json").read_text())
    assert "record" not in tb
    parts = {"claim": tb["claim"], "supersedes": "", "record_meta": tb.get("record") or {}}
    rec = runner.render_record(rid, json.loads(mbytes), runner.sha256_bytes(mbytes), parts)
    assert rec.encode() == (SIM / "smoke-inverter/records" / f"{rid}.md").read_bytes()


def test_smoke_testbench_declares_no_record_overrides():
    assert "record" not in SMOKE_TB and "include" not in SMOKE_TB


# ---- resistor-sets variant (#136): 225 points x 3 common modes = 675 combinations

RES = mx.load_by_id(mx.RESISTOR_SETS_ID)
VTB = rs.resolve_tb(TB, "resistor-sets")


def rreport(tamper=None):
    rep = report()
    rep["corners"] = []
    for p, t, v in RES.points():
        c = json.loads(json.dumps(report()["corners"][0]))
        c.update(corner_id=mx.corner_id(p, t, v), process=p, supply_v={"vsup": v}, temperature_c=float(t))
        for m in c["measurements"]:
            if m["name"].startswith(("rxd_pos", "rxd_p200")):
                m["value"] = v
        rep["corners"].append(c)
    if tamper:
        tamper(rep)
    return rep


def rproblems(tamper=None):
    return rs.evaluate(rreport(tamper), RES.points(), VTB)[1]


def test_variant_keeps_checks_stimulus_and_selects_225_matrix():
    assert rs.tb_matrix_id(TB, "resistor-sets") == mx.RESISTOR_SETS_ID and rs.tb_matrix_id(TB) == mx.LEGACY_ID
    for k in ("checks", "measure", "analysis", "netlist", "include", "timeout_s"):
        assert VTB[k] == TB[k]
    assert VTB["checks"]["vth_cm0p80_v"] == {"min": -0.2, "max": 0.2}
    assert "225" in VTB["claim"] and "675" in VTB["claim"] and "45-point" not in VTB["claim"]
    rec = VTB["record"]
    assert "5 resistor/capacitor parameter sets" in rec["statistical_convention"]
    assert "NOT run" in rec["statistical_convention"] and "not resistor-only" in rec["statistical_convention"]
    assert "5 process x 3" not in rec["statistical_convention"]
    assert rec["method"][:7] == TB["record"]["method"]
    assert any("675" in m for m in rec["method"])
    assert "layout parasitics" in rec["footer"] and "mismatch" in rec["footer"]


def test_good_225_grid_passes_all_675_combinations():
    results, probs = rs.evaluate(rreport(), RES.points(), VTB)
    assert probs == [] and len(results) == 225
    assert 225 * len(CMS) == 675


@pytest.mark.parametrize("tamper,needle", [
    (lambda r: r["corners"].pop(), "missing from report"),
    (lambda r: r["corners"].__setitem__(1, r["corners"][0]), "dup"),
    (lambda r: meas(r, 150, "vth_cm2p50_v").update(value=float("nan")), "vth_cm2p50_v"),
    (lambda r: r["corners"][200]["measurements"].remove(meas(r, 200, "rxd_m200_cm1p65_v")), "rxd_m200_cm1p65_v"),
    (lambda r: meas(r, 120, "vth_cm0p80_v").update(value=0.25), "above max"),
    (lambda r: meas(r, 120, "rxd_pos_min_cm1p65_v").update(value=0.0), "rxd_pos_min_cm1p65_v"),
    (lambda r: meas(r, 224, "rxd_neg_max_cm2p50_v").update(value=r["corners"][224]["supply_v"]["vsup"]), "rxd_neg_max_cm2p50_v"),
])
def test_variant_grid_rejects_bad_receivers(tamper, needle):
    probs = rproblems(tamper)
    assert any(needle in p for p in probs), probs


def test_legacy_45_report_is_not_a_225_variant_record():
    probs = rs.evaluate(report(), RES.points(), VTB)[1]
    assert any("missing from report" in p for p in probs)
