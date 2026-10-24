"""Toolchain-free checks for `manifests/artifacts/*.manifest.json` (stdlib + git only).

A manifest is what `klt artifact put --manifest` writes: `{"schema_version": 1, "entries": [...]}`,
one entry per stored object, naming it by sha256. The entry shape mirrors klt's own
(`klayout_tools.artifact_store.entry_problems`) so a manifest this lint accepts is one
`klt artifact verify` can read; it is re-implemented here because CI must not need klt.

Checks: schema, `artifact:<key>` URIs only (no bucket / endpoint / presigned URL may be written
to the repo), and that no stored object's bytes are also committed. "Also committed" means a
tracked file under the entry's run directory (name = `<bench>/<run-id>/<file>`) with the entry's file
name, or whose sha256 equals the entry's and whose path runs through that run directory. A byte-identical
frozen copy of a source file (e.g. the run's tb.json next to the committed testbench) is not a
duplicate; the same bytes under that run's own evidence path are.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .integrity import sha256_file

SCHEMA_VERSION = 1
KINDS = ("evidence", "transcript", "log", "pdk")
REQUIRED = ("sha256", "size", "kind", "producer", "uri")
OPTIONAL = ("name", "media_type")
PRODUCER = ("tool", "version", "loom.repo", "commit")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
URI_RE = re.compile(r"^artifact:([^/\s]\S*)$")
FORBIDDEN_RE = re.compile(r"s3://|arn:aws:|https?://|X-Amz-", re.IGNORECASE)
MANIFEST_GLOB = "manifests/artifacts/*.manifest.json"


def entry_problems(entry) -> list[str]:
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    out = []
    missing = [f for f in REQUIRED if f not in entry]
    extra = sorted(set(entry) - set(REQUIRED) - set(OPTIONAL))
    if missing:
        out.append(f"missing {', '.join(missing)}")
    if extra:
        out.append(f"unknown field(s) {', '.join(extra)}")
    sha = entry.get("sha256")
    if not isinstance(sha, str) or not SHA_RE.match(sha):
        out.append("sha256 must be 64 lowercase hex digits")
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        out.append("size must be a positive integer")
    if entry.get("kind") not in KINDS:
        out.append(f"kind must be one of {', '.join(KINDS)}")
    prod = entry.get("producer")
    if not isinstance(prod, dict) or set(prod) != set(PRODUCER):
        out.append(f"producer must carry exactly {', '.join(PRODUCER)}")
    uri = entry.get("uri")
    m = URI_RE.match(uri) if isinstance(uri, str) else None
    if m is None:
        out.append(f"uri {uri!r} is not artifact:<key> (only the logical artifact: scheme may be committed)")
    elif m.group(1).rsplit("/", 1)[-1] != sha:
        out.append("uri key does not end in the entry's sha256")
    for f in OPTIONAL:
        if f in entry and not isinstance(entry[f], str):
            out.append(f"{f} must be a string")
    return out


def load_manifest(path: Path) -> tuple[dict | None, list[str]]:
    """`(manifest, problems)`; manifest is None when the file cannot be used at all."""
    try:
        text = Path(path).read_text()
        data = json.loads(text)
    except (OSError, ValueError) as exc:
        return None, [f"{path.name}: unreadable manifest JSON ({exc})"]
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION \
            or not isinstance(data.get("entries"), list) or set(data) != {"schema_version", "entries"}:
        return None, [f"{path.name}: not {{schema_version: {SCHEMA_VERSION}, entries: [...]}}"]
    problems = []
    if FORBIDDEN_RE.search(text):
        problems.append(f"{path.name}: names a storage location or URL (s3://, arn:aws:, http, presigned query)")
    if not data["entries"]:
        problems.append(f"{path.name}: no entries")
    seen = set()
    for i, e in enumerate(data["entries"]):
        problems += [f"{path.name}: entry {i}: {p}" for p in entry_problems(e)]
        if isinstance(e, dict):
            key = (e.get("sha256"), e.get("name"))
            if key in seen:
                problems.append(f"{path.name}: entry {i}: duplicate sha256+name")
            seen.add(key)
    return data, problems


def tracked_files(repo: Path) -> tuple[list[str] | None, str]:
    r = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr.strip()
    return [p for p in r.stdout.split("\0") if p], ""


def committed_duplicates(repo: Path, manifest: dict, label: str, tracked: list[str]) -> list[str]:
    """Stored objects whose bytes are also committed (see the module docstring for the match rule)."""
    entries = [e for e in manifest["entries"] if isinstance(e, dict) and isinstance(e.get("sha256"), str)]
    by_size: dict[int, list[dict]] = {}
    for e in entries:
        if isinstance(e.get("size"), int):
            by_size.setdefault(e["size"], []).append(e)
    problems = []
    for rel in tracked:
        if rel.startswith("manifests/"):
            continue
        dirs, base = rel.split("/")[:-1], rel.rsplit("/", 1)[-1]
        for e in entries:
            parts = (e.get("name") or "").split("/")
            run_dir = parts[-2] if len(parts) >= 3 else None
            if run_dir and run_dir in dirs and base == parts[-1]:
                problems.append(f"{label}: stored object {e['name']} is also committed at {rel}")
        cands = by_size.get((repo / rel).stat().st_size if (repo / rel).is_file() else -1)
        if not cands:
            continue
        digest = sha256_file(repo / rel)
        for e in cands:
            parts = (e.get("name") or "").split("/")
            run_dir = parts[-2] if len(parts) >= 3 else None
            if e["sha256"] == digest and (run_dir is None or run_dir in dirs or Path(rel).stem == run_dir):
                problems.append(f"{label}: stored object {e.get('name') or e['sha256']} "
                                f"(sha256 {digest[:12]}...) has its bytes committed at {rel}")
    return problems


def check_repo(repo: Path) -> list[str]:
    """All manifests under `repo/manifests/artifacts/`: schema, artifact: URIs, no committed duplicates."""
    problems: list[str] = []
    mdir = repo / "manifests" / "artifacts"
    paths = sorted(mdir.glob("*.manifest.json")) if mdir.is_dir() else []
    loaded = []
    for p in paths:
        data, errs = load_manifest(p)
        problems += errs
        if data is not None and not errs:
            loaded.append((p, data))
    if loaded:
        tracked, err = tracked_files(repo)
        if tracked is None:
            return problems + [f"cannot list tracked files to check for committed duplicates ({err})"]
        for p, data in loaded:
            problems += committed_duplicates(repo, data, p.name, tracked)
    return problems
