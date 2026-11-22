"""Every leaf pex entry point routes to the one shared runner.

The refactors this suite pins: issue #419 folded sim/se-receiver-dp-pex/run.py and
sim/se-receiver-dm-pex/run.py (two 238-line copies) onto one shared implementation;
issue #425 moved that implementation to sim/harness/pex_runner.py and put the two
remaining leaf runners on it -- sim/diff-receiver-pex/run.py, which also gave up
its count-only inline equivalence gate for the shared exact-pair gate, and
sim/dplus-pullup-pex/run.py. Each entry point supplies thin `Bench` configs (plus,
for the pull-up, its own extracted-leg trim evaluator). What must not regress:
each entry point still selects its OWN layout, testbench and reference record,
stages and freezes its snapshot beneath its OWN bench directory, composes the
snapshot as deck + inlined includes, keeps the committed per-bench snapshot
byte-for-byte where the committed run already follows that composition, and
preserves the exit-code contract -- 0 for a matching schematic leg, 3 for a
mismatching one (for every bench, also when the delta's rows are lifted from
corners the bench never requested), 4 for a re-written run id, 2 for a refused
klt pex call -- plus the grading verdicts (grading failures do not change the
exit code; only equivalence does).

Toolchain-free: the klt pex call is faked with an envelope whose schematic leg
lifts (corner, measurement) values verbatim from the bench's own committed
reference record (the same shape sim/tests/test_pex_equivalence.py builds), runs
land in a scratch repo + stage directory, and every byte compared against is
committed in this tree.
"""

import copy
import datetime
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))

from harness import pex_equivalence, pex_runner, runner  # noqa: E402


