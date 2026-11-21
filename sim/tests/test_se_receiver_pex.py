"""Both single-ended-receiver pex entry points route to the one shared runner.

The refactor this suite pins (issue #419): sim/se-receiver-dp-pex/run.py and
sim/se-receiver-dm-pex/run.py were two 238-line copies differing only in the
leaf name, polarity label, deck/shim names and committed reference record; they
are now thin `Bench` configs over sim/harness/se_receiver_pex.py. What must not
regress: each entry point still selects its OWN layout, testbench and reference
record, stages and freezes its snapshot beneath its OWN bench directory, keeps
the committed per-leaf snapshot byte-for-byte, and preserves the exit-code
contract -- 0 for a matching schematic leg, 3 for a mismatching one, 4 for a
re-written run id, 2 for a refused klt pex call -- plus the grading verdicts
(grading failures do not change the exit code; only equivalence does).

Toolchain-free: the klt pex call is faked with an envelope whose schematic leg
lifts (corner, measurement) values verbatim from the bench's own committed
reference record (the same shape sim/tests/test_pex_equivalence.py builds), runs
land in a scratch repo + stage directory, and every byte compared against is
committed in this tree.
"""

import datetime
import importlib.util
import json
import sys
import types
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))

from harness import pex_equivalence, se_receiver_pex as srp  # noqa: E402


