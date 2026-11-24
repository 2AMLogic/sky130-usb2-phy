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
DIFF_RX = json.loads((SIM / "diff-receiver-sensitivity/testbench/tb.json").read_text())
SE_RX_DP = json.loads((SIM / "se-receiver-dp-thresholds/testbench/tb.json").read_text())
SE_RX_DM = json.loads((SIM / "se-receiver-dm-thresholds/testbench/tb.json").read_text())
PULLUP = json.loads((SIM / "dplus-pullup-tolerance/testbench/tb.json").read_text())


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


# ---- diff-receiver-sensitivity: the mapping matches the tb and the ratified numbers ----

def test_diff_rx_measurements_all_exist_with_equivalent_checks():
    limits = sl.measurement_limits("diff-receiver-sensitivity", DIFF_RX)
    assert limits, "diff-receiver-sensitivity must be mapped"
    for name in limits:
        assert name in DIFF_RX["measure"]
        assert name in DIFF_RX["checks"]


def test_diff_rx_limit_values_match_the_ratified_rows():
    limits = sl.measurement_limits("diff-receiver-sensitivity", DIFF_RX)
    # vth_* has no scale, so the emitted bounds are the row numbers in V
    vth = {"min": -0.2, "max": 0.2}
    for n in ("vth_cm0p80_v", "vth_cm1p65_v", "vth_cm2p50_v"):
        assert limits[n]["row"] == "6-09" and limits[n]["limits"] == vth


def test_diff_rx_maps_every_common_mode_test_condition():
    # row 6-10's range is exercised as the three test conditions; a condition
    # dropping out of the mapping would silently lose its 6-09 evidence
    limits = sl.measurement_limits("diff-receiver-sensitivity", DIFF_RX)
    assert set(limits) == {"vth_cm0p80_v", "vth_cm1p65_v", "vth_cm2p50_v"}


def test_diff_rx_engineering_only_measurements_carry_no_limits():
    # the per-supply output-level probes (polarity, boundary, beyond-boundary)
    # and the bias-current sanity bound are engineering criteria, not rows
    limits = sl.measurement_limits("diff-receiver-sensitivity", DIFF_RX)
    for n in ("rxd_pos_min_cm0p80_v", "rxd_neg_max_cm1p65_v", "rxd_p200_cm2p50_v",
              "rxd_m200_cm0p80_v", "isup_ua_cm1p65"):
        assert n not in limits


# ---- se-receiver-dp/dm-thresholds: the mapping matches the tb and the ratified numbers ----

def test_se_rx_measurements_all_exist_with_equivalent_checks():
    for bench, tb in (("se-receiver-dp-thresholds", SE_RX_DP), ("se-receiver-dm-thresholds", SE_RX_DM)):
        limits = sl.measurement_limits(bench, tb)
        assert limits, f"{bench} must be mapped"
        for name in limits:
            assert name in tb["measure"]
            assert name in tb["checks"]


def test_se_rx_limit_values_match_the_ratified_row():
    # row 6-11: the switching threshold must sit inside (0.8, 2.0) V. The tb
    # check spells the endpoints strictly (gt/lt); the row's inclusive bounds
    # are the same numbers, emitted unscaled (vth_v carries no scale)
    vth = {"min": 0.8, "max": 2.0}
    for bench, tb in (("se-receiver-dp-thresholds", SE_RX_DP), ("se-receiver-dm-thresholds", SE_RX_DM)):
        limits = sl.measurement_limits(bench, tb)
        assert limits["vth_v"]["row"] == "6-11"
        assert limits["vth_v"]["limits"] == vth
        assert limits["vth_v"]["display_limits"] == vth
        assert limits["vth_v"]["unit"] == "V"


