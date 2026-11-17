import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import json  # noqa: E402

import pytest  # noqa: E402

from harness import artifact_manifest as _am, evidence_store as _es, matrix as _mx  # noqa: E402


def fake_put_file(path, name, manifest):
    """Stand-in for `klt artifact put`: appends a valid manifest entry, touches no network."""
    import hashlib

    data = Path(path).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    m = json.loads(manifest.read_text()) if manifest.exists() else {"schema_version": 1, "entries": []}
    m["entries"].append({"sha256": sha, "size": len(data), "kind": "evidence",
                         "producer": {"tool": "klt", "version": "test", "loom.repo": "o/r", "commit": None},
                         "uri": f"artifact:evidence/o__r/{sha}", "name": name})
    manifest.write_text(json.dumps(m, indent=2) + "\n")


@pytest.fixture(autouse=True)
def no_real_artifact_store(monkeypatch):
    """No test may reach the real artifact broker: stub the store client for every test."""
    monkeypatch.delenv(_es.BROKER_ENV, raising=False)
    monkeypatch.setattr(_es, "preflight", lambda: None)
    monkeypatch.setattr(_es, "put_file", fake_put_file)
    monkeypatch.setattr(_es.subprocess, "run", _guard(_es.subprocess.run))


def _guard(real):
    def run(cmd, *a, **k):
        if isinstance(cmd, list) and cmd[:3] == [_es.KLT, "artifact", "put"]:
            raise AssertionError("a test reached the real `klt artifact put`")
        return real(cmd, *a, **k)
    return run


# ---- synthetic `klt sim` report builders shared by the analog self-tests ----
# One pinned envelope shape: when the report `klt sim` emits gains or renames a
# field, this is the single place to update.

RL = 15000.0  # the full-speed host load a D+ pull-up drives (ohm)


def v_of(r, vpu):
    """V(DP) for an effective pull-up resistance r into the 15 kohm host load."""
    return vpu * RL / (RL + r)


def meas(rep, idx, name):
    """The measurement entry `name` in corner `idx` of a synthetic report."""
    return next(m for m in rep["corners"][idx]["measurements"] if m["name"] == name)


def corner_envelope(point, measurements, *, status="pass"):
    """One `klt sim` corner envelope; `measurements` is the per-corner {name: value} dict."""
    p, t, v = point
    return {
        "corner_id": f"{p}/{v:.3f}V/{t:g}C", "process": p, "supply_v": {"vsup": v},
        "temperature_c": float(t), "status": status,
        "measurements": [{"name": n, "value": x, "status": "pass"} for n, x in measurements.items()],
        "artifacts": {"log": None},
    }


def full_environment(matrix):
    """The environment block a real batch run stamps (engine version, job id, PDK hashes)."""
    return {"engine_version": "46", "remote": {"job_id": "klt-sim-test"},
            "models_lib_sha256": matrix.pdk["lib_sha256"], "netlist_sha256": "x"}


def full_provenance(matrix):
    """The provenance block a real batch run stamps."""
    return {"pdk": {"version": "open_pdks " + matrix.pdk["open_pdks_commit"]}}


def synthetic_report(matrix, values_for, *, tamper=None, environment=None, provenance=None):
    """A full synthetic `klt sim` report over `matrix`; `values_for(p, t, v)` returns each
    corner's {name: value} dict, already scaled the way the block's testbench expects."""
    corners = [corner_envelope(pt, values_for(*pt)) for pt in matrix.points()]
    rep = {"status": "pass", "corners": corners,
           "environment": environment or {"remote": {"job_id": "j"}}}
    if provenance:
        rep["provenance"] = provenance
    if tamper:
        tamper(rep)
    return rep


# ---- run manifest + record-render arguments shared by the record-text self-tests ----
# One place that knows the fixed run-manifest keys `runner.render_record` reads.

RECORD_ID = "20260101-000000-abcdef0"
RECORD_SHA = "0" * 64


def render_manifest(experiment, matrix, status, measurements, problems=(), job_id="j",
                    result_status="ok"):
    """A synthetic run manifest. `measurements` is a {name: value} dict, or a callable
    taking the (process, temperature, supply) point and returning one."""
    per_point = measurements if callable(measurements) else (lambda _p: measurements)
    return {"experiment": experiment, "status": status,
            "results": [{"corner_id": _mx.corner_id(*p), "status": result_status,
                         "measurements": dict(per_point(p))} for p in matrix.points()],
            "axes": {"process": list(matrix.process), "temperature_c": list(matrix.temperature_c),
                     "supply_v": list(matrix.supply_v)},
            "problems": list(problems), "backend": "batch", "job_id": job_id, "klt_version": "k",
            "engine_version": "46", "pdk": {}, "git": {"head": "h", "dirty": False},
            "started_utc": "t", "author": "a"}


def render(manifest, tb, **kw):
    """`runner.render_record` over a manifest and a testbench's claim/record metadata."""
    from harness import runner
    parts = {"claim": tb["claim"], "supersedes": "", "record_meta": tb.get("record") or {}, **kw}
    return runner.render_record(RECORD_ID, manifest, RECORD_SHA, parts)
