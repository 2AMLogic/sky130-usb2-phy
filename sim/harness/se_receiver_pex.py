"""The one post-layout (klt pex) runner behind both single-ended-receiver benches.

sim/se-receiver-dp-pex/run.py (D+, se_receiver_dp) and sim/se-receiver-dm-pex/run.py
(D-, se_receiver_dm) are thin entry points: each supplies a `Bench` with its own leaf
name, deck, pin-order DUT shim, committed schematic reference record and bench
directory, then calls `main` here. Both CLI commands and both benches' per-leaf
evidence stay as they were; only the flow is shared, so a threshold-check or grading
fix lands in one place. See sim/README.md; regression tests in
sim/tests/test_se_receiver_pex.py.

Each bench submits its own testbench/tb.json -- that leaf's threshold bench re-run
at tt_27c_3.30v and at ff_lh_100c_3.00v, the binding corner of the leaf's committed
225-point resistor-set schematic record -- to `klt pex` against the committed leaf
GDS, checks the schematic leg of the report against that record's committed values,
grades the extracted leg against the bench's criteria, and stages an evidence
directory for `python3 sim/run_store_evidence.py <bench> <stage-dir>`.

    python3 sim/se-receiver-dp-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/se-receiver-dp-pex/run.py              # batch run, equivalence gate, staging

The equivalence gate (sim/harness/pex_equivalence.py, shared by the three leaf pex
runners) compares every delta row's schematic_value with the committed record's raw
report at relative deviation <= 1e-6 and exits 3 on any mismatch: the deck
restructure (in-deck DUT .include, pin-order shim, reordered instance line) is
trusted only while the schematic leg reproduces the committed numbers. The gate
derives the expected (corner id, measurement) pairs from the bench's own two
requested corners x 7 measurements = 14 rows and fails on any missing, duplicate,
unexpected or non-finite row -- the committed reference covers 225 corners, so rows
lifted from unrequested corners must fail, not pass vacuously.

grading.json evaluates the EXTRACTED leg per corner against the same criteria the
committed bench grades (strict (0.8 V, 2.0 V) crossing window, single crossing,
supply-relative output levels, supply current): klt pex grades only the request's
declared supply-absolute limits, so the supply-relative checks are evaluated here,
per corner, from the delta rows.

The committed bench's 8th measurement `vref_v` (`.meas dc ... FIND v(xrx.vref)`)
is NOT in either request: it probes a node inside the DUT by name, and the extracted
netlist renames internal nets to synthesized hub names, so the row errors the whole
envelope on the extracted leg (klt pex `no_such_vector`, 2AMLogic/klayout-tools#6990;
discovered by run 20261121-000805, whose schematic leg did reproduce the committed
vref_v at both corners). It is the bench's own sanity probe, not a spec row; the
equivalence gate therefore covers 7 of the committed record's 8 measurements (14
rows per leaf, not 16).

The run's netlist is frozen as sim/<bench>/netlist-snapshots/<run-id>.spice in the
bench's own directory, composed by the shared harness helper (`snapshot_body`: deck
bytes, then each in-deck `.include` target inlined behind a
`* ---- included: <path> ----` banner) so the snapshot reproduces the simulated
circuit and is never byte-identical to the deck staged into the artifact store. The
snapshot is written into the tracked tree immediately, while the store step is a
separate command: if a run is abandoned before `python3 sim/run_store_evidence.py`
mints its summary, the stray snapshot must be deleted by hand --
`sim/harness/evidence_lint.py` fails CI on any snapshot file no summary record cites.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import pex_equivalence
from .runner import snapshot_body

REPO = Path(__file__).resolve().parents[2]
REL_TOL = pex_equivalence.REL_TOL


@dataclass(frozen=True)
class Bench:
    """One leaf's per-bench facts; everything else in the pex flow is shared.

    Paths are derived against a repo root (the real tree by default) so the
    self-tests can drive `main` against a scratch copy without writing into the
    tracked tree.
    """

    leaf: str               # klt pex --top and the layout/analog/<leaf>/ GDS dir
    bench: str              # sim/<bench> directory; also the run_store_evidence name
    polarity: str           # "D+" or "D-": docstrings and diagnostics only
    deck: str               # testbench/<deck>, the bench-body netlist
    shim: str               # testbench/<shim>, the pin-order schematic-leg DUT shim
    reference_report: Path  # this leaf's committed schematic record (raw report)

    def gds(self, repo: Path = REPO) -> Path:
        return repo / f"layout/analog/{self.leaf}/{self.leaf}.gds"

    def bench_dir(self, repo: Path = REPO) -> Path:
        return repo / "sim" / self.bench

    def tb(self, repo: Path = REPO) -> Path:
        return self.bench_dir(repo) / "testbench" / "tb.json"

    def deck_path(self, repo: Path = REPO) -> Path:
        return self.bench_dir(repo) / "testbench" / self.deck

    def shim_path(self, repo: Path = REPO) -> Path:
        return self.bench_dir(repo) / "testbench" / self.shim


def head_sha(repo: Path = REPO) -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()[:7]


def deck_includes(deck: Path) -> list[str]:
    """The deck's `.include` targets, in order, as named (relative to the testbench dir)."""
    out = []
    for line in deck.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].lower() == ".include":
            out.append(line.split(None, 1)[1].strip().strip('"'))
    return out