def load_entry(bench):
    """Load one leaf's run.py as a module."""
    spec = importlib.util.spec_from_file_location(f"{bench.replace('-', '_')}_run",
                                                  SIM / bench / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENTRY = {bench: load_entry(bench) for bench in (
    "diff-receiver-pex", "se-receiver-dp-pex", "se-receiver-dm-pex", "dplus-pullup-pex",
    "diff-driver-pex")}
DRIVER = ENTRY["diff-driver-pex"]
CONFIGS = {name: mod.BENCH for name, mod in ENTRY.items() if mod is not DRIVER}
CONFIGS.update({f"{cfg.bench}-{cfg.variant}": cfg for cfg in DRIVER.BENCHES})
RID = "20261201-120000-deadbee"  # frozen clock + patched head_sha; never a committed run id
TT = "tt/3.300V/27C"

# Per bench, the committed facts each entry point must keep (sim/README.md): the
# leaf, the binding corners requested beside tt, the equivalence row count and
# one unrequested reference corner whose rows passed a count-only gate.
FACTS = {
    "diff-receiver-pex": {"leaf": "differential_receiver", "binding": ["sf/3.000V/100C"],
                          "rows": 36, "unrequested": "ff/3.000V/-40C"},
    "se-receiver-dp-pex": {"leaf": "se_receiver_dp", "binding": ["ff_lh/3.000V/100C"],
                           "rows": 14, "unrequested": "sf/3.000V/100C"},
    "se-receiver-dm-pex": {"leaf": "se_receiver_dm", "binding": ["ff_lh/3.000V/100C"],
                           "rows": 14, "unrequested": "sf/3.000V/100C"},
    "dplus-pullup-pex": {"leaf": "dplus_pullup", "binding": ["fs_hl/3.000V/100C"],
                         "rows": 52, "unrequested": "sf/3.000V/100C"},
    "diff-driver-pex-static": {"leaf": "differential_driver",
                               "binding": ["fs/3.600V/-40C", "sf/3.600V/-40C"],
                               "rows": 171, "unrequested": "tt/3.000V/-40C"},
    "diff-driver-pex-sq": {"leaf": "differential_driver",
                           "binding": ["fs/3.600V/100C", "sf/3.600V/-40C", "fs/3.000V/100C"],
                           "rows": 204, "unrequested": "tt/3.000V/-40C"},
}
# the benches whose committed run already froze the shared composition (deck +
# inlined includes) and must keep doing so byte-for-byte. diff-receiver-pex's
# committed run (20261115-051001) predates that convention (issue #315) and froze
# the bare deck, so for it only the composition a new run writes is pinned.
COMPOSED = ("se-receiver-dp-pex", "se-receiver-dm-pex", "dplus-pullup-pex",
            "diff-driver-pex-static", "diff-driver-pex-sq")
# grading checks per run (per corner: 8 receiver checks, 2 voff bounds + 1 trim)
CHECKS = {"se-receiver-dp-pex": 16, "se-receiver-dm-pex": 16, "dplus-pullup-pex": 6}
# each graded bench's own end-of-run lines over a passing grading (Bench.summarize);
# the pull-up's best codes are the committed schematic leg through sim/harness/trim.py
SUMMARY = {
    "se-receiver-dp-pex": ["extracted-leg grading: PASS (16 checks)"],
    "se-receiver-dm-pex": ["extracted-leg grading: PASS (16 checks)"],
    "dplus-pullup-pex": ["extracted trim at tt/3.300V/27C: PASS (best code 8: 1480.33 ohm)",
                         "extracted trim at fs_hl/3.000V/100C: PASS (best code 14: 1467.41 ohm)"],
}


def cfg_of(bench):
    return CONFIGS[bench]


def reference_of(cfg):
    return json.loads(cfg.reference_report.read_text())


def measurements_of(cfg):
    return [m["name"] for m in json.loads(cfg.tb().read_text())["measurements"]]


def envelope_from_reference(cfg, *, corners=None, extracted_tweak=None, schematic_tweak=None):
    """A synthetic klt pex envelope over `corners` (default: exactly this bench's
    requested corners) x its measurements, schematic values lifted verbatim from
    its own committed record. `schematic_tweak`/`extracted_tweak` optionally
    perturb one row's leg."""
    tb = json.loads(cfg.tb().read_text())
    committed = pex_equivalence.committed_values(reference_of(cfg))
    names = [m["name"] for m in tb["measurements"]]
    if corners is None:
        corners = list(dict.fromkeys(cid for cid, _ in pex_equivalence.expected_pairs(tb)))
    delta = []
    for cid in corners:
        for name in names:
            row = {"corner_id": cid, "spec_row": name,
                   "schematic_value": committed[(cid, name)],
                   "extracted_value": committed[(cid, name)], "status": "pass"}
            if schematic_tweak and (cid, name) == schematic_tweak[0]:
                row["schematic_value"] *= 1 + schematic_tweak[1]
            if extracted_tweak and (cid, name) == extracted_tweak[0]:
                row["extracted_value"] = extracted_tweak[1](row["extracted_value"])
            delta.append(row)
    return {"status": "pass", "corner_count": len(corners), "delta": delta,
            "passed": len(delta), "failed": 0, "errored": 0}


def fake_klt(monkeypatch, envelope, returncode=0):
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
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(pex_runner.subprocess, "run", run)
    return calls


def freeze_clock(monkeypatch):
    """Pin the run id: a frozen UTC clock and the patched git sha make every run
    mint RID, so a re-run of the same second is provably the same run id."""
    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 12, 1, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(pex_runner, "datetime",
                        types.SimpleNamespace(datetime=Frozen, timezone=datetime.timezone))
    monkeypatch.setattr(pex_runner, "head_sha", lambda repo=pex_runner.REPO: "deadbee")


def scratch_repo(tmp_path, cfg):
    """A scratch repo shaped for one bench: its committed testbench bytes at their
    real relative paths, so `main(..., repo=scratch)` never writes into this tree."""
    tb_dir = tmp_path / "repo" / "sim" / cfg.bench / "testbench"
    tb_dir.mkdir(parents=True)
    for f in (cfg.tb(), cfg.deck_path(), cfg.shim_path()):
        (tb_dir / f.name).write_bytes(f.read_bytes())
    return tmp_path / "repo"


def committed_snapshot(cfg):
    snaps = sorted((cfg.bench_dir() / "netlist-snapshots").glob(f"*{cfg.suffix}.spice"))
    assert len(snaps) == 1  # one committed run per bench today
    return snaps[0]


def composed_snapshot(cfg, repo):
    """The bytes the shared runner must freeze for this bench in `repo`: the deck,
    then each in-deck include inlined behind its banner."""
    deck = cfg.deck_path(repo)
    return runner.snapshot_body(deck.parent, cfg.deck, pex_runner.deck_includes(deck))


def invoke(cfg, argv, repo):
    if cfg.variant:
        return DRIVER.main(DRIVER.BENCHES, ["--bench", cfg.variant, *argv], repo=repo)
    return ENTRY[cfg.bench].main(cfg, argv, repo=repo)


def run_main(cfg, monkeypatch, tmp_path, envelope):
    calls = fake_klt(monkeypatch, envelope)
    freeze_clock(monkeypatch)
    scratch = scratch_repo(tmp_path, cfg)
    rc = invoke(cfg, ["--stage-dir", str(tmp_path / "work")], repo=scratch)
    return calls, scratch, tmp_path / "work" / (RID + cfg.suffix), rc


@pytest.mark.parametrize("bench", list(FACTS))
def test_each_entry_point_owns_its_leaf_facts(bench):
    """Every per-bench fact matches the committed one
    and every referenced file exists in the tracked tree at its leaf-named path."""
    cfg, facts = cfg_of(bench), FACTS[bench]
    assert cfg.bench + cfg.suffix == bench and cfg.leaf == facts["leaf"]
    assert cfg.gds().is_file() and cfg.leaf in str(cfg.gds())
    assert cfg.tb().is_file() and cfg.deck_path().is_file() and cfg.shim_path().is_file()
    reference = {"static": "driver-static", "sq": "driver-signal-quality"}.get(
        cfg.variant, bench.removesuffix("-pex"))
    assert cfg.reference_report.is_file()
    assert cfg.reference_report.relative_to(SIM).parts[0].startswith(reference)
    assert cfg.bench_dir(Path("scratch")) == Path("scratch/sim") / cfg.bench
    requested = list(dict.fromkeys(cid for cid, _ in pex_equivalence.expected_pairs(
        json.loads(cfg.tb().read_text()))))
    assert requested == [TT, *facts["binding"]] and facts["unrequested"] not in requested


def test_bench_configs_cover_five_distinct_leaves():
    benches = list(CONFIGS.values())
    assert len({p.leaf for p in benches}) == len({p.bench for p in benches}) == 5
    assert len({p.shim for p in benches}) == 5
    assert len({p.deck for p in benches}) == len({p.reference_report for p in benches}) == 6
    assert {p.polarity for p in benches if p.polarity} == {"D+", "D-"}
    # the differential receiver and driver grade nothing (equivalence.json alone); the
    # receivers share one evaluator, the pull-up brings its own
    assert {p.bench for p in benches if p.grade_extracted is None} == {"diff-receiver-pex", "diff-driver-pex"}
    assert cfg_of("se-receiver-dp-pex").grade_extracted is cfg_of("se-receiver-dm-pex").grade_extracted
    assert cfg_of("dplus-pullup-pex").grade_extracted is not cfg_of("se-receiver-dp-pex").grade_extracted
    assert all((p.grade_extracted is None) == (p.summarize is None) for p in benches)


@pytest.mark.parametrize("bench", list(ENTRY))
def test_no_entry_point_keeps_a_private_copy_of_the_flow(bench):
    """The consolidation itself: an entry point owns its `Bench` -- and at most its
    own grading -- never a private runner or equivalence gate. The count-only
    `check_equivalence` sim/diff-receiver-pex carried until #425 must not come back,
    and no entry point launches klt or git on its own."""
    mod = ENTRY[bench]
    assert mod.main is pex_runner.main and mod.Bench is pex_runner.Bench
    for name in ("head_sha", "deck_includes", "write_snapshot", "pex_cmd", "check_equivalence"):
        assert not hasattr(mod, name), name
    source = Path(mod.__file__).read_text()
    assert "subprocess" not in source and "argparse" not in source


@pytest.mark.parametrize("bench", list(FACTS))
def test_matching_leg_grades_and_freezes_under_the_own_bench(tmp_path, monkeypatch, capsys, bench):
    """The happy path per entry point: own GDS and testbench in the klt command, own
    reference record in equivalence.json, grading exactly where the bench has an
    evaluator, exit 0, and the snapshot -- the shared composition -- under its own
    bench directory."""
    cfg, facts = cfg_of(bench), FACTS[bench]
    calls, scratch, stage, rc = run_main(cfg, monkeypatch, tmp_path,
                                         envelope_from_reference(cfg))
    assert rc == 0, capsys.readouterr().err
    # own layout and own request, never a sibling leaf's
    cmd = calls[-1]
    assert str(cfg.gds(scratch)) in cmd and str(cfg.tb(scratch)) in cmd
    assert cmd[cmd.index("--top"):cmd.index("--top") + 2] == ["--top", cfg.leaf]
    joined = " ".join(cmd)
    for other, of in FACTS.items():
        if of["leaf"] != cfg.leaf:
            assert f"{of['leaf']}/{of['leaf']}.gds" not in joined and f"sim/{cfg_of(other).bench}/" not in joined
    # own committed reference record
    equiv = json.loads((stage / "equivalence.json").read_text())
    assert equiv["equivalent"] and len(equiv["rows"]) == facts["rows"]
    assert equiv["reference_record"] == str(cfg.reference_report.relative_to(pex_runner.REPO))
    assert equiv["rel_tol"] == pex_equivalence.REL_TOL
    # grading iff the bench supplies an evaluator
    out = capsys.readouterr().out
    if bench in CHECKS:
        grading = json.loads((stage / "grading.json").read_text())
        assert grading["all_pass"] and grading["leaf"] == cfg.leaf and grading["leg"] == "extracted"
        assert sum(len(c["checks"]) for c in grading["corners"].values()) == CHECKS[bench]
        assert set(grading["corners"]) == {TT, *facts["binding"]}
        assert all(line in out for line in SUMMARY[bench])
    else:
        assert not (stage / "grading.json").exists()
        assert "grading" not in out and "trim" not in out
    assert f"equivalence vs {equiv['reference_record']}: OK ({facts['rows']} rows)" in out
    assert f"store with: python3 sim/run_store_evidence.py {cfg.bench} {stage}" in out
    # staged bench inputs and the snapshot land in the own bench directory
    snap = cfg.bench_dir(scratch) / "netlist-snapshots" / f"{RID}{cfg.suffix}.spice"
    assert snap.read_bytes() == composed_snapshot(cfg, scratch)
    if bench in COMPOSED:
        assert snap.read_bytes() == committed_snapshot(cfg).read_bytes()
    for f in (cfg.tb(scratch), cfg.deck_path(scratch), cfg.shim_path(scratch)):
        assert (stage / f.name).read_bytes() == f.read_bytes()


@pytest.mark.parametrize("bench", list(FACTS))
def test_mismatching_schematic_leg_exits_3(tmp_path, monkeypatch, capsys, bench):
    cfg, facts = cfg_of(bench), FACTS[bench]
    name = measurements_of(cfg)[0]
    env = envelope_from_reference(cfg, schematic_tweak=((TT, name), 1e-3))  # >> the 1e-6 gate
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path / bench, env)
    assert rc == 3
    equiv = json.loads((stage / "equivalence.json").read_text())
    assert not equiv["equivalent"]
    bad = [r for r in equiv["rows"] if r["verdict"] == "MISMATCH"]
    assert [(r["corner_id"], r["measurement"]) for r in bad] == [(TT, name)]
    captured = capsys.readouterr()
    assert f"1 MISMATCH(ES) ({facts['rows']} rows)" in captured.out
    # every bench echoes its mismatching rows on stderr (the drift #425 closed:
    # the pull-up runner had dropped this printout)
    assert f"  {TT} {name}: committed=" in captured.err
    if bench in CHECKS:
        # the extracted leg still grades: the mismatch is schematic-only
        assert json.loads((stage / "grading.json").read_text())["all_pass"]


