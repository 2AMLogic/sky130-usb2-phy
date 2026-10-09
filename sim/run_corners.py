#!/usr/bin/env python3
"""PVT corner runner for sky130-usb2-phy (stdlib only). See sim/README.md.

    python3 sim/run_corners.py --check-env
    python3 sim/run_corners.py --list
    python3 sim/run_corners.py smoke-inverter                       # 45 corners, batch, recorded
    python3 sim/run_corners.py smoke-inverter --backend local --corner ss --temp -40 --supply 3.6 --no-write
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import matrix as mx, runner  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment", nargs="?")
    ap.add_argument("--list", action="store_true", help="print the 45-point matrix")
    ap.add_argument("--check-env", action="store_true", help="confirm PDK, model library and corner sections here")
    ap.add_argument("--backend", choices=("batch", "local"), default="batch",
                    help="batch (default; required for the full grid) or local (single-corner debug only)")
    ap.add_argument("--corner", nargs="+", help="debug subset: process section(s)")
    ap.add_argument("--temp", nargs="+", type=float, help="debug subset: temperature(s) in C")
    ap.add_argument("--supply", nargs="+", type=float, help="debug subset: supply(ies) in V")
    ap.add_argument("--no-write", action="store_true", help="do not record evidence (debug)")
    ap.add_argument("--klt-runner-version-check", choices=("enforce", "warn"), default=None,
                    help="batch only: how to treat fleet-runner/client klt version skew (default enforce)")
    ap.add_argument("--supersedes", default="", help="record id this run supersedes")
    args = ap.parse_args(argv)
    try:
        matrix = mx.load()
        if args.list:
            for i, p in enumerate(matrix.points(), 1):
                print(f"{i:>2} {mx.corner_id(*p)}")
            print(f"{len(matrix.points())} points; pdk {matrix.pdk['name']} {matrix.pdk['lib']}")
            return 0
        if args.check_env:
            for k, v in runner.check_env(matrix).items():
                print(f"{k}: {v}")
            return 0
        if not args.experiment:
            ap.print_help()
            return 3
        subset = {"process": args.corner, "temperature_c": args.temp, "supply_v": args.supply}
        return runner.run(args.experiment, args.backend, not args.no_write, subset, args.supersedes,
                          args.klt_runner_version_check)
    except (runner.RunError, mx.MatrixError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
