"""Mismatch Monte Carlo campaigns: one `klt sim` MC request per (receiver, corner), graded by `klt yield`.

An experiment directory with `testbench/mc.json` (instead of `testbench/tb.json`) is a Monte
Carlo mismatch experiment. For every receiver it declares and every corner it names, the runner
builds two `klt sim` requests -- the nominal campaign and a deterministic negative-control
campaign (same deck and seeds with one fixed skew) -- submits all of them to the batch fleet in
one `klt sim --batch-set` (never local: there is no fallback), pairs them with `klt
yield-samples`, grades the pair with `klt yield`, and mints an append-only record under
`sim/<experiment>/records/`; the raw evidence goes to the fleet artifact store and git keeps
`manifests/artifacts/<experiment>-<record-id>.manifest.json`.

`grade` and the file/hash conventions are shared with `mismatch_lint`, so the runner and the
toolchain-free lint apply one rule.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import HARNESS_VERSION, evidence_store as es, matrix as mx, runner

SCHEMA = "sky130-usb2-phy.sim.mismatch/1"
EVIDENCE_SCHEMA = "sky130-usb2-phy.sim.mismatch-evidence/1"
LIB = "libs.tech/ngspice/sky130.lib.spice"


class MismatchError(RuntimeError):
    pass


def load_spec(exp_dir: Path) -> dict:
    spec = json.loads((exp_dir / "testbench" / "mc.json").read_text())
    if spec.get("schema") != SCHEMA:
        raise MismatchError(f"{exp_dir.name}: mc.json schema is {spec.get('schema')!r}, expected {SCHEMA!r}")
    return spec


def build_body(exp_dir: Path, rcv: dict, control: bool) -> bytes:
    """The testbench deck plus the included design netlists; the control applies its replacements."""
    tb_dir = exp_dir / "testbench"
    text = (tb_dir / rcv["netlist"]).read_text()
    for inc in rcv.get("include", []):
        text += f"\n* ---- included: {inc} ----\n" + (tb_dir / inc).read_text()
    if control:
        for rep in rcv["control"]["replace"]:
            if text.count(rep["find"]) != 1:
                raise MismatchError(f"{rcv['id']}: control replacement {rep['find']!r} matches "
                                    f"{text.count(rep['find'])} times, expected exactly once")
            text = text.replace(rep["find"], rep["with"])
    return text.encode()


def campaign_stem(rcv_id: str, corner_id: str, kind: str) -> str:
    return f"{rcv_id}-{corner_id}-{kind}"


def build_request(spec: dict, rcv: dict, corner: dict, control: bool, body_name: str,
                  runner_version_check: str | None = None) -> dict:
    mc = spec["monte_carlo"]
    request = {
        "netlist": body_name,
        "engine": "ngspice",
        "backend": "batch",
        "models": {"pdk": "sky130A", "lib": LIB},
        "corners": {"process": [corner["process"]], "supply_v": {"vsup": [corner["supply_v"]]},
                    "temperature_c": [corner["temperature_c"]]},
        "monte_carlo": {"n": mc["n_control"] if control else mc["n"], "seed": mc["seed"], "vary": mc["vary"]},
        "analysis": rcv["analysis"],
        "measurements": [dict(name=n, **m) for n, m in rcv["measure"].items()],
        # the fleet image's PDK can lag the submitter's pin (the worker stamp differs after a
        # re-pin): stage the submitter's model files so the executed models are the pinned ones
        "options": {"timeout_s": 900, "stage_model_inputs": True},
    }
    hosts = (spec.get("remote_hosts") or {}).get("control" if control else "nominal", 1)
    if hosts > 1:
        # the fleet kills a job at its whole-job ceiling (3600 s) and loses every unit of it, so a
        # 400-sample campaign is sharded into jobs that each fit
        request["remote"] = {"hosts": hosts}
    batch = dict(spec.get("batch") or {})
    if runner_version_check:
        batch["runner_version_check"] = runner_version_check
    if batch:
        request["batch"] = batch
    return request


def resolve_limits(spec: dict, rcv: dict, corner: dict) -> dict:
    """The `klt yield --limits` document for one (receiver, corner): row limits at the corner supply."""
    y = spec["yield"]
    vdd = corner["supply_v"]
    out = {}
    for name, lim in rcv["limits"].items():
        r = {k: v for k, v in lim.items() if k in ("min", "max", "exclusive_min", "exclusive_max")}
        if "min_frac_vdd" in lim:
            r["min"] = round(lim["min_frac_vdd"] * vdd, 6)
        if "max_frac_vdd" in lim:
            r["max"] = round(lim["max_frac_vdd"] * vdd, 6)
        r["target_yield"] = y["target_yield"]
        out[name] = r
    return {"confidence": y["confidence"], "target_ci_halfwidth": y["target_ci_halfwidth"],
            "min_samples": 2, "measurements": out}


def grade(rcv: dict, yld: dict) -> tuple[dict, list[str]]:
    """Per-measurement digest of a `klt yield` report and the problems that stop it being a PASS.

    PASS needs, for every row measurement: the yield claim supported at the stated confidence
    (`status` pass), no errored / unmeasurable / censored / inconclusive sample, a sample-size
    verdict other than `insufficient`, a detected negative control for each measurement the
    declared skew is expected to degrade (`control.must_detect`), and a non-zero sample spread
    for the measurements that evidence mismatch activity (`spread_measures`).
    """
    problems: list[str] = []
    ms = {m.get("name"): m for m in yld.get("measurements", []) if isinstance(m, dict)}
    digest = {}
    for name in rcv["limits"]:
        m = ms.get(name)
        if m is None:
            problems.append(f"{name}: missing from the yield report")
            continue
        emp = ((m.get("yield") or {}).get("empirical") or {})
        ci = emp.get("confidence_interval") or {}
        nc = m.get("negative_control") or {}
        dist = m.get("distribution") or {}
        digest[name] = {
            "status": m.get("status"), "n": m.get("n"), "errored": m.get("errored"),
            "failed_unmeasurable": m.get("failed_unmeasurable"), "censored": m.get("censored"),
            "inconclusive": m.get("inconclusive"), "limits": m.get("limits"),
            "empirical_yield": emp.get("estimate"), "yield_ci_low": ci.get("low"),
            "yield_ci_high": ci.get("high"), "stddev": dist.get("stddev"), "mean": dist.get("mean"),
            "min": dist.get("min"), "max": dist.get("max"),
            "sample_size_verdict": (m.get("sample_size") or {}).get("verdict"),
            "negative_control_verdict": nc.get("verdict"),
            "negative_control_yield": ((nc.get("yield") or {}).get("empirical") or {}).get("estimate"),
        }
        if m.get("status") != "pass":
            problems.append(f"{name}: yield status {m.get('status')!r}, empirical yield "
                            f"{emp.get('estimate')} (95 % interval {ci.get('low')}..{ci.get('high')}), "
                            f"target {((m.get('limits') or {}).get('target_yield'))}")
        for k in ("errored", "failed_unmeasurable", "censored", "inconclusive"):
            if m.get(k):
                problems.append(f"{name}: {k} = {m.get(k)} sample(s); the yield is conditional on the rest")
        if (m.get("sample_size") or {}).get("verdict") in (None, "insufficient"):
            problems.append(f"{name}: sample_size.verdict is {(m.get('sample_size') or {}).get('verdict')!r}")
        if name in rcv["control"]["must_detect"] and nc.get("verdict") != "detected":
            problems.append(f"{name}: negative control verdict {nc.get('verdict')!r}, expected 'detected'")
        if name in rcv["spread_measures"] and not (isinstance(dist.get("stddev"), (int, float))
                                                    and dist["stddev"] > 0):
            problems.append(f"{name}: sample stddev {dist.get('stddev')!r}; mismatch did not vary the measurement")
    return digest, problems


def exec_pdk(report: dict) -> dict:
    """What a batch report says about the models the fleet actually executed.

    A one-job report carries its job under `environment.remote`; a sharded one (`remote.hosts`
    > 1) lists one entry per shard under `environment.remote.fleet`. Every shard counts.
    """
    env = report.get("environment") or {}
    remote = env.get("remote") or {}
    fleet = remote.get("fleet")
    shards = [s for s in fleet if isinstance(s, dict)] if isinstance(fleet, list) and fleet else [remote]

    def wpdk(s: dict) -> dict:
        return (s.get("worker_environment") or {}).get("pdk") or {}

    return {
        "provenance_pdk_version": ((report.get("provenance") or {}).get("pdk") or {}).get("version"),
        "models_lib_sha256": env.get("models_lib_sha256"),
        "models_staged": all(wpdk(s).get("models_staged") is True for s in shards),
        "worker_image_pdk_stamps": sorted({wpdk(s).get("stamp_text") for s in shards if wpdk(s).get("stamp_text")}),
        "job_ids": [s["job_id"] for s in shards if s.get("job_id")],
        "instance_types": sorted({s["instance_type"] for s in shards if s.get("instance_type")}),
        "lifecycles": sorted({s["lifecycle"] for s in shards if s.get("lifecycle")}),
    }


def pdk_problems(stem: str, ex: dict, pdk: dict) -> list[str]:
    """Why the executed models are not demonstrably the pinned ones, or []."""
    out = []
    if ex.get("models_staged") is not True:
        out.append(f"{stem}: models_staged is {ex.get('models_staged')!r}; the fleet image's PDK "
                   f"({ex.get('worker_image_pdk_stamps')!r}) would have run, not the pinned one")
    if pdk["open_pdks_commit"] not in str(ex.get("provenance_pdk_version")):
        out.append(f"{stem}: report provenance PDK {ex.get('provenance_pdk_version')!r} is not the pinned "
                   f"open_pdks {pdk['open_pdks_commit']}")
    if ex.get("models_lib_sha256") != pdk["lib_sha256"]:
        out.append(f"{stem}: models library sha256 {ex.get('models_lib_sha256')} != pinned {pdk['lib_sha256']}")
    if not ex.get("job_ids"):
        out.append(f"{stem}: the report carries no batch job id")
    return out


def _complete(report_path: Path) -> bool:
    """Every sample of a klt report simulated (none errored, lost or interrupted)."""
    try:
        corners = json.loads(report_path.read_text()).get("corners") or []
    except (OSError, ValueError):
        return False
    return bool(corners) and all(c.get("status") in ("pass", "fail") for c in corners)


def _git(*args: str) -> str:
    return runner._git(*args)


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def run(experiment: str, klt: str, hosts: int | None, runner_version_check: str | None,
        max_in_flight: int, record: bool, only: list[str] | None = None, supersedes: str = "",
        capacity_retries: int = 0, from_work: list[Path] | None = None) -> int:
    exp_dir = mx.SIM_DIR / experiment
    spec = load_spec(exp_dir)
    matrix = mx.load_by_id(mx.LEGACY_ID)
    env_info = runner.check_env(matrix)
    lib = Path(env_info["lib"])
    missing = [c["process"] for c in spec["corners"] if c["process"] not in runner.lib_sections(lib)]
    if missing:
        raise MismatchError(f"{lib} has no .lib section(s) {missing}")
    if record and only:
        raise MismatchError("a subset run cannot be recorded; drop --only or pass --no-write")
    if record:
        es.preflight()  # fail closed before submitting anything: recorded bytes go to the artifact store only

    now = _dt.datetime.now(_dt.timezone.utc)
    rid = runner.allocate_record_id(exp_dir / "records", now)
    work = runner.WORK_DIR / experiment / rid
    work.mkdir(parents=True, exist_ok=True)
    campaigns = []
    for rcv in spec["receivers"]:
        for corner in spec["corners"]:
            for kind in ("nominal", "control"):
                stem = campaign_stem(rcv["id"], corner["id"], kind)
                if only and rcv["id"] not in only and stem not in only:
                    continue
                body = build_body(exp_dir, rcv, kind == "control")
                (work / f"{stem}.spice").write_bytes(body)
                request = build_request(spec, rcv, corner, kind == "control", f"{stem}.spice", runner_version_check)
                (work / f"{stem}.request.json").write_text(json.dumps(request, indent=2) + "\n")
                campaigns.append({"receiver": rcv["id"], "corner": corner["id"], "kind": kind, "stem": stem})
    print(f"experiment {experiment}: {len(campaigns)} campaign request(s), backend batch, "
          f"record {rid if record else '(none)'}")

    if from_work:
        # re-collect finished batch-sets (e.g. the harness stopped after the fleet did its work, or
        # a Spot reclaim lost one request and only that request was submitted again): reuse their
        # output, but only if each request and deck is exactly what this spec generates -- nothing
        # is resubmitted and nothing is edited. A campaign takes its report from the LAST directory
        # that has a complete one (every sample simulated), else from the last that has any.
        envelope = {"requests": []}
        for k, d in enumerate(from_work):
            src = json.loads((d / "klt-batch-set.json").read_text())
            shutil.copy(d / "klt-batch-set.json", work / f"klt-batch-set-{k}.json")
            for r in src.get("requests", []):
                stem = Path(r["request"]).name.removesuffix(".request.json")
                c = next((c for c in campaigns if c["stem"] == stem), None)
                if c is None:
                    continue
                for suffix in (".request.json", ".spice"):
                    if (d / f"{stem}{suffix}").read_bytes() != (work / f"{stem}{suffix}").read_bytes():
                        raise MismatchError(f"{d}: {stem}{suffix} differs from what mc.json generates now")
                rep = d / r["report"] if r.get("report") else None
                have = rep is not None and rep.is_file()
                prev = next((e for e in envelope["requests"] if e["request"] == r["request"]), None)
                if prev is not None and prev["complete"] and not (have and _complete(rep)):
                    continue
                if prev is not None:
                    envelope["requests"].remove(prev)
                    shutil.rmtree(work / "out" / f"{stem}.request", ignore_errors=True)
                if have:
                    shutil.copytree(rep.parent, work / "out" / f"{stem}.request")
                envelope["requests"].append({**r, "report": f"out/{stem}.request/report.json" if have else None,
                                             "complete": bool(have and _complete(rep)), "from": d.name})
        (work / "klt-batch-set.json").write_text(json.dumps(envelope, indent=2) + "\n")
        (work / "klt-stderr.txt").write_text("".join(
            f"--- {d.name} ---\n" + (d / "klt-stderr.txt").read_text() for d in from_work))
    else:
        cmd = [klt, "sim", "--batch-set", *[f"{c['stem']}.request.json" for c in campaigns],
               "--max-in-flight", str(max_in_flight), "-o", "out", "--format", "json"]
        if hosts:
            cmd += ["--hosts", str(hosts)]
        if capacity_retries:
            cmd += ["--capacity-retries", str(capacity_retries)]
        proc = _run(cmd, work, {**os.environ, "PDK_ROOT": str(Path(env_info["path"]).parent)})
        try:
            envelope = json.loads(proc.stdout)
        except ValueError as exc:
            raise MismatchError(f"klt sim --batch-set produced no JSON envelope (exit {proc.returncode}); "
                                f"stderr tail:\n{(proc.stderr or proc.stdout)[-1500:]}") from exc
        (work / "klt-stderr.txt").write_text(proc.stderr or "")
        (work / "klt-batch-set.json").write_text(proc.stdout)
    problems: list[str] = []
    by_request = {Path(r["request"]).name: r for r in envelope.get("requests", [])}
    for c in campaigns:
        r = by_request.get(f"{c['stem']}.request.json") or {}
        c["job_ids"] = r.get("job_ids") or []
        report = r.get("report")
        path = None
        if report:
            path = Path(report) if Path(report).is_absolute() else work / report
        if path is None or not path.is_file():
            problems.append(f"{c['stem']}: campaign did not complete: {json.dumps(r.get('error'))}")
            c["report"] = None
        else:
            if not _complete(path):
                problems.append(f"{c['stem']}: not every sample simulated (a lost, interrupted or errored "
                                "sample); the report is kept as the evidence of that")
            c["report"] = path
            (work / f"{c['stem']}.report.json").write_bytes(path.read_bytes())
            c["exec_pdk"] = exec_pdk(json.loads(path.read_text()))
            problems += pdk_problems(c["stem"], c["exec_pdk"], {"open_pdks_commit": env_info["open_pdks_commit"],
                                                                 "lib_sha256": env_info["lib_sha256"]})
    if problems:
        print("BATCH ERROR: " + "; ".join(problems))
        if not record:
            return 2
    return _grade_and_record(spec, exp_dir, work, rid, now, klt, env_info, campaigns, problems, record, supersedes,
                             [d.name for d in from_work] if from_work else None)


def _grade_and_record(spec, exp_dir, work, rid, now, klt, env_info, campaigns, problems, record, supersedes,
                      collected_from=None) -> int:
    yields = []
    cpath = {(c["receiver"], c["corner"], c["kind"]): c for c in campaigns}
    for rcv in spec["receivers"]:
        for corner in spec["corners"]:
            nom, ctl = cpath.get((rcv["id"], corner["id"], "nominal")), cpath.get((rcv["id"], corner["id"], "control"))
            if not nom or not ctl or not nom["report"] or not ctl["report"]:
                continue
            stem = f"{rcv['id']}-{corner['id']}"
            (work / f"{stem}.limits.json").write_text(
                json.dumps(resolve_limits(spec, rcv, corner), indent=2) + "\n")
            nrep, crep = f"{nom['stem']}.report.json", f"{ctl['stem']}.report.json"
            ys = _run([klt, "yield-samples", nrep, "--negative-control", crep, "--description",
                       rcv["control"]["description"], "--format", "json"], work)
            if ys.returncode != 0:
                problems.append(f"{stem}: klt yield-samples exit {ys.returncode}: {(ys.stderr or ys.stdout)[-400:]}")
                continue
            (work / f"{stem}.samples.json").write_text(ys.stdout)
            yr = _run([klt, "yield", f"{stem}.samples.json", "--limits", f"{stem}.limits.json",
                       "--format", "json"], work)
            try:
                yld = json.loads(yr.stdout)
            except ValueError:
                problems.append(f"{stem}: klt yield produced no JSON (exit {yr.returncode}): "
                                f"{(yr.stderr or yr.stdout)[-400:]}")
                continue
            (work / f"{stem}.yield.json").write_text(json.dumps(yld, indent=2) + "\n")
            digest, probs = grade(rcv, yld)
            problems += [f"{stem}: {p}" for p in probs]
            yields.append({"receiver": rcv["id"], "corner": corner["id"], "yield_status": yld.get("status"),
                           "samples": f"{stem}.samples.json", "limits": f"{stem}.limits.json",
                           "yield": f"{stem}.yield.json", "measurements": digest})
            print(f"  {stem:<16} yield status {yld.get('status')}; problems {len(probs)}")
    expected = len(spec["receivers"]) * len(spec["corners"])
    if len(yields) != expected:
        problems.append(f"{len(yields)} of {expected} (receiver, corner) yield reports were produced")
    status = "PASS" if not problems else "FAIL"
    print(f"status {status}; problems: {len(problems)}")
    for p in problems[:12]:
        print("  -", p)
    if not record:
        return 0 if status == "PASS" else 1

    git = {"head": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))}
    pdk_ident = {"name": "sky130A", "open_pdks_commit": env_info["open_pdks_commit"],
                 "lib_sha256": env_info["lib_sha256"], "lib": LIB}
    rec = exp_dir / "records" / f"{rid}.md"
    if rec.exists() or (exp_dir / "campaigns" / rid).exists():
        raise MismatchError(f"{rid}: evidence exists; records are append-only")
    files = {"mc.json": (exp_dir / "testbench" / "mc.json").read_bytes(),
             "klt-stderr.txt": (work / "klt-stderr.txt").read_bytes(),
             "klt-batch-set.json": (work / "klt-batch-set.json").read_bytes()}
    for extra in sorted(work.glob("klt-batch-set-*.json")):  # original envelopes of a --from-work collection
        files[extra.name] = extra.read_bytes()
    camp_rows = []
    for c in campaigns:
        for suffix in (".spice", ".request.json"):
            files[f"{c['stem']}{suffix}"] = (work / f"{c['stem']}{suffix}").read_bytes()
        if c["report"]:
            files[f"{c['stem']}.report.json"] = (work / f"{c['stem']}.report.json").read_bytes()
        camp_rows.append({"receiver": c["receiver"], "corner": c["corner"], "kind": c["kind"],
                          "stem": c["stem"], "job_ids": c["job_ids"], "report": bool(c["report"]),
                          "exec_pdk": c.get("exec_pdk")})
    for y in yields:
        for k in ("samples", "limits", "yield"):
            files[y[k]] = (work / y[k]).read_bytes()
    import hashlib
    manifest = {
        "schema": EVIDENCE_SCHEMA, "record_id": rid, "experiment": exp_dir.name, "status": status,
        "problems": problems, "backend": "batch", "harness_version": HARNESS_VERSION,
        "started_utc": now.isoformat(timespec="seconds"), "author": f"{getpass.getuser()} (agent)",
        "git": git, "klt_version": runner.tool_version([klt, "--version"]), "pdk": pdk_ident,
        "collected_from_batch_set": collected_from,
        "monte_carlo": spec["monte_carlo"], "yield": spec["yield"],
        "corners": spec["corners"], "campaigns": camp_rows, "yields": yields,
        "files": {n: hashlib.sha256(d).hexdigest() for n, d in sorted(files.items())},
    }
    mbytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    files["evidence.json"] = mbytes
    bench = exp_dir.name
    stage = runner.WORK_DIR / ".stage" / bench / rid  # git-ignored; kept for a retry if a put fails
    staged = es.stage_bytes(stage, files)
    rows = es.store_files(bench, rid, {f"{bench}/{rid}/{n}": p for n, p in staged.items()},
                          stage.parent / f"{rid}.manifest.json")
    msha = hashlib.sha256(es.manifest_path(bench, rid).read_bytes()).hexdigest()
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(render_record(spec, rid, manifest, hashlib.sha256(mbytes).hexdigest(), supersedes,
                                 stored=(msha, rows)))
    print(f"record: {rec}")
    return 0 if status == "PASS" else 1


def _fmt(x, nd=6):
    return "-" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))


def render_record(spec: dict, rid: str, m: dict, manifest_sha: str, supersedes: str = "",
                  stored: tuple | None = None) -> str:
    meta = spec["record"]
    rel = f"sim/{m['experiment']}"
    mc, y = m["monte_carlo"], m["yield"]
    corners = "; ".join(f"{c['id']}: {c['process']} / {c['temperature_c']:g} C / {c['supply_v']:g} V" for c in m["corners"])
    jobs = sorted({j for c in m["campaigns"] for j in c["job_ids"]})
    lines = [
        f"# {m['experiment']} -- {rid}", "",
        f"- **Record ID**: {rid}",
        f"- **Status**: {m['status']}",
        f"- **Claim**: {spec['claim']}",
        f"- **Netlist provenance**: {meta['netlist_provenance']}",
        f"- **Corners run**: {corners} (each corner a separate Monte Carlo population; basis for the binding corner in the Method section)",
        f"- **Statistical convention**: {meta['statistical_convention']}",
        f"- **Monte Carlo**: seed {mc['seed']}, vary {mc['vary']}, n = {mc['n']} per corner per receiver, "
        f"n = {mc['n_control']} per negative-control campaign; confidence {y['confidence']}, "
        f"target_yield {y['target_yield']}, target CI half-width {y['target_ci_halfwidth']}; {y['sample_size_justification']}",
        f"- **Result**: {m['status']} -- " + ("every row measurement meets its yield claim, with a sufficient sample size and a detected negative control"
                                            if m["status"] == "PASS" else f"{len(m['problems'])} problem(s), listed under Failures; the failure is evidence, not a waived result"),
        (f"- **Links**: {rel}/testbench/, {rel}/campaigns/{rid}/ (evidence.json sha256 `{manifest_sha}`)") if stored is None else
        (f"- **Links**: {rel}/testbench/, {es.manifest_rel(m['experiment'], rid)} (manifest sha256 `{stored[0]}`)"),
        f"- **Timestamp / author**: {m['started_utc']} / {m['author']}",
        f"- **Supersedes**: {supersedes or '(none)'}",
        "", "## Provenance", "",
        f"- backend: `batch`; batch job ids: {', '.join(f'`{j}`' for j in jobs) or 'none'}",
        f"- klt: `{m['klt_version']}`",
        f"- PDK: `{m['pdk']['name']}` open_pdks `{m['pdk']['open_pdks_commit']}`; model library sha256 `{m['pdk']['lib_sha256']}`",
        f"- harness {HARNESS_VERSION}; repo HEAD `{m['git']['head']}` dirty={m['git']['dirty']}"]
    if m.get("collected_from_batch_set"):
        srcs = ", ".join(f"`{d}`" for d in m["collected_from_batch_set"])
        lines.append(f"- collected (`--from-work`) from the finished batch-set output(s) {srcs} (original envelopes: "
                     "`klt-batch-set-<n>.json`, in that order): the requests and decks were byte-compared with what mc.json "
                     "generates and nothing was resubmitted by the collection; a campaign takes its report from the last "
                     "directory with a complete one, and the batch job ids above are those of the reports used")
    if stored is not None:
        lines += [""] + es.stored_table(stored[1]) + ["", f"Fetch with `klt artifact get`; check with "
                  f"`klt artifact verify {es.manifest_rel(m['experiment'], rid)}`."]
    lines += ["", "## Method", ""] + [f"- {x}" for x in meta["method"]]
    for c in m["corners"]:
        lines.append(f"- Corner `{c['id']}`: {c['basis']}.")
    lines += ["", "## Yield per receiver and corner", "",
              "| receiver | corner | measurement | limits | n | errored | empirical yield (95 % interval) | stddev | sample size | negative control (yield) | status |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for yl in m["yields"]:
        for name, d in yl["measurements"].items():
            lim = d.get("limits") or {}
            lo = f"{'(' if lim.get('exclusive_min') else '['}{_fmt(lim.get('min'))}"
            hi = f"{_fmt(lim.get('max'))}{')' if lim.get('exclusive_max') else ']'}"
            lines.append(f"| {yl['receiver']} | {yl['corner']} | `{name}` | {lo}, {hi} | {_fmt(d['n'])} | {_fmt(d['errored'])} | "
                         f"{_fmt(d['empirical_yield'])} ({_fmt(d['yield_ci_low'])}..{_fmt(d['yield_ci_high'])}) | "
                         f"{_fmt(d['stddev'])} | {d['sample_size_verdict']} | "
                         f"{d['negative_control_verdict']} ({_fmt(d['negative_control_yield'])}) | {d['status']} |")
    lines += ["", "## Failures", ""] + ([f"- {p}" for p in m["problems"]] if m["problems"] else ["- none"])
    lines += ["", meta["footer"], ""]
    return "\n".join(lines)
