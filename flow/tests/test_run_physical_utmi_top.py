"""Mocked tests for `flow/run_physical_utmi_top.py`. No klt, PDK or network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FLOW_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FLOW_DIR))
import run_flow  # noqa: E402
import run_physical_utmi_top as rp  # noqa: E402

CORNERS = json.loads((FLOW_DIR / "corners.json").read_text())["committed"]


def fake_runner(overrides=None, fail_at=None, calls=None):
    overrides = overrides or {}

    def run(args, cwd, env):
        stage = args[0]
        if calls is not None:
            calls.append(list(args))
        if fail_at == stage:
            raise run_flow.StageError(f"{stage} blew up")
        if stage in overrides:
            return overrides[stage]
        if stage == "place-and-route":
            return {"def_path": "/x/a.def", "gds_path": {"path": "flow/build/a.gds", "scope": "repo"},
                    "verilog_path": "/x/a.v"}
        if stage == "sta":
            return {"worst_slack_ns": 0.5, "total_negative_slack_ns": 0.0}
        if stage == "extract":
            return {"status": "ok"}
        if stage == "lvs":
            return {"status": "match", "error_count": 0,
                    "power_connectivity": {"status": "match", "unchecked_expected_pins": []}}
        if stage == "drc":
            return {"status": "clean", "violation_count": 0}
        raise AssertionError(stage)

    return run


@pytest.mark.parametrize("corner", CORNERS)
def test_templates_and_corner_substitution(corner):
    assert rp.static_gate_problems(corner) == []
    par = rp.resolve_par(corner, "/n.v")
    assert par["pdk"]["corner"] == corner
    assert par["hdl_toplevel"] == "usb_utmi_top"
    assert par["constraints"] == {"clock_port": "clk_144", "clock_period_ns": 6.944}
    assert par["pdk"]["sweep_corners"] == CORNERS
    assert rp.resolve_sta(corner, "d")["pdk"]["corner"] == corner


def test_pdn_and_lvs_gate_match_stub():
    stub = run_flow.load_json(rp.STUB_PAR)
    assert rp.resolve_par("tt_025C_1v80", "n")["power"] == stub["power"]
    lvs = rp.resolve_lvs("a", "b")
    assert lvs["options"]["power_connectivity"]["expected_nets"] == {"VPWR": "VPWR", "VGND": "VGND"}


def test_input_netlist_is_committed_top():
    assert rp.NETLIST.is_file()
    assert rp.NETLIST.name == "usb_utmi_top.v"


def test_dry_run_all_corners(capsys):
    assert rp.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    for c in CORNERS:
        assert f"== corner {c} ==" in out
    assert "design/netlist/usb_utmi_top.v" in out
    assert "TEMPLATE PROBLEMS" not in out and "nothing executed" in out
    assert "clk_utmi" in out


def test_unknown_corner_rejected():
    assert rp.main(["--dry-run", "--corners", "bogus"]) == 2


def test_happy_path_chains_and_retains(tmp_path):
    calls = []
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w", {}, fake_runner(calls=calls))
    assert [c[0] for c in calls] == ["place-and-route", "sta", "extract", "lvs", "drc"]
    work = tmp_path / "w"
    sta_req = json.loads((work / "request-sta.json").read_text())
    assert sta_req["def"] == "/x/a.def"
    assert sta_req["pdk"]["corner"] == "tt_025C_1v80"
    assert calls[2][1].endswith("a.gds") or calls[2][1].endswith("flow/build/a.gds")
    lvs_req = json.loads((work / "request-lvs.json").read_text())
    assert lvs_req["reference"]["netlist"] == "/x/a.v"
    assert lvs_req["layout"]["netlist"].endswith("usb_utmi_top.gate.spice")
    for stage in rp.STAGE_ORDER:
        assert (work / f"{stage}-report.json").is_file()
    assert s["gate_findings"] == [] and s["timing"]["verdict"] == "pass"
    assert s["claims"]["timing_closure"] is False
    assert s["timing"]["coverage"]["cdc_covered"] is False


def test_sentinel_timing_is_not_closure(tmp_path):
    r = fake_runner({"sta": {"worst_slack_ns": 1e39, "total_negative_slack_ns": 0.0}})
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w", {}, r)
    assert s["timing"]["verdict"] == "unconstrained"
    assert any("not a constrained pass" in f for f in s["gate_findings"])


def test_negative_slack_preserved(tmp_path):
    r = fake_runner({"sta": {"worst_slack_ns": -0.7, "total_negative_slack_ns": -3.0}})
    s = rp.run_corner("ss_n40C_1v60", tmp_path / "w", {}, r)
    assert s["timing"]["verdict"] == "fail" and s["timing"]["worst_slack_ns"] == -0.7
    assert s["stage_status"]["drc"] == "ran"  # later stages still ran


def test_stage_failure_keeps_partial_results(tmp_path):
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w", {}, fake_runner(fail_at="lvs"))
    assert s["failed_stage"] == "lvs"
    assert s["stage_status"] == {"place_and_route": "ran", "sta": "ran", "extract": "ran",
                                 "lvs": "failed", "drc": "not_run"}
    assert (tmp_path / "w" / "summary.json").is_file()
    assert (tmp_path / "w" / "place_and_route-report.json").is_file()


def test_missing_stage_output(tmp_path):
    r = fake_runner({"place-and-route": {"def_path": "/x/a.def", "verilog_path": "/x/a.v"}})
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w", {}, r)
    assert s["failed_stage"] == "place_and_route"
    assert "gds_path" in s["stage_error"]
    assert s["stage_status"]["sta"] == "not_run"


def test_power_and_lvs_gates(tmp_path):
    bad = {"status": "match", "error_count": 0}  # no power_connectivity -> unreported
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w", {}, fake_runner({"lvs": bad}))
    assert any("power connectivity" in f for f in s["gate_findings"])
    mism = {"status": "mismatch", "error_count": 2,
            "power_connectivity": {"status": "mismatch"}}
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w2", {}, fake_runner({"lvs": mism}))
    assert any("LVS is" in f for f in s["gate_findings"])


def test_drc_dirty(tmp_path):
    s = rp.run_corner("tt_025C_1v80", tmp_path / "w",  {},
                      fake_runner({"drc": {"status": "violations", "violation_count": 4}}))
    assert any("DRC" in f for f in s["gate_findings"])
