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

Campaign and yield completeness is checked against the corners the record *declares it covers*
(`evidence.json` `corners`), not the full declared matrix, so a `--corner`-scoped run can land
one corner per record. On the committed-evidence path that declaration is checked against the
frozen `mc.json` and fails closed (`covered_corners`); on the stored-evidence path the record's
`Corners run` declaration is cross-checked against the committed manifest (`stored_coverage`).
Neither path lets a record declare less coverage than was run and pass — but a stored record's
PASS/FAIL verdict is still not re-derivable here: those bytes live in the artifact store.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import artifact_manifest as am, evidence_lint as el, matrix as mx, mismatch as mm
from .integrity import check_record_header, load_json, sha256_file

REQUIRED_FIELDS = ("Record ID", "Status", "Claim", "Netlist provenance", "Corners run", "Statistical convention",
                   "Monte Carlo", "Result", "Links", "Timestamp / author", "Supersedes")


def check_record(exp_dir: Path, rec: Path) -> list[str]:
    rid = rec.stem
    fields, problems = check_record_header(rec, exp_dir / "records", REQUIRED_FIELDS)
    if fields is None:
        return problems
    status = fields.get("Status")
    cdir = exp_dir / "campaigns" / rid
    if el.MANIFEST_CITE_RE.search(fields.get("Links", "")):
        # bytes live in the artifact store: PASS/FAIL cannot be re-derived here (klt artifact
        # get/verify does that); check the citation, that no copy is also committed, and that the
        # record's declared corner coverage agrees with the committed manifest (stored_coverage)
        problems += el.check_stored_summary(rec.read_text(), rid, exp_dir.parent.parent)
        problems += stored_coverage(fields, rid, exp_dir, exp_dir.parent.parent)
        if cdir.exists():
            problems.append(f"{rid}: campaigns/{rid}/ is committed but the record cites stored evidence")
        return problems
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


CORNERS_RUN_ID_RE = re.compile(r"^\s*(?P<id>[A-Za-z0-9_]+)\s*:")
CORNERS_RUN_DEF_RE = re.compile(r"^\s*(?P<id>[A-Za-z0-9_]+)\s*:\s*(?P<proc>\S+)\s*/\s*(?P<temp>-?\d+(?:\.\d+)?)"
                                r"\s*C\s*/\s*(?P<volt>\d+(?:\.\d+)?)\s*V\b")
COVERS_ALL_RE = re.compile(r"covers all (\d+) corner\(s\) mc\.json declares")
COVERS_SOME_RE = re.compile(r"covers (\d+) of the (\d+) corner\(s\) mc\.json declares")
NO_CLAIM_RE = re.compile(r"makes no claim about ([^;)]*)")


