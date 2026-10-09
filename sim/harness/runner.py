"""Run one experiment's PVT grid through `klt sim` and mint an evidence record.

The full 45-point grid always goes to the batch backend, requested explicitly
(`--backend batch` on the klt command line *and* `backend` in the request). A
backend error fails the run: there is no local fallback for a grid. A local
backend exists only for single-corner debug probes that are never recorded.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from . import HARNESS_VERSION, matrix as mx, results as rs

KLT = "klt"
WORK_DIR = mx.SIM_DIR / ".work"


class RunError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def find_pdk_dir(name: str) -> Path | None:
    import os

    roots = []
    if os.environ.get("PDK_ROOT"):
        roots.append(Path(os.environ["PDK_ROOT"]))
    roots += [Path("~/.volare").expanduser(), Path("~/.ciel").expanduser(), Path("/usr/share/pdk"),
              Path("/usr/local/share/pdk"), Path("/opt/pdk")]
    for root in roots:
        if (root / name / "libs.tech" / "ngspice").is_dir():
            return root / name
    return None


def lib_sections(lib_path: Path) -> set[str]:
    out = set()
    for line in lib_path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].lower() == ".lib":
            out.add(parts[1])
    return out


def check_env(matrix: mx.Matrix) -> dict:
    """Confirm, on this host, the PDK, model library and corner sections."""
    pdk = find_pdk_dir(matrix.pdk["name"])
    if pdk is None:
        raise RunError(f"{matrix.pdk['name']} not found (set PDK_ROOT or install it under ~/.volare)")
    lib = pdk / matrix.pdk["lib"]
    if not lib.is_file():
        raise RunError(f"model library missing: {lib}")
    missing = [s for s in matrix.process if s not in lib_sections(lib)]
    if missing:
        raise RunError(f"{lib} has no .lib section(s) {missing}")
    sources = pdk / "SOURCES"
    commit = "unknown"
    if sources.is_file():
        for line in sources.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "open_pdks":
                commit = parts[1]
    return {"path": str(pdk), "lib": str(lib), "lib_sha256": sha256_file(lib), "open_pdks_commit": commit,
            "sections_present": list(matrix.process)}


def _git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(mx.REPO_ROOT), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def tool_version(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except (OSError, IndexError):
        return "unavailable"


def allocate_record_id(records_dir: Path, now: _dt.datetime) -> str:
    sha = _git("rev-parse", "--short=7", "HEAD") or "0000000"
    rid = f"{now:%Y%m%d-%H%M%S}-{sha}"
    if (records_dir / f"{rid}.md").exists():
        raise RunError(f"record {rid} already exists; records are append-only (wait a second)")
    return rid


def invoke_klt(request_path: Path, outdir: Path, backend: str, workdir: Path) -> tuple[dict, str, int]:
    cmd = [KLT, "sim", str(request_path), "--format", "json", "-o", str(outdir), "--backend", backend]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RunError("klt not found on PATH") from exc
    try:
        report = json.loads(proc.stdout)
        if not isinstance(report, dict):
            raise ValueError("not an object")
    except ValueError as exc:
        raise RunError(
            f"klt sim ({backend}) produced no JSON report (exit {proc.returncode}); stderr tail:\n"
            f"{(proc.stderr or proc.stdout)[-1500:]}"
        ) from exc
    return report, proc.stderr or "", proc.returncode


def write_evidence(exp_dir: Path, rid: str, parts: dict) -> Path:
    """Write snapshot + corners/<rid>/ + records/<rid>.md. Never overwrites."""
    snap = exp_dir / "netlist-snapshots" / f"{rid}.spice"
    cdir = exp_dir / "corners" / rid
    rec = exp_dir / "records" / f"{rid}.md"
    for p in (snap, cdir, rec):
        if p.exists():
            raise RunError(f"{p} exists; evidence is append-only")
    snap.parent.mkdir(parents=True, exist_ok=True)
    rec.parent.mkdir(parents=True, exist_ok=True)
    cdir.mkdir(parents=True)
    snap.write_bytes(parts["body"])
    files = {"request.json": parts["request_bytes"], "tb.json": parts["tb_bytes"],
             "corners.json": parts["matrix_bytes"], "klt-stderr.txt": parts["stderr"].encode()}
    if parts.get("report") is not None:
        files["report.json"] = (json.dumps(parts["report"], indent=2) + "\n").encode()
    files.update(parts["logs"])
    for name, data in files.items():
        (cdir / name).write_bytes(data)
    manifest = dict(parts["manifest"])
    manifest["files"] = {n: sha256_bytes(d) for n, d in sorted(files.items())}
    manifest["snapshot_sha256"] = sha256_bytes(parts["body"])
    mbytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (cdir / "evidence.json").write_bytes(mbytes)
    rec.write_text(render_record(rid, manifest, sha256_bytes(mbytes), parts))
    return rec


#: Record prose used when a testbench declares no `record` block: the harness
#: smoke wording. Experiments that make real electrical claims override these
#: (see `tb["record"]` in sim/README.md); the defaults must not change.
SMOKE_RECORD_DEFAULTS = {
    "netlist_provenance": "schematic-level hand netlist (harness smoke deck); no layout, no PHY block",
    "statistical_convention": "not applicable (deterministic operating-point corners, no Monte Carlo)",
    "bounds": "the harness-only bounds in tb.json",
    "footer": "No design claim: this record is harness evidence only.",
}


def _measurement_ranges(m: dict) -> list[str]:
    """Per-measurement min/max over the corners that produced a value, with the corner ids."""
    rows = []
    names = sorted({n for r in m["results"] for n in r["measurements"]})
    for n in names:
        vals = [(r["measurements"][n], r["corner_id"]) for r in m["results"] if n in r["measurements"]]
        lo, hi = min(vals), max(vals)
        rows.append(f"| `{n}` | {len(vals)} | {lo[0]:.6g} (`{lo[1]}`) | {hi[0]:.6g} (`{hi[1]}`) |")
    return ["| measurement | corners with a value | min (corner) | max (corner) |", "|---|---|---|---|"] + rows


def render_record(rid: str, m: dict, manifest_sha: str, parts: dict) -> str:
    rel = f"sim/{m['experiment']}"
    ok = sum(1 for r in m["results"] if r["status"] == "ok")
    meta = {**SMOKE_RECORD_DEFAULTS, **(parts.get("record_meta") or {})}
    detailed = bool(meta.get("detailed"))
    if not m["problems"]:
        problem_note = ""
    elif detailed:
        # Detailed records list every failure in their own section; only the count goes here.
        problem_note = f"; {len(m['problems'])} problem(s)"
    else:
        # Smoke wording, byte-identical to records minted before `detailed` existed.
        problem_note = f"; problems: {'; '.join(m['problems'][:5])}"
    lines = [
        f"# {m['experiment']} -- {rid}", "",
        f"- **Record ID**: {rid}",
        f"- **Status**: {m['status']}",
        f"- **Claim**: {parts['claim']}",
        f"- **Netlist provenance**: {meta['netlist_provenance']}",
        f"- **Corner matrix run**: {len(m['results'])} points = process {{{', '.join(m['axes']['process'])}}} x "
        f"temperature {{{', '.join(f'{t:g}' for t in m['axes']['temperature_c'])}}} C x supply "
        f"{{{', '.join(f'{v:g}' for v in m['axes']['supply_v'])}}} V (sim/corners.json); full matrix, no subset",
        f"- **Statistical convention**: {meta['statistical_convention']}",
        f"- **Result**: {m['status']} -- {ok}/{len(m['results'])} corners simulated with finite measurements inside "
        f"{meta['bounds']}{problem_note}",
        f"- **Links**: {rel}/testbench/, {rel}/netlist-snapshots/{rid}.spice, {rel}/corners/{rid}/ "
        f"(evidence.json sha256 `{manifest_sha}`)",
        f"- **Timestamp / author**: {m['started_utc']} / {m['author']}",
        f"- **Supersedes**: {parts.get('supersedes') or '(none)'}",
        "", "## Provenance", "",
        f"- backend: `{m['backend']}`; batch job id: `{m['job_id'] or 'none'}`",
        f"- klt: `{m['klt_version']}`; ngspice (execution host, from report): `{m['engine_version']}`",
        f"- PDK: `{m['pdk'].get('name')}` open_pdks `{m['pdk'].get('open_pdks_commit')}`; "
        f"model library sha256 `{m['pdk'].get('lib_sha256')}`",
        f"- harness {HARNESS_VERSION}; repo HEAD `{m['git']['head']}` dirty={m['git']['dirty']}",
    ]
    if meta.get("method"):
        lines += ["", "## Method", ""] + [f"- {x}" for x in meta["method"]]
    if detailed:
        lines += ["", "## Measurement ranges over the grid", ""] + _measurement_ranges(m)
        if meta.get("corner_table"):
            cols = meta["corner_table"]
            lines += ["", "## Per-corner selection", "",
                      "| corner | " + " | ".join(f"`{c}`" for c in cols) + " |",
                      "|---|" + "---|" * len(cols)]
            for r in m["results"]:
                cells = [f"{r['measurements'][c]:.6g}" if c in r["measurements"] else "-" for c in cols]
                lines.append(f"| `{r['corner_id']}` | " + " | ".join(cells) + " |")
        lines += ["", "## Failures (corner id: measurement and value)", ""]
        lines += [f"- {p}" for p in m["problems"]] if m["problems"] else ["- none"]
    lines += ["", meta["footer"], ""]
    return "\n".join(lines)


def run(experiment: str, backend: str, record: bool, subset: dict, supersedes: str = "",
        runner_version_check: str | None = None) -> int:
    matrix = mx.load()
    exp_dir = mx.SIM_DIR / experiment
    tb_path = exp_dir / "testbench" / "tb.json"
    if not tb_path.is_file():
        raise RunError(f"no experiment {experiment!r}: {tb_path} missing")
    tb = json.loads(tb_path.read_text())
    body = (exp_dir / "testbench" / tb["netlist"]).read_bytes()
    for inc in tb.get("include", []):  # design netlists the deck instantiates, frozen into the snapshot
        body += b"\n* ---- included: " + inc.encode() + b" ----\n" + (exp_dir / "testbench" / inc).read_bytes()

    full = not any(subset.values())
    if record and not full:
        raise RunError("a subset run cannot be recorded; drop --corner/--temp/--supply or pass --no-write")
    if record and backend != "batch":
        raise RunError("recorded evidence requires the batch backend (full grids never run locally)")
    if backend != "batch" and full:
        raise RunError("the full grid must go through the batch backend; use --corner/--temp/--supply "
                       "for a single-corner local debug probe")

    env = check_env(matrix)  # submitting host: fails early if the pin is wrong
    if env["open_pdks_commit"] != matrix.pdk["open_pdks_commit"] or env["lib_sha256"] != matrix.pdk["lib_sha256"]:
        raise RunError("installed PDK differs from the pin in sim/corners.json "
                       f"(open_pdks {env['open_pdks_commit']}, lib sha {env['lib_sha256']})")

    request = rs.build_request(tb, matrix, backend=backend, process=subset.get("process"),
                               temperature_c=subset.get("temperature_c"), supply_v=subset.get("supply_v"),
                               runner_version_check=runner_version_check)
    if full:
        problems = mx.check_request(request, matrix)
        if problems:
            raise RunError("resolved request is not the sky130 matrix: " + "; ".join(problems))
    now = _dt.datetime.now(_dt.timezone.utc)
    rid = allocate_record_id(exp_dir / "records", now)
    work = WORK_DIR / experiment / rid
    work.mkdir(parents=True, exist_ok=True)
    (work / "body.spice").write_bytes(body)
    request_bytes = (json.dumps(request, indent=2) + "\n").encode()
    (work / "request.json").write_bytes(request_bytes)
    git = {"head": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))}

    points = [p for p in matrix.points()
              if (not subset.get("process") or p[0] in subset["process"])
              and (not subset.get("temperature_c") or p[1] in subset["temperature_c"])
              and (not subset.get("supply_v") or p[2] in subset["supply_v"])]
    print(f"experiment {experiment}: {len(points)} point(s), backend {backend}, record {rid if record else '(none)'}")

    base = {
        "schema": "sky130-usb2-phy.sim.evidence/1", "record_id": rid, "experiment": experiment,
        "harness_version": HARNESS_VERSION, "backend": backend, "axes": {
            "process": list(matrix.process), "temperature_c": list(matrix.temperature_c),
            "supply_v": list(matrix.supply_v)},
        "started_utc": now.isoformat(timespec="seconds"), "author": f"{getpass.getuser()} (agent)",
        "git": git, "klt_version": tool_version([KLT, "--version"]),
        "pdk": {"name": matrix.pdk["name"], "open_pdks_commit": env["open_pdks_commit"],
                "lib_sha256": env["lib_sha256"], "lib": matrix.pdk["lib"]},
    }
    parts = {"body": body, "request_bytes": request_bytes, "tb_bytes": tb_path.read_bytes(),
             "matrix_bytes": mx.CORNERS_JSON.read_bytes(), "claim": tb["claim"], "supersedes": supersedes,
             "record_meta": tb.get("record") or {},
             "logs": {}, "stderr": "", "report": None}

    try:
        report, stderr, code = invoke_klt(work / "request.json", work / "klt-out", backend, work)
    except RunError as exc:
        # Backend failure: never fall back to a local grid. Preserve the attempt.
        print(f"BACKEND ERROR: {exc}")
        if record:
            parts["stderr"] = str(exc)
            parts["manifest"] = dict(base, status="FAIL", job_id=None, engine_version=None,
                                     problems=[f"backend error: {str(exc).splitlines()[0]}"],
                                     results=[{"corner_id": mx.corner_id(*p), "status": "missing",
                                               "measurements": {}} for p in points])
            print(f"failed attempt recorded: {write_evidence(exp_dir, rid, parts)}")
        return 2

    results, problems = rs.evaluate(report, points, tb)
    jid = rs.job_id(report)
    if backend == "batch" and not jid:
        problems.append("batch run but the report carries no remote job id")
    if backend == "batch":
        pv = (report.get("provenance") or {}).get("pdk") or {}
        env_rep = report.get("environment") or {}
        if env_rep.get("models_lib_sha256") != matrix.pdk["lib_sha256"]:
            problems.append("execution host model library sha256 "
                            f"{env_rep.get('models_lib_sha256')} != pinned {matrix.pdk['lib_sha256']}")
        if matrix.pdk["open_pdks_commit"] not in str(pv.get("version", "")):
            problems.append(f"execution host PDK version {pv.get('version')!r} != pinned open_pdks commit")

    by_key = {rs.corner_key(c): c for c in report.get("corners") or [] if isinstance(c, dict)}
    for p, r in zip(points, results):
        c = by_key.get(mx.key(*p))
        art = ((c or {}).get("artifacts") or {}).get("log")
        if c is not None and art and Path(art).is_file():
            parts["logs"][f"{r['corner_id']}.log"] = Path(art).read_bytes()
        elif c is not None:
            problems.append(f"{r['corner_id']}: raw ngspice log not retrievable ({art!r})")
    status = "PASS" if not problems and all(r["status"] == "ok" for r in results) else "FAIL"
    for p, r in zip(points, results):
        print(f"  {r['corner_id']:<18} {r['status']:<7} " + "  ".join(f"{k}={v:.4g}" for k, v in r["measurements"].items()))
    print(f"status {status}; job id {jid}; problems: {len(problems)}")
    for pr in problems[:10]:
        print("  -", pr)

    parts.update(report=report, stderr=stderr)
    parts["manifest"] = dict(base, status=status, job_id=jid, engine_version=(report.get("environment") or {}).get("engine_version"),
                             problems=problems, results=results, klt_exit_code=code)
    if record:
        print(f"record: {write_evidence(exp_dir, rid, parts)}")
    shutil.rmtree(work / "klt-out", ignore_errors=True) if record else None
    return 0 if status == "PASS" else 1
