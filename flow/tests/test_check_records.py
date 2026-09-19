"""Tests for `flow/check_records.py`.

Issue #11's acceptance criterion 5 requires the lint to *demonstrably* fail on
each of its three stated conditions, not merely claim it does. Each test below
builds a valid record, breaks exactly one thing, and asserts that the lint
fails with a finding tagged by the check that owns that condition:

  1. missing required field           -> `required-field`
  2. edited / deleted existing record -> `append-only`
  3. corner subset, no justification  -> `corner-matrix`

The remaining tests cover the rules the convention needs in order to mean
anything (freshness, the timing gate, DRC deck pinning) and the pure timing
classifier in `run_flow.py`.

Pure standard library plus pytest. No `klt`, no PDK, no network.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FLOW_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = FLOW_DIR.parent
sys.path.insert(0, str(FLOW_DIR))

import check_records  # noqa: E402
import run_flow  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def real_record_paths() -> list[Path]:
    return sorted((FLOW_DIR / "smoke-utmi_stub" / "records").glob("*.md"))


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A self-contained copy of flow/ that a test may corrupt freely.

    Seeded from the real committed evidence, so a test that breaks one field is
    breaking a record that would otherwise pass -- the fixture cannot silently
    drift into "vacuously failing for an unrelated reason".
    """
    dest = tmp_path / "flow"
    dest.mkdir()
    for name in (
        "corners.json",
        "drc-deck-coverage.json",
        "waivers.json",
        "request-synth-utmi_stub.json",
        "request-par-utmi_stub.json",
        "request-sta-utmi_stub.json",
        "request-extract-utmi_stub.json",
        "request-lvs-utmi_stub.json",
        "request-drc-utmi_stub.json",
    ):
        shutil.copy2(FLOW_DIR / name, dest / name)
    shutil.copytree(
        FLOW_DIR / "smoke-utmi_stub" / "records", dest / "smoke-utmi_stub" / "records"
    )
    return dest


def run_lint(sandbox: Path, *extra: str) -> tuple[int, check_records.Findings]:
    """Invoke the lint in-process so findings can be inspected by check name."""
    findings = check_records.Findings()
    argv = ["--flow-dir", str(sandbox), "--no-git", *extra]
    code = check_records.main(argv, findings=findings)
    return code, findings


def checks_in(findings: check_records.Findings) -> set[str]:
    return {check for check, _ in findings.items}


def standing_record(sandbox: Path) -> Path:
    """A record no other record supersedes.

    Freshness is only asked of records that still stand: a superseded record is
    frozen evidence of what the flow reported against an earlier revision of
    its own committed inputs, and is deliberately exempt. A freshness test must
    therefore corrupt a standing record, not just the oldest one on disk.
    """
    records = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))
    superseded = check_records.superseded_record_ids([read_meta(p) for p in records])
    standing = [p for p in records if p.stem not in superseded]
    assert standing, "fixture has no standing (un-superseded) record to corrupt"
    return standing[0]


def read_meta(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    start = text.index("<!-- record-meta") + len("<!-- record-meta")
    end = text.index("-->", start)
    return json.loads(text[start:end])


def write_meta(path: Path, meta: dict) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index("<!-- record-meta")
    end = text.index("-->", start) + len("-->")
    rebuilt = (
        text[:start] + "<!-- record-meta\n" + json.dumps(meta, indent=2) + "\n-->" + text[end:]
    )
    path.write_text(rebuilt, encoding="utf-8")


def rebuild_manifest(records_dir: Path) -> None:
    """Re-stamp the manifest so a test isolates the condition it is testing."""
    lines = ["# test manifest"]
    for record in sorted(records_dir.glob("*.md")):
        lines.append(f"{sha256_bytes(record.read_bytes())}  {record.name}")
    (records_dir / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Baseline: the committed evidence is clean
# --------------------------------------------------------------------------
def test_committed_records_exist():
    assert real_record_paths(), "no committed evidence records to lint"


def test_committed_records_pass_the_lint():
    code, findings = run_lint(FLOW_DIR)
    assert code == 0, f"the committed evidence does not lint clean: {findings.items}"


def test_sandbox_baseline_is_clean(sandbox: Path):
    code, findings = run_lint(sandbox)
    assert code == 0, f"the fixture is not clean before corruption: {findings.items}"


# --------------------------------------------------------------------------
# Condition 1 -- a record missing a required field
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "dotted",
    [
        "corner",
        "git_revision",
        "timing.worst_slack_ns",
        "timing.total_negative_slack_ns",
        "stages.drc.deck.content_hash",
        "stages.lvs.engine",
        "provenance.inputs",
        "tool_gaps",
    ],
)
def test_missing_required_field_fails(sandbox: Path, dotted: str):
    records = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))
    target = records[0]
    meta = read_meta(target)

    node = meta
    *parents, leaf = dotted.split(".")
    for part in parents:
        node = node[part]
    del node[leaf]

    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "required-field" in checks_in(findings), findings.items
    assert any(dotted in message for _, message in findings.items), findings.items


