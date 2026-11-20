"""sim/harness/spec_limits.py: request limits generated from the ratified row table.

Issue #401 Part A: the grader credits a spec row only for a bound `klt sim`
itself checked, so the request must carry `measurements[].limits`. These tests
pin the generator to the two sources it must never drift from -- the ratified
row table (signoff/spec/analog-rows.json) and each bench's tb.json checks --
and pin the envelope-vs-harness cross-check's agreement semantics.
"""

import json
import copy
from pathlib import Path

import pytest

from conftest import corner_envelope
from harness import matrix as mx, spec_limits as sl

SIM = Path(__file__).resolve().parents[1]
ROWS = json.loads(sl.ROWS_FILE.read_text())
ROW_IDS = {r["id"] for r in ROWS["rows"]}
DRIVER_STATIC = json.loads((SIM / "driver-static/testbench/tb.json").read_text())


def limited_request(tb=None, experiment="driver-static"):
    from harness import matrix as mx, results as rs
    tb = tb or DRIVER_STATIC
    request = rs.build_request(tb, mx.load(), backend="batch")
    mapping = sl.apply(request, experiment, tb)
    return request, mapping


# ---- the row table and the mapping are bound together ----

def test_row_table_is_ratified_and_pins_the_spec():
    assert ROWS["status"] == "ratified"
    assert ROWS["source"]["file"] == "spec/usb2-phy.md"


def test_every_mapped_row_is_declared_in_the_ratified_table():
    rows = sl.load_rows()
    for bench, mapping in sl.BENCH_ROWS.items():
        for name, (row, role) in mapping.items():
            assert row in rows, f"{bench}/{name} maps to undeclared row {row}"
            assert row in sl.ROW_BOUNDS and role in sl.ROW_BOUNDS[row]


def test_row_bounds_cover_every_cited_row_of_the_six_benches():
    # The manifest's 5.analog citations (issue #401): rows 6-04..6-11 and 6-14.
    assert set(sl.ROW_BOUNDS) == {"6-04", "6-05", "6-06", "6-07", "6-09", "6-11", "6-14"}
    assert set(sl.ROW_BOUNDS) <= ROW_IDS


def test_load_rows_fails_closed(tmp_path):
    bad = tmp_path / "rows.json"
    bad.write_text(json.dumps({"status": "draft", "rows": [{"id": "6-04"}]}))
    with pytest.raises(sl.SpecLimitError):
        sl.load_rows(bad)
    bad.write_text("not json")
    with pytest.raises(sl.SpecLimitError):
        sl.load_rows(bad)


# ---- driver-static: the mapping matches the tb and the ratified numbers ----

def test_driver_static_measurements_all_exist_with_equivalent_checks():
    limits = sl.measurement_limits("driver-static", DRIVER_STATIC)
    assert limits, "driver-static must be mapped"
    for name in limits:
        assert name in DRIVER_STATIC["measure"]
        assert name in DRIVER_STATIC["checks"]


def test_driver_static_limit_values_match_the_ratified_rows():
    limits = sl.measurement_limits("driver-static", DRIVER_STATIC)
    voh = {"min": 2.8, "max": 3.6}
    vol = {"min": 0.0, "max": 0.3}
    rout = {"min": 28.0, "max": 44.0}
    for n in ("voh_dp_v", "voh15_dp_v", "voh_dm_v", "voh15_dm_v"):
        assert limits[n]["row"] == "6-04" and limits[n]["limits"] == voh
    for n in ("vol_dp_v", "vol_dm_v"):
        assert limits[n]["limits"] == vol
    for n in ("rout_high_dp_ohm", "rout_low_dp_ohm", "rout_high_dm_ohm", "rout_low_dm_ohm"):
        assert limits[n]["row"] == "6-05" and limits[n]["limits"] == rout


def test_unmapped_bench_leaves_the_request_untouched():
    request, mapping = limited_request(experiment="smoke-inverter")
    assert mapping == {}
    assert all("limits" not in m for m in request["measurements"])


def test_apply_writes_limits_and_units_into_the_request():
    request, mapping = limited_request()
    by_name = {m["name"]: m for m in request["measurements"]}
    assert set(by_name) >= set(mapping)
    for name, entry in mapping.items():
        assert by_name[name]["limits"] == entry["limits"]
        assert by_name[name].get("unit") == entry.get("unit")
    # engineering-only measurements (truth table, leakage) carry no limits
    for n in ("tt_dp_d00_e00_v", "leak_dp_3p6v_na", "isup_static_ua"):
        assert "limits" not in by_name[n]


def test_limits_are_emitted_in_raw_units_under_scale():
    tb = copy.deepcopy(DRIVER_STATIC)
    tb["measure"]["voh_dp_v"]["scale"] = 1000.0  # raw mV, harness checks V
    limits = sl.measurement_limits("driver-static", tb)
    assert limits["voh_dp_v"]["limits"] == {"min": 0.0028, "max": 0.0036}


# ---- fail-closed: drift between the mapping, the tb and the row table ----

def test_stale_measurement_name_is_refused():
    tb = copy.deepcopy(DRIVER_STATIC)
    tb["measure"].pop("voh_dp_v")
    with pytest.raises(sl.SpecLimitError, match="voh_dp_v"):
        sl.measurement_limits("driver-static", tb)