@pytest.mark.parametrize("bench", list(FACTS))
def test_rows_lifted_from_an_unrequested_corner_exit_3(tmp_path, monkeypatch, capsys, bench):
    """The count-only gap #425 closed: a passing envelope with the right number of
    rows and the committed reference value in each, but the requested binding
    corner replaced by a corner of the same reference the bench never asked for.
    sim/diff-receiver-pex's inline gate exited 0 on this shape; every entry point
    must now exit 3."""
    cfg, facts = cfg_of(bench), FACTS[bench]
    env = envelope_from_reference(cfg, corners=[TT, *facts["binding"][:-1], facts["unrequested"]])
    n_meas = len(measurements_of(cfg))
    assert len(env["delta"]) == facts["rows"] and env["status"] == "pass"  # what a count-only gate checks
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path / bench, env)
    assert rc == 3
    equiv = json.loads((stage / "equivalence.json").read_text())
    assert not equiv["equivalent"]
    verdicts = [r["verdict"] for r in equiv["rows"]]
    # Each substituted row produces one unexpected and one missing pair.
    assert sum(v.startswith("missing delta row") for v in verdicts) == n_meas
    assert sum(v.startswith("delta row is not a requested") for v in verdicts) == n_meas
    assert verdicts.count("ok") == facts["rows"] - n_meas
    assert f"{2 * n_meas} MISMATCH(ES) ({facts['rows'] + n_meas} rows)" in capsys.readouterr().out


