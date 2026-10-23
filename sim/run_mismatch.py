#!/usr/bin/env python3
"""Mismatch Monte Carlo runner for sky130-usb2-phy (stdlib only). See sim/README.md.

    python3 sim/run_mismatch.py --list
    python3 sim/run_mismatch.py diff-receiver-mismatch --klt /path/to/klt-with-yield/bin/klt
    python3 sim/run_mismatch.py se-receiver-mismatch --klt ... --no-write     # grade, do not record

Every campaign goes to the batch fleet through `klt sim --batch-set`; a backend error fails the
run, there is no local fallback. `klt yield` needs the klt_yield_native extension: point --klt at
a klt that has it (see sim/README.md, "Mismatch Monte Carlo").

A recorded run stores the raw evidence in the artifact store and commits only the manifest and
the record; the store is checked before anything is submitted (exit 4 if it is unusable).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import evidence_store as es, matrix as mx, mismatch, runner  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment", nargs="?")
    ap.add_argument("--list", action="store_true", help="list the mismatch experiments and their campaigns")
    ap.add_argument("--klt", default="klt", help="klt binary used for sim, yield-samples and yield (default: klt)")
    ap.add_argument("--hosts", type=int, default=None, help="shard each batch request across N fleet jobs")
    ap.add_argument("--max-in-flight", type=int, default=4, help="batch requests in flight at once (default 4)")
    ap.add_argument("--capacity-retries", type=int, default=0,
                    help="re-submit a request refused for fleet capacity up to N more times (default 0)")
    ap.add_argument("--from-work", type=Path, nargs="+", default=None, metavar="DIR",
                    help="grade and record the output of batch-set(s) that already finished (previous "
                         "sim/.work/<experiment>/<id> directories, later ones win for a campaign they complete) "
                         "instead of submitting again")
    ap.add_argument("--only", nargs="+", help="subset: receiver id(s) and/or campaign stem(s) such as dp-tt-nominal "
                    "(e.g. to resubmit one request after a Spot reclaim); cannot be recorded, use --from-work")
    ap.add_argument("--no-write", action="store_true", help="grade but do not record evidence")
    ap.add_argument("--klt-runner-version-check", choices=("enforce", "warn"), default=None,
                    help="batch only: how to treat fleet-runner/client klt version skew (default enforce)")
    ap.add_argument("--supersedes", default="", help="record id this run supersedes")
    args = ap.parse_args(argv)
    try:
        if args.list:
            for exp in sorted(p for p in mx.SIM_DIR.iterdir() if (p / "testbench" / "mc.json").is_file()):
                spec = mismatch.load_spec(exp)
                mc = spec["monte_carlo"]
                for rcv in spec["receivers"]:
                    for c in spec["corners"]:
                        print(f"{exp.name} {rcv['id']} {c['id']} ({c['process']}, {c['temperature_c']:g} C, "
                              f"{c['supply_v']:g} V): n={mc['n']} + control n={mc['n_control']}, seed {mc['seed']}")
            return 0
        if not args.experiment:
            ap.print_help()
            return 3
        return mismatch.run(args.experiment, args.klt, args.hosts, args.klt_runner_version_check,
                            args.max_in_flight, not args.no_write, args.only, args.supersedes,
                            args.capacity_retries, args.from_work)
    except es.StoreUnavailable as exc:
        print(f"error: artifact store unavailable, nothing was recorded: {exc}", file=sys.stderr)
        return 4
    except (runner.RunError, mx.MatrixError, mismatch.MismatchError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
