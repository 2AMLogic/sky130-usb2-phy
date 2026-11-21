#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the dplus_pullup leaf. See sim/README.md.

Submits sim/dplus-pullup-pex/testbench/tb.json -- the pull-up tolerance bench re-run
at tt_27c_3.30v and at fs_hl_100c_3.00v, the binding corner of the committed
225-point resistor-set schematic record 20261020-174658-ca4a45a -- to `klt pex`
against the committed leaf GDS, checks the schematic leg of the report against that
record's committed values, grades the extracted leg, and stages an evidence
directory for `python3 sim/run_store_evidence.py dplus-pullup-pex <stage-dir>`.

    python3 sim/dplus-pullup-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/dplus-pullup-pex/run.py              # batch run, equivalence gate, staging

The equivalence gate (sim/harness/pex_equivalence.py, shared by the three leaf pex
runners) compares every delta row's schematic_value with the committed record's raw
report at relative deviation <= 1e-6 and exits 3 on any mismatch. The gate derives
the expected (corner id, measurement) pairs from this bench's own two requested
corners x 26 measurements = 52 rows and fails on any missing, duplicate, unexpected
or non-finite row -- the committed reference covers 225 corners, so rows lifted
from unrequested corners must fail, not pass vacuously.

grading.json evaluates the EXTRACTED leg per corner with the committed bench's own
evaluator: the 16 code voltages go through sim/harness/trim.py (R_eff against the
15 kohm host load; the corner passes when every code yields a finite positive
R_eff and at least one lands inside the inclusive [1425, 1575] ohm window of the
ratified 'FS device D+ pull-up' row), the disabled-state D+ voltage keeps its
0.8 V bound, and the leakage/supply currents are recorded as engineering data (no
ratified limit). klt pex grades only the request's declared supply-absolute limits
(the two voff rows); the trim criterion is existential over codes within each
corner, which no per-row limit can express.

The run's netlist is frozen as sim/dplus-pullup-pex/netlist-snapshots/<run-id>.spice,
composed by the shared harness helper (`snapshot_body`: deck bytes, then each in-deck
`.include` target inlined behind a `* ---- included: <path> ----` banner). The
snapshot is written into the tracked tree immediately, while the store step is a
separate command: if a run is abandoned before `python3 sim/run_store_evidence.py`
mints its summary, the stray snapshot must be deleted by hand --
`sim/harness/evidence_lint.py` fails CI on any snapshot file no summary record cites.
"""

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "sim"))

from harness import pex_equivalence, trim  # noqa: E402
from harness.runner import snapshot_body  # noqa: E402

LEAF = "dplus_pullup"
GDS = REPO / f"layout/analog/{LEAF}/{LEAF}.gds"
TB = Path(__file__).resolve().parent / "testbench/tb.json"
DECK = Path(__file__).resolve().parent / "testbench/dplus_pullup_pex_tb.spice"
SHIM = Path(__file__).resolve().parent / "testbench/dplus_pullup_pex_dut.spice"
BENCH_TB = REPO / "sim/dplus-pullup-tolerance/testbench/tb.json"
REFERENCE_REPORT = (REPO / "sim/dplus-pullup-tolerance/corners/"
                    "20261020-174658-ca4a45a/report.json")
REL_TOL = pex_equivalence.REL_TOL
CODES = 16


def head_sha() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.strip()[:7]


def deck_includes(deck: Path) -> list[str]:
    """The deck's `.include` targets, in order, as named (relative to the testbench dir)."""
    out = []
    for line in deck.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].lower() == ".include":
            out.append(line.split(None, 1)[1].strip().strip('"'))
    return out


def write_snapshot(rid: str, repo: Path = REPO) -> Path:
    """Freeze the netlist as submitted into netlist-snapshots/<rid>.spice (append-only)."""
    snap = repo / "sim/dplus-pullup-pex/netlist-snapshots" / f"{rid}.spice"
    if snap.exists():
        raise FileExistsError(f"{snap} exists; evidence is append-only")
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(snapshot_body(DECK.parent, DECK.name, deck_includes(DECK)))
    return snap


def pex_cmd(stage: Path, backend: str, wait: int, dry_run: bool) -> list[str]:
    cmd = ["klt", "pex", str(GDS), str(TB),
           "--top", LEAF, "--pdk", "sky130A", "--deck", "sky130",
           "--backend", backend]
    if backend == "batch":
        cmd += ["--wait-for-capacity", str(wait)]
    if dry_run:
        cmd += ["--dry-run"]
    else:
        cmd += ["-o", str(stage / "extracted-netlist.spice"),
                "--envelope-out", str(stage / "pex-envelope.json"),
                "--outdir", str(stage / "klt-pex")]
    return cmd + ["--format", "json"]


