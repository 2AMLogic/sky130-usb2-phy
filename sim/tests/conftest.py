import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import json  # noqa: E402

import pytest  # noqa: E402

from harness import artifact_manifest as _am, evidence_store as _es  # noqa: E402


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