def _num_eq(text: str, value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(text) == float(value)


def stored_coverage(fields: dict, rid: str, exp_dir: Path, repo: Path) -> list[str]:
    """Corner coverage of a stored-citation record, re-derived from committed bytes only.

    A stored record's PASS/FAIL cannot be re-derived here (the bytes live in the artifact store),
    but the corners it ran are: the cited manifest is committed and its campaign object names are
    `campaign_stem()` = `<receiver>-<corner>-<kind>`, so the forward membership test
    `<receiver>-<corner>-nominal.request.json` among the entry basenames yields the corner set
    that actually ran. This fails closed on the same shapes `covered_corners` rejects on the
    committed path (an empty or unparseable declaration, an id the live mc.json does not declare,
    a duplicate, and a covered corner whose rendered definition differs) plus the shape this check
    exists for: a manifest showing corners the record does not claim to cover. When the manifest's
    mc.json sha256 equals the live `testbench/mc.json` the two specs are byte-identical and the
    corner definitions are compared; when they differ the frozen spec is out of reach and the
    check degrades to ids plus the record's own coverage clause, cross-checked for internal
    consistency only: a degraded record's corner count `M` is taken on the record's word, because
    nothing committed records the frozen corner set (see sim/README.md) — never silently
    claiming full confidence.
    """
    cite = el.MANIFEST_CITE_RE.search(fields.get("Links", ""))
    if cite is None:
        return []  # no citation: check_stored_summary has already reported it
    data, _ = am.load_manifest(repo / cite.group(1))
    if data is None:
        return []  # unusable manifest: already reported
    bad: list[str] = []
    spec = load_json(exp_dir / "testbench" / "mc.json", bad, rid)
    if not isinstance(spec, dict) or spec.get("schema") != mm.SCHEMA:
        return bad + [f"{rid}: live testbench/mc.json is missing or not a {mm.SCHEMA} document; "
                      f"corner coverage cannot be checked"]
    rcv_ids = [r["id"] for r in spec.get("receivers", []) if isinstance(r, dict) and isinstance(r.get("id"), str)]
    corners = {c["id"]: c for c in spec.get("corners", []) if isinstance(c, dict) and isinstance(c.get("id"), str)}
    if not rcv_ids or not corners:
        return bad + [f"{rid}: live mc.json declares no receivers/corners; corner coverage cannot be checked"]
    stems = [f"{r}-{c}" for r in rcv_ids for c in corners]
    if len(stems) != len(set(stems)):
        return bad + [f"{rid}: mc.json receivers x corners yields ambiguous campaign object names; "
                      f"coverage cannot be derived from the manifest"]
    basenames = {(e.get("name") or "").rsplit("/", 1)[-1] for e in data["entries"] if isinstance(e, dict)}
    ran = {c for r in rcv_ids for c in corners if f"{r}-{c}-nominal.request.json" in basenames}
    if not ran:
        return bad + [f"{rid}: the cited manifest has no mismatch campaign object "
                      f"(<receiver>-<corner>-nominal.request.json); no corner coverage could be established"]
    declared: dict[str, str] = {}
    for seg in (s.strip() for s in fields.get("Corners run", "").split(";")):
        m = CORNERS_RUN_ID_RE.match(seg)
        if not m:
            continue
        if m["id"] in declared:
            return bad + [f"{rid}: Corners run declares covered corner {m['id']!r} more than once"]
        declared[m["id"]] = seg
    if not declared:
        return bad + [f"{rid}: Corners run must declare the corners it covers as "
                      f"`<id>: <process> / <T> C / <V> V` entries; got {fields.get('Corners run', '')!r}"]
    unknown = sorted(set(declared) - set(corners))
    if unknown:
        return bad + [f"{rid}: Corners run covers corner(s) {unknown}, which the live mc.json does "
                      f"not declare (declared: {sorted(corners)})"]
    unclaimed = sorted(ran - set(declared))
    if unclaimed:
        bad.append(f"{rid}: the cited manifest shows campaign evidence for corner(s) {unclaimed} that "
                   f"the record does not claim to cover")
    ghost = sorted(set(declared) - ran)
    if ghost:
        bad.append(f"{rid}: Corners run claims corner(s) {ghost} for which the cited manifest shows "
                   f"no campaign evidence")
    mc_entries = [e for e in data["entries"] if isinstance(e, dict)
                  and (e.get("name") or "").rsplit("/", 1)[-1] == "mc.json"]
    shas = sorted({e["sha256"] for e in mc_entries if isinstance(e.get("sha256"), str)})
    byte_exact = len(shas) == 1 and shas[0] == sha256_file(exp_dir / "testbench" / "mc.json")
    if len(shas) != 1:
        bad.append(f"{rid}: the cited manifest has no single mc.json object; which spec the campaign "
                   f"froze cannot be established")
    elif byte_exact:
        for cid, seg in declared.items():
            d = CORNERS_RUN_DEF_RE.match(seg)
            if d is None:
                bad.append(f"{rid}: covered corner {cid!r} in Corners run is not "
                           f"`<id>: <process> / <T> C / <V> V`; its definition cannot be compared "
                           f"with the live mc.json")
            elif (d["proc"] != str(corners[cid].get("process")) or not _num_eq(d["temp"], corners[cid].get("temperature_c"))
                  or not _num_eq(d["volt"], corners[cid].get("supply_v"))):
                bad.append(f"{rid}: covered corner {cid!r} differs from the corner the live mc.json declares")
    uncovered = set(corners) - set(declared)
    for fname in ("Corners run", "Result"):
        fval = fields.get(fname, "")
        all_m, some_m = COVERS_ALL_RE.search(fval), COVERS_SOME_RE.search(fval)
        claim = NO_CLAIM_RE.search(fval)
        degraded = " (frozen mc.json differs from live; clause checked for internal consistency only)"
        if all_m:
            total = int(all_m.group(1))
            if byte_exact:
                if total != len(corners) or uncovered:
                    bad.append(f"{rid}: {fname} claims full coverage of {total} corner(s) but the record "
                               f"declares {len(declared)} of the {len(corners)} the live mc.json declares")
            elif total != len(declared):
                bad.append(f"{rid}: {fname} claims full coverage of {total} corner(s) but the record "
                           f"declares {len(declared)} of them{degraded}")
            if claim:
                names = set(re.findall(r"`([A-Za-z0-9_]+)`", claim.group(1)))
                bad.append(f"{rid}: {fname} claims full coverage but also makes no claim about {sorted(names)}")
        elif some_m:
            n, total = int(some_m.group(1)), int(some_m.group(2))
            if byte_exact:
                if total != len(corners) or n != len(declared) or n >= total:
                    bad.append(f"{rid}: {fname} claims {n} of the {total} corner(s) but the record declares "
                               f"{len(declared)} of the {len(corners)} the live mc.json declares")
                else:
                    names = set(re.findall(r"`([A-Za-z0-9_]+)`", claim.group(1))) if claim else set()
                    if names != uncovered:
                        bad.append(f"{rid}: {fname} makes no claim about {sorted(names)} but the declared "
                                   f"coverage leaves {sorted(uncovered)} uncovered")
            elif n != len(declared) or n >= total:
                bad.append(f"{rid}: {fname} claims {n} of the {total} corner(s) but the record declares "
                           f"{len(declared)} of them{degraded}")
            else:
                raw = re.findall(r"`([A-Za-z0-9_]+)`", claim.group(1)) if claim else []
                names = set(raw)
                if len(raw) > len(names):
                    bad.append(f"{rid}: {fname} makes no claim about {sorted(names)} but names a corner "
                               f"more than once{degraded}")
                overlap = sorted(names & set(declared))
                if overlap:
                    bad.append(f"{rid}: {fname} makes no claim about {overlap} but Corners run declares "
                               f"it covered{degraded}")
                if len(names) != total - n:
                    bad.append(f"{rid}: {fname} makes no claim about {sorted(names)} but the clause leaves "
                               f"{total - n} corner(s) unclaimed{degraded}")
    return bad


def covered_corners(rid: str, m: dict, declared: dict[str, dict]) -> tuple[dict[str, dict] | None, list[str]]:
    """The corners a record claims to cover, checked against the frozen mc.json.

    A run scoped with `--corner` records a subset of the declared corners, so completeness is
    derived from this declaration rather than from the full matrix. That only holds if the
    declaration itself cannot be fudged, so this **fails closed**: a missing, empty or
    malformed `corners` list, a corner the frozen mc.json does not declare, a duplicate, or a
    covered corner whose definition differs from the frozen one all return `None` (no coverage
    could be established) instead of an empty set, which would make an empty record lint clean.

    Returns `(covered by id, problems)`; `covered` is None when the declaration is unusable.
    """
    corners = m.get("corners")
    if not isinstance(corners, list) or not corners:
        return None, [f"{rid}: evidence.json must declare the corners it covers in a non-empty "
                      f"`corners` list; got {corners!r}"]
    out: dict[str, dict] = {}
    for c in corners:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str):
            return None, [f"{rid}: evidence.json `corners` entry {c!r} is not a corner declaration"]
        cid = c["id"]
        if cid in out:
            return None, [f"{rid}: evidence.json declares covered corner {cid!r} more than once"]
        if cid not in declared:
            return None, [f"{rid}: evidence.json covers corner {cid!r}, which the frozen mc.json "
                          f"does not declare (declared: {sorted(declared)})"]
        if c != declared[cid]:
            return None, [f"{rid}: evidence.json covered corner {cid!r} differs from the corner the "
                          f"frozen mc.json declares"]
        out[cid] = c
    return out, []