def write_snapshot(cfg: Bench, rid: str, repo: Path = REPO) -> Path:
    """Freeze the netlist as submitted into this bench's netlist-snapshots/<rid>.spice
    (append-only)."""
    snap = cfg.bench_dir(repo) / "netlist-snapshots" / f"{rid}.spice"
    if snap.exists():
        raise FileExistsError(f"{snap} exists; evidence is append-only")
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(snapshot_body(cfg.deck_path(repo).parent, cfg.deck,
                                   deck_includes(cfg.deck_path(repo))))
    return snap


def pex_cmd(cfg: Bench, stage: Path, backend: str, wait: int, dry_run: bool,
            repo: Path = REPO) -> list[str]:
    cmd = ["klt", "pex", str(cfg.gds(repo)), str(cfg.tb(repo)),
           "--top", cfg.leaf, "--pdk", "sky130A", "--deck", "sky130",
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


def supply_v(unit: dict) -> float:
    return float(next(iter(unit["supply_v"].values())))


def grade_extracted(cfg: Bench, envelope: dict, tb: dict) -> dict:
    """The bench's own checks, evaluated on the extracted leg per corner (the
    supply-relative criteria klt pex cannot declare in one request)."""
    extracted = {(r.get("corner_id"), r.get("spec_row")): r.get("extracted_value")
                 for r in envelope.get("delta") or []}

    def check(cid, name, value, ok, bound):
        return {"corner_id": cid, "check": name, "value": value,
                "verdict": "pass" if (value is not None and ok(value)) else "FAIL",
                "bound": bound}

    corners = {}
    all_pass = True
    for unit in tb["corners"]["units"]:
        cid = pex_equivalence.unit_corner_id(unit)
        vdd = supply_v(unit)
        rows = []

        def v(name):
            return extracted.get((cid, name))

        for name in ("vth_v", "vth_last_v"):
            rows.append(check(cid, f"{name} strictly inside (0.8, 2.0) V", v(name),
                              lambda x: 0.8 < x < 2.0, "0.8 V < x < 2.0 V (exclusive)"))
        rows.append(check(cid, "vth_last_v equals vth_v within one 1 mV step",
                          None if v("vth_v") is None or v("vth_last_v") is None
                          else abs(v("vth_last_v") - v("vth_v")),
                          lambda x: x <= 0.001, "|vth_last_v - vth_v| <= 0.001 V"))
        rows.append(check(cid, "rxd_low_max_v <= 0.1*VDD", v("rxd_low_max_v"),
                          lambda x: x <= 0.1 * vdd, f"<= {0.1 * vdd:g} V"))
        rows.append(check(cid, "rxd_at_vil_v <= 0.1*VDD", v("rxd_at_vil_v"),
                          lambda x: x <= 0.1 * vdd, f"<= {0.1 * vdd:g} V"))
        rows.append(check(cid, "rxd_high_min_v >= 0.9*VDD", v("rxd_high_min_v"),
                          lambda x: x >= 0.9 * vdd, f">= {0.9 * vdd:g} V"))
        rows.append(check(cid, "rxd_at_vih_v >= 0.9*VDD", v("rxd_at_vih_v"),
                          lambda x: x >= 0.9 * vdd, f">= {0.9 * vdd:g} V"))
        rows.append(check(cid, "isup_ua in [1, 500] uA (raw A)", v("isup_ua"),
                          lambda x: 1e-06 <= x <= 5e-04, "[1e-06, 5e-04] A"))
        corners[cid] = {"supply_v": vdd, "checks": rows}
        all_pass = all_pass and all(r["verdict"] == "pass" for r in rows)
    return {"leaf": cfg.leaf, "leg": "extracted", "all_pass": all_pass, "corners": corners}


def main(cfg: Bench, argv=None, repo: Path = REPO) -> int:
    ap = argparse.ArgumentParser(
        description=f"Post-layout (klt pex) runner for the {cfg.leaf} leaf. See sim/README.md.")
    ap.add_argument("--dry-run", action="store_true", help="klt pex pre-flight, nothing extracted")
    ap.add_argument("--backend", choices=("batch", "local"), default="batch")
    ap.add_argument("--wait-for-capacity", type=int, default=600)
    ap.add_argument("--stage-dir", type=Path, default=repo / f"sim/.work/{cfg.bench}")
    args = ap.parse_args(argv)

    started = time.monotonic()
    if args.dry_run:
        stage = args.stage_dir / "dry-run"
        stage.mkdir(parents=True, exist_ok=True)
        cmd = pex_cmd(cfg, stage, args.backend, args.wait_for_capacity, True, repo)
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        (stage / "dry-run-stdout.json").write_text(r.stdout)
        (stage / "dry-run-stderr.txt").write_text(r.stderr)
        if r.returncode != 0:
            print(f"dry-run refused (exit {r.returncode}): {r.stderr.strip()[-400:]}", file=sys.stderr)
            return 2
        envelope = json.loads(r.stdout)
        print(f"dry-run: status={envelope.get('status')} "
              f"units={[u['corner_id'] for u in envelope['testbenches'][0]['sim']['units']]}")
        return 0

    rid = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{head_sha(repo)}"
    stage = args.stage_dir / rid
    stage.mkdir(parents=True, exist_ok=True)
    cmd = pex_cmd(cfg, stage, args.backend, args.wait_for_capacity, False, repo)
    (stage / "command.txt").write_text(" ".join(cmd) + "\n")
    print(f"submitting klt pex (backend {args.backend}); stage {stage}")
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    (stage / "pex-stdout.json").write_text(r.stdout)
    (stage / "pex-stderr.txt").write_text(r.stderr)
    if r.returncode != 0 or not (stage / "pex-envelope.json").is_file():
        print(f"klt pex failed (exit {r.returncode}, {elapsed:.0f}s); envelope and stderr "
              f"kept under {stage} (a failed attempt is committed evidence per AC 6)", file=sys.stderr)
        return 2
    envelope = json.loads((stage / "pex-envelope.json").read_text())

    tb = json.loads(cfg.tb(repo).read_text())
    ok, rows = pex_equivalence.check_equivalence(envelope, tb,
                                                 json.loads(cfg.reference_report.read_text()))
    (stage / "equivalence.json").write_text(json.dumps(
        {"reference_record": str(cfg.reference_report.relative_to(REPO)), "rel_tol": REL_TOL,
         "equivalent": ok, "rows": rows}, indent=1) + "\n")
    (stage / "grading.json").write_text(json.dumps(grade_extracted(cfg, envelope, tb), indent=1) + "\n")
    for f in (cfg.tb(repo), cfg.deck_path(repo), cfg.shim_path(repo)):
        (stage / f.name).write_bytes(f.read_bytes())
    try:
        write_snapshot(cfg, rid, repo)
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
    print(f"equivalence vs {cfg.reference_report.relative_to(REPO)}: "
          f"{'OK' if ok else f'{len(bad)} MISMATCH(ES)'} ({len(rows)} rows)")
    print(f"extracted-leg grading: {'PASS' if grading['all_pass'] else 'FAIL'} "
          f"({sum(len(c['checks']) for c in grading['corners'].values())} checks)")
    for r_ in bad[:10]:
        print(f"  {r_['corner_id']} {r_['measurement']}: committed={r_['committed']} "
              f"schematic={r_['schematic']}", file=sys.stderr)
    print(f"evidence staged under {stage}; netlist frozen to netlist-snapshots/{rid}.spice; "
          f"store with: python3 sim/run_store_evidence.py {cfg.bench} {stage}")
    return 0 if ok else 3
