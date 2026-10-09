"""Lint tests in temporary git fixtures (no klt/PDK; nothing is submitted)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from harness import evidence_lint as lint

SIM = Path(__file__).resolve().parents[1]
EXP = SIM / "smoke-inverter"
PASS_RID = next(
    p.stem for p in sorted((EXP / "records").glob("*.md")) if "- **Status**: PASS" in p.read_text()
)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A git repo whose base commit holds the committed smoke experiment."""
    r = tmp_path / "repo"
    (r / "sim").mkdir(parents=True)
    shutil.copy(SIM / "corners.json", r / "sim/corners.json")
    shutil.copytree(EXP, r / "sim/smoke-inverter", ignore=shutil.ignore_patterns("__pycache__"))
    git(r, "init", "-q", "-b", "main")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    git(r, "branch", "base")
    return r


def problems(repo, append_only=True):
    out = lint.lint_all(repo / "sim")
    if append_only:
        out += lint.check_append_only(repo, "base")
    return out


def test_committed_records_pass_the_lint():
    assert lint.lint_all(SIM) == []


def test_clean_tree_and_new_record_are_accepted(repo):
    assert problems(repo) == []
    # Appending a rerun: a new record id; prior evidence stays byte-identical.
    new = "20261010-000000-abcdef0"
    e = repo / "sim/smoke-inverter"
    shutil.copy(e / f"netlist-snapshots/{PASS_RID}.spice", e / f"netlist-snapshots/{new}.spice")
    shutil.copytree(e / f"corners/{PASS_RID}", e / f"corners/{new}")
    rec = (e / f"records/{PASS_RID}.md").read_text().replace(PASS_RID, new)
    m = json.loads((e / f"corners/{new}/evidence.json").read_text())
    m["record_id"] = new
    mp = e / f"corners/{new}/evidence.json"
    mp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    import re
    rec = re.sub(r"evidence\.json sha256 `[0-9a-f]{64}`", f"evidence.json sha256 `{lint.sha256_file(mp)}`", rec)
    (e / f"records/{new}.md").write_text(rec)
    assert problems(repo) == []


def test_edited_record_fails_append_only(repo):
    p = repo / f"sim/smoke-inverter/records/{PASS_RID}.md"
    p.write_text(p.read_text() + "\nedited\n")
    assert any("append-only" in x and "modified" in x for x in problems(repo))


@pytest.mark.parametrize("rel", [
    f"netlist-snapshots/{PASS_RID}.spice",
    f"corners/{PASS_RID}/ss_-40c_3.60v.log",
    f"corners/{PASS_RID}/report.json",
])
def test_edited_or_deleted_evidence_fails(repo, rel):
    p = repo / "sim/smoke-inverter" / rel
    p.write_bytes(p.read_bytes() + b"x")
    assert any("append-only" in x for x in problems(repo))
    git(repo, "checkout", "--", str(p))
    p.unlink()
    assert any("append-only" in x and "deleted" in x for x in problems(repo))


def test_rename_fails(repo):
    e = repo / "sim/smoke-inverter"
    (e / f"corners/{PASS_RID}/ss_-40c_3.60v.log").rename(e / f"corners/{PASS_RID}/renamed.log")
    git(repo, "add", "-A")
    assert any("append-only" in x for x in problems(repo))


def test_unavailable_base_history_fails(repo):
    assert any("not available" in x for x in lint.check_append_only(repo, "origin/nope"))
    assert any("no base ref" in x for x in lint.check_append_only(repo, ""))


def test_missing_referenced_evidence_fails(repo):
    (repo / f"sim/smoke-inverter/corners/{PASS_RID}/tt_27c_3.30v.log").unlink()
    assert any("missing" in x for x in problems(repo, append_only=False))


def test_hash_mismatch_fails(repo):
    p = repo / f"sim/smoke-inverter/corners/{PASS_RID}/tt_27c_3.30v.log"
    p.write_text("tampered\n")
    assert any("sha256 mismatch" in x for x in problems(repo, append_only=False))


def test_pass_record_with_dropped_corner_fails(repo):
    """Even a self-consistent rewrite (hashes fixed up) cannot claim 45 with 44."""
    cdir = repo / f"sim/smoke-inverter/corners/{PASS_RID}"
    rep = json.loads((cdir / "report.json").read_text())
    rep["corners"].pop()
    (cdir / "report.json").write_text(json.dumps(rep, indent=2) + "\n")
    m = json.loads((cdir / "evidence.json").read_text())
    m["files"]["report.json"] = lint.sha256_file(cdir / "report.json")
    (cdir / "evidence.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    rec = repo / f"sim/smoke-inverter/records/{PASS_RID}.md"
    import re
    rec.write_text(re.sub(r"evidence\.json sha256 `[0-9a-f]{64}`",
                          f"evidence.json sha256 `{lint.sha256_file(cdir / 'evidence.json')}`", rec.read_text()))
    assert any("missing from report" in x for x in problems(repo, append_only=False))