def derive(cdir: Path, rid: str, m: dict) -> tuple[list[str] | None, list[str]]:
    """(criteria failures re-derived from the raw files, structural problems with the evidence)."""
    bad: list[str] = []
    spec = load_json(cdir / "mc.json", bad, rid)
    if not isinstance(spec, dict) or spec.get("schema") != mm.SCHEMA:
        return None, bad + [f"{rid}: frozen mc.json is missing or not a {mm.SCHEMA} document"]
    rcvs = {r["id"]: r for r in spec["receivers"]}
    corners = {c["id"]: c for c in spec["corners"]}
    mc = spec["monte_carlo"]
    if m.get("monte_carlo") != mc:
        bad.append(f"{rid}: evidence.json monte_carlo differs from the frozen mc.json")
    if not (isinstance(mc.get("seed"), int) and mc.get("vary") == "mismatch" and mc.get("n", 0) >= 2):
        bad.append(f"{rid}: monte_carlo must record an integer seed, vary 'mismatch' and n >= 2")
    covered, cov_bad = covered_corners(rid, m, corners)
    if covered is None:
        return None, bad + cov_bad
    failing: list[str] = []
    want = {(r, c, k) for r in rcvs for c in covered for k in ("nominal", "control")}
    got = {(c["receiver"], c["corner"], c["kind"]) for c in m.get("campaigns", [])}
    if want != got:
        bad.append(f"{rid}: campaigns {sorted(got)} != declared receivers x covered corners "
                   f"{sorted(covered)} x (nominal, control)")
    bodies: dict[tuple, str] = {}
    for c in m.get("campaigns", []):
        stem = c["stem"]
        rcv, corner = rcvs.get(c["receiver"]), corners.get(c["corner"])
        if rcv is None or corner is None or stem != mm.campaign_stem(c["receiver"], c["corner"], c["kind"]):
            bad.append(f"{rid}: campaign {stem} does not match the declared receivers/corners")
            continue
        request = load_json(cdir / f"{stem}.request.json", bad, rid)
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
        report = load_json(cdir / f"{stem}.report.json", bad, rid)
        if not isinstance(report, dict):
            continue
        env = report.get("environment") or {}
        if env.get("netlist_sha256") != sha256_file(cdir / f"{stem}.spice"):
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
    if set(ys) != {(r, c) for r in rcvs for c in covered}:
        failing.append(f"yield reports present for {sorted(ys)}, expected every (receiver, corner) "
                       f"over the covered corners {sorted(covered)}")
    for (r, cn), y in ys.items():
        rcv, corner = rcvs.get(r), corners.get(cn)
        if rcv is None or corner is None:
            bad.append(f"{rid}: yield entry {r}/{cn} is not a declared receiver/corner")
            continue
        yld = load_json(cdir / y["yield"], bad, rid)
        samples = load_json(cdir / y["samples"], bad, rid)
        limits = load_json(cdir / y["limits"], bad, rid)
        if not all(isinstance(x, dict) for x in (yld, samples, limits)):
            continue
        if limits != mm.resolve_limits(spec, rcv, corner):
            bad.append(f"{rid}: {y['limits']} is not the row limits the frozen mc.json declares at this corner")
        der = samples.get("derivation") or {}
        for key, kind in (("nominal", "nominal"), ("negative_control", "control")):
            src = (der.get(key) or {}).get("content_hash")
            rep = cdir / f"{mm.campaign_stem(r, cn, kind)}.report.json"
            if rep.is_file() and src != f"sha256:{sha256_file(rep)}":
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
        if p.is_file() and p.suffix == ".md":  # stored-evidence summary (run_store_evidence.py)
                    problems += el.check_stored_summary(p.read_text(), f"campaigns/{p.name}", exp_dir.parent.parent)
        elif p.stem not in rids:
            problems.append(f"campaigns/{p.name}: no summary record cites it")
    return problems


def lint_all(sim_dir: Path = mx.SIM_DIR) -> list[str]:
    problems: list[str] = []
    for exp in sorted(p for p in sim_dir.iterdir() if (p / "testbench" / "mc.json").is_file()):
        problems += [f"{exp.name}: {p}" for p in lint_experiment(exp)]
    return problems
