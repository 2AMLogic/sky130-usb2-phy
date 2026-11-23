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
DRIVER_SQ = json.loads((SIM / "driver-signal-quality/testbench/tb.json").read_text())


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


# ---- driver-signal-quality: the mapping matches the tb and the ratified numbers ----

def test_driver_sq_measurements_all_exist_with_equivalent_checks():
    limits = sl.measurement_limits("driver-signal-quality", DRIVER_SQ)
    assert limits, "driver-signal-quality must be mapped"
    for name in limits:
        assert name in DRIVER_SQ["measure"]
        assert name in DRIVER_SQ["checks"]


def test_driver_sq_limit_values_match_the_ratified_rows():
    limits = sl.measurement_limits("driver-signal-quality", DRIVER_SQ)
    # tr/tf scale raw seconds to ns, so the emitted bounds are the row numbers
    # divided by the scale (klt grades the raw value)
    tr = {"min": 4e-09, "max": 2e-08}
    tr_match = {"min": 0.9, "max": 1.1}
    vcross = {"min": 1.3, "max": 2.0}
    for n in ("trise_dp_ns", "tfall_dp_ns", "trise_dm_ns", "tfall_dm_ns"):
        assert limits[n]["row"] == "6-06" and limits[n]["limits"] == tr
    for n in ("trf_dp_ratio", "trf_dm_ratio", "trf_x1_ratio", "trf_x2_ratio"):
        assert limits[n]["row"] == "6-06" and limits[n]["limits"] == tr_match
    for n in ("vcross_rise_v", "vcross_fall_v"):
        assert limits[n]["row"] == "6-07" and limits[n]["limits"] == vcross


def test_driver_sq_engineering_only_measurements_carry_no_limits():
    # monotonic-edge slopes, single-crossing times and the OE transition pad
    # currents are engineering criteria, not ratified rows
    limits = sl.measurement_limits("driver-signal-quality", DRIVER_SQ)
    for n in ("slope_rise_dp_min_vns", "tx_first_ns", "oe_xb_dp_on_ma", "tpd_rise_dp_ns"):
        assert n not in limits


def test_unmapped_bench_leaves_the_request_untouched():
    request, mapping = limited_request(experiment="smoke-inverter")
    assert mapping == {}
    assert all("limits" not in m for m in request["measurements"])


def test_apply_writes_limits_and_units_into_the_request():
    # driver-static is all scale 1.0 (raw == display), so the row unit still
    # belongs beside the raw limits; under scale the unit is skipped (below)
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
    # display_limits keeps the row's own numbers in the unit `unit` names
    assert limits["voh_dp_v"]["display_limits"] == {"min": 2.8, "max": 3.6}


# ---- issue #424: the emitted unit must agree with the emitted numbers ----

def test_driver_sq_entry_carries_raw_limits_and_display_limits():
    # limits stays raw (what klt grades, pre-scale); display_limits is the
    # row's ratified numbers in the display unit the `unit` string names
    limits = sl.measurement_limits("driver-signal-quality", DRIVER_SQ)
    tr = limits["trise_dp_ns"]
    assert tr["limits"] == {"min": 4e-09, "max": 2e-08}
    assert tr["display_limits"] == {"min": 4.0, "max": 20.0}
    assert tr["unit"] == "ns" and tr["scale"] == 1e9


def test_apply_writes_raw_limits_but_no_display_unit_under_scale():
    # the graded request declares raw limits; a display-unit name beside them
    # would misstate the numbers by the scale factor (no raw-unit name is
    # derivable: tb.json measures and the built request carry none)
    request, mapping = limited_request(tb=DRIVER_SQ, experiment="driver-signal-quality")
    by_name = {m["name"]: m for m in request["measurements"]}
    for n in ("trise_dp_ns", "tfall_dp_ns", "trise_dm_ns", "tfall_dm_ns"):
        assert by_name[n]["limits"] == {"min": 4e-09, "max": 2e-08}
        assert "unit" not in by_name[n]
    # the same bench's scale-1 measurements still carry the row unit
    for n in ("vcross_rise_v", "vcross_fall_v"):
        assert by_name[n].get("unit") == "V"
    # ratios: the row carries no unit, so neither does the request
    for n in ("trf_dp_ratio", "trf_dm_ratio", "trf_x1_ratio", "trf_x2_ratio"):
        assert "unit" not in by_name[n]


def test_render_cross_states_display_limits_with_the_display_unit():
    # row 6-06 must read ">= 4 and <= 20 ns", never the raw 4e-09..2e-08
    # beside "ns" (the committed e260498 record read exactly that; records
    # are append-only, so the correction lands in the next record)
    mapping = sl.measurement_limits("driver-signal-quality", DRIVER_SQ)
    summary = {n: {"envelope": {"pass": 45, "fail": 0}, "harness": {"pass": 45, "fail": 0},
                   "disagree": 0} for n in mapping}
    lines = sl.render_cross(summary, mapping)
    row = next(l for l in lines if "`trise_dp_ns`" in l)
    assert ">= 4 and <= 20 ns" in row
    assert "4e-09" not in row and "2e-08" not in row
    # scale-1 rows render exactly as before
    vcross = next(l for l in lines if "`vcross_rise_v`" in l)
    assert ">= 1.3 and <= 2 V" in vcross


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


def test_cross_check_flags_unrecognised_envelope_status():
    # a third per-measurement status must fail closed, not fall through
    # uncounted while the record still reads PASS
    corners = [corner_envelope(("tt", 27, 3.3), {"voh_dp_v": 3.2})]
    corners[0]["measurements"][0]["status"] = "error"
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "ok",
                "measurements": {"voh_dp_v": 3.2}}]
    problems, summary = _cross(corners, results)
    assert any("voh_dp_v" in p and "error" in p for p in problems)
    assert summary["voh_dp_v"]["envelope"] == {"pass": 0, "fail": 0}


def test_cross_check_flags_unrecognised_status_without_harness_verdict():
    # fail closed regardless of the harness verdict: the measurement value is
    # absent, so har is None, and the status must still surface
    corners = [corner_envelope(("tt", 27, 3.3), {"voh_dp_v": 3.2})]
    corners[0]["measurements"][0]["status"] = "error"
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "ok",
                "measurements": {}}]
    problems, _ = _cross(corners, results)
    assert any("voh_dp_v" in p and "error" in p for p in problems)


def test_cross_check_flags_unrecognised_status_alongside_a_pass():
    # one errored limited measurement in a corner whose other limited
    # measurement passes: exactly one problem, the passing one still counted
    corners = [corner_envelope(("tt", 27, 3.3), {"voh_dp_v": 3.2, "vol_dp_v": 0.1})]
    corners[0]["measurements"][1]["status"] = "error"  # vol_dp_v
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "ok",
                "measurements": {"voh_dp_v": 3.2, "vol_dp_v": 0.1}}]
    problems, summary = _cross(corners, results)
    assert len(problems) == 1 and "vol_dp_v" in problems[0] and "error" in problems[0]
    assert summary["voh_dp_v"]["envelope"] == {"pass": 1, "fail": 0}
    assert summary["vol_dp_v"]["envelope"] == {"pass": 0, "fail": 0}


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