def load_entry(bench):
    """Load one bench's run.py as a module (two files share the name `run`)."""
    spec = importlib.util.spec_from_file_location(f"{bench.replace('-', '_')}_run",
                                                  SIM / bench / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DP = load_entry("se-receiver-dp-pex")
DM = load_entry("se-receiver-dm-pex")
BENCHES = (DP.BENCH, DM.BENCH)
RID = "20261201-120000-deadbee"  # frozen clock + patched head_sha; never a committed run id


def reference_of(cfg):
    return json.loads(cfg.reference_report.read_text())


def envelope_from_reference(cfg, *, extracted_tweak=None, schematic_tweak=None):
    """A synthetic klt pex envelope over exactly this bench's requested (corner,
    measurement) pairs, schematic values lifted verbatim from its own committed
    record. `schematic_tweak`/`extracted_tweak` optionally perturb one row's leg."""
    tb = json.loads(cfg.tb().read_text())
    committed = pex_equivalence.committed_values(reference_of(cfg))
    delta = []
    for cid, name in pex_equivalence.expected_pairs(tb):
        row = {"corner_id": cid, "spec_row": name,
               "schematic_value": committed[(cid, name)],
               "extracted_value": committed[(cid, name)], "status": "pass"}
        if schematic_tweak and (cid, name) == schematic_tweak[0]:
            row["schematic_value"] *= 1 + schematic_tweak[1]
        if extracted_tweak and (cid, name) == extracted_tweak[0]:
            row["extracted_value"] = extracted_tweak[1](row["extracted_value"])
        delta.append(row)
    return {"status": "pass", "corner_count": 2, "delta": delta,
            "passed": len(delta), "failed": 0, "errored": 0}


def fake_klt(monkeypatch, envelope):
    """Replace every subprocess the shared runner launches: `klt pex` writes the
    fixture envelope to the request's --envelope-out (or answers a dry-run); git
    answers a fixed short sha. Returns the recorded klt command lines."""
    calls = []

    def run(cmd, *a, **k):
        if cmd[0] == "git":
            return types.SimpleNamespace(returncode=0, stdout="deadbeef99\n", stderr="")
        calls.append(cmd)
        stdout = json.dumps({"status": "accepted", "testbenches": [
            {"sim": {"units": [{"corner_id": "tt/3.300V/27C"}, {"corner_id": "ff_lh/3.000V/100C"}]}}]})
        if "--dry-run" not in cmd:
            out = Path(cmd[cmd.index("--envelope-out") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(envelope))
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(srp.subprocess, "run", run)
    return calls


def freeze_clock(monkeypatch):
    """Pin the run id: a frozen UTC clock and the patched git sha make every run
    mint RID, so a re-run of the same second is provably the same run id."""
    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 12, 1, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(srp, "datetime",
                        types.SimpleNamespace(datetime=Frozen, timezone=datetime.timezone))
    monkeypatch.setattr(srp, "head_sha", lambda repo=srp.REPO: "deadbee")


def scratch_repo(tmp_path, cfg):
    """A scratch repo shaped for one bench: its committed testbench bytes at their
    real relative paths, so `main(..., repo=scratch)` never writes into this tree."""
    tb_dir = tmp_path / "repo" / "sim" / cfg.bench / "testbench"
    tb_dir.mkdir(parents=True)
    for f in (cfg.tb(), cfg.deck_path(), cfg.shim_path()):
        (tb_dir / f.name).write_bytes(f.read_bytes())
    return tmp_path / "repo"


def committed_snapshot(cfg):
    snaps = sorted((cfg.bench_dir() / "netlist-snapshots").glob("*.spice"))
    assert len(snaps) == 1  # one committed run per bench today
    return snaps[0]


def run_main(cfg, monkeypatch, tmp_path, envelope):
    calls = fake_klt(monkeypatch, envelope)
    freeze_clock(monkeypatch)
    scratch = scratch_repo(tmp_path, cfg)
    rc = srp.main(cfg, ["--stage-dir", str(tmp_path / "work")], repo=scratch)
    return calls, scratch, tmp_path / "work" / RID, rc


def test_each_entry_point_owns_its_leaf_facts():
    """Two commands, two leaves: every per-bench fact differs and every referenced
    file exists in the tracked tree at its leaf-named path."""
    for cfg in BENCHES:
        assert cfg.gds().is_file() and cfg.leaf in str(cfg.gds())
        assert cfg.tb().is_file() and cfg.deck_path().is_file() and cfg.shim_path().is_file()
        assert cfg.reference_report.is_file()
        assert cfg.bench_dir(Path("x" * 60)) == Path("x" * 60) / "sim" / cfg.bench
    assert DP.BENCH.leaf == "se_receiver_dp" and DM.BENCH.leaf == "se_receiver_dm"
    assert DP.BENCH.bench == "se-receiver-dp-pex" and DM.BENCH.bench == "se-receiver-dm-pex"
    assert DP.BENCH.deck != DM.BENCH.deck and DP.BENCH.shim != DM.BENCH.shim
    assert DP.BENCH.reference_report != DM.BENCH.reference_report
    assert {p.polarity for p in BENCHES} == {"D+", "D-"}


def test_matching_leg_grades_and_freezes_under_the_own_bench(tmp_path, monkeypatch, capsys):
    """The happy path per entry point: own GDS and testbench in the klt command, own
    reference record in equivalence.json, PASS grading, exit 0, and the snapshot --
    byte-identical to the bench's committed snapshot -- under its own bench dir."""
    for cfg in BENCHES:
        calls, scratch, stage, rc = run_main(cfg, monkeypatch, tmp_path / cfg.bench,
                                             envelope_from_reference(cfg))
        assert rc == 0, capsys.readouterr().err
        # own layout and own request, never the sibling's
        cmd = calls[-1]
        assert str(cfg.gds(scratch)) in cmd and str(cfg.tb(scratch)) in cmd
        assert f"--top {cfg.leaf}".split() == cmd[cmd.index("--top"):cmd.index("--top") + 2]
        assert "se_receiver_d" not in " ".join(cmd).replace(cfg.leaf, "")
        # own committed reference record
        equiv = json.loads((stage / "equivalence.json").read_text())
        assert equiv["equivalent"] and len(equiv["rows"]) == 14
        assert equiv["reference_record"] == str(cfg.reference_report.relative_to(srp.REPO))
        # grading: both corners, all 8 checks each, recorded under the own leaf name
        grading = json.loads((stage / "grading.json").read_text())
        assert grading["all_pass"] and grading["leaf"] == cfg.leaf
        assert len(grading["corners"]) == 2
        assert sum(len(c["checks"]) for c in grading["corners"].values()) == 16
        # staged bench inputs and the snapshot land in the own bench directory
        snap = scratch / "sim" / cfg.bench / "netlist-snapshots" / f"{RID}.spice"
        assert snap.is_file() and snap.read_bytes() == committed_snapshot(cfg).read_bytes()
        for f in (cfg.tb(scratch), cfg.deck_path(scratch), cfg.shim_path(scratch)):
            assert (stage / f.name).read_bytes() == f.read_bytes()


def test_mismatching_schematic_leg_exits_3(tmp_path, monkeypatch):
    for cfg in BENCHES:
        env = envelope_from_reference(
            cfg, schematic_tweak=(("tt/3.300V/27C", "vth_v"), 1e-3))  # >> the 1e-6 gate
        _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path / cfg.bench, env)
        assert rc == 3
        equiv = json.loads((stage / "equivalence.json").read_text())
        assert not equiv["equivalent"]
        bad = [r for r in equiv["rows"] if r["verdict"] == "MISMATCH"]
        assert [(r["corner_id"], r["measurement"]) for r in bad] == [("tt/3.300V/27C", "vth_v")]
        # the extracted leg still grades: the mismatch is schematic-only
        assert json.loads((stage / "grading.json").read_text())["all_pass"]


def test_extracted_leg_failure_is_graded_not_exit_changing(tmp_path, monkeypatch):
    """Preserved behavior: an extracted-leg bound violation FAILs its check in
    grading.json while the exit code stays 0 -- only equivalence sets exit 3."""
    cfg = DP.BENCH
    env = envelope_from_reference(
        cfg, extracted_tweak=(("tt/3.300V/27C", "rxd_low_max_v"), lambda _v: 1.0))  # > 0.33 V
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path, env)
    assert rc == 0
    grading = json.loads((stage / "grading.json").read_text())
    assert not grading["all_pass"]
    failed = [c for corner in grading["corners"].values() for c in corner["checks"]
              if c["verdict"] == "FAIL"]
    assert [(c["corner_id"], c["check"]) for c in failed] == \
        [("tt/3.300V/27C", "rxd_low_max_v <= 0.1*VDD")]
    assert failed[0]["bound"] == "<= 0.33 V"