def test_undeclared_row_is_refused():
    tb = copy.deepcopy(DRIVER_STATIC)
    rows = {r["id"]: r for r in ROWS["rows"]}
    del rows["6-05"]
    with pytest.raises(sl.SpecLimitError, match="6-05"):
        sl.measurement_limits("driver-static", tb, rows)


def test_drifted_check_number_is_refused():
    tb = copy.deepcopy(DRIVER_STATIC)
    tb["checks"]["voh_dp_v"]["min"] = 2.9  # neither the spec nor the row moved
    with pytest.raises(sl.SpecLimitError, match="differs from the ratified row bound"):
        sl.measurement_limits("driver-static", tb)


def test_per_supply_check_is_refused():
    tb = copy.deepcopy(DRIVER_STATIC)
    tb["checks"]["voh_dp_v"] = {"min": 0.86, "per_supply": True}
    with pytest.raises(sl.SpecLimitError, match="no request equivalent"):
        sl.measurement_limits("driver-static", tb)


def test_missing_check_is_refused():
    tb = copy.deepcopy(DRIVER_STATIC)
    del tb["checks"]["rout_high_dp_ohm"]
    with pytest.raises(sl.SpecLimitError, match="no tb.json check"):
        sl.measurement_limits("driver-static", tb)


def test_strict_check_endpoints_match_inclusive_row_bounds():
    # A gt/lt check is the strict spelling of the row's inclusive endpoint.
    tb = copy.deepcopy(DRIVER_STATIC)
    tb["checks"]["voh_dp_v"] = {"gt": 2.8, "lt": 3.6}
    limits = sl.measurement_limits("driver-static", tb)
    assert limits["voh_dp_v"]["limits"] == {"min": 2.8, "max": 3.6}


# ---- the envelope-vs-harness cross-check ----

def _cross(report_corners, harness_results):
    report = {"corners": report_corners}
    tb = copy.deepcopy(DRIVER_STATIC)
    mapping = sl.measurement_limits("driver-static", tb)
    return sl.cross_check(report, harness_results, tb, mapping)


def test_cross_check_agrees_when_both_sides_pass():
    corners = [corner_envelope(("tt", 27, 3.3), {"voh_dp_v": 3.2})]
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "ok",
                "measurements": {"voh_dp_v": 3.2}}]
    problems, summary = _cross(corners, results)
    assert problems == []
    assert summary["voh_dp_v"] == {"envelope": {"pass": 1, "fail": 0},
                                   "harness": {"pass": 1, "fail": 0}, "disagree": 0}


def test_cross_check_agrees_when_both_sides_fail():
    corners = [corner_envelope(("tt", 27, 3.3), {"voh_dp_v": 2.5})]
    corners[0]["measurements"][0]["status"] = "fail"
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "failed",
                "measurements": {"voh_dp_v": 2.5}}]
    problems, summary = _cross(corners, results)
    assert problems == []
    assert summary["voh_dp_v"]["envelope"] == {"pass": 0, "fail": 1}
    assert summary["voh_dp_v"]["harness"] == {"pass": 0, "fail": 1}


def test_cross_check_flags_disagreement():
    # envelope says pass, harness re-check says outside: must surface as a problem
    corners = [corner_envelope(("tt", 27, 3.3), {"voh_dp_v": 2.5})]
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "ok",
                "measurements": {"voh_dp_v": 2.5}}]
    problems, summary = _cross(corners, results)
    assert len(problems) == 1 and "disagrees" in problems[0]
    assert summary["voh_dp_v"]["disagree"] == 1


def test_cross_check_flags_missing_envelope_verdict():
    corners = [corner_envelope(("tt", 27, 3.3), {"vol_dp_v": 0.1})]  # voh_dp_v absent
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "ok",
                "measurements": {"voh_dp_v": 3.2}}]
    problems, _ = _cross(corners, results)
    assert any("no limit verdict" in p for p in problems)


def test_render_cross_table_lists_every_limited_measurement():
    mapping = sl.measurement_limits("driver-static", DRIVER_STATIC)
    summary = {n: {"envelope": {"pass": 45, "fail": 0}, "harness": {"pass": 45, "fail": 0},
                   "disagree": 0} for n in mapping}
    lines = sl.render_cross(summary, mapping)
    assert len(lines) == len(mapping) + 2
    assert all(str(45) in line for line in lines[2:])


def test_record_states_both_verdicts():
    from conftest import RECORD_ID, render, render_manifest
    from harness import matrix as mx
    mapping = sl.measurement_limits("driver-static", DRIVER_STATIC)
    summary = {n: {"envelope": {"pass": 45, "fail": 0}, "harness": {"pass": 45, "fail": 0},
                   "disagree": 0} for n in mapping}
    manifest = render_manifest("driver-static", mx.load(), "PASS", {"voh_dp_v": 3.2})
    text = render(manifest, DRIVER_STATIC, spec_limits={"mapping": mapping, "summary": summary})
    assert "## Spec limits (envelope) and harness cross-check" in text
    assert "signoff/spec/analog-rows.json" in text
    assert "`voh_dp_v` | 6-04" in text
    assert text.count("| 45/0 | 45/0 | 0 |") == len(mapping)
    # and a record with no limits applied keeps the old shape
    plain = render(render_manifest("smoke-inverter", mx.load(), "PASS", {"vout_v": 1.0}),
                   json.loads((SIM / "smoke-inverter/testbench/tb.json").read_text()))
    assert "Spec limits" not in plain
