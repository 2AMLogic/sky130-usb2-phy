"""Toolchain-free tests for the single-ended receiver experiments (D+ and D-).

No klt, ngspice or PDK: reports are synthetic. These prove the checks reject bad
receivers (a threshold on or outside the 0.8 / 2.0 V endpoints, missing or
non-finite crossings, inverted or multi-crossing responses, weak output levels)
and that the ratified window is not relaxed. They say nothing about the circuit
itself; that is the recorded 45-corner run.
"""

import json
import re
from pathlib import Path

import pytest

from harness import matrix as mx, results as rs, runner

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parent
MATRIX = mx.load()
LINES = {"dp": ("DP", "RXDP"), "dm": ("DM", "RXDM")}


def tb_of(lbl):
    return json.loads((SIM / f"se-receiver-{lbl}-thresholds/testbench/tb.json").read_text())


def good_values(vdd):
    return {"vth_v": 1.38, "vth_last_v": 1.38, "rxd_low_max_v": 1e-9, "rxd_high_min_v": vdd,
            "rxd_at_vil_v": 1e-9, "rxd_at_vih_v": vdd, "vref_v": 0.425 * vdd, "isup_ua": 125e-6}


def report(tamper=None):
    corners = []
    for p, t, v in MATRIX.points():
        corners.append({
            "corner_id": f"{p}/{v:.3f}V/{t:g}C", "process": p, "supply_v": {"vsup": v},
            "temperature_c": float(t), "status": "pass",
            "measurements": [{"name": n, "value": x, "status": "pass"} for n, x in good_values(v).items()],
            "artifacts": {"log": None}})
    rep = {"status": "pass", "corners": corners, "environment": {"remote": {"job_id": "j"}}}
    if tamper:
        tamper(rep)
    return rep


def meas(rep, idx, name):
    return next(m for m in rep["corners"][idx]["measurements"] if m["name"] == name)


def set_both(idx, value):
    def tamper(r):
        meas(r, idx, "vth_v").update(value=value)
        meas(r, idx, "vth_last_v").update(value=value)
    return tamper


@pytest.mark.parametrize("lbl", LINES)
def test_good_grid_passes(lbl):
    results, problems = rs.evaluate(report(), MATRIX.points(), tb_of(lbl))
    assert problems == [] and len(results) == 45


@pytest.mark.parametrize("lbl", LINES)
@pytest.mark.parametrize("tamper,needle", [
    # endpoints are not "strictly inside" (0.8, 2.0)
    (set_both(3, 0.8), "not strictly above 0.8"),
    (set_both(3, 2.0), "not strictly below 2.0"),
    (set_both(3, 0.75), "not strictly above 0.8"),
    (set_both(3, 2.3), "not strictly below 2.0"),
    # missing / non-finite crossing (also: an inverted receiver has no rising crossing)
    (lambda r: r["corners"][5]["measurements"].remove(meas(r, 5, "vth_v")), "vth_v"),
    (lambda r: meas(r, 5, "vth_v").update(value=float("nan")), "vth_v"),
    (lambda r: meas(r, 5, "vth_last_v").update(value=None), "vth_last_v"),
    # multi-crossing: last crossing differs from the first rising one
    (lambda r: meas(r, 6, "vth_last_v").update(value=1.6), "differs from vth_v"),
    # inverted / wrong polarity: output high with the input low, low with the input high
    (lambda r: meas(r, 7, "rxd_low_max_v").update(value=r["corners"][7]["supply_v"]["vsup"]), "rxd_low_max_v"),
    (lambda r: meas(r, 7, "rxd_high_min_v").update(value=0.0), "rxd_high_min_v"),
    # weak levels at the boundary probes
    (lambda r: meas(r, 8, "rxd_at_vih_v").update(value=0.8 * r["corners"][8]["supply_v"]["vsup"]), "rxd_at_vih_v"),
    (lambda r: meas(r, 8, "rxd_at_vil_v").update(value=0.2 * r["corners"][8]["supply_v"]["vsup"]), "rxd_at_vil_v"),
    (lambda r: r["corners"].pop(), "missing from report"),
    (lambda r: r["corners"][2].update(status="error"), "simulation status"),
])
def test_bad_receiver_never_passes(lbl, tamper, needle):
    probs = rs.evaluate(report(tamper), MATRIX.points(), tb_of(lbl))[1]
    assert any(needle in p for p in probs), probs


