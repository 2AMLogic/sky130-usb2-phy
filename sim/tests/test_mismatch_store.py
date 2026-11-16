"""Mismatch Monte Carlo evidence goes to the artifact store: fail-closed run, manifest record, lint.

`klt artifact put`, the broker and every other klt verb are stubbed; nothing here reaches a store.
"""

import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from harness import evidence_store as es, matrix as mx, mismatch as mm, mismatch_lint as ml, runner
from test_mismatch import PINS, synth_spec, ymeas

REPO = Path(__file__).resolve().parents[2]
REAL_PREFLIGHT = es.preflight
ENV = {"open_pdks_commit": PINS["open_pdks_commit"], "lib_sha256": PINS["lib_sha256"], "lib": mm.LIB,
       "path": "/pdk/sky130A"}


@pytest.fixture
def tree(tmp_path, monkeypatch):
    sim = tmp_path / "sim"
    exp = sim / "x-mismatch"
    (exp / "testbench").mkdir(parents=True)
    (exp / "testbench/mc.json").write_text(json.dumps(synth_spec()))
    (exp / "testbench/t.spice").write_text("* deck\nXR2 a b L=14 mult=1\n")
    monkeypatch.setattr(mx, "SIM_DIR", sim)
    monkeypatch.setattr(runner, "WORK_DIR", sim / ".work")
    monkeypatch.setattr(runner, "check_env", lambda m: dict(ENV))
    monkeypatch.setattr(runner, "lib_sections", lambda lib: {"tt_mm"})
    monkeypatch.setattr(mm, "load_spec", lambda d: synth_spec())
    monkeypatch.setattr(mm, "_git", lambda *a: "abc1234")
    return exp


def written(exp):
    sim = exp.parent
    return sorted(str(p.relative_to(sim.parent)) for d in (sim, sim.parent / "manifests") if d.exists()
                  for p in d.rglob("*") if p.is_file() and ".work" not in p.parts)


@pytest.mark.parametrize("why", ["broker unset", "put verb missing", "broker unreachable"])
def test_unusable_store_fails_before_anything_is_submitted(tree, monkeypatch, why):
    def down():
        raise es.StoreUnavailable(why)

    monkeypatch.setattr(es, "preflight", down)
    monkeypatch.setattr(mm, "_run", lambda *a, **k: pytest.fail("a klt command ran before the store check"))
    before = written(tree)
    with pytest.raises(es.StoreUnavailable):
        mm.run("x-mismatch", "klt", None, None, 4, True)
    assert written(tree) == before and not (runner.WORK_DIR / "x-mismatch").exists()


