"""Fleet artifact store for new sim evidence: bytes go to the store, git keeps a manifest.

`klt artifact put` is the only client. The broker URL comes from `$KLT_ARTIFACT_BROKER` and is
never put in argv, printed or written to the repo. There is no fallback: if the store is not
usable the run fails closed, before anything is simulated, and nothing is committed.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from . import matrix as mx

KLT = "klt"
BROKER_ENV = "KLT_ARTIFACT_BROKER"
MANIFEST_SUBDIR = Path("manifests") / "artifacts"


class StoreUnavailable(RuntimeError):
    """The artifact store cannot be used; nothing was committed."""


def manifest_dir() -> Path:
    return mx.SIM_DIR.parent / MANIFEST_SUBDIR


def manifest_path(bench: str, rid: str) -> Path:
    return manifest_dir() / f"{bench}-{rid}.manifest.json"


def manifest_rel(bench: str, rid: str) -> str:
    return f"{MANIFEST_SUBDIR.as_posix()}/{bench}-{rid}.manifest.json"


def preflight() -> None:
    """Fail closed unless a put can plausibly succeed. Stores nothing."""
    broker = os.environ.get(BROKER_ENV, "").strip()
    if not broker:
        raise StoreUnavailable(f"${BROKER_ENV} is not set: recorded sim evidence goes to the artifact store "
                               "and there is no fallback that commits bytes")
    if shutil.which(KLT) is None:
        raise StoreUnavailable("klt not found on PATH (need `klt artifact put`; see sim/README.md)")
    try:
        r = subprocess.run([KLT, "artifact", "put", "--help"], capture_output=True, text=True)
    except OSError as exc:
        raise StoreUnavailable(f"cannot run klt: {exc}") from exc
    if r.returncode != 0:
        raise StoreUnavailable("this klt has no `artifact put` verb; install klayout-tools 7e3561f or later")
    parts = urlsplit(broker)
    host = parts.hostname
    if not host or parts.scheme not in ("http", "https"):
        raise StoreUnavailable(f"${BROKER_ENV} is not an http(s) URL")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        socket.create_connection((host, port), timeout=5).close()
    except (OSError, ValueError) as exc:
        raise StoreUnavailable(f"artifact broker unreachable ({type(exc).__name__})") from exc


def put_file(path: Path, name: str, manifest: Path) -> None:
    cmd = [KLT, "artifact", "put", "--manifest", str(manifest), "--name", name, str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(mx.REPO_ROOT))
    except OSError as exc:
        raise StoreUnavailable(f"klt artifact put failed to start: {exc}") from exc
    if r.returncode != 0:
        raise StoreUnavailable(f"klt artifact put {name} failed (exit {r.returncode}): "
                               f"{(r.stderr or r.stdout).strip()[-400:]}")


def store_files(bench: str, rid: str, files: dict[str, Path], tmp_manifest: Path) -> list[dict]:
    """Put each `name -> staged file`, then publish the manifest. Returns `{name,size,sha256}` rows.

    Zero-byte files are not storable (a manifest entry needs size >= 1) and are listed with
    size 0 and the empty-input digest instead. The committed manifest appears only after every
    put succeeded; on failure the staged files stay where they are.
    """
    from . import artifact_manifest as am

    final = manifest_path(bench, rid)
    if final.exists() or tmp_manifest.exists():
        raise StoreUnavailable(f"{final.name} already exists; manifests are append-only")
    rows = []
    for name in sorted(files):
        p = files[name]
        if p.stat().st_size == 0:
            rows.append({"name": name, "size": 0, "sha256": hashlib.sha256(b"").hexdigest()})
            continue
        put_file(p, name, tmp_manifest)
    if tmp_manifest.is_file():
        data, problems = am.load_manifest(tmp_manifest)
        if problems or data is None:
            raise StoreUnavailable("klt wrote an unusable manifest: " + "; ".join(problems[:3]))
        for e in data["entries"]:
            rows.append({"name": e.get("name"), "size": e["size"], "sha256": e["sha256"]})
        have = {r["name"] for r in rows}
        missing = [n for n in files if n not in have]
        if missing:
            raise StoreUnavailable(f"manifest lacks entries for {missing[:3]}")
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmp_manifest, final)
    return sorted(rows, key=lambda r: r["name"])


def stage_bytes(stage: Path, files: dict[str, bytes]) -> dict[str, Path]:
    stage.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, data in files.items():
        (stage / name).write_bytes(data)
        out[name] = stage / name
    return out


def stored_table(rows: list[dict]) -> list[str]:
    lines = ["## Stored evidence", "", "| name | size | sha256 |", "|---|---|---|"]
    lines += [f"| `{r['name']}` | {r['size']} | `{r['sha256']}` |" for r in rows]
    return lines