@pytest.mark.parametrize(("results", "expected"), [((2, 3), 2), ((3, 4), 3), ((0, 4), 4)])
@pytest.mark.parametrize("argv", [[], ["--bench", "both"]])
def test_both_driver_benches_run_and_return_the_first_error(monkeypatch, argv, results, expected):
    calls = []
    outcomes = iter(results)

    def run_bench(cfg, args, repo):
        calls.append(cfg.variant)
        return next(outcomes)

    monkeypatch.setattr(pex_runner, "run_bench", run_bench)
    assert DRIVER.main(DRIVER.BENCHES, argv) == expected
    assert calls == ["static", "sq"]


@pytest.mark.parametrize("cfg", DRIVER.BENCHES, ids=lambda cfg: cfg.variant)
def test_driver_stages_negative_extracted_evidence(tmp_path, monkeypatch, cfg):
    # klt returns a nonzero exit for failing extracted rows. A returned envelope
    # still goes through the schematic equivalence gate and evidence staging.
    env = envelope_from_reference(cfg)
    env["delta"][0].update(status="fail", extracted_value=None)
    env.update(passed=len(env["delta"]) - 1, failed=1)
    fake_klt(monkeypatch, env, returncode=1)
    freeze_clock(monkeypatch)
    scratch = scratch_repo(tmp_path, cfg)
    stage = tmp_path / "work" / f"{RID}{cfg.suffix}"
    assert invoke(cfg, ["--stage-dir", str(stage.parent)], scratch) == 0
    assert json.loads((stage / "pex-envelope.json").read_text()) == env
    assert json.loads((stage / "equivalence.json").read_text())["equivalent"]