def grade_extracted(envelope: dict, tb: dict) -> dict:
    """The committed bench's own evaluator on the extracted leg, per corner."""
    extracted = {(r.get("corner_id"), r.get("spec_row")): r.get("extracted_value")
                 for r in envelope.get("delta") or []}
    trim_cfg = json.loads(BENCH_TB.read_text())["trim"]
    corners = {}
    all_pass = True
    for unit in tb["corners"]["units"]:
        cid = pex_equivalence.unit_corner_id(unit)
        vpu = float(next(iter(unit["supply_v"].values())))
        rows = []

        def v(name):
            return extracted.get((cid, name))

        for name in ("voff_d1_v", "voff_d0_v"):
            value = v(name)
            rows.append({"corner_id": cid, "check": f"{name} <= 0.8 V", "value": value,
                         "verdict": "pass" if (value is not None and value <= 0.8) else "FAIL",
                         "bound": "<= 0.8 V"})
        v_dp = [v(f"vdp_c{k:02d}_v") for k in range(CODES)]
        derived, problems = trim.analyse(v_dp, vpu, trim_cfg)
        in_window = int(derived.get("n_in_window", 0))
        best = None
        if "best_code" in derived:
            best = {"code": int(derived["best_code"]), "r_ohm": derived["best_r_ohm"],
                    "err_ohm": derived["best_err_ohm"]}
        rows.append({"corner_id": cid,
                     "check": "every code finite-positive and >= 1 code inside "
                              f"[{trim_cfg['lo_ohm']:g}, {trim_cfg['hi_ohm']:g}] ohm",
                     "value": {"n_in_window": in_window, "best": best},
                     "verdict": "pass" if not problems else "FAIL",
                     "bound": "trim.analyse over the 16 code voltages at the 15 kohm load"})
        corners[cid] = {"supply_v": vpu, "checks": rows, "trim_problems": problems,
                        "r_eff_ohm": {f"c{k:02d}": derived.get(f"r_c{k:02d}_ohm")
                                      for k in range(CODES)}}
        all_pass = all_pass and all(r["verdict"] == "pass" for r in rows)
    return {"leaf": LEAF, "leg": "extracted", "all_pass": all_pass, "corners": corners}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="klt pex pre-flight, nothing extracted")
    ap.add_argument("--backend", choices=("batch", "local"), default="batch")
    ap.add_argument("--wait-for-capacity", type=int, default=600)
    ap.add_argument("--stage-dir", type=Path, default=REPO / "sim/.work/dplus-pullup-pex")
    args = ap.parse_args(argv)

    started = time.monotonic()
    if args.dry_run:
        stage = args.stage_dir / "dry-run"
        stage.mkdir(parents=True, exist_ok=True)
        cmd = pex_cmd(stage, args.backend, args.wait_for_capacity, True)
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        (stage / "dry-run-stdout.json").write_text(r.stdout)
        (stage / "dry-run-stderr.txt").write_text(r.stderr)
        if r.returncode != 0:
            print(f"dry-run refused (exit {r.returncode}): {r.stderr.strip()[-400:]}", file=sys.stderr)
            return 2
        envelope = json.loads(r.stdout)
        print(f"dry-run: status={envelope.get('status')} "
              f"units={[u['corner_id'] for u in envelope['testbenches'][0]['sim']['units']]}")
        return 0

    rid = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{head_sha()}"
    stage = args.stage_dir / rid
    stage.mkdir(parents=True, exist_ok=True)
    cmd = pex_cmd(stage, args.backend, args.wait_for_capacity, False)
    (stage / "command.txt").write_text(" ".join(cmd) + "\n")
    print(f"submitting klt pex (backend {args.backend}); stage {stage}")
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    (stage / "pex-stdout.json").write_text(r.stdout)
    (stage / "pex-stderr.txt").write_text(r.stderr)
    if r.returncode != 0 or not (stage / "pex-envelope.json").is_file():
        print(f"klt pex failed (exit {r.returncode}, {elapsed:.0f}s); envelope and stderr "
              f"kept under {stage} (a failed attempt is committed evidence per AC 6)", file=sys.stderr)
        return 2
    envelope = json.loads((stage / "pex-envelope.json").read_text())

    tb = json.loads(TB.read_text())
    ok, rows = pex_equivalence.check_equivalence(envelope, tb,
                                                 json.loads(REFERENCE_REPORT.read_text()))
    (stage / "equivalence.json").write_text(json.dumps(
        {"reference_record": str(REFERENCE_REPORT.relative_to(REPO)), "rel_tol": REL_TOL,
         "equivalent": ok, "rows": rows}, indent=1) + "\n")
    (stage / "grading.json").write_text(json.dumps(grade_extracted(envelope, tb), indent=1) + "\n")
    for f in (TB, DECK, SHIM):
        (stage / f.name).write_bytes(f.read_bytes())
    try:
        write_snapshot(rid)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    bb = envelope.get("body_bias") or {}
    mm = envelope.get("model_mismatch")
    bad = [r_ for r_ in rows if r_["verdict"] != "ok"]
    grading = json.loads((stage / "grading.json").read_text())
    print(f"klt pex status={envelope.get('status')} corners={envelope.get('corner_count')} "
          f"delta rows pass/fail/error={envelope.get('passed')}/{envelope.get('failed')}/"
          f"{envelope.get('errored')} body_bias={bb.get('status')} "
          f"model_mismatch={'present' if mm else 'null'} elapsed={elapsed:.0f}s")
    print(f"equivalence vs {REFERENCE_REPORT.relative_to(REPO)}: "
          f"{'OK' if ok else f'{len(bad)} MISMATCH(ES)'} ({len(rows)} rows)")
    for cid, c in grading["corners"].items():
        best = next((r["value"]["best"] for r in c["checks"] if r["value"] and isinstance(r["value"], dict)
                     and r["value"].get("best") is not None), None)
        print(f"extracted trim at {cid}: {'PASS' if c['checks'][-1]['verdict'] == 'pass' else 'FAIL'}"
              f" (best code {best['code']}: {best['r_ohm']:.2f} ohm)" if best else
              f"extracted trim at {cid}: FAIL {c['trim_problems']}")
    print(f"evidence staged under {stage}; netlist frozen to netlist-snapshots/{rid}.spice; "
          f"store with: python3 sim/run_store_evidence.py dplus-pullup-pex {stage}")
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
