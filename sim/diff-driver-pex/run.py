#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the differential_driver leaf. See sim/README.md.

Submits the two committed driver benches restructured for `klt pex` -- the static
bench (testbench/tb-static.json: rows 6-04 VOH, 6-05 VOL, 6-08 output resistance)
and the signal-quality bench (testbench/tb-sq.json: rows 6-06 rise/fall + matching,
6-07 crossover, the decision-record 0008 crossover load) -- each at tt_27c_3.30v
plus its binding corners, against the committed leaf GDS. Each run checks the
schematic leg of its report against that bench's committed 45-point record
(20261020-194710-ca4a45a static, 20261020-181618-ca4a45a signal quality) and
stages an evidence directory for `python3 sim/run_store_evidence.py
diff-driver-pex <stage-dir>`.

    python3 sim/diff-driver-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/diff-driver-pex/run.py              # batch runs, equivalence gates, staging
    python3 sim/diff-driver-pex/run.py --bench static    # one bench only

The corner sets are deliberate subsets, not the frozen 45-point matrix (each
bench's binding corner set is derived from its committed record: the corner whose
ratified-row value sits closest to a bound): static = tt + fs_-40c_3.60v (VOH
6-04 binding: voh 3.5929 V vs the 3.6 V bound) + sf_-40c_3.60v (VOL 6-05 and
output-resistance 6-08 binding: vol 0.0690 V, rout_low 29.418 ohm vs the 28 ohm
bound); signal quality = tt + fs_100c_3.60v (crossover 6-07 binding: vcross
1.9933 V vs the 2.0 V bound) + sf_-40c_3.60v (matching 6-06 binding: trf ratio
1.0772 vs the 1.1 bound) + fs_100c_3.00v (matching 6-06 binding: trf ratio
0.9278 vs the 0.9 bound). The full 45-point post-layout runs are named as
follow-up.

The equivalence gate compares every delta[] row's schematic_value with the
committed record's report (sim/driver-static/corners/20261020-194710-ca4a45a/
report.json, sim/driver-signal-quality/corners/20261020-181618-ca4a45a/
report.json) at relative deviation <= 1e-6 and exits 3 on any mismatch: the deck
restructure (in-deck DUT .include, pin-order shim, instance-line reorder) is
trusted only while the schematic leg reproduces the committed numbers. The gate
also fails (exit 3) unless the envelope's status is `pass` and its delta carries
exactly corners x measurements distinct rows: absent, partial or duplicated data
must fail the run, not pass it vacuously.

Each run's netlist is frozen as sim/diff-driver-pex/netlist-snapshots/<run-id>.spice,
composed by the shared harness helper (`snapshot_body`: deck bytes, then each in-deck
`.include` target inlined behind a `* ---- included: <path> ----` banner) so the snapshot
reproduces the simulated circuit and is never byte-identical to the deck staged into the
artifact store (which would re-trigger committed_duplicates on every re-run). The snapshot
is written into the tracked tree immediately, while the store step is a separate command:
if a run is abandoned before `python3 sim/run_store_evidence.py` mints its summary, the
stray snapshot must be deleted by hand -- `sim/harness/evidence_lint.py` fails CI on any
snapshot file no summary record cites.
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

from harness.runner import snapshot_body  # noqa: E402

GDS = REPO / "layout/analog/differential_driver/differential_driver.gds"
EXP = Path(__file__).resolve().parent
REL_TOL = 1e-6

BENCHES = {
    "static": {
        "tb": EXP / "testbench/tb-static.json",
        "deck": EXP / "testbench/driver_static_pex_tb.spice",
        "reference_report": REPO / "sim/driver-static/corners/20261020-194710-ca4a45a/report.json",
    },
    "sq": {
        "tb": EXP / "testbench/tb-sq.json",
        "deck": EXP / "testbench/driver_sq_pex_tb.spice",
        "reference_report": REPO / "sim/driver-signal-quality/corners/20261020-181618-ca4a45a/report.json",
    },
}
SHIM = EXP / "testbench/differential_driver_pex_dut.spice"


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


