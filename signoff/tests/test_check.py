"""Negative controls for signoff/check.py's artifact-anchored items 9 and 10.

Run: python3 -m pytest signoff/tests -v

Each test works on a throwaway copy of the files the inventories list, so the
real tree is never mutated.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SIGNOFF = Path(__file__).resolve().parent.parent
REAL_ROOT = SIGNOFF.parent


def _load_check():
    spec = importlib.util.spec_from_file_location("signoff_check", SIGNOFF / "check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["signoff_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    """A copy of the signoff dir plus every file an inventory lists."""
    check = _load_check()
    shutil.copytree(SIGNOFF, tmp_path / "signoff", ignore=shutil.ignore_patterns("tests"))
    names = [v[0] for v in check.ANCHORED.values()]
    for name in names:
        inventory = json.loads((REAL_ROOT / name).read_text())
        for member in check._members(inventory):
            dest = tmp_path / member["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REAL_ROOT / member["path"], dest)
    for _inventory, envelope_rel in check.ATTESTED.values():
        envelope = json.loads((REAL_ROOT / envelope_rel).read_text())
        for entry in envelope["attestation"]["checks"]:
            if entry["check"] == "present":
                dest = tmp_path / entry["path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(REAL_ROOT / entry["path"], dest)
    manifest = json.loads((REAL_ROOT / "signoff" / "block-manifest.json").read_text())
    for cite in manifest["evidence"][check.ITEM6_ANALOG_KEY]:
        report = REAL_ROOT / cite["file"]
        for src in (report, report.parent / json.loads(report.read_text())["samples"]):
            shutil.copy(src, _mk(tmp_path / src.relative_to(REAL_ROOT)))
    # Native analog citations (items 3, 4, 11): the cited envelopes, the leaf
    # records dirs (for the latest-record check) and each LVS reference netlist.
    for key in check.NATIVE_CITATIONS:
        for cite in manifest["evidence"][key]:
            envelope_path = REAL_ROOT / cite["file"]
            shutil.copy(envelope_path, _mk(tmp_path / cite["file"]))
            if envelope_path.name == "lvs-report.json":
                ref = check._repo_rel(json.loads(envelope_path.read_text())["reference"])
                shutil.copy(REAL_ROOT / ref, _mk(tmp_path / ref))
    for leaf in check.NATIVE_LEAVES:
        for record in (REAL_ROOT / f"flow/analog-layout-{leaf}/records").glob("2*.md"):
            _mk(tmp_path / record.relative_to(REAL_ROOT)).touch()
        gds = f"layout/analog/{leaf}/{leaf}.gds"
        shutil.copy(REAL_ROOT / gds, _mk(tmp_path / gds))
    shutil.copy(REAL_ROOT / "spec" / "usb2-phy.md", _mk(tmp_path / "spec" / "usb2-phy.md"))
    shutil.copy(REAL_ROOT / "docs" / "characterization.md", _mk(tmp_path / "docs" / "characterization.md"))
    # klt resolves a `scope: repo` input path against the repo root it finds
    # from the evidence file; give the copy one.
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(check, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check, "SIGNOFF_DIR", tmp_path / "signoff")
    monkeypatch.setattr(check, "MANIFEST", tmp_path / "signoff" / "block-manifest.json")
    return check, tmp_path


def _mk(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_fresh_copy_passes(tree):
    check, _ = tree
    assert check.check_inventory_members()


@pytest.mark.parametrize(
    "mutated",
    [
        "verification/test_usb_rx.py",  # item 9 member
        "sim/smoke-inverter/testbench/tb.json",  # item 9 analog member
        "README.md",  # item 10 member
        "LICENSE",  # item 10 member
    ],
)
def test_mutating_an_inventoried_file_fails_the_gate(tree, mutated, capsys):
    check, root = tree
    with (root / mutated).open("a") as handle:
        handle.write("\n// mutated\n")
    assert not check.check_inventory_members()
    assert mutated in capsys.readouterr().err


def manifest_for(check):
    return json.loads(check.MANIFEST.read_text())


def test_attested_item1_fresh_copy_passes(tree):
    check, _ = tree
    assert check.check_attested(manifest_for(check))


@pytest.mark.parametrize("mutated", ["rtl/usb_rx_cdc.v", "flow/request-synth-usb_utmi_top.json"])
def test_mutating_an_item1_source_fails_the_gate(tree, mutated, capsys):
    check, root = tree
    with (root / mutated).open("a") as handle:
        handle.write("\n// mutated\n")
    assert not check.check_attested(manifest_for(check))
    assert mutated in capsys.readouterr().err


def test_item9_inventory_is_complete_for_the_real_tree():
    check = _load_check()
    assert check.check_item9_complete(REAL_ROOT)


@pytest.mark.parametrize(
    "added",
    [
        "verification/test_new_suite.py",  # a new cocotb suite
        "verification/request-new-suite.json",  # its klt request
        "sim/new-block/testbench/tb.json",  # a new analog testbench
    ],
)
def test_an_uninventoried_testbench_fails_the_gate(tree, added, capsys):
    check, root = tree
    assert check.check_item9_complete(root)
    _mk(root / added).write_text("{}\n")
    assert not check.check_item9_complete(root)
    assert added in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("klt") is None, reason="klt not on PATH")
@pytest.mark.parametrize("item", ["9", "10"])
def test_grader_renders_stale_when_the_bound_inventory_moves(tree, item):
    """Changing the audited artifact without re-pinning is stale_evidence."""
    check, root = tree
    inventory = root / check.ANCHORED[item][0]
    inventory.write_text(inventory.read_text() + " ")
    proc = subprocess.run(
        ["klt", "signoff", "--manifest", "signoff/block-manifest.json", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    report = json.loads(proc.stdout)
    rows = [i for i in report["items"] if i["tier"] == "T1" and i["id"] == int(item)]
    assert rows and all(r["reason"] == "stale_evidence" for r in rows)


def _manifest(root: Path) -> dict:
    return json.loads((root / "signoff" / "block-manifest.json").read_text())


def test_item6_binding_passes_on_the_real_tree(tree):
    check, root = tree
    assert check.check_item6_binding(_manifest(root), root)


def test_editing_the_spec_markdown_fails_the_item6_gate(tree, capsys):
    check, root = tree
    with (root / "spec" / "usb2-phy.md").open("a") as handle:
        handle.write("\nA new row.\n")
    assert not check.check_item6_binding(_manifest(root), root)
    assert "now hashes to" in capsys.readouterr().err


@pytest.mark.parametrize("edit", ["drop", "add"])
def test_a_statement_row_mismatch_fails_the_item6_gate(tree, edit, capsys):
    check, root = tree
    path = root / check.ITEM6_STATEMENT
    statement = json.loads(path.read_text())
    if edit == "drop":
        statement["rows"].pop()
    else:
        statement["rows"].append({"id": "extra-row", "class": "x", "reason": "y"})
    path.write_text(json.dumps(statement))
    assert not check.check_item6_binding(_manifest(root), root)
    assert "must account for exactly the rows" in capsys.readouterr().err


def test_item6_analog_binding_passes_on_the_real_tree(tree):
    check, root = tree
    assert check.check_item6_analog(_manifest(root), root)


def test_editing_the_spec_markdown_fails_the_item6_analog_gate(tree, capsys):
    check, root = tree
    with (root / "spec" / "usb2-phy.md").open("a") as handle:
        handle.write("\nA new row.\n")
    assert not check.check_item6_analog(_manifest(root), root)
    assert "now hashes to" in capsys.readouterr().err


def test_a_drifted_cited_samples_document_fails_the_item6_analog_gate(tree, capsys):
    check, root = tree
    cite = _manifest(root)["evidence"][check.ITEM6_ANALOG_KEY][0]
    report = root / cite["file"]
    samples = report.parent / json.loads(report.read_text())["samples"]
    with samples.open("a") as handle:
        handle.write("\n")
    assert not check.check_item6_analog(_manifest(root), root)
    assert "samples document now hashes to" in capsys.readouterr().err


@pytest.mark.parametrize("edit", ["drop", "add", "undeclared-citation"])
def test_a_row_set_mismatch_fails_the_item6_analog_gate(tree, edit, capsys):
    check, root = tree
    path = root / "signoff" / "block-manifest.json"
    manifest = json.loads(path.read_text())
    declared = manifest["spec_rows"][check.ITEM6_ANALOG_KEY]
    if edit == "drop":
        declared.pop()
    elif edit == "add":
        declared.append({"id": "6-99"})
    else:
        manifest["evidence"][check.ITEM6_ANALOG_KEY][0]["rows"] = ["6-99"]
    path.write_text(json.dumps(manifest))
    assert not check.check_item6_analog(_manifest(root), root)
    err = capsys.readouterr().err
    assert "must equal the rows" in err or "undeclared" in err


SCAN_WORDS = ("sigma", "σ", "yield", "cpk", "offset", "mismatch", "matching", "accuracy", "monte carlo", "std dev")


def test_item6_texts_avoid_the_graders_statistical_vocabulary():
    check = _load_check()
    for rel in (check.ITEM6_SPEC, check.ITEM6_STATEMENT):
        data = json.loads((REAL_ROOT / rel).read_text())
        rows = [r for r in data["rows"]]
        text = json.dumps(rows, ensure_ascii=False).lower()
        assert not [w for w in SCAN_WORDS if w in text], rel


@pytest.mark.skipif(shutil.which("klt") is None, reason="klt not on PATH")
def test_grader_refuses_a_scan_word_in_a_statement_class(tree):
    check, root = tree
    path = root / check.ITEM6_STATEMENT
    statement = json.loads(path.read_text())
    statement["rows"][0]["class"] = "yield bound"
    path.write_text(json.dumps(statement))
    check.refresh_item6()
    proc = subprocess.run(
        ["klt", "signoff", "--manifest", "signoff/block-manifest.json", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    row = [i for i in json.loads(proc.stdout)["items"] if i["id"] == 6 and i["partition"] == "digital"][0]
    assert row["status"] != "not_applicable"


# --- native analog citations (items 3, 4, 11) and the item-2 layout inventory


def test_native_citations_pass_on_the_real_tree(tree):
    check, _ = tree
    assert check.check_native_citations(manifest_for(check))


@pytest.mark.parametrize("leaf", ["differential_driver", "se_receiver_dp"])
def test_a_one_byte_leaf_gds_change_fails_the_native_gate(tree, leaf, capsys):
    check, root = tree
    gds = root / f"layout/analog/{leaf}/{leaf}.gds"
    data = bytearray(gds.read_bytes())
    data[-1] ^= 0x01
    gds.write_bytes(bytes(data))
    assert not check.check_native_citations(manifest_for(check))
    assert f"{leaf}.gds changed since the envelope was produced" in capsys.readouterr().err
    # The same edit also trips the item-2 inventory (the GDS is a member).
    assert not check.check_inventory_members()


def test_a_changed_lvs_reference_netlist_fails_the_native_gate(tree, capsys):
    check, root = tree
    with (root / "design/netlist/se_receiver_dm.spice").open("a") as handle:
        handle.write("* mutated\n")
    assert not check.check_native_citations(manifest_for(check))
    assert "reference netlist design/netlist/se_receiver_dm.spice" in capsys.readouterr().err


def test_a_missing_leaf_citation_fails_the_native_gate(tree, capsys):
    check, _ = tree
    manifest = manifest_for(check)
    manifest["evidence"]["3.analog"].pop()
    assert not check.check_native_citations(manifest)
    assert "se_receiver_dp" in capsys.readouterr().err
