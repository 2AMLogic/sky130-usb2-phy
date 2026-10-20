"""PDK root resolution checks the open_pdks revision against the repo pin (#151).

Fake PDK trees in tmp dirs; no `klt`, no PDK, no network.
"""

import json
import sys
from pathlib import Path

import pytest

FLOW = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FLOW))
import run_flow  # noqa: E402

PIN = json.loads((FLOW.parent / "sim" / "corners.json").read_text())["pdk"]["open_pdks_commit"]
OLD = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"


def fake_root(root: Path, commit: str | None) -> Path:
    (root / "sky130A").mkdir(parents=True)
    if commit is not None:
        (root / "sky130A" / "SOURCES").write_text(f"open_pdks {commit}\n")
    return root


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setattr(run_flow.shutil, "which", lambda name: None)  # klt absent: no fallback
    return h


def test_pin_is_the_ciel_revision():
    assert PIN == "f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7" == run_flow.pinned_open_pdks_commit()


def test_ciel_tree_at_the_pin_is_resolved_and_exported(home):
    root = fake_root(home / ".ciel", PIN)
    env = {"PDK": "sky130A"}
    assert run_flow.resolve_pdk_root(env) == str(root)
    assert env["PDK_ROOT"] == str(root)


def test_stray_volare_tree_is_not_picked_up(home):
    fake_root(home / ".volare", OLD)
    assert run_flow.resolve_pdk_root({"PDK": "sky130A"}) is None


def test_explicit_pdk_root_at_the_wrong_revision_fails_naming_both(home, tmp_path):
    stale = fake_root(tmp_path / "stale", OLD)
    with pytest.raises(run_flow.StageError) as exc:
        run_flow.resolve_pdk_root({"PDK": "sky130A", "PDK_ROOT": str(stale)})
    assert OLD in str(exc.value) and PIN in str(exc.value)


def test_missing_sources_is_unknown_and_fails(home):
    root = fake_root(home / ".ciel", None)
    with pytest.raises(run_flow.StageError) as exc:
        run_flow.resolve_pdk_root({"PDK": "sky130A", "PDK_ROOT": str(root)})
    assert "unknown" in str(exc.value)