def test_no_write_does_not_need_the_store(tree, monkeypatch):
    monkeypatch.setattr(es, "preflight", lambda: pytest.fail("--no-write must not touch the store"))
    monkeypatch.setattr(mm, "_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("submitted")))
    with pytest.raises(RuntimeError, match="submitted"):
        mm.run("x-mismatch", "klt", None, None, 4, False)


def test_real_preflight_broker_unset_blocks_a_recorded_run(tree, monkeypatch):
    monkeypatch.setattr(es, "preflight", REAL_PREFLIGHT)  # undo the conftest stub
    monkeypatch.delenv(es.BROKER_ENV, raising=False)
    with pytest.raises(es.StoreUnavailable, match="not set"):
        mm.run("x-mismatch", "klt", None, None, 4, True)


def test_run_mismatch_exits_4_when_store_unavailable(monkeypatch, capsys):
    sys.path.insert(0, str(REPO / "sim"))
    import run_mismatch

    def boom(*a, **k):
        raise es.StoreUnavailable("no broker")

    monkeypatch.setattr(mm, "run", boom)
    assert run_mismatch.main(["diff-receiver-mismatch"]) == 4
    assert "nothing was recorded" in capsys.readouterr().err


# ---- grading + recording with every klt verb stubbed -----------------------------------------

def graded(tree, monkeypatch):
    spec = synth_spec()
    rid = "20261023-120000-abc1234"
    work = runner.WORK_DIR / "x-mismatch" / rid
    work.mkdir(parents=True, exist_ok=True)
    (work / "klt-stderr.txt").write_text("")
    (work / "klt-batch-set.json").write_text("{}")
    campaigns = []
    for kind in ("nominal", "control"):
        stem = mm.campaign_stem("r", "tt", kind)
        (work / f"{stem}.spice").write_text(f"* {kind}\n")
        (work / f"{stem}.request.json").write_text("{}")
        (work / f"{stem}.report.json").write_text("{}")
        campaigns.append({"receiver": "r", "corner": "tt", "kind": kind, "stem": stem, "job_ids": ["j"],
                          "report": work / f"{stem}.report.json", "exec_pdk": {}})
    yld = {"status": "pass", "measurements": [ymeas("vth"), ymeas("lvl", negative_control=None)]}

    def fake_run(cmd, cwd, env=None):
        out = json.dumps(yld) if cmd[1] == "yield" else "{}"
        return type("P", (), {"returncode": 0, "stdout": out, "stderr": ""})()

    monkeypatch.setattr(mm, "_run", fake_run)
    monkeypatch.setattr(runner, "tool_version", lambda c: "klt test")
    return spec, rid, work, campaigns


def record(tree, monkeypatch):
    spec, rid, work, campaigns = graded(tree, monkeypatch)
    status = mm._grade_and_record(spec, tree, work, rid, __import__("datetime").datetime.now(), "klt", ENV,
                                  campaigns, [], True, "")
    return status, rid


def test_recorded_campaign_commits_manifest_and_record_but_no_raw_bytes(tree, monkeypatch):
    status, rid = record(tree, monkeypatch)
    assert status == 0
    assert not (tree / "campaigns").exists()
    man = json.loads(es.manifest_path("x-mismatch", rid).read_text())
    assert man["entries"] and all(e["uri"].startswith("artifact:") for e in man["entries"])
    assert f"x-mismatch/{rid}/evidence.json" in {e["name"] for e in man["entries"]}
    text = (tree / "records" / f"{rid}.md").read_text()
    assert "## Stored evidence" in text and "manifest sha256" in text and "/campaigns/" not in text
    assert sorted(written(tree)) == [f"manifests/artifacts/x-mismatch-{rid}.manifest.json",
                                     f"sim/x-mismatch/records/{rid}.md",
                                     "sim/x-mismatch/testbench/mc.json", "sim/x-mismatch/testbench/t.spice"]
    assert ml.lint_experiment(tree) == []


def test_put_failing_after_the_grid_commits_nothing_and_keeps_staged_bytes(tree, monkeypatch):
    n = {"k": 0}
    real = es.put_file

    def flaky(path, name, manifest):
        n["k"] += 1
        if n["k"] == 4:
            raise es.StoreUnavailable("klt artifact put failed (exit 1)")
        real(path, name, manifest)

    monkeypatch.setattr(es, "put_file", flaky)
    before = written(tree)
    with pytest.raises(es.StoreUnavailable):
        record(tree, monkeypatch)
    assert written(tree) == before
    assert list((runner.WORK_DIR / ".stage/x-mismatch").glob("*/evidence.json"))  # kept for a retry


def test_lint_flags_altered_manifest_and_committed_campaign_dir(tree, monkeypatch):
    _, rid = record(tree, monkeypatch)
    mp = es.manifest_path("x-mismatch", rid)
    (tree / "campaigns" / rid).mkdir(parents=True)
    assert any("campaigns/" in p and "stored evidence" in p for p in ml.lint_experiment(tree))
    (tree / "campaigns" / rid).rmdir()
    mp.write_text(mp.read_text() + "\n")
    assert any("sha256 does not match" in p for p in ml.lint_experiment(tree))
    mp.unlink()
    assert any("is missing" in p for p in ml.lint_experiment(tree))


def test_rerun_of_a_stored_record_is_refused(tree, monkeypatch):
    _, rid = record(tree, monkeypatch)
    with pytest.raises(mm.MismatchError, match="append-only"):
        record(tree, monkeypatch)


def test_historical_mismatch_records_are_unchanged_by_the_new_rules():
    assert ml.lint_all(REPO / "sim") == []


# ---- stored-path corner-coverage lint (#292) --------------------------------------------------

RID = "20261114-120000-abc1234"


def spec4():
    s = synth_spec()
    s["corners"] = [{"id": cid, "process": proc, "temperature_c": t, "supply_v": v, "basis": "b"}
                    for cid, proc, t, v in (("tt", "tt_mm", 27.0, 3.3), ("binding", "ff_mm", 100.0, 3.3),
                                            ("fs100v36", "fs_mm", 100.0, 3.6), ("sf40v36", "sf_mm", 40.0, 3.6))]
    return s


def make_exp(tmp_path, spec=None):
    spec = synth_spec() if spec is None else spec
    exp = tmp_path / "sim" / "x-mismatch"
    (exp / "testbench").mkdir(parents=True, exist_ok=True)
    (exp / "testbench/mc.json").write_text(json.dumps(spec))
    return exp


def entry(name, body=b"x"):
    sha = hashlib.sha256(body).hexdigest()
    return {"name": name, "sha256": sha, "size": max(len(body), 1), "kind": "evidence",
            "producer": {"tool": "klt", "version": "test", "loom.repo": "r", "commit": "c"},
            "uri": f"artifact:store/{sha}"}


def write_manifest(repo, name, entries):
    path = repo / "manifests" / "artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "entries": entries}, indent=2) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def campaign_entries(rid, corners):
    return [entry(f"x-mismatch/{rid}/{mm.campaign_stem('r', c, k)}.request.json")
            for c in corners for k in ("nominal", "control")]


def sfields(rid=RID, corners_run=None, result="PASS -- ok", sha="0" * 64,
            manifest=f"x-mismatch-{RID}.manifest.json"):
    return {"Record ID": rid, "Status": "PASS",
            "Corners run": corners_run if corners_run is not None
            else "tt: tt_mm / 27 C / 3.3 V (covers all 1 corner(s) mc.json declares)",
            "Result": result,
            "Links": f"sim/x-mismatch/testbench/, manifests/artifacts/{manifest} (manifest sha256 `{sha}`)"}


def test_stored_full_coverage_record_passes(tmp_path):
    exp = make_exp(tmp_path)
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [mc_entry := entry(f"x-mismatch/{RID}/mc.json",
                                             (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    assert ml.stored_coverage(sfields(sha=msha), RID, exp, tmp_path) == []


def test_stored_corner_scoped_record_passes(tmp_path):
    exp = make_exp(tmp_path, spec4())
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    clause = ("covers 1 of the 4 corner(s) mc.json declares and makes no claim about "
              "`binding`, `fs100v36`, `sf40v36`")
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert problems == []


def test_stored_record_declaring_fewer_corners_than_its_manifest_shows_is_rejected(tmp_path):
    exp = make_exp(tmp_path, spec4())
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt", "binding", "fs100v36", "sf40v36"])])
    clause = "covers 1 of the 4 corner(s) mc.json declares and makes no claim about `binding`, `fs100v36`, `sf40v36`"
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("does not claim to cover" in p and "binding" in p for p in problems), problems


def test_stored_coverage_declaration_fails_closed(tmp_path):
    exp = make_exp(tmp_path)
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    empty = ml.stored_coverage(sfields(sha=msha, corners_run="no corner declarations here"),
                               RID, exp, tmp_path)
    assert any(f"{RID}: Corners run must declare the corners it covers" in p for p in empty), empty
    unknown = ml.stored_coverage(sfields(sha=msha, corners_run="zz: tt_mm / 27 C / 3.3 V"),
                                 RID, exp, tmp_path)
    assert any(f"{RID}: Corners run covers corner(s) ['zz'], which the live mc.json does not declare" in p
               for p in unknown), unknown
    dup = ml.stored_coverage(sfields(sha=msha, corners_run="tt: tt_mm / 27 C / 3.3 V; tt: tt_mm / 27 C / 3.3 V"),
                             RID, exp, tmp_path)
    assert any(f"{RID}: Corners run declares covered corner 'tt' more than once" in p for p in dup), dup


def test_stored_record_claims_corner_with_no_manifest_evidence(tmp_path):
    exp = make_exp(tmp_path, spec4())
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    clause = "covers 2 of the 4 corner(s) mc.json declares and makes no claim about `fs100v36`, `sf40v36`"
    problems = ml.stored_coverage(
        sfields(sha=msha,
                corners_run=f"tt: tt_mm / 27 C / 3.3 V; binding: ff_mm / 100 C / 3.3 V ({clause})",
                result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("shows no campaign evidence" in p and "binding" in p for p in problems), problems


def test_stored_manifest_without_campaign_objects_fails_closed(tmp_path):
    exp = make_exp(tmp_path)
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           entry(f"x-mismatch/{RID}/evidence.json")])
    problems = ml.stored_coverage(sfields(sha=msha), RID, exp, tmp_path)
    assert any("no mismatch campaign object" in p for p in problems), problems


def test_stored_byte_exact_definition_mismatch_is_rejected(tmp_path):
    exp = make_exp(tmp_path)
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    problems = ml.stored_coverage(sfields(sha=msha, corners_run="tt: ff_mm / 27 C / 3.3 V"),
                                  RID, exp, tmp_path)
    assert any(f"{RID}: covered corner 'tt' differs from the corner the live mc.json declares" in p
               for p in problems), problems
    unparseable = ml.stored_coverage(sfields(sha=msha, corners_run="tt: not-a-definition"),
                                     RID, exp, tmp_path)
    assert any("cannot be compared" in p for p in unparseable), unparseable


def test_stored_degraded_mode_still_checks_ids_and_clause(tmp_path):
    exp = make_exp(tmp_path, spec4())
    clause = "covers 1 of the 4 corner(s) mc.json declares and makes no claim about `binding`, `fs100v36`, `sf40v36`"
    sha1 = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", b"frozen-but-different"),
                           *campaign_entries(RID, ["tt"])])
    assert ml.stored_coverage(sfields(sha=sha1, corners_run=f"tt: zz_mm / 99 C / 9.9 V ({clause})",
                                      result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path) == []
    sha2 = write_manifest(tmp_path, f"x-mismatch-{RID}-b.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", b"frozen-but-different"),
                           *campaign_entries(RID, ["tt", "binding"])])
    problems = ml.stored_coverage(sfields(sha=sha2, manifest=f"x-mismatch-{RID}-b.manifest.json",
                                          corners_run=f"tt: zz_mm / 99 C / 9.9 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("does not claim to cover" in p and "binding" in p for p in problems), problems


def test_stored_coverage_clause_disagreeing_with_declaration_is_rejected(tmp_path):
    exp = make_exp(tmp_path, spec4())
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    problems = ml.stored_coverage(sfields(sha=msha, corners_run="tt: tt_mm / 27 C / 3.3 V "
                                                          "(covers all 4 corner(s) mc.json declares)"),
                                  RID, exp, tmp_path)
    assert any("claims full coverage of 4 corner(s) but the record declares 1 of the 4" in p
               for p in problems), problems


def test_stored_degraded_mode_ignores_a_corner_added_to_the_live_spec_after_mint(tmp_path):
    exp = make_exp(tmp_path, spec4())
    frozen = (exp / "testbench/mc.json").read_bytes()
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", frozen),
                           *campaign_entries(RID, ["tt"])])
    spec = json.loads((exp / "testbench/mc.json").read_text())
    spec["corners"].append({"id": "ss125v30", "process": "ss_mm", "temperature_c": 125.0,
                            "supply_v": 3.0, "basis": "b"})
    (exp / "testbench/mc.json").write_text(json.dumps(spec))
    clause = ("covers 1 of the 4 corner(s) mc.json declares and makes no claim about "
              "`binding`, `fs100v36`, `sf40v36`")
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert problems == [], problems


def test_stored_degraded_mode_full_coverage_clause_is_internal_only(tmp_path):
    exp = make_exp(tmp_path, spec4())
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", b"frozen-but-different"),
                           *campaign_entries(RID, ["tt"])])
    problems = ml.stored_coverage(sfields(sha=msha, corners_run="tt: tt_mm / 27 C / 3.3 V "
                                                           "(covers all 1 corner(s) mc.json declares)"),
                                  RID, exp, tmp_path)
    assert problems == [], problems
    problems = ml.stored_coverage(sfields(sha=msha, corners_run="tt: tt_mm / 27 C / 3.3 V "
                                                           "(covers all 4 corner(s) mc.json declares)"),
                                  RID, exp, tmp_path)
    assert any("claims full coverage of 4 corner(s) but the record declares 1 of them" in p
               for p in problems), problems
    problems = ml.stored_coverage(sfields(sha=msha, corners_run="tt: tt_mm / 27 C / 3.3 V "
                                                           "(covers all 1 corner(s) mc.json declares and "
                                                           "makes no claim about `binding`)"),
                                  RID, exp, tmp_path)
    assert any("claims full coverage but also makes no claim about ['binding']" in p
               for p in problems), problems


