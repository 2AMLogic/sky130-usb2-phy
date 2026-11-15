#!/usr/bin/env python3
"""Post-layout (klt pex) runner for the differential_receiver leaf. See sim/README.md.

Submits sim/diff-receiver-pex/testbench/tb.json -- the sensitivity bench re-run at
tt_27c_3.30v and at sf_100c_3.00v, the binding corner of the committed 45-point
schematic record 20261020-172719-ca4a45a -- to `klt pex` against the committed leaf
GDS, checks the schematic leg of the report against that record's committed values,
and stages an evidence directory for `python3 sim/run_store_evidence.py
diff-receiver-pex <stage-dir>`.

    python3 sim/diff-receiver-pex/run.py --dry-run    # pre-flight, no extraction
    python3 sim/diff-receiver-pex/run.py              # batch run, equivalence gate, staging

The equivalence gate compares every delta[] row's schematic_value with the committed
record's report (sim/diff-receiver-sensitivity/corners/20261020-172719-ca4a45a/
report.json) at relative deviation <= 1e-6 and exits 3 on any mismatch: the deck
restructure (in-deck DUT .include, pin order shim) is trusted only while the
schematic leg reproduces the committed numbers. The gate also fails (exit 3)
unless the envelope's status is `pass` and its delta carries exactly
corners x measurements distinct rows: absent, partial or duplicated data must
fail the run, not pass it vacuously.
"""

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GDS = REPO / "layout/analog/differential_receiver/differential_receiver.gds"
TB = Path(__file__).resolve().parent / "testbench/tb.json"
DECK = Path(__file__).resolve().parent / "testbench/diff_receiver_pex_tb.spice"
SHIM = Path(__file__).resolve().parent / "testbench/differential_receiver_pex_dut.spice"
REFERENCE_REPORT = (REPO / "sim/diff-receiver-sensitivity/corners/"
                    "20261020-172719-ca4a45a/report.json")
REL_TOL = 1e-6


def head_sha() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.strip()[:7]


def pex_cmd(stage: Path, backend: str, wait: int, dry_run: bool) -> list[str]:
    cmd = ["klt", "pex", str(GDS), str(TB),
           "--top", "differential_receiver", "--pdk", "sky130A", "--deck", "sky130",
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


def check_equivalence(envelope: dict) -> tuple[bool, list[dict]]:
    ref = json.loads(REFERENCE_REPORT.read_text())
    committed = {}
    for corner in ref["corners"]:
        for m in corner["measurements"]:
            committed[(corner["corner_id"], m["name"])] = m.get("value")
    tb = json.loads(TB.read_text())
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
                                "(corners x measurements from testbench/tb.json)"})
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="klt pex pre-flight, nothing extracted")
    ap.add_argument("--backend", choices=("batch", "local"), default="batch")
    ap.add_argument("--wait-for-capacity", type=int, default=600)
    ap.add_argument("--stage-dir", type=Path, default=REPO / "sim/.work/diff-receiver-pex")
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

    ok, rows = check_equivalence(envelope)
    (stage / "equivalence.json").write_text(json.dumps(
        {"reference_record": str(REFERENCE_REPORT.relative_to(REPO)), "rel_tol": REL_TOL,
         "equivalent": ok, "rows": rows}, indent=1) + "\n")
    for f in (TB, DECK, SHIM):
        (stage / f.name).write_bytes(f.read_bytes())

    bb = envelope.get("body_bias") or {}
    mm = envelope.get("model_mismatch")
    bad = [r_ for r_ in rows if r_["verdict"] != "ok"]
    print(f"klt pex status={envelope.get('status')} corners={envelope.get('corner_count')} "
          f"delta rows pass/fail/error={envelope.get('passed')}/{envelope.get('failed')}/"
          f"{envelope.get('errored')} body_bias={bb.get('status')} "
          f"model_mismatch={'present' if mm else 'null'} elapsed={elapsed:.0f}s")
    print(f"equivalence vs {REFERENCE_REPORT.relative_to(REPO)}: "
          f"{'OK' if ok else f'{len(bad)} MISMATCH(ES)'} ({len(rows)} rows)")
    for r_ in bad[:10]:
        print(f"  {r_['corner_id']} {r_['measurement']}: committed={r_['committed']} "
              f"schematic={r_['schematic']}", file=sys.stderr)
    print(f"evidence staged under {stage}; store with: python3 sim/run_store_evidence.py "
          f"diff-receiver-pex {stage}")
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
