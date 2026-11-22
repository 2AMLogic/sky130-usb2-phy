"""The exact-pair schematic-leg equivalence gate shared by the three leaf pex runners.

Why exact pairs (the regression these tests pin): the committed schematic reference
covers 225 corners but a leaf pex bench requests only two, so a delta carrying the
right *number* of rows with the reference value in each is not evidence the
requested bench ran -- rows lifted from unrequested corners would pass a count-only
check. The hermit probe behind these tests built exactly such an envelope at
`4bdccc4` (36 rows, passing status, reference value in every row, the requested
binding corner absent) and the count-only gate returned True. These tests build the
same shape from the committed DP reference against the new shared gate and require
False. The receiver envelopes use 7 measurements (the 8th, the internal-node
vref_v probe, is deliberately absent from the pex benches -- not
extraction-portable, klayout-tools#6990). Toolchain-free: committed JSON only, no klt, no ngspice, nothing written.
"""

import json
import sys
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))

from harness import pex_equivalence  # noqa: E402

DP_PEX = SIM / "se-receiver-dp-pex"
PU_PEX = SIM / "dplus-pullup-pex"
DP_REFERENCE = json.loads((SIM / "se-receiver-dp-thresholds/corners/"
                           "20261020-205102-ea63f5c/report.json").read_text())
PU_REFERENCE = json.loads((SIM / "dplus-pullup-tolerance/corners/"
                           "20261020-174658-ca4a45a/report.json").read_text())


def envelope_from(reference, corners, measurements, status="pass"):
    """A synthetic klt pex envelope whose schematic leg lifts (corner, measurement)
    values verbatim from the committed reference -- the hermit probe's shape."""
    values = {(c["corner_id"], m["name"]): m["value"]
              for c in reference["corners"] for m in c["measurements"]}
    delta = [{"corner_id": cid, "spec_row": name,
              "schematic_value": values[(cid, name)],
              "extracted_value": values[(cid, name)], "status": "pass"}
             for cid in corners for name in measurements]
    return {"status": status, "corner_count": len(corners), "delta": delta,
            "passed": len(delta), "failed": 0, "errored": 0}


def test_unit_corner_id_matches_the_report_spelling():
    assert pex_equivalence.unit_corner_id(
        {"process": "tt", "temperature_c": 27, "supply_v": {"vsup": 3.3}}) == "tt/3.300V/27C"
    assert pex_equivalence.unit_corner_id(
        {"process": "ff_lh", "temperature_c": 100, "supply_v": {"vsup": 3.0}}) == "ff_lh/3.000V/100C"
    assert pex_equivalence.unit_corner_id(
        {"process": "fs_hl", "temperature_c": 100, "supply_v": {"vsup": 3.0}}) == "fs_hl/3.000V/100C"


def test_expected_pairs_are_the_requested_bench_not_the_reference_matrix():
    # the receiver benches carry 7 of the committed bench's 8 measurements: the 8th
    # (vref_v) probes a DUT-internal node by name and is not extraction-portable
    # (klayout-tools#6990), so it is absent from the pex request by design
    for bench, n_meas, binding in ((DP_PEX, 7, "ff_lh/3.000V/100C"),
                                   (PU_PEX, 26, "fs_hl/3.000V/100C")):
        tb = json.loads((bench / "testbench/tb.json").read_text())
        pairs = pex_equivalence.expected_pairs(tb)
        assert len(pairs) == 2 * n_meas
        assert ("tt/3.300V/27C", tb["measurements"][0]["name"]) in pairs
        assert (binding, tb["measurements"][-1]["name"]) in pairs
        # the other 223 corners of the committed reference are NOT requested
        assert ("sf/3.000V/100C", tb["measurements"][0]["name"]) not in pairs


def test_reference_values_reproduce_equivalence():
    """The two requested corners lifted verbatim from the committed record pass."""
    tb = json.loads((DP_PEX / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(DP_REFERENCE, ["tt/3.300V/27C", "ff_lh/3.000V/100C"], names)
    ok, rows = pex_equivalence.check_equivalence(env, tb, DP_REFERENCE)
    assert ok, [r for r in rows if r["verdict"] != "ok"]
    assert len(rows) == 14 and all(r["verdict"] == "ok" and r["rel_dev"] == 0 for r in rows)


def test_a_row_set_with_the_binding_corner_missing_fails():
    """The hermit probe's envelope: 16 rows, passing status, the reference value in
    every row -- but the requested ff_lh corner replaced by an unrequested corner
    that also exists in the 225-point reference. A count-only gate passes this."""
    tb = json.loads((DP_PEX / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(DP_REFERENCE, ["tt/3.300V/27C", "ff_ll/3.000V/100C"], names)
    ok, rows = pex_equivalence.check_equivalence(env, tb, DP_REFERENCE)
    assert not ok
    verdicts = {r["verdict"] for r in rows if r["verdict"] != "ok"}
    assert any("missing delta row" in v for v in verdicts)
    assert any("not a requested" in v for v in verdicts)


def test_duplicate_row_fails():
    tb = json.loads((DP_PEX / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(DP_REFERENCE, ["tt/3.300V/27C", "ff_lh/3.000V/100C"], names)
    env["delta"].append(dict(env["delta"][0]))
    ok, rows = pex_equivalence.check_equivalence(env, tb, DP_REFERENCE)
    assert not ok and any(r["verdict"] == "duplicate delta row" for r in rows)


def test_non_finite_value_fails():
    tb = json.loads((DP_PEX / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(DP_REFERENCE, ["tt/3.300V/27C", "ff_lh/3.000V/100C"], names)
    env["delta"][3]["schematic_value"] = float("inf")
    env["delta"][4]["schematic_value"] = None
    ok, rows = pex_equivalence.check_equivalence(env, tb, DP_REFERENCE)
    assert not ok and sum(1 for r in rows if "non-finite" in r["verdict"]) == 2


def test_drifted_value_fails_within_tolerance_rules():
    tb = json.loads((DP_PEX / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(DP_REFERENCE, ["tt/3.300V/27C", "ff_lh/3.000V/100C"], names)
    env["delta"][0]["schematic_value"] *= 1 + 5e-4  # far above the 1e-6 gate
    ok, rows = pex_equivalence.check_equivalence(env, tb, DP_REFERENCE)
    assert not ok and any(r["verdict"] == "MISMATCH" for r in rows)


def test_envelope_status_must_be_pass():
    tb = json.loads((DP_PEX / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(DP_REFERENCE, ["tt/3.300V/27C", "ff_lh/3.000V/100C"], names, status="error")
    ok, rows = pex_equivalence.check_equivalence(env, tb, DP_REFERENCE)
    assert not ok and any("envelope status" in r["verdict"] for r in rows)