def test_stored_degraded_mode_clause_internal_inconsistency_is_rejected(tmp_path):
    exp = make_exp(tmp_path, spec4())
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", b"frozen-but-different"),
                           *campaign_entries(RID, ["tt"])])
    problems = ml.stored_coverage(sfields(sha=msha, corners_run="tt: tt_mm / 27 C / 3.3 V "
                                                           "(covers 2 of the 4 corner(s) mc.json declares)"),
                                  RID, exp, tmp_path)
    assert any("claims 2 of the 4 corner(s) but the record declares 1 of them" in p
               for p in problems), problems
    clause = "covers 1 of the 4 corner(s) mc.json declares and makes no claim about `binding`, `fs100v36`"
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("makes no claim about ['binding', 'fs100v36'] but the clause leaves 3 corner(s) unclaimed" in p
               for p in problems), problems
    clause = ("covers 1 of the 4 corner(s) mc.json declares and makes no claim about "
              "`tt`, `binding`, `fs100v36`")
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("makes no claim about ['tt'] but Corners run declares it covered" in p
               for p in problems), problems
    clause = ("covers 1 of the 4 corner(s) mc.json declares and makes no claim about "
              "`binding`, `binding`, `fs100v36`")
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("makes no claim about ['binding', 'fs100v36'] but names a corner more than once" in p
               for p in problems), problems


