"""Toolchain-free tests for the open_pdks pin (#151): PDK search order, revision check, known pins.

Fake PDK trees in tmp dirs stand in for the installed ones; nothing needs klt, ngspice or a real PDK.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness import matrix as mx, pdk_pin, runner

SIM = Path(__file__).resolve().parents[1]
NEW = "f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"
OLD = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"
LEGACY = mx.load()
LIB_SHA = LEGACY.pdk["lib_sha256"]


def fake_tree(root: Path, commit: str | None) -> Path:
    """A minimal `<root>/sky130A` with a library and (optionally) a SOURCES revision."""
    pdk = root / "sky130A"
    (pdk / "libs.tech" / "ngspice").mkdir(parents=True)
    (pdk / "libs.tech" / "ngspice" / "sky130.lib.spice").write_text("* lib\n")
    if commit is not None:
        (pdk / "SOURCES").write_text(f"open_pdks {commit}\n")
    return pdk


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("PDK_ROOT", raising=False)
    return h


def test_both_pin_files_name_the_ciel_revision():
    pins = json.loads((SIM / "pdk-pins.json").read_text())
    assert pins["current"]["open_pdks_commit"] == NEW
    assert LEGACY.pdk["open_pdks_commit"] == NEW == mx.load_by_id(mx.RESISTOR_SETS_ID).pdk["open_pdks_commit"]
    assert LEGACY.pdk["lib_sha256"] == pins["current"]["lib_sha256"]


def test_ciel_is_searched_and_volare_is_not(home):
    fake_tree(home / ".volare", OLD)
    assert runner.find_pdk_dir("sky130A") is None
    ciel = fake_tree(home / ".ciel", NEW)
    assert runner.find_pdk_dir("sky130A") == ciel


def test_ciel_wins_over_a_stray_volare_tree(home):
    fake_tree(home / ".volare", OLD)
    ciel = fake_tree(home / ".ciel", NEW)
    assert runner.find_pdk_dir("sky130A") == ciel


def test_explicit_pdk_root_is_searched_first_and_still_checked(home, tmp_path, monkeypatch):
    fake_tree(home / ".ciel", NEW)
    stale = tmp_path / "stale"
    fake_tree(stale, OLD)
    monkeypatch.setenv("PDK_ROOT", str(stale))
    assert runner.find_pdk_dir("sky130A") == stale / "sky130A"
    with pytest.raises(runner.RunError) as exc:
        runner.check_env(LEGACY)
    assert OLD in str(exc.value) and NEW in str(exc.value)


def test_missing_sources_is_unknown_not_a_match(home):
    pdk = fake_tree(home / ".ciel", None)
    assert runner.pdk_open_pdks_commit(pdk) == "unknown"
    with pytest.raises(runner.RunError) as exc:
        runner.check_env(LEGACY)
    assert "unknown" in str(exc.value) and NEW in str(exc.value)


def test_matching_revision_passes_the_revision_check(home, monkeypatch):
    fake_tree(home / ".ciel", NEW)
    # the fake library has no corner sections, so check_env stops at the section check, after
    # the revision check has already accepted the tree
    with pytest.raises(runner.RunError) as exc:
        runner.check_env(LEGACY)
    assert "no .lib section" in str(exc.value)


def write_approved_sections(lib: Path) -> None:
    """Give the fake library the exact `.lib` sections check_env's approved map expects."""
    lines = []
    for s in sorted(LEGACY.process):
        lines.append(f".lib {s}")
        lines += [f".include {t}" for t in runner.expected_includes(s)]
        lines.append(".endl")
    (lib.parent / lib.name).write_text("\n".join(lines) + "\n")


def test_check_env_success_returns_the_pinned_commit(home):
    pdk = fake_tree(home / ".ciel", NEW)
    write_approved_sections(pdk / "libs.tech" / "ngspice" / "sky130.lib.spice")
    env = runner.check_env(LEGACY)
    # the regression this test exists for: check_env dropped the shared helper's revision
    # binding and raised NameError here on every successful call
    assert env["open_pdks_commit"] == NEW
    assert env["path"] == str(pdk)
    assert set(env["sections_present"]) == set(LEGACY.process)
    assert set(env["sections"]) == set(LEGACY.process)


def test_known_pins_by_record_date():
    cur = {"open_pdks_commit": NEW, "lib_sha256": LIB_SHA}
    old = {"open_pdks_commit": OLD, "lib_sha256": LIB_SHA}
    assert mx.pin_problem(cur, "20261020-000000-abcdef0") is None
    assert mx.pin_problem(cur, "20260915-000000-abcdef0") is None
    assert mx.pin_problem(old, "20261010-072418-0d51889") is None
    assert "retired" in mx.pin_problem(old, "20261020-000000-abcdef0")
    # a mixed identity (one field from each pin) or an unknown one is rejected
    assert mx.pin_problem({"open_pdks_commit": NEW, "lib_sha256": "0" * 64}, "20261020-000000-abcdef0")
    assert mx.pin_problem({"open_pdks_commit": "deadbeef", "lib_sha256": LIB_SHA}, "20261010-072418-0d51889")


# ---- the shared pinned-PDK module (`pdk_pin`) and the netlist-export shim over it

SHIM = SIM.parent / "sim" / "harness" / "pdk_pin.py"


def add_xschemrc(pdk: Path) -> Path:
    rc = pdk / "libs.tech" / "xschem" / "xschemrc"
    rc.parent.mkdir(parents=True)
    rc.write_text("# xschemrc\n")
    return rc


def run_shim(env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    """Run the shim with the ambient PDK_ROOT scrubbed, then `env_overrides` applied."""
    env = {k: v for k, v in os.environ.items() if k != "PDK_ROOT"}
    env.update(env_overrides)
    return subprocess.run([sys.executable, str(SHIM)], capture_output=True, text=True, env=env)


def test_xschem_marker_accepts_only_a_tree_with_the_rcfile(home):
    pdk = fake_tree(home / ".ciel", NEW)
    assert pdk_pin.xschem_rcfile(pdk) is None
    rc = add_xschemrc(pdk)
    assert pdk_pin.xschem_rcfile(pdk) == rc


def test_netlist_shim_prints_the_pinned_xschemrc(home):
    rc = add_xschemrc(fake_tree(home / ".ciel", NEW))
    out = run_shim({"HOME": str(home)})
    assert out.returncode == 0
    assert out.stdout.strip() == str(rc)


def test_netlist_shim_refuses_a_stale_pdk_root_naming_both_revisions(home, tmp_path):
    stale = tmp_path / "stale"
    add_xschemrc(fake_tree(stale, OLD))
    out = run_shim({"HOME": str(home), "PDK_ROOT": str(stale)})
    assert out.returncode != 0
    assert OLD in out.stderr and NEW in out.stderr


def test_netlist_shim_fails_when_no_tree_exists(home):
    out = run_shim({"HOME": str(home)})
    assert out.returncode != 0
    assert "sky130A not found" in out.stderr