def test_null_in_a_non_nullable_required_field_fails(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["stages"]["drc"]["deck"]["known_coverage_gaps"] = None
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "required-field" in checks_in(findings), findings.items


# --------------------------------------------------------------------------
# Condition 2 -- an edited or deleted existing record
# --------------------------------------------------------------------------
def test_edited_record_fails(sandbox: Path):
    """Edit a record in place WITHOUT re-stamping the manifest."""
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    text = target.read_text(encoding="utf-8")
    target.write_text(text + "\n<!-- quietly appended after the fact -->\n", encoding="utf-8")

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "append-only" in checks_in(findings), findings.items
    assert any("edited in place" in message for _, message in findings.items), findings.items


def test_deleted_record_fails(sandbox: Path):
    records = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))
    records[0].unlink()

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "append-only" in checks_in(findings), findings.items
    assert any("is not on disk" in message for _, message in findings.items), findings.items


def test_unregistered_new_record_fails(sandbox: Path):
    """A record added without a manifest line is unverifiable, so it is rejected."""
    records_dir = sandbox / "smoke-utmi_stub" / "records"
    source = sorted(records_dir.glob("*.md"))[0]
    meta = read_meta(source)
    meta["record_id"] = "20990101-000000-deadbee-tt_025C_1v80"
    clone = records_dir / f"{meta['record_id']}.md"
    shutil.copy2(source, clone)
    write_meta(clone, meta)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "append-only" in checks_in(findings), findings.items
    assert any(
        "absent from MANIFEST.sha256" in message for _, message in findings.items
    ), findings.items