def test_stored_byte_exact_mode_still_rejects_a_clause_stale_against_the_live_spec(tmp_path):
    exp = make_exp(tmp_path, spec4())
    spec = json.loads((exp / "testbench/mc.json").read_text())
    spec["corners"].append({"id": "ss125v30", "process": "ss_mm", "temperature_c": 125.0,
                            "supply_v": 3.0, "basis": "b"})
    (exp / "testbench/mc.json").write_text(json.dumps(spec))
    msha = write_manifest(tmp_path, f"x-mismatch-{RID}.manifest.json",
                          [entry(f"x-mismatch/{RID}/mc.json", (exp / "testbench/mc.json").read_bytes()),
                           *campaign_entries(RID, ["tt"])])
    clause = ("covers 1 of the 4 corner(s) mc.json declares and makes no claim about "
              "`binding`, `fs100v36`, `sf40v36`")
    problems = ml.stored_coverage(sfields(sha=msha, corners_run=f"tt: tt_mm / 27 C / 3.3 V ({clause})",
                                          result=f"PASS -- ok -- this record {clause}"), RID, exp, tmp_path)
    assert any("claims 1 of the 4 corner(s) but the record declares 1 of the 5 the live mc.json declares" in p
               for p in problems), problems


@pytest.fixture
def tree4(tmp_path, monkeypatch):
    sim = tmp_path / "sim"
    exp = sim / "x-mismatch"
    (exp / "testbench").mkdir(parents=True)
    (exp / "testbench/mc.json").write_text(json.dumps(spec4()))
    monkeypatch.setattr(mx, "SIM_DIR", sim)
    monkeypatch.setattr(runner, "WORK_DIR", sim / ".work")
    monkeypatch.setattr(runner, "check_env", lambda m: dict(ENV))
    monkeypatch.setattr(runner, "lib_sections", lambda lib: {"tt_mm"})
    monkeypatch.setattr(mm, "load_spec", lambda d: spec4())
    monkeypatch.setattr(mm, "_git", lambda *a: "abc1234")
    return exp


