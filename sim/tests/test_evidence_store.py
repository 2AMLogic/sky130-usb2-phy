"""Artifact-store evidence path: fail-closed preflight, store failures, manifest records, manifest lint.

`klt artifact put` and the broker are always stubbed (conftest.py); nothing here reaches a store.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness import artifact_manifest as am, evidence_lint as lint, evidence_store as es, runner
from test_harness import sandbox, stub_klt  # noqa: F401  (fixtures)

REPO = Path(__file__).resolve().parents[2]
REAL_PREFLIGHT = es.preflight
RID = r"\d{8}-\d{6}-[0-9a-f]{7}"


# ---- preflight: every failure mode fails closed, before simulating ----------------------------

def test_preflight_broker_unset(monkeypatch):
    monkeypatch.delenv(es.BROKER_ENV, raising=False)
    with pytest.raises(es.StoreUnavailable, match="KLT_ARTIFACT_BROKER"):
        REAL_PREFLIGHT()


def test_preflight_klt_missing(monkeypatch):
    monkeypatch.setenv(es.BROKER_ENV, "http://127.0.0.1:9")
    monkeypatch.setattr(es.shutil, "which", lambda n: None)
    with pytest.raises(es.StoreUnavailable, match="klt not found"):
        REAL_PREFLIGHT()


def test_preflight_put_verb_missing(monkeypatch):
    monkeypatch.setenv(es.BROKER_ENV, "http://127.0.0.1:9")
    monkeypatch.setattr(es.shutil, "which", lambda n: "/bin/klt")
    monkeypatch.setattr(es.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 2, "", "invalid choice"))
    with pytest.raises(es.StoreUnavailable, match="no `artifact put` verb"):
        REAL_PREFLIGHT()


def test_preflight_broker_unreachable_and_url_never_echoed(monkeypatch):
    url = "http://127.0.0.1:9/secret-path"
    monkeypatch.setenv(es.BROKER_ENV, url)
    monkeypatch.setattr(es.shutil, "which", lambda n: "/bin/klt")
    monkeypatch.setattr(es.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))

    def refuse(*a, **k):
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr(es.socket, "create_connection", refuse)
    with pytest.raises(es.StoreUnavailable, match="unreachable") as ei:
        REAL_PREFLIGHT()
    assert "secret-path" not in str(ei.value)


def written(sim):
    return sorted(str(p.relative_to(sim.parent)) for d in (sim, sim.parent / "manifests") if d.exists()
                  for p in d.rglob("*") if p.is_file())


def test_unusable_store_fails_before_any_simulation(sandbox, monkeypatch, tmp_path):
    calls = stub_klt(monkeypatch, tmp_path)
    before = written(sandbox)

    def down():
        raise es.StoreUnavailable("broker unreachable")

    monkeypatch.setattr(es, "preflight", down)
    with pytest.raises(es.StoreUnavailable):
        runner.run("smoke-inverter", "batch", True, {})
    assert calls == []  # klt sim never invoked
    assert written(sandbox) == before and not (sandbox.parent / "manifests").exists()


def test_put_failing_after_the_grid_commits_nothing_and_keeps_staged_bytes(sandbox, monkeypatch, tmp_path):
    stub_klt(monkeypatch, tmp_path)
    n = {"k": 0}
    real = es.put_file

    def flaky(path, name, manifest):
        n["k"] += 1
        if n["k"] == 3:
            raise es.StoreUnavailable("klt artifact put failed (exit 1)")
        real(path, name, manifest)

    monkeypatch.setattr(es, "put_file", flaky)
    before = written(sandbox)
    with pytest.raises(es.StoreUnavailable):
        runner.run("smoke-inverter", "batch", True, {})
    assert written(sandbox) == before
    assert not (sandbox.parent / "manifests").exists()
    staged = list((sandbox.parent / "work/.stage/smoke-inverter").glob("*/*.log"))
    assert len(staged) == 45  # kept for a retry


def test_run_corners_exits_4_when_store_unavailable(monkeypatch, capsys):
    sys.path.insert(0, str(REPO / "sim"))
    import run_corners

    def boom(*a, **k):
        raise es.StoreUnavailable("no broker")

    monkeypatch.setattr(runner, "run", boom)
    assert run_corners.main(["smoke-inverter"]) == 4
    assert "nothing was recorded" in capsys.readouterr().err


# ---- the stored-evidence record ----------------------------------------------------------------

def new_record(sandbox):
    recs = sorted((sandbox / "smoke-inverter/records").glob("*.md"))
    return recs[-1]


def test_recorded_run_writes_manifest_summary_and_no_raw_bytes(sandbox, monkeypatch, tmp_path):
    stub_klt(monkeypatch, tmp_path)
    assert runner.run("smoke-inverter", "batch", True, {}) == 0
    rec = new_record(sandbox)
    rid = rec.stem
    assert not (sandbox / "smoke-inverter/corners" / rid).exists()
    assert (sandbox / "smoke-inverter/netlist-snapshots" / f"{rid}.spice").is_file()
    man = json.loads(es.manifest_path("smoke-inverter", rid).read_text())
    assert man["entries"] and all(e["uri"].startswith("artifact:") for e in man["entries"])
    names = {e["name"] for e in man["entries"]}
    assert f"smoke-inverter/{rid}/evidence.json" in names and len(names) >= 45  # the empty klt-stderr.txt is listed in the table, not stored
    text = rec.read_text()
    assert "## Stored evidence" in text and "manifest sha256" in text and "corners/" not in text.split("**Links**")[1].split("\n")[0]
    assert lint.lint_all(sandbox) == []


def test_zero_byte_file_is_listed_not_stored(sandbox, monkeypatch, tmp_path):
    stage = tmp_path / "st"
    stage.mkdir()
    (stage / "a.txt").write_bytes(b"abc")
    (stage / "empty.txt").write_bytes(b"")
    rows = es.store_files("smoke-inverter", "20261023-000000-abcdef0",
                          {"b/r/a.txt": stage / "a.txt", "b/r/empty.txt": stage / "empty.txt"}, tmp_path / "m.json")
    assert {r["name"]: r["size"] for r in rows} == {"b/r/a.txt": 3, "b/r/empty.txt": 0}
    assert len(json.loads(es.manifest_path("smoke-inverter", "20261023-000000-abcdef0").read_text())["entries"]) == 1


def test_rerun_of_a_stored_manifest_is_refused(sandbox, monkeypatch, tmp_path):
    stub_klt(monkeypatch, tmp_path)
    runner.run("smoke-inverter", "batch", True, {})
    rid = new_record(sandbox).stem
    with pytest.raises(es.StoreUnavailable, match="append-only"):
        es.store_files("smoke-inverter", rid, {}, tmp_path / "other.json")


# ---- lint of manifest-based records -----------------------------------------------------------

@pytest.fixture
def stored(sandbox, monkeypatch, tmp_path):
    stub_klt(monkeypatch, tmp_path)
    runner.run("smoke-inverter", "batch", True, {})
    rec = new_record(sandbox)
    return sandbox, rec, es.manifest_path("smoke-inverter", rec.stem)


def reseal(rec, mp):
    sha = hashlib.sha256(mp.read_bytes()).hexdigest()
    rec.write_text(re.sub(r"manifest sha256 `[0-9a-f]{64}`", f"manifest sha256 `{sha}`", rec.read_text()))


def test_lint_flags_missing_or_altered_manifest(stored):
    sim, rec, mp = stored
    mp.write_text(mp.read_text() + "\n")
    assert any("sha256 does not match" in p for p in lint.lint_all(sim))
    mp.unlink()
    assert any("is missing" in p for p in lint.lint_all(sim))


def test_lint_flags_table_manifest_disagreement(stored):
    sim, rec, mp = stored
    rec.write_text("\n".join(l for l in rec.read_text().splitlines() if "evidence.json`" not in l or "|" not in l) + "\n")
    assert any("lacks manifest object" in p for p in lint.lint_all(sim))


def test_lint_rejects_committed_corners_next_to_a_stored_record(stored):
    sim, rec, mp = stored
    (sim / "smoke-inverter/corners" / rec.stem).mkdir(parents=True)
    assert any("corners/" in p and "stored evidence" in p for p in lint.lint_all(sim))


def test_lint_rejects_non_artifact_uri_and_storage_locations(stored):
    sim, rec, mp = stored
    m = json.loads(mp.read_text())
    m["entries"][0]["uri"] = "s3://bucket/key"
    mp.write_text(json.dumps(m))
    reseal(rec, mp)
    probs = lint.lint_all(sim)
    assert any("not artifact:<key>" in p for p in probs) and any("storage location" in p for p in probs)


def test_manifest_append_only_is_enforced(tmp_path):
    r = tmp_path / "r"
    (r / "manifests/artifacts").mkdir(parents=True)
    (r / "sim").mkdir()
    (r / "manifests/artifacts/x.manifest.json").write_text("{}")
    g = ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*g, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "commit", "-qm", "b"], check=True)
    subprocess.run([*g, "branch", "base"], check=True)
    (r / "manifests/artifacts/x.manifest.json").write_text("{ }")
    assert any("append-only" in p and "x.manifest.json" in p for p in lint.check_append_only(r, "base"))


def test_historical_records_are_unchanged_by_the_new_rules():
    assert lint.lint_all(REPO / "sim") == []


# ---- scripts/check_artifact_manifests.py ------------------------------------------------------

def entry(name, data, uri=None):
    sha = hashlib.sha256(data).hexdigest()
    return {"sha256": sha, "size": len(data), "kind": "evidence",
            "producer": {"tool": "klt", "version": "x", "loom.repo": "o/r", "commit": None},
            "uri": uri or f"artifact:evidence/o__r/{sha}", "name": name}


def make_repo(tmp_path, entries, files=None):
    r = tmp_path / "repo"
    (r / "manifests/artifacts").mkdir(parents=True)
    (r / "manifests/artifacts/b-run.manifest.json").write_text(
        json.dumps({"schema_version": 1, "entries": entries}))
    for rel, data in (files or {}).items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_bytes(data)
    g = ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*g, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "commit", "-qm", "b"], check=True)
    return r


def test_check_accepts_a_clean_manifest(tmp_path):
    r = make_repo(tmp_path, [entry("b/run/x.log", b"stored bytes")], {"sim/b/testbench/tb.json": b"{}"})
    assert am.check_repo(r) == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e.update(uri="s3://bucket/" + e["sha256"]), "not artifact:<key>"),
    (lambda e: e.update(uri="https://x.example/" + e["sha256"]), "not artifact:<key>"),
    (lambda e: e.pop("kind"), "missing kind"),
    (lambda e: e.update(size=0), "positive integer"),
    (lambda e: e.update(extra=1), "unknown field"),
    (lambda e: e.update(uri="artifact:evidence/o__r/" + "0" * 64), "does not end in"),
])
def test_check_rejects_bad_entries(tmp_path, mutate, needle):
    e = entry("b/run/x.log", b"stored bytes")
    mutate(e)
    r = make_repo(tmp_path, [e])
    assert any(needle in p for p in am.check_repo(r))


def test_check_rejects_committed_bytes_by_sha_and_by_name(tmp_path):
    data = b"ngspice log contents"
    by_sha = make_repo(tmp_path / "a", [entry("b/run/x.log", data)], {"sim/b/corners/run/other.log": data})
    assert any("has its bytes committed" in p for p in am.check_repo(by_sha))
    by_name = make_repo(tmp_path / "b", [entry("b/run/x.log", data)], {"sim/b/corners/run/x.log": b"different"})
    assert any("also committed" in p for p in am.check_repo(by_name))


def test_frozen_copy_of_a_committed_source_is_not_a_duplicate(tmp_path):
    tb = b'{"tb": 1}'
    r = make_repo(tmp_path, [entry("b/run/tb.json", tb)], {"sim/b/testbench/tb.json": tb})
    assert am.check_repo(r) == []


def test_cli_exit_codes(tmp_path):
    ok = make_repo(tmp_path / "a", [entry("b/run/x.log", b"abc")])
    bad = make_repo(tmp_path / "b", [entry("b/run/x.log", b"abc", uri="s3://b/k")])
    script = str(REPO / "scripts/check_artifact_manifests.py")
    assert subprocess.run([sys.executable, script, str(ok)], capture_output=True).returncode == 0
    assert subprocess.run([sys.executable, script, str(bad)], capture_output=True).returncode == 1


# ---- gitignore and repo hygiene ----------------------------------------------------------------

def test_new_corner_logs_and_stage_are_git_ignored():
    for rel in ("sim/smoke-inverter/corners/20990101-000000-abcdef0/tt_27c_3.30v.log",
                "sim/.work/.stage/smoke-inverter/x/report.json"):
        r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", rel])
        assert r.returncode == 0, rel


def test_no_storage_locations_in_committed_manifests():
    r = subprocess.run(["git", "-C", str(REPO), "grep", "-nE", "s3://|arn:aws:", "--", "manifests/"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and r.stdout == ""


def test_store_cli_refuses_a_tracked_staging_dir(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(REPO / "sim"))
    import run_store_evidence

    monkeypatch.setattr(es, "preflight", lambda: (_ for _ in ()).throw(AssertionError("must refuse first")))
    assert run_store_evidence.main(["smoke-inverter", str(REPO / "sim/smoke-inverter/testbench")]) == 3
    assert "tracked tree" in capsys.readouterr().err