def write_snapshot(rid: str) -> Path:
    """Freeze the netlist as submitted into netlist-snapshots/<rid>.spice (append-only).

    The snapshots directory is evidence: an existing snapshot for the same run id must
    never be overwritten (mirrors sim/harness/runner.py's append-only refusal).
    """
    bench = rid.rsplit("-", 1)[1]
    deck = BENCHES[bench]["deck"]
    snap = EXP / "netlist-snapshots" / f"{rid}.spice"
    if snap.exists():
        raise FileExistsError(f"{snap} exists; evidence is append-only")
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(snapshot_body(deck.parent, deck.name, deck_includes(deck)))
    return snap


def pex_cmd(bench: str, stage: Path, backend: str, wait: int, dry_run: bool) -> list[str]:
    cmd = ["klt", "pex", str(GDS), str(BENCHES[bench]["tb"]),
           "--top", "differential_driver", "--pdk", "sky130A", "--deck", "sky130",
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


def check_equivalence(bench: str, envelope: dict) -> tuple[bool, list[dict]]:
    ref = json.loads(BENCHES[bench]["reference_report"].read_text())
    committed = {}
    for corner in ref["corners"]:
        for m in corner["measurements"]:
            committed[(corner["corner_id"], m["name"])] = m.get("value")
    tb = json.loads(BENCHES[bench]["tb"].read_text())
    expected_rows = len(tb["corners"]["units"]) * len(tb["measurements"])
    rows = []
    ok = True
    if envelope.get("status") != "pass":
        ok = False
        rows.append({"corner_id": "-", "measurement": "(envelope)",
                     "committed": None, "schematic": None,
                     "verdict": f"envelope status {envelope.get('status')!r} != 'pass'"})
    delta = envelope.get("delta") or []
    if len(delta) != expected_rows:
        ok = False
        rows.append({"corner_id": "-", "measurement": "(envelope)",
                     "committed": None, "schematic": None,
                     "verdict": f"delta has {len(delta)} rows, expected {expected_rows} "
                                "(corners x measurements from the bench tb.json)"})
    seen = set()
    for row in delta:
        key = (row["corner_id"], row["spec_row"])
        if key in seen:
            ok = False
            rows.append({"corner_id": row["corner_id"], "measurement": row["spec_row"],
                         "committed": committed.get(key),
                         "schematic": row.get("schematic_value"),
                         "verdict": "duplicate delta row"})
            continue
        seen.add(key)
        want = committed.get(key)
        got = row.get("schematic_value")
        if want is None:
            ok = False
            rows.append({"corner_id": row["corner_id"], "measurement": row["spec_row"],
                         "committed": want, "schematic": got, "verdict": "no committed value"})
            continue
        if got is None:
            ok = False
            rows.append({"corner_id": row["corner_id"], "measurement": row["spec_row"],
                         "committed": want, "schematic": got, "verdict": "schematic value missing"})
            continue
        dev = abs(got - want) / max(abs(want), 1e-300)
        verdict = "ok" if dev <= REL_TOL else "MISMATCH"
        if verdict != "ok":
            ok = False
        rows.append({"corner_id": row["corner_id"], "measurement": row["spec_row"],
                     "committed": want, "schematic": got, "rel_dev": dev, "verdict": verdict})
    return ok, rows


def run_bench(bench: str, stage_root: Path, backend: str, wait: int, dry_run: bool) -> int:
    if dry_run:
        stage = stage_root / f"dry-run-{bench}"
        stage.mkdir(parents=True, exist_ok=True)
        cmd = pex_cmd(bench, stage, backend, wait, True)
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        (stage / "dry-run-stdout.json").write_text(r.stdout)
        (stage / "dry-run-stderr.txt").write_text(r.stderr)
        if r.returncode != 0:
            print(f"[{bench}] dry-run refused (exit {r.returncode}): {r.stderr.strip()[-400:]}",
                  file=sys.stderr)
            return 2
        envelope = json.loads(r.stdout)
        print(f"[{bench}] dry-run: status={envelope.get('status')} "
              f"units={[u['corner_id'] for u in envelope['testbenches'][0]['sim']['units']]}")
        return 0

    rid = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{head_sha()}-{bench}"
    stage = stage_root / rid
    stage.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    cmd = pex_cmd(bench, stage, backend, wait, False)
    (stage / "command.txt").write_text(" ".join(cmd) + "\n")
    print(f"[{bench}] submitting klt pex (backend {backend}); stage {stage}")
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    (stage / "pex-stdout.json").write_text(r.stdout)
    (stage / "pex-stderr.txt").write_text(r.stderr)
    if not (stage / "pex-envelope.json").is_file():
        print(f"[{bench}] klt pex failed (exit {r.returncode}, {elapsed:.0f}s) with no envelope; "
              f"stderr kept under {stage} (a failed attempt is committed evidence)", file=sys.stderr)
        return 2
    envelope = json.loads((stage / "pex-envelope.json").read_text())
    if r.returncode != 0:
        print(f"[{bench}] klt pex exited {r.returncode} ({elapsed:.0f}s; failing/erroring rows keep "
              f"the exit nonzero); gate and evidence continue on the envelope", file=sys.stderr)

    ok, rows = check_equivalence(bench, envelope)
    (stage / "equivalence.json").write_text(json.dumps(
        {"reference_record": str(BENCHES[bench]["reference_report"].relative_to(REPO)),
         "rel_tol": REL_TOL, "equivalent": ok, "rows": rows}, indent=1) + "\n")
    for f in (BENCHES[bench]["tb"], BENCHES[bench]["deck"], SHIM):
        (stage / f.name).write_bytes(f.read_bytes())
    try:
        write_snapshot(rid)
    except FileExistsError as exc:
        print(f"[{bench}] error: {exc}", file=sys.stderr)
        return 4

    bb = envelope.get("body_bias") or {}
    mm = envelope.get("model_mismatch")
    bad = [r_ for r_ in rows if r_["verdict"] != "ok"]
    print(f"[{bench}] klt pex status={envelope.get('status')} corners={envelope.get('corner_count')} "
          f"delta rows pass/fail/error={envelope.get('passed')}/{envelope.get('failed')}/"
          f"{envelope.get('errored')} body_bias={bb.get('status')} "
          f"model_mismatch={'present' if mm else 'null'} elapsed={elapsed:.0f}s")
    print(f"[{bench}] equivalence vs {BENCHES[bench]['reference_report'].relative_to(REPO)}: "
          f"{'OK' if ok else f'{len(bad)} MISMATCH(ES)'} ({len(rows)} rows)")
    for r_ in bad[:10]:
        print(f"  {r_['corner_id']} {r_['measurement']}: committed={r_['committed']} "
              f"schematic={r_['schematic']}", file=sys.stderr)
    print(f"[{bench}] evidence staged under {stage}; netlist frozen to netlist-snapshots/{rid}.spice; "
          f"store with: python3 sim/run_store_evidence.py diff-driver-pex {stage} --run-id {rid}")
    return 0 if ok else 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="klt pex pre-flight, nothing extracted")
    ap.add_argument("--bench", choices=("static", "sq", "both"), default="both")
    ap.add_argument("--backend", choices=("batch", "local"), default="batch")
    ap.add_argument("--wait-for-capacity", type=int, default=600)
    ap.add_argument("--stage-dir", type=Path, default=REPO / "sim/.work/diff-driver-pex")
    args = ap.parse_args(argv)

    benches = ["static", "sq"] if args.bench == "both" else [args.bench]
    rc = 0
    for bench in benches:
        rc |= run_bench(bench, args.stage_dir, args.backend, args.wait_for_capacity, args.dry_run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
