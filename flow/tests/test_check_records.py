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
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
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
    target = sorted((sandbox / "smoke-utmi_stub" / "records").glob("*.md"))[0]
    meta = read_meta(target)
    meta["provenance"]["inputs"].append(
        {"path": "rtl/does_not_exist.v", "content_hash": "sha256:" + "1" * 64}
    )
    write_meta(target, meta)
    rebuild_manifest(target.parent)

    code, findings = run_lint(sandbox)
    assert code == 1
    assert "freshness" in checks_in(findings), findings.items


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
