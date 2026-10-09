"""Toolchain-free tests: matrix, request, result validation, mocked batch runner.

No klt, ngspice or PDK is needed; `klt sim` is replaced by a stub.
"""

import copy
import json
import math
import shutil
from pathlib import Path

import pytest

from harness import evidence_lint as lint, matrix as mx, results as rs, runner

SIM = Path(__file__).resolve().parents[1]
TB = json.loads((SIM / "smoke-inverter/testbench/tb.json").read_text())
MATRIX = mx.load()


def test_matrix_is_exactly_45_unique_sky130_tuples():
    pts = MATRIX.points()
    assert len(pts) == len({mx.key(*p) for p in pts}) == 45
    assert set(MATRIX.process) == {"tt", "ff", "ss", "fs", "sf"}
    assert set(MATRIX.temperature_c) == {-40, 27, 100}
    assert set(MATRIX.supply_v) == {3.0, 3.3, 3.6}
    assert MATRIX.pdk["name"] == "sky130A" and MATRIX.pdk["lib"].endswith("sky130.lib.spice")


def test_request_is_the_matrix_and_has_no_inherited_gf180_defaults():
    req = rs.build_request(TB, MATRIX, backend="batch")
    assert mx.check_request(req, MATRIX) == []
    text = json.dumps(req)
    for banned in ("sm141064", "gf180", "typical", "125", "2.97", "3.63"):
        assert banned not in text
    assert req["backend"] == "batch"


def test_gf180_style_request_is_rejected():
    req = rs.build_request(TB, MATRIX, backend="batch")
    req["models"] = {"pdk": "gf180mcuD", "lib": "libs.tech/ngspice/sm141064.ngspice"}
    req["corners"]["process"] = ["typical", "ff", "ss", "fs", "sf"]
    req["corners"]["temperature_c"] = [-40, 27, 125]
    req["corners"]["supply_v"] = {"vsup": [2.97, 3.3, 3.63]}
    problems = mx.check_request(req, MATRIX)
    assert any("models.pdk" in p for p in problems)
    assert any("models.lib" in p for p in problems)
    assert any("differ from corners.json" in p for p in problems)


def test_duplicate_or_dropped_tuple_is_rejected():
    req = rs.build_request(TB, MATRIX, backend="batch")
    req["corners"]["temperature_c"] = [-40, 27, 27]
    assert any("duplicate" in p for p in mx.check_request(req, MATRIX))
    req["corners"]["temperature_c"] = [-40, 27]
    assert any("differ" in p for p in mx.check_request(req, MATRIX))


def fake_report(points=None, tamper=None):
    corners = []
    for p, t, v in points or MATRIX.points():
        meas = {"voh_v": v, "vol_v": 1e-9, "vm_v": v * (0.45 + 0.01 * MATRIX.process.index(p)), "isup_ua": 50.0}
        corners.append({
            "corner_id": f"{p}/{v:.3f}V/{t:g}C", "process": p, "supply_v": {"vsup": v},
            "temperature_c": float(t), "status": "pass",
            "measurements": [{"name": n, "value": x * (-1e-6 if n == "isup_ua" else 1.0), "status": "pass"}
                             for n, x in meas.items()],
            "artifacts": {"log": None},
        })
    report = {"status": "pass", "corners": corners,
              "environment": {"engine_version": "46", "remote": {"job_id": "klt-sim-test"},
                              "models_lib_sha256": MATRIX.pdk["lib_sha256"],
                              "netlist_sha256": "x"},
              "provenance": {"pdk": {"version": "open_pdks " + MATRIX.pdk["open_pdks_commit"]}}}
    if tamper:
        tamper(report)
    return report


def test_complete_report_passes():
    results, problems = rs.evaluate(fake_report(), MATRIX.points(), TB)
    assert problems == [] and len(results) == 45 and all(r["status"] == "ok" for r in results)


@pytest.mark.parametrize("tamper,needle", [
    (lambda r: r["corners"].pop(), "missing from report"),
    (lambda r: r["corners"].append(copy.deepcopy(r["corners"][0])), "duplicate corner"),
    (lambda r: r["corners"][3].update(status="error"), "simulation status"),
    (lambda r: r["corners"][3]["measurements"][0].update(value=float("nan")), "non-finite"),
    (lambda r: r["corners"][3]["measurements"][1].update(value=None), "non-finite"),
    (lambda r: r["corners"][3]["measurements"].pop(), "missing or non-finite"),
    (lambda r: r["corners"][3]["measurements"][0].update(value=1.0), "below min"),
    (lambda r: r["corners"].append({**copy.deepcopy(r["corners"][0]), "temperature_c": 125.0}), "unexpected corner"),
])
def test_incomplete_or_failed_grid_never_passes(tamper, needle):
    _, problems = rs.evaluate(fake_report(tamper=tamper), MATRIX.points(), TB)
    assert any(needle in p for p in problems), problems