def test_se_rx_maps_only_the_first_crossing():
    # the last-crossing/single-crossing, output-level, VREF and supply-current
    # probes are engineering criteria; only the first rising crossing carries
    # the row (mapping vth_last_v would also need its `same_as` key honoured,
    # which no request limit can express)
    for bench, tb in (("se-receiver-dp-thresholds", SE_RX_DP), ("se-receiver-dm-thresholds", SE_RX_DM)):
        limits = sl.measurement_limits(bench, tb)
        assert set(limits) == {"vth_v"}
        for n in ("vth_last_v", "rxd_low_max_v", "rxd_high_min_v", "rxd_at_vil_v",
                  "rxd_at_vih_v", "vref_v", "isup_ua"):
            assert n not in limits


# ---- dplus-pullup-tolerance: the mapping matches the tb and the ratified numbers ----

def test_pullup_measurements_all_exist_with_equivalent_checks():
    limits = sl.measurement_limits("dplus-pullup-tolerance", PULLUP)
    assert limits, "dplus-pullup-tolerance must be mapped"
    for name in limits:
        assert name in PULLUP["measure"]
        assert name in PULLUP["checks"]


def test_pullup_limit_values_match_the_ratified_row():
    # row 6-14's trim-code existential, carried by the two extreme codes as
    # one-sided reachability bounds: the largest per-code resistance (code 0)
    # must reach at least the window floor, the smallest (code 15) at most its
    # ceiling. The expr measurements are unscaled ohm, so raw == display
    limits = sl.measurement_limits("dplus-pullup-tolerance", PULLUP)
    assert limits["r_c00_ohm"]["row"] == "6-14" and limits["r_c00_ohm"]["role"] == "r_eff_min"
    assert limits["r_c00_ohm"]["limits"] == {"min": 1425.0}
    assert limits["r_c15_ohm"]["role"] == "r_eff_max"
    assert limits["r_c15_ohm"]["limits"] == {"max": 1575.0}
    for n in ("r_c00_ohm", "r_c15_ohm"):
        assert limits[n]["display_limits"] == limits[n]["limits"]
        assert limits[n]["unit"] == "ohm" and limits[n]["scale"] == 1.0


def test_pullup_extreme_code_mapping_matches_the_monotone_ladder():
    # the recorded 2026-10-20 grid: r_c00 spans 1787-2026 ohm (above the
    # window) and r_c15 1031-1219 ohm (below it), so the mapped pairing is the
    # only one the ratified existential can hold -- the swapped pairing
    # (r_c00 <= 1575, r_c15 >= 1425) would fail all 45 corners
    limits = sl.measurement_limits("dplus-pullup-tolerance", PULLUP)
    assert limits["r_c00_ohm"]["limits"] == {"min": 1425.0}, "code 0 is the LARGEST resistance"
    assert limits["r_c15_ohm"]["limits"] == {"max": 1575.0}, "code 15 is the SMALLEST"


def test_pullup_expr_measurements_declare_exactly_one_form():
    # the derived request measurements are ngspice `expr` entries (klt
    # evaluates them after the analysis and grades their limits like any
    # .meas card); the raw code voltages stay .meas cards
    for n, m in PULLUP["measure"].items():
        assert ("spice" in m) != ("expr" in m), f"{n} must declare exactly one measurement form"
    assert PULLUP["measure"]["r_c00_ohm"]["expr"].startswith("vecmin(15000*(v(vdd)-v(dp00))")
    assert PULLUP["measure"]["r_c15_ohm"]["expr"].startswith("vecmin(15000*(v(vdd)-v(dp15))")


def test_pullup_engineering_only_measurements_carry_no_limits():
    # the disabled-state voltage/leakage probes, the raw code voltages and the
    # per-corner trim selections (best code, steps, count in window) are
    # harness-derived engineering data, not mapped rows
    limits = sl.measurement_limits("dplus-pullup-tolerance", PULLUP)
    for n in ("vdp_c00_v", "vdp_c15_v", "voff_d1_v", "voff_d0_v", "ioff_dz_na", "isup_dh_na"):
        assert n not in limits


