"""Mismatch Monte Carlo evidence goes to the artifact store: fail-closed run, manifest record, lint.

`klt artifact put`, the broker and every other klt verb are stubbed; nothing here reaches a store.
"""

import hashlib
import json
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