def test_second_write_of_the_same_run_id_is_refused(tmp_path, monkeypatch):
    """Append-only, both ways: the direct snapshot writer raises, and a re-run of
    the same run id through the entry point surfaces it as exit 4."""
    cfg = DM.BENCH
    scratch = scratch_repo(tmp_path, cfg)
    snap = srp.write_snapshot(cfg, RID, scratch)
    assert snap.read_bytes() == committed_snapshot(cfg).read_bytes()
    try:
        srp.write_snapshot(cfg, RID, scratch)
        raise AssertionError("second write of the same run id was allowed")
    except FileExistsError:
        pass
    fake_klt(monkeypatch, envelope_from_reference(cfg))
    freeze_clock(monkeypatch)
    rc = srp.main(cfg, ["--stage-dir", str(tmp_path / "work")], repo=scratch)
    assert rc == 4


def test_dry_run_is_a_pre_flight_without_extraction(tmp_path, monkeypatch, capsys):
    calls = fake_klt(monkeypatch, None)
    freeze_clock(monkeypatch)
    scratch = scratch_repo(tmp_path, DP.BENCH)
    rc = srp.main(DP.BENCH, ["--dry-run", "--stage-dir", str(tmp_path / "work")], repo=scratch)
    assert rc == 0
    cmd = calls[-1]
    assert "--dry-run" in cmd and "-o" not in cmd and "--envelope-out" not in cmd
    assert (tmp_path / "work/dry-run/dry-run-stdout.json").is_file()
    assert "dry-run: status=accepted" in capsys.readouterr().out


def test_klt_pex_failure_keeps_its_evidence_and_exits_2(tmp_path, monkeypatch):
    """A refused klt pex call (non-zero exit, no envelope) keeps stdout/stderr under
    the stage dir as committed evidence and exits 2."""
    freeze_clock(monkeypatch)

    def run(cmd, *a, **k):
        if cmd[0] == "git":
            return types.SimpleNamespace(returncode=0, stdout="deadbeef99\n", stderr="")
        return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(srp.subprocess, "run", run)
    scratch = scratch_repo(tmp_path, DP.BENCH)
    rc = srp.main(DP.BENCH, ["--stage-dir", str(tmp_path / "work")], repo=scratch)
    stage = tmp_path / "work" / RID
    assert rc == 2
    assert (stage / "pex-stderr.txt").read_text() == "boom"
    assert (stage / "command.txt").is_file()