def test_values_just_inside_the_window_pass():
    tb = tb_of("dp")
    for v in (0.8005, 1.9995):
        assert rs.evaluate(report(set_both(3, v)), MATRIX.points(), tb)[1] == []


def test_failure_names_corner_and_value():
    probs = rs.evaluate(report(set_both(0, 2.0)), MATRIX.points(), tb_of("dm"))[1]
    assert any(p.startswith("tt_-40c_3.00v: vth_v=2 ") for p in probs), probs


@pytest.mark.parametrize("lbl", LINES)
def test_ratified_window_is_strict_and_unrelaxed(lbl):
    tb = tb_of(lbl)
    assert tb["checks"]["vth_v"] == {"gt": 0.8, "lt": 2.0}
    assert tb["checks"]["vth_last_v"]["gt"] == 0.8 and tb["checks"]["vth_last_v"]["lt"] == 2.0
    assert tb["checks"]["vth_last_v"]["same_as"] == {"measure": "vth_v", "tol": 0.001}
    assert tb["analysis"]["args"] == "vin 0 3.0 0.001"
    m = tb["measure"]
    assert "FROM=0 TO=0.8" in m["rxd_low_max_v"]["spice"] and "FROM=2.0 TO=3.0" in m["rxd_high_min_v"]["spice"]
    assert "AT=0.8" in m["rxd_at_vil_v"]["spice"] and "AT=2.0" in m["rxd_at_vih_v"]["spice"]
    assert "RISE=1" in m["vth_v"]["spice"] and "CROSS=LAST" in m["vth_last_v"]["spice"]
    assert set(m) == set(tb["checks"])


@pytest.mark.parametrize("lbl", LINES)
def test_design_netlist_uses_only_sky130_devices_and_documented_pins(lbl):
    pin, out = LINES[lbl]
    cell = f"se_receiver_{lbl}"
    net = (REPO / f"design/netlist/{cell}.spice").read_text()
    sch = (REPO / f"design/{cell}.sch").read_text()
    assert f".subckt {cell} VDD VSS {pin} {out}" in net
    assert re.search(rf"^XMN_INA LOADDIODE {pin} TAIL", net, re.M)
    assert re.search(r"^XMN_INB AMPOUT VREF TAIL", net, re.M)
    models = set(re.findall(r"\s(\w*(?:fet|res)\w*)\s+(?:L|W)=", net))
    assert models and all(m.startswith("sky130_fd_pr__") for m in models), models
    assert "gf180" not in net.lower() and "ppolyf" not in net and "03v3" not in net
    devs = [x for x in re.findall(r"^C \{(\S+)\.sym\}", sch, re.M) if not x.startswith("devices/")]
    assert devs and all(x.startswith("sky130_fd_pr/") for x in devs), devs
    deck = (SIM / f"se-receiver-{lbl}-thresholds/testbench/se_rx_{lbl}_tb.spice").read_text()
    assert f"xrx vddr 0 in {out.lower()} {cell}" in deck


def test_record_discloses_method_and_no_monte_carlo():
    tb = tb_of("dp")
    m = {"experiment": "se-receiver-dp-thresholds", "status": "PASS",
         "results": [{"corner_id": mx.corner_id(*p), "status": "ok", "measurements": {"vth_v": 1.38}}
                     for p in MATRIX.points()],
         "axes": {"process": list(MATRIX.process), "temperature_c": list(MATRIX.temperature_c),
                  "supply_v": list(MATRIX.supply_v)},
         "problems": [], "backend": "batch", "job_id": "j", "klt_version": "k", "engine_version": "46",
         "pdk": {}, "git": {"head": "h", "dirty": False}, "started_utc": "t", "author": "a"}
    rec = runner.render_record("20260101-000000-abcdef0", m, "0" * 64,
                               {"claim": tb["claim"], "supersedes": "", "record_meta": tb["record"]})
    assert "Monte Carlo was NOT run" in rec and "harness smoke deck" not in rec
    assert "strictly inside (0.8 V, 2.0 V)" in rec and "VIH > 2.0 V, VIL < 0.8 V" in rec
    assert "xschem export of design/se_receiver_dp.sch" in rec