@pytest.mark.parametrize("bench", ["se-receiver-dp-pex", "se-receiver-dm-pex"])
def test_receiver_extracted_leg_failure_is_graded_not_exit_changing(
        tmp_path, monkeypatch, capsys, bench):
    """Preserved behavior: an extracted-leg bound violation FAILs its check in
    grading.json while the exit code stays 0 -- only equivalence sets exit 3."""
    cfg = cfg_of(bench)
    env = envelope_from_reference(
        cfg, extracted_tweak=((TT, "rxd_low_max_v"), lambda _v: 1.0))  # > 0.33 V
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path, env)
    assert rc == 0
    assert "extracted-leg grading: FAIL (16 checks)" in capsys.readouterr().out
    grading = json.loads((stage / "grading.json").read_text())
    assert not grading["all_pass"]
    failed = [c for corner in grading["corners"].values() for c in corner["checks"]
              if c["verdict"] == "FAIL"]
    assert [(c["corner_id"], c["check"]) for c in failed] == \
        [(TT, "rxd_low_max_v <= 0.1*VDD")]
    assert failed[0]["bound"] == "<= 0.33 V"


def test_pullup_trim_grading_pass_or_fail_never_changes_the_exit_code(
        tmp_path, monkeypatch, capsys):
    """The pull-up's own evaluator on the extracted leg, three ways, none of which
    moves the exit code (only equivalence sets exit 3): the committed schematic leg
    taken as the extracted leg trims into the window at both corners (PASS);
    halving every tt code voltage roughly doubles R_eff, so no code lands in the
    window (FAIL, best code reported); no tt code voltage at all is a FAIL that
    lists the problems instead of a best code."""
    cfg, binding = cfg_of("dplus-pullup-pex"), FACTS["dplus-pullup-pex"]["binding"][0]
    codes = {f"vdp_c{k:02d}_v" for k in range(16)}

    def tt_code_rows(delta):
        return [r for r in delta if r["corner_id"] == TT and r["spec_row"] in codes]

    def with_tt_codes(env, mutate):
        env = copy.deepcopy(env)
        for r in tt_code_rows(env["delta"]):
            r["extracted_value"] = mutate(r["extracted_value"])
        return env

    def trim_check(grading, cid):
        return grading["corners"][cid]["checks"][-1]

    base = envelope_from_reference(cfg)

    # PASS: every code finite-positive, 3 codes in the window at tt and 2 at the
    # binding corner; best codes as the committed bench's evaluator picks them
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path / "pass", base)
    out = capsys.readouterr().out
    grading = json.loads((stage / "grading.json").read_text())
    assert rc == 0 and grading["all_pass"]
    for cid, n_in, code, r_ohm in ((TT, 3, 8, 1480.33), (binding, 2, 14, 1467.41)):
        corner = grading["corners"][cid]
        assert corner["trim_problems"] == [] and len(corner["r_eff_ohm"]) == 16
        assert trim_check(grading, cid)["verdict"] == "pass"
        assert trim_check(grading, cid)["value"]["n_in_window"] == n_in
        assert trim_check(grading, cid)["value"]["best"]["code"] == code
        assert f"extracted trim at {cid}: PASS (best code {code}: {r_ohm:.2f} ohm)" in out

    # FAIL, nothing in the window: R_eff about doubles, every code still valid
    env = with_tt_codes(base, lambda v: v / 2)
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path / "fail-window", env)
    out = capsys.readouterr().out
    assert rc == 0  # a grading FAIL never sets the exit code
    grading = json.loads((stage / "grading.json").read_text())
    assert not grading["all_pass"]
    corner = grading["corners"][TT]
    assert trim_check(grading, TT)["verdict"] == "FAIL"
    assert trim_check(grading, TT)["value"]["n_in_window"] == 0
    assert all(r > 1575 for r in corner["r_eff_ohm"].values())
    assert len(corner["trim_problems"]) == 1
    assert corner["trim_problems"][0].startswith("no trim code inside [1425, 1575] ohm")
    assert all(c["verdict"] == "pass" for c in corner["checks"][:2])  # the voff bounds hold
    assert trim_check(grading, binding)["verdict"] == "pass"  # the other corner is untouched
    best = trim_check(grading, TT)["value"]["best"]
    assert f"extracted trim at {TT}: FAIL (best code {best['code']}: {best['r_ohm']:.2f} ohm)" in out
    assert f"extracted trim at {binding}: PASS (best code 14: 1467.41 ohm)" in out

    # FAIL, no valid code: every tt code voltage missing
    env = with_tt_codes(base, lambda _v: None)
    _, _, stage, rc = run_main(cfg, monkeypatch, tmp_path / "fail-missing", env)
    out = capsys.readouterr().out
    assert rc == 0
    grading = json.loads((stage / "grading.json").read_text())
    corner = grading["corners"][TT]
    assert trim_check(grading, TT)["verdict"] == "FAIL"
    assert trim_check(grading, TT)["value"] == {"n_in_window": 0, "best": None}
    assert corner["r_eff_ohm"] == {f"c{k:02d}": None for k in range(16)}
    assert corner["trim_problems"] == \
        [f"code {k}: no finite positive R_eff (V(DP)=None, VPU=3.3)" for k in range(16)]
    assert f"extracted trim at {TT}: FAIL {corner['trim_problems']}" in out