def test_flat_vm_means_corners_did_not_take_effect():
    def flatten(r):
        for c in r["corners"]:
            c["measurements"][2]["value"] = 0.5 * c["supply_v"]["vsup"]
    _, problems = rs.evaluate(fake_report(tamper=flatten), MATRIX.points(), TB)
    assert any("spread" in p for p in problems)


# ---- mocked runner ----------------------------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    sim = tmp_path / "sim"
    (sim / "smoke-inverter").mkdir(parents=True)
    shutil.copytree(SIM / "smoke-inverter/testbench", sim / "smoke-inverter/testbench")
    shutil.copy(SIM / "corners.json", sim / "corners.json")
    monkeypatch.setattr(mx, "SIM_DIR", sim)
    monkeypatch.setattr(mx, "CORNERS_JSON", sim / "corners.json")
    monkeypatch.setattr(runner, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(runner, "check_env", lambda m: {
        "open_pdks_commit": m.pdk["open_pdks_commit"], "lib_sha256": m.pdk["lib_sha256"]})
    return sim


def stub_klt(monkeypatch, tmp_path, report=None, error=None):
    calls = []

    def fake(request_path, outdir, backend, workdir):
        calls.append(backend)
        if error:
            raise runner.RunError(error)
        rep = copy.deepcopy(report or fake_report())
        for c in rep["corners"]:
            log = tmp_path / f"{c['process']}{c['temperature_c']}{c['supply_v']['vsup']}.log"
            log.write_text("ngspice log\n")
            c["artifacts"] = {"log": str(log)}
        body = (workdir / "body.spice").read_bytes()
        rep["environment"]["netlist_sha256"] = runner.sha256_bytes(body)
        return rep, "", 0

    monkeypatch.setattr(runner, "invoke_klt", fake)
    return calls


def test_batch_success_writes_a_record_the_lint_accepts(sandbox, monkeypatch, tmp_path):
    calls = stub_klt(monkeypatch, tmp_path)
    assert runner.run("smoke-inverter", "batch", True, {}) == 0
    assert calls == ["batch"]
    assert lint.lint_all(sandbox) == []
    rec = next((sandbox / "smoke-inverter/records").glob("*.md")).read_text()
    assert "- **Status**: PASS" in rec and "klt-sim-test" in rec


def test_backend_error_fails_without_any_local_run(sandbox, monkeypatch, tmp_path):
    calls = stub_klt(monkeypatch, tmp_path, error="batch submit failed: no credentials")
    real_run = runner.subprocess.run

    def guarded(cmd, *a, **k):
        if cmd[0] == "ngspice" or cmd[:2] == ["klt", "sim"]:
            raise AssertionError(f"a simulator was launched after a backend error: {cmd}")
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(runner.subprocess, "run", guarded)
    assert runner.run("smoke-inverter", "batch", True, {}) == 2
    assert calls == ["batch"]  # exactly one attempt, on batch, no fallback
    rec = next((sandbox / "smoke-inverter/records").glob("*.md")).read_text()
    assert "- **Status**: FAIL" in rec
    assert lint.lint_all(sandbox) == []  # a failed attempt is preserved, valid, failed evidence


def test_incomplete_batch_result_is_recorded_as_fail(sandbox, monkeypatch, tmp_path):
    rep = fake_report()
    rep["corners"].pop()
    stub_klt(monkeypatch, tmp_path, report=rep)
    assert runner.run("smoke-inverter", "batch", True, {}) == 1
    rec = next((sandbox / "smoke-inverter/records").glob("*.md")).read_text()
    assert "- **Status**: FAIL" in rec


def test_full_grid_cannot_run_locally_and_subsets_cannot_be_recorded(sandbox, monkeypatch, tmp_path):
    calls = stub_klt(monkeypatch, tmp_path)
    with pytest.raises(runner.RunError):
        runner.run("smoke-inverter", "local", False, {})
    with pytest.raises(runner.RunError):
        runner.run("smoke-inverter", "batch", True, {"process": ["tt"]})
    assert calls == []