def graded4(tree4, monkeypatch, corners, rid="20261114-130000-abc1234"):
    spec = spec4()
    work = runner.WORK_DIR / "x-mismatch" / rid
    work.mkdir(parents=True, exist_ok=True)
    (work / "klt-stderr.txt").write_text("")
    (work / "klt-batch-set.json").write_text("{}")
    campaigns = []
    for c in corners:
        for kind in ("nominal", "control"):
            stem = mm.campaign_stem("r", c, kind)
            (work / f"{stem}.spice").write_text(f"* {kind}\n")
            (work / f"{stem}.request.json").write_text("{}")
            (work / f"{stem}.report.json").write_text("{}")
            campaigns.append({"receiver": "r", "corner": c, "kind": kind, "stem": stem, "job_ids": ["j"],
                              "report": work / f"{stem}.report.json", "exec_pdk": {}})
    yld = {"status": "pass", "measurements": [ymeas("vth"), ymeas("lvl", negative_control=None)]}

    def fake_run(cmd, cwd, env=None):
        out = json.dumps(yld) if cmd[1] == "yield" else "{}"
        return type("P", (), {"returncode": 0, "stdout": out, "stderr": ""})()

    monkeypatch.setattr(mm, "_run", fake_run)
    monkeypatch.setattr(runner, "tool_version", lambda c: "klt test")
    return spec, rid, work, campaigns