@pytest.mark.parametrize("bench", list(FACTS))
def test_second_write_of_the_same_run_id_is_refused(tmp_path, monkeypatch, bench):
    """Append-only, both ways: the direct snapshot writer raises, and a re-run of
    the same run id through the entry point surfaces it as exit 4 -- the refused
    re-run leaving the first write untouched."""
    cfg = cfg_of(bench)
    scratch = scratch_repo(tmp_path, cfg)
    composed = composed_snapshot(cfg, scratch)
    snap = pex_runner.write_snapshot(cfg, RID + cfg.suffix, scratch)
    assert snap == cfg.bench_dir(scratch) / "netlist-snapshots" / f"{RID}{cfg.suffix}.spice"
    assert snap.read_bytes() == composed
    with pytest.raises(FileExistsError, match="append-only"):
        pex_runner.write_snapshot(cfg, RID + cfg.suffix, scratch)
    assert snap.read_bytes() == composed
    fake_klt(monkeypatch, envelope_from_reference(cfg))
    freeze_clock(monkeypatch)
    rc = invoke(cfg, ["--stage-dir", str(tmp_path / "work")], repo=scratch)
    assert rc == 4
    assert snap.read_bytes() == composed


@pytest.mark.parametrize("bench", list(FACTS))
def test_dry_run_is_a_pre_flight_without_extraction(tmp_path, monkeypatch, capsys, bench):
    cfg = cfg_of(bench)
    calls = fake_klt(monkeypatch, None)
    freeze_clock(monkeypatch)
    scratch = scratch_repo(tmp_path, cfg)
    rc = invoke(cfg, ["--dry-run", "--stage-dir", str(tmp_path / "work")], repo=scratch)
    assert rc == 0
    cmd = calls[-1]
    assert "--dry-run" in cmd and "-o" not in cmd and "--envelope-out" not in cmd
    assert str(cfg.gds(scratch)) in cmd and cmd[cmd.index("--top") + 1] == cfg.leaf
    assert (tmp_path / "work" / f"dry-run{cfg.suffix}" / "dry-run-stdout.json").is_file()
    assert "dry-run: status=accepted" in capsys.readouterr().out
    assert not (cfg.bench_dir(scratch) / "netlist-snapshots").exists()


@pytest.mark.parametrize("bench", list(FACTS))
def test_klt_pex_failure_keeps_its_evidence_and_exits_2(tmp_path, monkeypatch, bench):
    """A refused klt pex call (non-zero exit, no envelope) keeps stdout/stderr under
    the stage dir as committed evidence and exits 2."""
    cfg = cfg_of(bench)
    freeze_clock(monkeypatch)

    def run(cmd, *a, **k):
        if cmd[0] == "git":
            return types.SimpleNamespace(returncode=0, stdout="deadbeef99\n", stderr="")
        return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(pex_runner.subprocess, "run", run)
    scratch = scratch_repo(tmp_path, cfg)
    rc = invoke(cfg, ["--stage-dir", str(tmp_path / "work")], repo=scratch)
    stage = tmp_path / "work" / (RID + cfg.suffix)
    assert rc == 2
    assert (stage / "pex-stderr.txt").read_text() == "boom"
    assert (stage / "command.txt").is_file()
    assert not (cfg.bench_dir(scratch) / "netlist-snapshots").exists()
