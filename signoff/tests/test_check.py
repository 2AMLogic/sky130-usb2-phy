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
    names = [v[0] for v in check.ANCHORED.values()] + list(check.UNCITED_INVENTORIES)
    for name in names:
        inventory = json.loads((REAL_ROOT / name).read_text())
        for member in check._members(inventory):
            dest = tmp_path / member["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REAL_ROOT / member["path"], dest)
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
        "rtl/usb_rx_cdc.v",  # item 1 (digital) member
    ],
)
def test_mutating_an_inventoried_file_fails_the_gate(tree, mutated, capsys):
    check, root = tree
    with (root / mutated).open("a") as handle:
        handle.write("\n// mutated\n")
    assert not check.check_inventory_members()
    assert mutated in capsys.readouterr().err


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