def test_corner_scoped_stored_record_lints_clean_end_to_end(tree4, monkeypatch):
    spec, rid, work, campaigns = graded4(tree4, monkeypatch, ["tt"])
    status = mm._grade_and_record(spec, tree4, work, rid, datetime.datetime.now(), "klt", ENV,
                                  campaigns, [], True, "", None, [spec["corners"][0]])
    assert status == 0
    assert ml.lint_experiment(tree4) == []


def test_full_stored_record_edited_to_under_declare_is_rejected(tree4, monkeypatch):
    spec, rid, work, campaigns = graded4(tree4, monkeypatch, ["tt", "binding", "fs100v36", "sf40v36"])
    status = mm._grade_and_record(spec, tree4, work, rid, datetime.datetime.now(), "klt", ENV,
                                  campaigns, [], True, "")
    assert status == 0
    assert ml.lint_experiment(tree4) == []  # as minted: full coverage, byte-exact frozen spec
    rec = tree4 / "records" / f"{rid}.md"
    clause = ("covers 1 of the 4 corner(s) mc.json declares and makes no claim about "
              "`binding`, `fs100v36`, `sf40v36`")
    text = re.sub(r"(?m)^- \*\*Corners run\*\*:.*$",
                  f"- **Corners run**: tt: tt_mm / 27 C / 3.3 V ({clause}; each corner a separate "
                  "Monte Carlo population)", rec.read_text())
    text = re.sub(r"(?m)^- \*\*Result\*\*:.*$",
                  f"- **Result**: PASS -- every row measurement meets its yield claim -- this record {clause}",
                  text)
    rec.write_text(text)
    problems = ml.lint_experiment(tree4)
    assert any("does not claim to cover" in p and "binding" in p for p in problems), problems