def test_manifest_removal_is_caught_by_the_git_layer(tmp_path: Path):
    """The manifest alone cannot stop an edit that also rewrites the manifest.

    This exercises the second, git-based layer: a record blob that exists in a
    base ref must be byte-identical in the working tree, whatever the manifest
    says. The test builds a throwaway git repo so it never touches this one.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    repo = tmp_path / "repo"
    (repo / "flow" / "smoke-utmi_stub" / "records").mkdir(parents=True)
    flow = repo / "flow"
    for name in ("corners.json", "drc-deck-coverage.json"):
        shutil.copy2(FLOW_DIR / name, flow / name)
    records_dir = flow / "smoke-utmi_stub" / "records"
    source = real_record_paths()[0]
    shutil.copy2(source, records_dir / source.name)
    rebuild_manifest(records_dir)

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "test")
    git("add", "-A")
    git("commit", "-qm", "seed")

    # Rewrite the record AND its manifest line -- the manifest layer is now happy.
    victim = records_dir / source.name
    victim.write_text(
        victim.read_text(encoding="utf-8") + "\n<!-- rewritten history -->\n",
        encoding="utf-8",
    )
    rebuild_manifest(records_dir)

    original_root = check_records.REPO_ROOT
    try:
        check_records.REPO_ROOT = repo
        findings = check_records.Findings()
        check_records.check_append_only_git(records_dir, "main", findings)
    finally:
        check_records.REPO_ROOT = original_root

    assert findings, "the git layer did not notice a rewritten record"
    assert any("differs from main" in message for _, message in findings.items), findings.items


# --------------------------------------------------------------------------
# Condition 3 -- a corner subset with no stated justification
# --------------------------------------------------------------------------
def test_corner_subset_without_justification_fails(sandbox: Path):
    records_dir = sandbox / "smoke-utmi_stub" / "records"
    committed = json.loads((sandbox / "corners.json").read_text())["committed"]
    subset = committed[:3]

    for record in sorted(records_dir.glob("*.md")):
        meta = read_meta(record)
        if meta["corner"] not in subset:
            record.unlink()
            continue
        meta["corner_matrix"]["run"] = subset
        meta["corner_matrix"]["subset_justification"] = None
        write_meta(record, meta)
    rebuild_manifest(records_dir)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "corner-matrix" in checks_in(findings), findings.items
    assert any(
        "subset_justification is empty" in message for _, message in findings.items
    ), findings.items


def test_corner_subset_with_justification_passes(sandbox: Path):
    records_dir = sandbox / "smoke-utmi_stub" / "records"
    committed = json.loads((sandbox / "corners.json").read_text())["committed"]
    subset = committed[:3]

    for record in sorted(records_dir.glob("*.md")):
        meta = read_meta(record)
        if meta["corner"] not in subset:
            record.unlink()
            continue
        meta["corner_matrix"]["run"] = subset
        meta["corner_matrix"]["subset_justification"] = (
            "Bisecting a P&R regression; only the three corners that reproduce it "
            "were rebuilt. Not signoff evidence."
        )
        write_meta(record, meta)
    rebuild_manifest(records_dir)

    code, findings = run_lint(sandbox)
    assert code == 0, findings.items


def test_corner_matrix_disagreeing_with_corners_json_fails(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["corner_matrix"]["committed"] = ["tt_025C_1v80"]
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "corner-matrix" in checks_in(findings), findings.items


# --------------------------------------------------------------------------
# Freshness
# --------------------------------------------------------------------------
def test_stale_input_hash_fails(sandbox: Path):
    target = standing_record(sandbox)
    meta = read_meta(target)
    assert meta["provenance"]["inputs"], "record carries no provenance inputs"
    meta["provenance"]["inputs"][0]["content_hash"] = "sha256:" + "0" * 64
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "freshness" in checks_in(findings), findings.items
    assert any("is stale" in message for _, message in findings.items), findings.items


def test_vanished_input_fails(sandbox: Path):
    target = standing_record(sandbox)
    meta = read_meta(target)
    meta["provenance"]["inputs"].append(
        {"path": "rtl/does_not_exist.v", "content_hash": "sha256:" + "1" * 64}
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "freshness" in checks_in(findings), findings.items


def test_superseded_record_is_exempt_from_freshness(sandbox: Path):
    """A frozen record is not retro-failed when a committed input changes.

    Adding the `power` block to `request-par-utmi_stub.json` (issue #59)
    changed a file every prior record cites. Those records are append-only
    evidence of what the flow reported *before* that change, so freshness must
    skip them once a newer record for the same corner supersedes them.
    """
    records = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))
    metas = [read_meta(p) for p in records]
    superseded = check_records.superseded_record_ids(metas)
    assert superseded, "fixture has no superseded record to exercise the exemption"

    target = next(p for p in records if p.stem in superseded)
    meta = read_meta(target)
    assert meta["provenance"]["inputs"], "record carries no provenance inputs"
    meta["provenance"]["inputs"][0]["content_hash"] = "sha256:" + "0" * 64
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 0, findings.items


# --------------------------------------------------------------------------
# The power/ground half of LVS (issue #59)
# --------------------------------------------------------------------------
def pdn_record(sandbox: Path) -> Path:
    """A standing record whose place-and-route run generated a real PDN."""
    records = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))
    superseded = check_records.superseded_record_ids([read_meta(p) for p in records])
    for path in records:
        if path.stem in superseded:
            continue
        meta = read_meta(path)
        if (meta.get("stages", {}).get("place_and_route", {}).get("power") or {}).get("pdn"):
            return path
    raise AssertionError("fixture has no standing record that reports a generated PDN")


def test_power_connectivity_mismatch_fails(sandbox: Path):
    target = pdn_record(sandbox)
    meta = read_meta(target)
    meta["stages"]["lvs"]["power_connectivity"].update(
        {"status": "mismatch", "finding_count": 3}
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "power-connectivity" in checks_in(findings), findings.items


def test_pdn_record_without_power_verdict_fails(sandbox: Path):
    """A signal-only LVS `match` may never stand in for a power verdict."""
    target = pdn_record(sandbox)
    meta = read_meta(target)
    del meta["stages"]["lvs"]["power_connectivity"]
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "power-connectivity" in checks_in(findings), findings.items


def test_unverified_power_connectivity_must_carry_a_note(sandbox: Path):
    target = pdn_record(sandbox)
    meta = read_meta(target)
    meta["stages"]["lvs"]["power_connectivity"].update(
        {"status": "unreported", "note": "   "}
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "power-connectivity" in checks_in(findings), findings.items


def test_standing_record_missing_power_echo_fails(sandbox: Path):
    """A standing record with no `power` echo at all must not escape the gate.

    `stages.place_and_route.power.pdn` is deliberately absent from
    `REQUIRED_FIELDS` so records that predate the `power` block are not
    retro-failed (issue #59's follow-up, issue #67). But that exemption must
    be scoped to records some other record `supersedes` -- a *standing*
    record that simply omits the echo cannot say whether it generated a PDN,
    and must fail rather than take the same silent-skip path a genuine
    pre-`power`-block vintage record takes.
    """
    target = pdn_record(sandbox)
    meta = read_meta(target)
    del meta["stages"]["place_and_route"]["power"]
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "power-connectivity" in checks_in(findings), findings.items


def test_superseded_record_missing_power_echo_stays_exempt(sandbox: Path):
    """The vintage exemption is real: a superseded record may still lack `power`.

    This repo's own committed evidence already has this shape -- records
    minted before `request-par-utmi_stub.json` grew its `power` block, later
    superseded by a record that carries one. They are frozen, append-only
    evidence and must not be retro-failed just because a *later* record's
    schema grew a field they never had.
    """
    records = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))
    metas = {p.stem: read_meta(p) for p in records}
    superseded_ids = check_records.superseded_record_ids(list(metas.values()))
    target = next(
        (p for p in records if p.stem in superseded_ids
         and "power" not in metas[p.stem].get("stages", {}).get("place_and_route", {})),
        None,
    )
    assert target is not None, (
        "fixture has no superseded record that already lacks `power` -- "
        "this test needs one to demonstrate the exemption without fabricating it"
    )

    code, findings = run_lint(sandbox)
    assert code == 0, findings.items
    assert "power-connectivity" not in checks_in(findings), findings.items


def test_par_request_must_declare_a_power_block(sandbox: Path):
    """Without `power`, `klt place-and-route` emits no PDN at all (issue #59)."""
    request = sandbox / "request-par-utmi_stub.json"
    doc = json.loads(request.read_text(encoding="utf-8"))
    del doc["power"]
    request.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "request" in checks_in(findings), findings.items
    assert any(
        "power.straps" in message for _, message in findings.items
    ), findings.items


def test_lvs_request_must_declare_expected_supply_nets(sandbox: Path):
    """Without `expected_nets` the power check is only self-consistency.

    Every instance agreeing on the *wrong* net passes a relative check --
    which is how the pre-#59 evidence corresponded `VGND` to `TXREADY` and
    still reported `match`.
    """
    request = sandbox / "request-lvs-utmi_stub.json"
    doc = json.loads(request.read_text(encoding="utf-8"))
    del doc["options"]["power_connectivity"]["expected_nets"]
    request.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "request" in checks_in(findings), findings.items
    assert any(
        "options.power_connectivity.expected_nets" in message
        for _, message in findings.items
    ), findings.items


def test_unresolved_expected_power_pin_fails(sandbox: Path):
    """A declared pin the check never resolved is not a clean verdict.

    `klt lvs` emits no finding for it, so without gating on
    `unchecked_expected_pins` it reads exactly like a pin that was checked and
    found correct (klayout-tools#1978).
    """
    target = pdn_record(sandbox)
    meta = read_meta(target)
    meta["stages"]["lvs"]["power_connectivity"]["unchecked_expected_pins"] = ["VPWR"]
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "power-connectivity" in checks_in(findings), findings.items


# --------------------------------------------------------------------------
# The timing gate
# --------------------------------------------------------------------------
def test_negative_wns_without_waiver_fails(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["timing"].update(
        {
            "worst_slack_ns": -0.42,
            "total_negative_slack_ns": -7.9,
            "verdict": "fail",
            "waiver": None,
            "note": "Negative setup WNS at this corner and no waiver.",
        }
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "timing-gate" in checks_in(findings), findings.items


def test_negative_wns_with_a_written_waiver_passes(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["timing"].update(
        {
            "worst_slack_ns": -0.42,
            "total_negative_slack_ns": -7.9,
            "verdict": "waived",
            "waiver": {
                "reason": "Known -0.42 ns path through an unbudgeted IO port; "
                "tracked separately and not on the FS datapath.",
                "author": "test",
                "date": "2026-09-15",
            },
            "note": "Negative setup WNS waived, see waiver.",
        }
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 0, findings.items


def test_waiver_without_a_reason_fails(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["timing"].update(
        {
            "worst_slack_ns": -0.42,
            "total_negative_slack_ns": -7.9,
            "verdict": "waived",
            "waiver": {"reason": "   ", "author": "test", "date": "2026-09-15"},
            "note": "waived",
        }
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "timing-gate" in checks_in(findings), findings.items


def test_calling_the_unconstrained_sentinel_a_pass_fails(sandbox: Path):
    """The trap this gate exists for: 1e+39 is positive, and is not a margin."""
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    assert check_records.is_sentinel(meta["timing"]["worst_slack_ns"])
    meta["timing"]["verdict"] = "pass"
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "timing-gate" in checks_in(findings), findings.items
    assert any(
        "has not closed timing" in message or "false claim" in message
        for _, message in findings.items
    ), findings.items


def test_unconstrained_verdict_requires_a_note(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["timing"]["note"] = "   "
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "timing-gate" in checks_in(findings), findings.items


# --------------------------------------------------------------------------
# DRC deck pinning
# --------------------------------------------------------------------------
def test_deck_hash_drift_fails(sandbox: Path):
    """A deck upgrade invalidates the committed gap enumeration, loudly."""
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["stages"]["drc"]["deck"]["content_hash"] = "sha256:" + "f" * 64
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "drc-deck" in checks_in(findings), findings.items


def test_dropping_a_coverage_gap_from_a_record_fails(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["stages"]["drc"]["deck"]["known_coverage_gaps"] = meta["stages"]["drc"]["deck"][
        "known_coverage_gaps"
    ][:2]
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "drc-deck" in checks_in(findings), findings.items
    assert any("omits gap" in message for _, message in findings.items), findings.items


def test_clean_verdict_with_violations_fails(sandbox: Path):
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["stages"]["drc"]["violation_count"] = 3
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "drc-deck" in checks_in(findings), findings.items


# --------------------------------------------------------------------------
# Committed request documents
# --------------------------------------------------------------------------
def test_malformed_request_document_fails(sandbox: Path):
    (sandbox / "request-drc-utmi_stub.json").write_text("{not json", encoding="utf-8")
    code, findings = run_lint(sandbox)
    assert code == 1
    assert "request" in checks_in(findings), findings.items


def test_request_missing_a_required_field_fails(sandbox: Path):
    path = sandbox / "request-par-utmi_stub.json"
    doc = json.loads(path.read_text())
    del doc["seed"]
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "request" in checks_in(findings), findings.items


def test_request_naming_an_uncommitted_corner_fails(sandbox: Path):
    path = sandbox / "request-sta-utmi_stub.json"
    doc = json.loads(path.read_text())
    doc["pdk"]["corner"] = "ss_n40C_1v28"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "request" in checks_in(findings), findings.items


def test_unvalidated_stray_request_file_fails(sandbox: Path):
    (sandbox / "request-mystery-stage.json").write_text("{}", encoding="utf-8")
    code, findings = run_lint(sandbox)
    assert code == 1
    assert "request" in checks_in(findings), findings.items


# --------------------------------------------------------------------------
# The pure timing classifier in run_flow.py
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "wns,tns,waiver,expected",
    [
        (1.5, 0.0, None, "pass"),
        (0.0, 0.0, None, "pass"),
        (-0.001, -0.001, None, "fail"),
        (-2.0, -40.0, None, "fail"),
        (-2.0, -40.0, {"reason": "known", "author": "a", "date": "d"}, "waived"),
        (1e39, 0.0, None, "unconstrained"),
        (1e39, 0.0, {"reason": "nope", "author": "a", "date": "d"}, "unconstrained"),
        (None, None, None, "fail"),
    ],
)
def test_evaluate_timing(wns, tns, waiver, expected):
    verdict, note = run_flow.evaluate_timing(wns, tns, waiver)
    assert verdict == expected
    assert note.strip()


def test_sentinel_detection_boundaries():
    assert check_records.is_sentinel(1e39)
    assert check_records.is_sentinel(-1e39)
    assert not check_records.is_sentinel(1e29)
    assert not check_records.is_sentinel(0)
    assert not check_records.is_sentinel(-3.2)
    assert not check_records.is_sentinel("1e39")


def test_a_waiver_cannot_launder_the_unconstrained_sentinel():
    """No waiver turns 'never measured' into 'measured and acceptable'."""
    verdict, _ = run_flow.evaluate_timing(
        1e39, 0.0, {"reason": "please pass", "author": "a", "date": "d"}
    )
    assert verdict == "unconstrained"


# --------------------------------------------------------------------------
# Record shape invariants that are easy to regress
# --------------------------------------------------------------------------
def test_every_committed_record_declares_it_anchors_no_design_claim():
    for record in real_record_paths():
        meta = read_meta(record)
        assert meta["design"]["anchors_design_claim"] is False, record.name


def test_every_committed_record_lists_the_upstream_tool_gaps():
    for record in real_record_paths():
        meta = read_meta(record)
        assert meta["tool_gaps"], record.name
        assert all(url.startswith("https://") for url in meta["tool_gaps"]), record.name


def test_one_record_per_committed_corner():
    committed = json.loads((FLOW_DIR / "corners.json").read_text())["committed"]
    corners = {read_meta(r)["corner"] for r in real_record_paths()}
    assert set(committed) <= corners, f"no record for {set(committed) - corners}"


def test_record_ids_are_unique():
    ids = [read_meta(r)["record_id"] for r in real_record_paths()]
    assert len(ids) == len(set(ids))


def test_record_meta_round_trips_as_json():
    for record in real_record_paths():
        meta = read_meta(record)
        assert json.loads(json.dumps(meta)) == copy.deepcopy(meta)


# --------------------------------------------------------------------------
# Issue #66: the supply-to-signal correspondence artifact must stay disclosed
# --------------------------------------------------------------------------
SUPPLY_NETS = {"VGND", "VPWR", "VPB", "VNB"}


def supply_to_signal_pairings(lvs_report: Path) -> list[dict]:
    """Rows where the layout's supply net was corresponded to a signal net."""
    correspondence = json.loads(lvs_report.read_text())["net_correspondence"]
    return [
        row
        for row in correspondence
        if row.get("layout") in SUPPLY_NETS
        and row.get("reference")
        and row["reference"] not in SUPPLY_NETS
    ]


def test_committed_lvs_reports_still_pair_a_supply_net_to_a_signal_net():
    """The artifact #66 documents is real and present, not a historical note.

    This is the premise the disclosure rests on. If `klt` ever stops emitting
    the pairing, this test fails and the README/per-record prose asserting it
    in the present tense must be revisited -- a disclosure that has silently
    become false is the exact failure mode #66 was filed about.
    """
    reports = sorted(
        (FLOW_DIR / "smoke-utmi_stub" / "artifacts").glob("*/lvs-report.json")
    )
    assert reports, "no committed lvs-report.json artifacts found"
    for report in reports:
        pairings = supply_to_signal_pairings(report)
        assert pairings, f"{report.parent.name} no longer carries the pairing"
        # And the compare still calls the overall result a match anyway.
        assert json.loads(report.read_text())["status"] == "match", report.parent.name


def test_rendered_power_section_discloses_the_correspondence_artifact():
    """`render_record()` must disclose the artifact in the power section.

    The power verdict is only trustworthy to a reader who knows not to read
    `net_correspondence` as a power statement, so every record that carries a
    `power_connectivity` verdict must say so in the same breath.
    """
    rendered = 0
    for record in real_record_paths():
        meta = read_meta(record)
        if "power_connectivity" not in (meta.get("stages", {}).get("lvs") or {}):
            continue  # predates the verdict entirely; nothing to disclose beside
        body = run_flow.render_record(meta)
        _, _, power_section = body.partition("### Power/ground connectivity")
        assert power_section, record.name
        assert "net_correspondence" in power_section, record.name
        assert "2136" in power_section, record.name
        rendered += 1
    assert rendered, "no committed record exercised the power-section rendering"
