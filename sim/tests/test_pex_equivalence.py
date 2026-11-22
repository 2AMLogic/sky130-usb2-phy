"""The exact-pair schematic-leg equivalence gate shared by every leaf pex runner.

Why exact pairs (the regression these tests pin): the committed schematic reference
covers far more corners than a leaf pex bench requests (225 for the receivers and
the pull-up, 45 for the differential receiver) but a bench requests only two, so a
delta carrying the right *number* of rows with the reference value in each is not
evidence the requested bench ran -- rows lifted from unrequested corners would pass
a count-only check. The hermit probe behind these tests built exactly such an
envelope at `4bdccc4` (36 rows, passing status, reference value in every row, the
requested binding corner absent) and the count-only gate returned True. These tests
build the same shape from the committed DP reference against the shared gate and
require False. Issue #425 retired the last count-only gate -- the inline
`check_equivalence` sim/diff-receiver-pex had kept, which exited 0 on that very
shape -- so the same controls now run against the committed differential-receiver
reference too. The receiver envelopes use 7 measurements (the 8th, the
internal-node vref_v probe, is deliberately absent from the pex benches -- not
extraction-portable, klayout-tools#6990). Toolchain-free: committed JSON only, no
klt, no ngspice, nothing written.
"""

import json
import sys
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))

from harness import pex_equivalence  # noqa: E402

DP_PEX = SIM / "se-receiver-dp-pex"
PU_PEX = SIM / "dplus-pullup-pex"
DIFF_PEX = SIM / "diff-receiver-pex"
DP_REFERENCE = json.loads((SIM / "se-receiver-dp-thresholds/corners/"
                           "20261020-205102-ea63f5c/report.json").read_text())
PU_REFERENCE = json.loads((SIM / "dplus-pullup-tolerance/corners/"
                           "20261020-174658-ca4a45a/report.json").read_text())
DIFF_REFERENCE = json.loads((SIM / "diff-receiver-sensitivity/corners/"
                             "20261020-172719-ca4a45a/report.json").read_text())

# per bench: its committed reference, the binding corner it requests beside
# tt/3.300V/27C, its measurement count, and a corner of that reference it does
# NOT request -- lifting that corner's rows is what a count-only gate passed
BENCHES = {
    "se-receiver-dp-pex": (DP_REFERENCE, "ff_lh/3.000V/100C", 7, "ff_ll/3.000V/100C"),
    "dplus-pullup-pex": (PU_REFERENCE, "fs_hl/3.000V/100C", 26, "sf/3.000V/100C"),
    "diff-receiver-pex": (DIFF_REFERENCE, "sf/3.000V/100C", 18, "ff/3.000V/-40C"),
}


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


@pytest.mark.parametrize("bench", list(BENCHES))
def test_expected_pairs_are_the_requested_bench_not_the_reference_matrix(bench):
    # the receiver benches carry 7 of the committed bench's 8 measurements: the 8th
    # (vref_v) probes a DUT-internal node by name and is not extraction-portable
    # (klayout-tools#6990), so it is absent from the pex request by design
    reference, binding, n_meas, unrequested = BENCHES[bench]
    tb = json.loads((SIM / bench / "testbench/tb.json").read_text())
    pairs = pex_equivalence.expected_pairs(tb)
    assert len(pairs) == 2 * n_meas
    assert ("tt/3.300V/27C", tb["measurements"][0]["name"]) in pairs
    assert (binding, tb["measurements"][-1]["name"]) in pairs
    # the other corners of the committed reference are NOT requested -- and they do
    # exist there, so lifting their rows into a delta is possible
    assert (unrequested, tb["measurements"][0]["name"]) not in pairs
    assert unrequested in {c["corner_id"] for c in reference["corners"]}


@pytest.mark.parametrize("bench", list(BENCHES))
def test_reference_values_reproduce_equivalence(bench):
    """The positive control per bench: its own two requested corners lifted verbatim
    from the committed record pass -- 14, 52 and (on this gate since issue #425)
    36 rows."""
    reference, binding, n_meas, _ = BENCHES[bench]
    tb = json.loads((SIM / bench / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(reference, ["tt/3.300V/27C", binding], names)
    ok, rows = pex_equivalence.check_equivalence(env, tb, reference)
    assert ok, [r for r in rows if r["verdict"] != "ok"]
    assert len(rows) == 2 * n_meas and all(r["verdict"] == "ok" and r["rel_dev"] == 0 for r in rows)


@pytest.mark.parametrize("bench", list(BENCHES))
def test_a_row_set_with_the_binding_corner_missing_fails(bench):
    """The hermit probe's envelope, per bench: 2 corners x measurements rows, passing
    status, the reference value in every row -- but the requested binding corner
    replaced by an unrequested corner that also exists in the committed reference.
    A count-only gate passes this (sim/diff-receiver-pex's did, exiting 0, until
    issue #425); the exact-pair gate rejects it."""
    reference, _, n_meas, unrequested = BENCHES[bench]
    tb = json.loads((SIM / bench / "testbench/tb.json").read_text())
    names = [m["name"] for m in tb["measurements"]]
    env = envelope_from(reference, ["tt/3.300V/27C", unrequested], names)
    assert len(env["delta"]) == 2 * n_meas  # the only thing a count-only gate checks
    committed = pex_equivalence.committed_values(reference)
    assert all(r["schematic_value"] == committed[(r["corner_id"], r["spec_row"])]
               for r in env["delta"])
    ok, rows = pex_equivalence.check_equivalence(env, tb, reference)
    assert not ok
    verdicts = [r["verdict"] for r in rows if r["verdict"] != "ok"]
    assert sum("missing delta row" in v for v in verdicts) == n_meas
    assert sum("not a requested" in v for v in verdicts) == n_meas


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
