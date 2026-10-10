"""Toolchain-free lint for the append-only analog evidence under sim/.

Needs only python3 and git: no klt, no ngspice, no PDK, never submits a job.

Per `sim/<slug>/records/<record-id>.md` it checks the record format, the
immutable netlist snapshot, and the evidence directory `corners/<record-id>/`
(request, raw klt envelope, testbench and matrix copies, per-corner logs,
`evidence.json`) -- every file present and matching its recorded SHA-256. A
PASS record is re-derived from the raw envelope: exactly the frozen matrix's
unique tuples (45 for the original matrix, 225 for the approved resistor-set matrix; the
frozen matrix must equal an approved configuration), each simulated successfully with
finite measurements inside the testbench bounds, a batch job id, and a request that is the sky130 matrix
(no gf180 path / `typical` / 125 C / +-10 % supply).

Append-only is enforced against an explicit base ref (`--base-ref`, CI passes
FLOW_LINT_BASE_REF): any added file under records/, netlist-snapshots/ or
corners/ is fine; a modified, deleted, renamed or type-changed one fails, and
an unresolvable base ref FAILS (a shallow clone must not silently skip it).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from . import matrix as mx, results as rs

REQUIRED_FIELDS = ("Record ID", "Status", "Claim", "Netlist provenance", "Corner matrix run",
                   "Statistical convention", "Result", "Links", "Timestamp / author", "Supersedes")
RECORD_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{7,40}$")
FIELD_RE = re.compile(r"^- \*\*(?P<k>[^*]+)\*\*:\s*(?P<v>.*)$")
CORNER_LOG_RE = re.compile(r"^(?P<p>[a-z]+(?:_[a-z]+)?)_(?P<t>-?\d+(?:\.\d+)?)c_(?P<v>\d+\.\d\d)v\.log$")
EVIDENCE_PATH_RE = re.compile(r"^sim/[^/]+/(records|netlist-snapshots|corners)/")
NO_SUPERSESSION_RE = re.compile(r"^\(?\s*(none|n/?a)\b", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_fields(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = FIELD_RE.match(line)
        if m:
            out[m.group("k").strip()] = m.group("v").strip()
    return out


def _git(repo: Path, *args: str):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def check_append_only(repo: Path, base_ref: str) -> list[str]:
    """Only additions are allowed under sim/*/{records,netlist-snapshots,corners}/."""
    if not base_ref:
        return ["append-only: no base ref given (set FLOW_LINT_BASE_REF or pass --base-ref)"]
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}").returncode != 0:
        return [f"append-only: base ref {base_ref!r} is not available in this checkout "
                "(fetch full history); the required check cannot be skipped"]
    mb = _git(repo, "merge-base", base_ref, "HEAD")
    if mb.returncode != 0 or not mb.stdout.strip():
        return [f"append-only: no merge base between {base_ref!r} and HEAD (shallow clone?)"]
    diff = _git(repo, "diff", "--name-status", "--no-renames", mb.stdout.strip(), "--", "sim")
    if diff.returncode != 0:
        return [f"append-only: git diff failed: {diff.stderr.strip()}"]
    problems = []
    for line in diff.stdout.splitlines():
        status, _, path = line.partition("\t")
        if EVIDENCE_PATH_RE.match(path) and status != "A":
            problems.append(f"append-only: {path} was {'deleted' if status == 'D' else 'modified'}"
                            f" ({status}) relative to {base_ref}; evidence is append-only -- mint a new record")
    return problems


def _load_json(path: Path, problems: list[str], what: str):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        problems.append(f"{what}: unreadable JSON {path.name} ({exc})")
        return None


def check_evidence_dir(cdir: Path, rid: str, record_sha_of_manifest: str | None) -> tuple[list[str], dict | None]:
    problems: list[str] = []
    manifest_path = cdir / "evidence.json"
    if not manifest_path.is_file():
        return [f"{rid}: {cdir.name}/evidence.json missing"], None
    if record_sha_of_manifest and sha256_file(manifest_path) != record_sha_of_manifest:
        problems.append(f"{rid}: evidence.json sha256 does not match the one cited in the record's Links")
    m = _load_json(manifest_path, problems, rid)
    if not isinstance(m, dict):
        return problems, None
    if m.get("record_id") != rid:
        problems.append(f"{rid}: evidence.json record_id is {m.get('record_id')!r}")
    files = m.get("files")
    if not isinstance(files, dict):
        return problems + [f"{rid}: evidence.json has no files map"], m
    on_disk = {p.name for p in cdir.iterdir() if p.name != "evidence.json"}
    for name in sorted(set(files) - on_disk):
        problems.append(f"{rid}: referenced evidence {name} is missing")
    for name in sorted(on_disk - set(files)):
        problems.append(f"{rid}: unreferenced file {name} in evidence directory")
    for name, digest in files.items():
        if name in on_disk and sha256_file(cdir / name) != digest:
            problems.append(f"{rid}: {name} sha256 mismatch (evidence was altered)")
    return problems, m


def check_pass_record(exp_dir: Path, cdir: Path, rid: str, m: dict) -> list[str]:
    """Re-derive the verdict of a PASS record from the raw envelope."""
    problems: list[str] = []
    try:
        matrix = mx.from_dict(json.loads((cdir / "corners.json").read_text()))
        tb = json.loads((cdir / "tb.json").read_text())
        request = json.loads((cdir / "request.json").read_text())
        report = json.loads((cdir / "report.json").read_text())
    except (OSError, ValueError, mx.MatrixError) as exc:
        return [f"{rid}: PASS record lacks readable corners/tb/request/report evidence ({exc})"]
    # The matrix must be an approved configuration (from_dict above) AND the one this record's
    # experiment variant, evidence manifest and (for resistor-set matrices) section mapping name.
    try:
        tb = rs.resolve_tb(tb, m.get("variant"))
    except rs.VariantError as exc:
        return [f"{rid}: {exc}"]
    if rs.tb_matrix_id(tb) != matrix.matrix_id or m.get("matrix_id", mx.LEGACY_ID) != matrix.matrix_id:
        problems.append(f"{rid}: testbench/manifest matrix id "
                        f"{rs.tb_matrix_id(tb)!r}/{m.get('matrix_id', mx.LEGACY_ID)!r} != corners.json {matrix.matrix_id!r}")
    if matrix.matrix_id != mx.LEGACY_ID:
        sections = m.get("sections")
        want = {s: {"mos": mx.SECTION_MAP[s][0], "resistor_set": mx.SECTION_MAP[s][1],
                    "capacitor_set": mx.SECTION_MAP[s][2]} for s in matrix.process}
        got = {s: {k: v for k, v in (d or {}).items() if k != "includes"} for s, d in (sections or {}).items()} \
            if isinstance(sections, dict) else None
        if got != want:
            problems.append(f"{rid}: evidence.json section mapping is missing or differs from the approved "
                            "section -> (MOS, resistor set, capacitor set) map")
        elif any(d.get("includes") is None for d in sections.values()):
            problems.append(f"{rid}: evidence.json section mapping lacks the resolved library includes")
        pin = (m.get("pdk") or {})
        if pin.get("lib_sha256") != matrix.pdk.get("lib_sha256") or \
                pin.get("open_pdks_commit") != matrix.pdk.get("open_pdks_commit"):
            problems.append(f"{rid}: evidence PDK identity differs from the pin in corners.json")
    problems += [f"{rid}: request: {p}" for p in mx.check_request(request, matrix)]
    if request.get("backend") != "batch" or m.get("backend") != "batch":
        problems.append(f"{rid}: a PASS record must come from the batch backend")
    if len(matrix.points()) != matrix.expected_points:
        problems.append(f"{rid}: matrix does not expand to {matrix.expected_points} points")
    if len(m.get("results", [])) != matrix.expected_points:
        problems.append(f"{rid}: evidence.json lists {len(m.get('results', []))} results, "
                        f"expected {matrix.expected_points}")
    results, errs = rs.evaluate(report, matrix.points(), tb)
    problems += [f"{rid}: {e}" for e in errs]
    if not rs.job_id(report) or rs.job_id(report) != m.get("job_id"):
        problems.append(f"{rid}: batch job id missing or inconsistent with evidence.json")
    snap = exp_dir / "netlist-snapshots" / f"{rid}.spice"
    if snap.is_file() and (report.get("environment") or {}).get("netlist_sha256") != sha256_file(snap):
        problems.append(f"{rid}: snapshot sha256 differs from the netlist hash in the klt envelope")
    for r in results:
        if f"{r['corner_id']}.log" not in m["files"]:
            problems.append(f"{rid}: raw log for {r['corner_id']} missing")
    for name in m["files"]:
        if name.endswith(".log") and not CORNER_LOG_RE.match(name):
            problems.append(f"{rid}: log name {name} does not parse as <process>_<temp>c_<supply>v.log")
    if [r["status"] for r in m.get("results", [])] != [r["status"] for r in results]:
        problems.append(f"{rid}: evidence.json results disagree with the raw report")
    return problems


def lint_experiment(exp_dir: Path) -> list[str]:
    problems: list[str] = []
    records = exp_dir / "records"
    rids = set()
    for rec in sorted(records.glob("*.md")) if records.is_dir() else []:
        rid = rec.stem
        rids.add(rid)
        if not RECORD_ID_RE.match(rid):
            problems.append(f"{rec.name}: not a <YYYYMMDD>-<HHMMSS>-<sha> record id")
            continue
        fields = parse_fields(rec.read_text())
        for f in REQUIRED_FIELDS:
            if not fields.get(f):
                problems.append(f"{rid}: required field {f!r} missing or empty")
        if fields.get("Record ID") != rid:
            problems.append(f"{rid}: Record ID field {fields.get('Record ID')!r} != filename")
        status = fields.get("Status")
        if status not in ("PASS", "FAIL"):
            problems.append(f"{rid}: Status must be PASS or FAIL")
        sup = fields.get("Supersedes", "")
        if sup and not NO_SUPERSESSION_RE.match(sup):
            ref = re.search(r"\d{8}-\d{6}-[0-9a-f]{7,40}", sup)
            if not ref or not (records / f"{ref.group(0)}.md").is_file():
                problems.append(f"{rid}: Supersedes names a record that does not exist")
        if not (exp_dir / "netlist-snapshots" / f"{rid}.spice").is_file():
            problems.append(f"{rid}: netlist-snapshots/{rid}.spice missing")
        cdir = exp_dir / "corners" / rid
        if not cdir.is_dir():
            problems.append(f"{rid}: corners/{rid}/ missing")
            continue
        cited = re.search(r"evidence\.json sha256 `([0-9a-f]{64})`", fields.get("Links", ""))
        if not cited:
            problems.append(f"{rid}: Links must cite the evidence.json sha256")
        errs, m = check_evidence_dir(cdir, rid, cited.group(1) if cited else None)
        problems += errs
        if m is None:
            continue
        if m.get("status") != status:
            problems.append(f"{rid}: record Status {status} != evidence.json status {m.get('status')}")
        if (cdir / "corners.json").is_file():  # any record, PASS or FAIL: the frozen matrix is approved
            try:
                mx.from_dict(json.loads((cdir / "corners.json").read_text()))
            except (OSError, ValueError, mx.MatrixError) as exc:
                problems.append(f"{rid}: frozen corners.json is not an approved matrix ({exc})")
        if status == "PASS" and not errs:
            problems += check_pass_record(exp_dir, cdir, rid, m)
        if status == "FAIL" and m.get("status") == "FAIL" and not m.get("problems"):
            problems.append(f"{rid}: FAIL record must state its problems")
    for sub in ("netlist-snapshots", "corners"):
        d = exp_dir / sub
        for p in sorted(d.iterdir()) if d.is_dir() else []:
            if p.stem not in rids:
                problems.append(f"{sub}/{p.name}: no summary record cites it")
    return problems


def lint_all(sim_dir: Path = mx.SIM_DIR) -> list[str]:
    problems: list[str] = []
    for matrix_id, cfg in mx.APPROVED_MATRICES.items():
        path = sim_dir / cfg["file"]
        if matrix_id != mx.LEGACY_ID and not path.is_file():
            continue  # optional supplemental matrix
        try:
            if mx.load(path).matrix_id != matrix_id:
                problems.append(f"{cfg['file']}: declares a different matrix id than {matrix_id!r}")
        except (OSError, ValueError, mx.MatrixError) as exc:
            problems.append(f"{cfg['file']}: {exc}")
    for exp in sorted(p for p in sim_dir.iterdir() if (p / "testbench" / "tb.json").is_file()):
        problems += [f"{exp.name}: {p}" for p in lint_experiment(exp)]
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Analog evidence-record lint (toolchain-free).")
    ap.add_argument("--base-ref", default=None, help="git ref the append-only rule is enforced against")
    ap.add_argument("--no-append-only", action="store_true", help="skip the git check (unit tests / local format check)")
    args = ap.parse_args(argv)
    problems = lint_all()
    if not args.no_append_only:
        problems += check_append_only(mx.REPO_ROOT, args.base_ref or "")
    for p in problems:
        print(f"FAIL {p}")
    print("analog evidence lint: " + ("FAILED" if problems else "OK"))
    return 1 if problems else 0