def test_pullup_zero_qualifying_codes_fails_both_verdicts():
    # a corner whose ladder does not even reach the window floor: the envelope
    # limit verdict on r_c00_ohm is fail and the harness re-check of the same
    # bound agrees (the corner itself then dies in the trim analysis with
    # "no trim code inside", which is what turns spanning into compliance)
    tb = PULLUP
    mapping = sl.measurement_limits("dplus-pullup-tolerance", tb)
    r_short = 1300.0  # every code below 1425: nothing reaches the floor
    corners = [corner_envelope(("tt", 27, 3.3), {"r_c00_ohm": r_short, "r_c15_ohm": r_short - 400})]
    corners[0]["measurements"][0]["status"] = "fail"  # r_c00_ohm below its floor
    results = [{"corner_id": mx.corner_id("tt", 27, 3.3), "status": "failed",
                "measurements": {"r_c00_ohm": r_short, "r_c15_ohm": r_short - 400}}]
    problems, summary = sl.cross_check({"corners": corners}, results, tb, mapping)
    assert problems == []
    assert summary["r_c00_ohm"] == {"envelope": {"pass": 0, "fail": 1},
                                    "harness": {"pass": 0, "fail": 1}, "disagree": 0}
    assert summary["r_c15_ohm"]["harness"] == {"pass": 1, "fail": 0}


def test_pullup_roles_carry_one_sided_bounds_only():
    # the envelope can never claim "a code is inside" by itself: each mapped
    # role carries exactly ONE bound (a reachability endpoint), so two codes on
    # opposite sides of the window pass both envelope verdicts -- the
    # in-window claim is the harness trim analysis's alone (the straddling
    # corner failing via "no trim code inside" is pinned in test_dplus_pullup.py)
    assert sl.ROW_BOUNDS["6-14"]["r_eff_min"] == {"min": 1425.0, "unit": "ohm"}
    assert sl.ROW_BOUNDS["6-14"]["r_eff_max"] == {"max": 1575.0, "unit": "ohm"}
    ladder = [1580.0 + 200.0 * (14 - k) for k in range(15)] + [1420.0]
    assert ladder[0] >= 1425.0 and ladder[-1] <= 1575.0  # spanning: both bounds pass
    assert not any(1425.0 <= r <= 1575.0 for r in ladder), "ladder must straddle, not enter, the window"
    from conftest import v_of
    from harness import trim as trimmod
    derived, problems = trimmod.analyse([v_of(r, 3.3) for r in ladder], 3.3, PULLUP["trim"])
    assert derived["n_in_window"] == 0.0
    assert any("no trim code inside" in p for p in problems)


def test_pullup_request_carries_the_expr_measurements_with_limits():
    from harness import results as rs
    request = rs.build_request(PULLUP, mx.load(), backend="batch")
    mapping = sl.apply(request, "dplus-pullup-tolerance", PULLUP)
    by_name = {m["name"]: m for m in request["measurements"]}
    assert by_name["r_c00_ohm"]["expr"].startswith("vecmin(")
    assert by_name["r_c00_ohm"]["limits"] == {"min": 1425.0}
    assert by_name["r_c00_ohm"]["unit"] == "ohm"
    assert by_name["r_c15_ohm"]["limits"] == {"max": 1575.0}
    assert by_name["vdp_c00_v"]["spice"].startswith(".meas dc")
    assert "limits" not in by_name["vdp_c00_v"]


def test_se_rx_request_carries_the_threshold_limits():
    from harness import results as rs
    for bench, tb in (("se-receiver-dp-thresholds", SE_RX_DP), ("se-receiver-dm-thresholds", SE_RX_DM)):
        request = rs.build_request(tb, mx.load(), backend="batch")
        mapping = sl.apply(request, bench, tb)
        by_name = {m["name"]: m for m in request["measurements"]}
        assert by_name["vth_v"]["limits"] == {"min": 0.8, "max": 2.0}
        assert by_name["vth_v"]["unit"] == "V"
        assert "limits" not in by_name["vth_last_v"]


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
