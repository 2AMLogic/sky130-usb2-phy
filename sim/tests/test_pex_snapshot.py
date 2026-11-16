"""The pex bench's netlist snapshot: one shared composition, gate-safe bytes, append-only.

The convention (sim/README.md): a deck with in-deck `.include` lines is frozen with each
included file inlined behind a `* ---- included: <path> ----` banner (harness `snapshot_body`),
so the snapshot reproduces the simulated circuit and is never byte-identical to the deck
staged into the artifact store -- a bare-deck snapshot re-triggers `committed_duplicates` on
every re-run and freezes a netlist with no device cards (issue #315). Toolchain-free: real
committed bytes, no git command, no klt, nothing written inside the repo.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from harness import artifact_manifest as am, runner

SIM = Path(__file__).resolve().parents[1]
BENCH = "diff-receiver-pex"
TESTBENCH = SIM / BENCH / "testbench"
DECK = TESTBENCH / "diff_receiver_pex_tb.spice"
SHIM = TESTBENCH / "differential_receiver_pex_dut.spice"
RID = "20261201-120000-abcdef1"  # synthetic: never collides with a committed run id

sys.path.insert(0, str(SIM / BENCH))
import run as pex_run  # noqa: E402


def x_cards(data: bytes) -> int:
    """Device/instance cards in a netlist (lines whose first token is X, case-insensitive)."""
    return sum(1 for line in data.decode().splitlines() if line.lstrip().lower().startswith("x"))


def manifest_entry(data: bytes) -> dict:
    sha = hashlib.sha256(data).hexdigest()
    return {"sha256": sha, "size": len(data), "kind": "evidence",
            "producer": {"tool": "klt", "version": "test", "loom.repo": "o/r", "commit": None},
            "uri": f"artifact:evidence/o__r/{sha}",
            "name": f"{BENCH}/{RID}/diff_receiver_pex_tb.spice"}


def pex_shape(tmp_path, snapshot: bytes):
    """A scratch repo shaped like this bench: committed snapshot + pinned testbench files,
    and a manifest storing the deck's bytes under `<bench>/<rid>/diff_receiver_pex_tb.spice`
    (exactly the collision shape `committed_duplicates` must police)."""
    exp = tmp_path / "sim" / BENCH
    (exp / "testbench").mkdir(parents=True)
    (exp / "netlist-snapshots").mkdir(parents=True)
    for f in (DECK, SHIM, TESTBENCH / "tb.json"):
        (exp / "testbench" / f.name).write_bytes(f.read_bytes())
    (exp / "netlist-snapshots" / f"{RID}.spice").write_bytes(snapshot)
    mdir = tmp_path / "manifests" / "artifacts"
    mdir.mkdir(parents=True)
    mp = mdir / f"{BENCH}-{RID}.manifest.json"
    mp.write_text(json.dumps({"schema_version": 1, "entries": [manifest_entry(DECK.read_bytes())]},
                             indent=2) + "\n")
    tracked = [f"sim/{BENCH}/netlist-snapshots/{RID}.spice",
               f"sim/{BENCH}/testbench/{DECK.name}", f"sim/{BENCH}/testbench/{SHIM.name}",
               f"sim/{BENCH}/testbench/tb.json"]
    return tmp_path, json.loads(mp.read_text()), mp.name, tracked


def test_snapshot_body_reproduces_the_sibling_snapshot_byte_for_byte():
    """The harness's own frozen snapshot must be what the shared helper emits: the refactor
    that extracted it must not have moved a byte (the four committed sensitivity records
    re-derive their snapshot sha256 against the klt envelope on every lint)."""
    tb = json.loads((SIM / "diff-receiver-sensitivity/testbench/tb.json").read_text())
    body = runner.snapshot_body(SIM / "diff-receiver-sensitivity/testbench", tb["netlist"], tb["include"])
    committed = (SIM / "diff-receiver-sensitivity/netlist-snapshots/"
                 "20261020-172719-ca4a45a.spice").read_bytes()
    assert body == committed


def test_pex_snapshot_freezes_the_circuit_not_the_bare_deck():
    includes = pex_run.deck_includes(DECK)
    assert includes == ["differential_receiver_pex_dut.spice"]
    body = runner.snapshot_body(DECK.parent, DECK.name, includes)
    deck, shim = DECK.read_bytes(), SHIM.read_bytes()
    assert b".subckt differential_receiver" in body
    assert x_cards(deck) == 3 and x_cards(shim) == 11
    assert x_cards(body) == x_cards(deck) + x_cards(shim) == 14
    assert body != deck and hashlib.sha256(body).hexdigest() != hashlib.sha256(deck).hexdigest()
    assert b"\n* ---- included: differential_receiver_pex_dut.spice ----\n" in body


def test_committed_duplicates_accepts_a_helper_written_snapshot(tmp_path):
    body = runner.snapshot_body(DECK.parent, DECK.name, pex_run.deck_includes(DECK))
    repo, manifest, label, tracked = pex_shape(tmp_path, body)
    assert am.committed_duplicates(repo, manifest, label, tracked) == []


def test_bare_deck_snapshot_retriggers_the_gate(tmp_path):
    """The tooth: with the pre-#315 convention (snapshot = deck bytes) the same shape fires
    `committed_duplicates`, so this suite detects a regression to it rather than passing vacuously."""
    repo, manifest, label, tracked = pex_shape(tmp_path, DECK.read_bytes())
    problems = am.committed_duplicates(repo, manifest, label, tracked)
    assert len(problems) == 1 and RID in problems[0] and "committed at" in problems[0]


def test_deck_without_include_freezes_the_deck_bytes_unchanged(tmp_path):
    deck = tmp_path / "plain.spice"
    deck.write_bytes(b"* plain deck, no includes\nv1 a 0 dc 1\n")
    assert runner.snapshot_body(tmp_path, deck.name, []) == deck.read_bytes()


def test_deck_with_multiple_includes_inlines_each_in_order(tmp_path):
    (tmp_path / "a.spice").write_bytes(b"* a\n")
    (tmp_path / "b.spice").write_bytes(b"* b\n")
    deck = tmp_path / "deck.spice"
    deck.write_bytes(b'* deck\n.include "a.spice"\n.include b.spice\n')
    body = runner.snapshot_body(tmp_path, deck.name, pex_run.deck_includes(deck))
    assert body == (b'* deck\n.include "a.spice"\n.include b.spice\n'
                    b"\n* ---- included: a.spice ----\n* a\n"
                    b"\n* ---- included: b.spice ----\n* b\n")


def test_write_snapshot_is_append_only_and_emits_helper_bytes(tmp_path):
    snap = pex_run.write_snapshot(RID, tmp_path)
    assert snap == tmp_path / "sim" / BENCH / "netlist-snapshots" / f"{RID}.spice"
    assert snap.read_bytes() == runner.snapshot_body(DECK.parent, DECK.name, pex_run.deck_includes(DECK))
    with pytest.raises(FileExistsError, match="append-only"):
        pex_run.write_snapshot(RID, tmp_path)
    assert snap.read_bytes() == runner.snapshot_body(DECK.parent, DECK.name, pex_run.deck_includes(DECK))
