"""Toolchain-free lint for the append-only mismatch Monte Carlo evidence under sim/.

Needs only python3: no klt, no ngspice, no PDK, never submits a job. Per
`sim/<experiment>/records/<record-id>.md` of an experiment with `testbench/mc.json` it checks the
record format, the evidence directory `campaigns/<record-id>/` (every file present and matching
its SHA-256, via evidence_lint.check_evidence_dir) and re-derives the verdict from the raw
files: the requests (batch, one `*_mm` corner, mismatch only, staged pinned models), the deck
hashes against the klt reports, the negative-control deck against the nominal deck plus the
declared replacement, the executed-PDK identity, the pairing hashes in each sample set, and
the grading of every `klt yield` report (`mismatch.grade`). A PASS record cannot survive any
of these; a FAIL record must state its problems.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import matrix as mx, mismatch as mm

REQUIRED_FIELDS = ("Record ID", "Status", "Claim", "Netlist provenance", "Corners run", "Statistical convention",
                   "Monte Carlo", "Result", "Links", "Timestamp / author", "Supersedes")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, problems: list[str], rid: str):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        problems.append(f"{rid}: unreadable JSON {path.name} ({exc})")
        return None


def check_record(exp_dir: Path, rec: Path) -> list[str]:
    from . import evidence_lint as el

    rid = rec.stem
    if not el.RECORD_ID_RE.match(rid):
        return [f"{rec.name}: not a <YYYYMMDD>-<HHMMSS>-<sha> record id"]
    problems: list[str] = []
    fields = el.parse_fields(rec.read_text())
    for f in REQUIRED_FIELDS:
        if not fields.get(f):
            problems.append(f"{rid}: required field {f!r} missing or empty")
    if fields.get("Record ID") != rid:
        problems.append(f"{rid}: Record ID field {fields.get('Record ID')!r} != filename")
    status = fields.get("Status")
    if status not in ("PASS", "FAIL"):
        problems.append(f"{rid}: Status must be PASS or FAIL")
    sup = fields.get("Supersedes", "")
    if sup and not el.NO_SUPERSESSION_RE.match(sup):
        ref = re.search(r"\d{8}-\d{6}-[0-9a-f]{7,40}", sup)
        if not ref or not (exp_dir / "records" / f"{ref.group(0)}.md").is_file():
            problems.append(f"{rid}: Supersedes names a record that does not exist")
    cdir = exp_dir / "campaigns" / rid
    if not cdir.is_dir():
        return problems + [f"{rid}: campaigns/{rid}/ missing"]
    cited = re.search(r"evidence\.json sha256 `([0-9a-f]{64})`", fields.get("Links", ""))
    if not cited:
        problems.append(f"{rid}: Links must cite the evidence.json sha256")
    errs, m = el.check_evidence_dir(cdir, rid, cited.group(1) if cited else None)
    problems += errs
    if m is None or errs:
        return problems
    if m.get("schema") != mm.EVIDENCE_SCHEMA:
        return problems + [f"{rid}: evidence.json schema is {m.get('schema')!r}"]
    if m.get("status") != status:
        problems.append(f"{rid}: record Status {status} != evidence.json status {m.get('status')}")
    bad_pin = mx.pin_problem(m.get("pdk") or {}, rid)
    if bad_pin:
        problems.append(f"{rid}: {bad_pin}")
    derived, why = derive(cdir, rid, m)
    problems += why
    if derived is not None:
        if status == "PASS" and derived:
            problems += [f"{rid}: a PASS record has a failing criterion: {p}" for p in derived]
        if status == "FAIL" and not m.get("problems"):
            problems.append(f"{rid}: FAIL record must state its problems")
        if status == "FAIL" and not derived:
            problems.append(f"{rid}: FAIL record, but every criterion re-derives as met")
        if sorted(derived) != sorted(m.get("problems", [])) and status == "PASS":
            problems.append(f"{rid}: evidence.json problems disagree with the re-derived list")
    return problems


def derive(cdir: Path, rid: str, m: dict) -> tuple[list[str] | None, list[str]]:
    """(criteria failures re-derived from the raw files, structural problems with the evidence)."""
    bad: list[str] = []
    spec = _load(cdir / "mc.json", bad, rid)
    if not isinstance(spec, dict) or spec.get("schema") != mm.SCHEMA:
        return None, bad + [f"{rid}: frozen mc.json is missing or not a {mm.SCHEMA} document"]
    rcvs = {r["id"]: r for r in spec["receivers"]}
    corners = {c["id"]: c for c in spec["corners"]}
    mc = spec["monte_carlo"]
    if m.get("monte_carlo") != mc:
        bad.append(f"{rid}: evidence.json monte_carlo differs from the frozen mc.json")
    if not (isinstance(mc.get("seed"), int) and mc.get("vary") == "mismatch" and mc.get("n", 0) >= 2):
        bad.append(f"{rid}: monte_carlo must record an integer seed, vary 'mismatch' and n >= 2")
    failing: list[str] = []
    want = {(r, c, k) for r in rcvs for c in corners for k in ("nominal", "control")}
    got = {(c["receiver"], c["corner"], c["kind"]) for c in m.get("campaigns", [])}
    if want != got:
        bad.append(f"{rid}: campaigns {sorted(got)} != declared receivers x corners x (nominal, control)")
    bodies: dict[tuple, str] = {}
    for c in m.get("campaigns", []):
        stem = c["stem"]
        rcv, corner = rcvs.get(c["receiver"]), corners.get(c["corner"])
        if rcv is None or corner is None or stem != mm.campaign_stem(c["receiver"], c["corner"], c["kind"]):
            bad.append(f"{rid}: campaign {stem} does not match the declared receivers/corners")
            continue
        request = _load(cdir / f"{stem}.request.json", bad, rid)
        if not isinstance(request, dict):
            continue
        control = c["kind"] == "control"
        expect = mm.build_request(spec, rcv, corner, control, f"{stem}.spice",
                                  (request.get("batch") or {}).get("runner_version_check"))
        if request != expect:
            bad.append(f"{rid}: {stem}.request.json is not the request the frozen mc.json generates")
        if request.get("backend") != "batch":
            bad.append(f"{rid}: {stem}: a Monte Carlo record must come from the batch backend")
        if not str(request["corners"]["process"][0]).endswith("_mm"):
            bad.append(f"{rid}: {stem}: process section {request['corners']['process']} is not a mismatch (`*_mm`) section")
        body = (cdir / f"{stem}.spice").read_text()
        bodies[(c["receiver"], c["corner"], c["kind"])] = body
        if not c.get("report"):
            failing.append(f"{stem}: campaign did not complete (no report)")
            continue
        report = _load(cdir / f"{stem}.report.json", bad, rid)
        if not isinstance(report, dict):
            continue
        env = report.get("environment") or {}
        if env.get("netlist_sha256") != _sha(cdir / f"{stem}.spice"):
            bad.append(f"{rid}: {stem}: deck sha256 differs from the netlist hash in the klt report")
        mcs = [x for x in report.get("corners", []) if isinstance(x, dict) and x.get("monte_carlo")]
        if len(mcs) != request["monte_carlo"]["n"]:
            bad.append(f"{rid}: {stem}: report has {len(mcs)} Monte Carlo samples, request asked for "
                       f"{request['monte_carlo']['n']}")
        if (env.get("monte_carlo") or {}).get("seed") != mc["seed"]:
            bad.append(f"{rid}: {stem}: report seed {(env.get('monte_carlo') or {}).get('seed')!r} != {mc['seed']}")
        ex = mm.exec_pdk(report)
        if c.get("exec_pdk") != ex:
            bad.append(f"{rid}: {stem}: evidence.json exec_pdk differs from the report")
        failing += mm.pdk_problems(stem, ex, m["pdk"])
    for (r, cn, k), body in bodies.items():
        if k != "control":
            continue
        nominal = bodies.get((r, cn, "nominal"))
        if nominal is None:
            continue
        derived = nominal
        for rep in rcvs[r]["control"]["replace"]:
            if derived.count(rep["find"]) != 1:
                bad.append(f"{rid}: {r}-{cn}: nominal deck does not contain control replacement {rep['find']!r} once")
                break
            derived = derived.replace(rep["find"], rep["with"])
        else:
            if derived != body:
                bad.append(f"{rid}: {r}-{cn}: control deck is not the nominal deck plus the declared skew")
    ys = {(y["receiver"], y["corner"]): y for y in m.get("yields", [])}
    if set(ys) != {(r, c) for r in rcvs for c in corners}:
        failing.append(f"yield reports present for {sorted(ys)}, expected every (receiver, corner)")
    for (r, cn), y in ys.items():
        rcv, corner = rcvs.get(r), corners.get(cn)
        if rcv is None or corner is None:
            bad.append(f"{rid}: yield entry {r}/{cn} is not a declared receiver/corner")
            continue
        yld = _load(cdir / y["yield"], bad, rid)
        samples = _load(cdir / y["samples"], bad, rid)
        limits = _load(cdir / y["limits"], bad, rid)
        if not all(isinstance(x, dict) for x in (yld, samples, limits)):
            continue
        if limits != mm.resolve_limits(spec, rcv, corner):
            bad.append(f"{rid}: {y['limits']} is not the row limits the frozen mc.json declares at this corner")
        der = samples.get("derivation") or {}
        for key, kind in (("nominal", "nominal"), ("negative_control", "control")):
            src = (der.get(key) or {}).get("content_hash")
            rep = cdir / f"{mm.campaign_stem(r, cn, kind)}.report.json"
            if rep.is_file() and src != f"sha256:{_sha(rep)}":
                bad.append(f"{rid}: {y['samples']}: {key} hash does not pin {rep.name}")
        if yld.get("status") != y.get("yield_status"):
            bad.append(f"{rid}: {y['yield']}: status {yld.get('status')!r} != evidence.json {y.get('yield_status')!r}")
        digest, probs = mm.grade(rcv, yld)
        if digest != y.get("measurements"):
            bad.append(f"{rid}: {y['yield']}: evidence.json measurement digest differs from the yield report")
        for name, d in digest.items():
            if d.get("n") is not None and d["n"] + (d.get("errored") or 0) + (d.get("failed_unmeasurable") or 0) \
                    + (d.get("censored") or 0) + (d.get("inconclusive") or 0) != mc["n"]:
                bad.append(f"{rid}: {y['yield']}: {name} accounts for "
                           f"{d['n'] + (d.get('errored') or 0) + (d.get('failed_unmeasurable') or 0) + (d.get('censored') or 0) + (d.get('inconclusive') or 0)}"
                           f" samples, the campaign drew {mc['n']}")
        failing += [f"{r}-{cn}: {p}" for p in probs]
    return failing, bad


def lint_experiment(exp_dir: Path) -> list[str]:
    problems: list[str] = []
    rec_dir = exp_dir / "records"
    rids = set()
    for rec in sorted(rec_dir.glob("*.md")) if rec_dir.is_dir() else []:
        rids.add(rec.stem)
        problems += check_record(exp_dir, rec)
    d = exp_dir / "campaigns"
    for p in sorted(d.iterdir()) if d.is_dir() else []:
        if p.stem not in rids:
            problems.append(f"campaigns/{p.name}: no summary record cites it")
    return problems


def lint_all(sim_dir: Path = mx.SIM_DIR) -> list[str]:
    problems: list[str] = []
    for exp in sorted(p for p in sim_dir.iterdir() if (p / "testbench" / "mc.json").is_file()):
        problems += [f"{exp.name}: {p}" for p in lint_experiment(exp)]
    return problems
