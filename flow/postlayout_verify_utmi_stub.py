#!/usr/bin/env python3
"""Re-run `verification/test_utmi_stub.py` against the post-layout gate-level
netlist, via `klt functional-verification` (issue #37, T1 checklist item 7).

## What this checks, and what it does not

`klt functional-verification`'s request schema takes RTL/Verilog `sources`
through Icarus/Verilator -- it has no SPICE simulator path, so it cannot run
directly against `layout/utmi_stub.extracted.spice` (the transistor-level
layout-derived netlist). What it *can* run is `layout/utmi_stub.asbuilt.v`,
the as-built gate-level netlist `klt place-and-route` writes -- and issue
#11/PR #55's own LVS stage already proved that netlist is *structurally
equivalent* to the extracted SPICE netlist (LVS status: match). So exercising
the gate-level netlist through the identical cocotb suite that already
passed against the pre-layout RTL is the practical, tool-available way to
satisfy T1 item 7's "re-run against the extracted netlist" for this design --
see `flow/README.md` ("No post-layout functional simulation") and this
script's own emitted record for the exact chain of custody.

This is a **functional-only** check: the `sky130_fd_sc_hd` cell library is
compiled with the `FUNCTIONAL` define (its UDP-based, zero-delay simulation
model), and no SDF is annotated -- issue #11's P&R request never set
`post_route_sdf`, so no post-route SDF file exists to back-annotate. This
proves structural/functional equivalence of the post-layout netlist under
the same stimulus as the pre-layout suite; it is not a timing-annotated
re-verification (see `klt functional-verification`'s own `options.sdf`).

Per `flow/README.md`'s "one directory per distinct claim under test"
convention, and per `flow/README.md`'s own disclaimer ("No post-layout
functional simulation. ... issue #37's scope, and it is a different
claim."), this is a genuinely different claim from the six-stage physical-
flow smoke experiment -- so this script does not touch `run_flow.py`. It
augments the *existing* nominal-corner record for the same design-under-test
by minting a new record that supersedes it, adding a `functional_verification`
stage entry; the five other corners' records are untouched.

Unlike `run_flow.py`'s six committed request documents, this stage's request
cannot be a static committed JSON: `sources` must name the PDK's
`sky130_fd_sc_hd` behavioral Verilog models, which live outside this repo at
a host-resolved path (`klt pdk find`). Committing an absolute host path would
silently break on every other machine (and would be auto-swept by
`scripts/check-ci.sh`'s `verification/request-*.json` glob if placed there),
so this script resolves the PDK root itself, the same way `run_flow.py`'s own
`resolve_pdk_root` does, and builds the request in memory.

Usage:

    PDK=sky130A python3 flow/postlayout_verify_utmi_stub.py
    python3 flow/postlayout_verify_utmi_stub.py --format json

Exit codes: 0 the regression passed, 1 the regression ran but failed/had a
functional-verification error, 2 the environment (PDK, klt, netlist) could
not be resolved.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_DIR = REPO_ROOT / "flow"
LAYOUT_DIR = REPO_ROOT / "layout"
VERIFICATION_DIR = REPO_ROOT / "verification"

sys.path.insert(0, str(FLOW_DIR))
from check_records import sha256_file  # noqa: E402  (path set above on purpose)
from run_flow import resolve_pdk_root  # noqa: E402  (reuses the #1868 workaround)

HDL_TOPLEVEL = "utmi_stub"
CELL_LIBRARY = "sky130_fd_sc_hd"
NETLIST_PATH = LAYOUT_DIR / "utmi_stub.asbuilt.v"


def resolve_cell_library_sources(pdk_root: str, variant: str) -> list[Path]:
    """Locate the PDK's behavioral Verilog model for `CELL_LIBRARY`.

    `primitives.v` defines the UDP primitives (`sky130_fd_sc_hd__udp_dff...`)
    the cell-level modules in `<CELL_LIBRARY>.v` instantiate; both are
    required sources, in that order, for Icarus to elaborate any standard
    cell under the `FUNCTIONAL` define.
    """
    verilog_dir = Path(pdk_root) / variant / "libs.ref" / CELL_LIBRARY / "verilog"
    primitives = verilog_dir / "primitives.v"
    behavioral = verilog_dir / f"{CELL_LIBRARY}.v"
    missing = [p for p in (primitives, behavioral) if not p.is_file()]
    if missing:
        raise SystemExit(
            "postlayout_verify_utmi_stub: missing PDK verilog source(s): "
            + ", ".join(str(p) for p in missing)
        )
    return [primitives, behavioral]


def build_request(cell_sources: list[Path]) -> dict:
    return {
        "schema": "klt.functional_verification.request/1",
        "engine": "icarus",
        "sources": [str(p) for p in cell_sources] + [str(NETLIST_PATH)],
        "hdl_toplevel": HDL_TOPLEVEL,
        "testbench": {
            "module": "test_utmi_stub",
            "testcase": None,
        },
        "options": {
            "coverage": False,
            "timescale": ["1ns", "1ps"],
            "random_seed": 1,
            # No `USE_POWER_PINS`: `layout/utmi_stub.asbuilt.v`'s cell
            # instances connect no VPWR/VGND pins, so the library must be
            # compiled with the power-pin-free port list to match.
            "defines": {"FUNCTIONAL": None},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    if not NETLIST_PATH.is_file():
        print(
            f"postlayout_verify_utmi_stub: missing {NETLIST_PATH} -- "
            "run flow/run_flow.py first (issue #11/PR #55's stage 2 writes it)",
            file=sys.stderr,
        )
        return 2

    env = dict(os.environ)
    env["PDK"] = args.pdk
    # `resolve_pdk_root` prints its own one-line notice via `run_flow.log()`
    # (stdout, by design, for `run_flow.py`'s own CLI use) -- swallow it here
    # so `--format json` output stays pure JSON on stdout, mirroring how
    # `run_flow.py` itself is fine mixing that notice into its own prose
    # output but this script's `--format json` mode is not.
    with contextlib.redirect_stdout(io.StringIO()) as pdk_log:
        pdk_root = resolve_pdk_root(env)
    if args.format == "text" and pdk_log.getvalue():
        print(pdk_log.getvalue(), end="")
    if not pdk_root:
        print(
            "postlayout_verify_utmi_stub: could not resolve a PDK root "
            "(klt pdk find failed) -- see docs/environment-setup.md",
            file=sys.stderr,
        )
        return 2

    cell_sources = resolve_cell_library_sources(pdk_root, args.pdk)
    request = build_request(cell_sources)

    cmd = ["klt", "functional-verification", json.dumps(request), "--format", "json"]
    # cwd=VERIFICATION_DIR: (a) request_dir for an inline-JSON request is
    # os.getcwd() (see klayout_tools._paths.load_request_arg), which resolves
    # the testbench module next to the existing test_utmi_stub.py without a
    # `search_path` override; (b) klt's own scratch tree lands under
    # verification/.klt/, already gitignored -- exactly where `scripts/
    # check-ci.sh`'s own functional-verification runs leave it, instead of an
    # uncovered bare `.klt/` at the repo root.
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(VERIFICATION_DIR))
    stdout = result.stdout.strip()
    if not stdout:
        print(
            f"postlayout_verify_utmi_stub: `klt functional-verification` produced "
            f"no JSON on stdout (exit {result.returncode})\n{result.stderr.strip()}",
            file=sys.stderr,
        )
        return 2
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(
            f"postlayout_verify_utmi_stub: unparseable JSON from "
            f"`klt functional-verification`: {exc}\n{stdout[:400]}",
            file=sys.stderr,
        )
        return 2

    # Chain-of-custody metadata this script alone can supply -- the PDK root
    # actually resolved, and content hashes of everything the regression
    # consumed outside the request document itself (which klt's own envelope
    # does not echo back).
    envelope["provenance_extra"] = {
        "netlist_under_test": {
            "path": str(NETLIST_PATH.relative_to(REPO_ROOT)),
            "content_hash": sha256_file(NETLIST_PATH),
            "role": (
                "as-built gate-level netlist (the LVS reference); LVS-proven "
                "structurally equivalent to layout/utmi_stub.extracted.spice"
            ),
        },
        "cell_library": {
            "name": CELL_LIBRARY,
            "pdk": args.pdk,
            "pdk_root": pdk_root,
            "sources": {p.name: sha256_file(p) for p in cell_sources},
            "model": "FUNCTIONAL (zero-delay UDP-based simulation model)",
        },
        "sdf_back_annotation": False,
        "sdf_note": (
            "No SDF file exists for this design: issue #11/PR #55's P&R request "
            "never set post_route_sdf. This is a zero/unit-delay functional-only "
            "check, not a timing-annotated re-verification."
        ),
    }

    if args.format == "json":
        print(json.dumps(envelope, indent=2))
    else:
        environment = envelope.get("environment", {})
        print(f"engine        : {envelope.get('engine')}")
        print(f"engine_version: {environment.get('engine_version')}")
        print(f"cocotb_version: {environment.get('cocotb_version')}")
        print(f"test_count    : {envelope.get('test_count')}")
        print(f"passed_count  : {envelope.get('passed_count')}")
        print(f"failed_count  : {envelope.get('failed_count')}")
        print(f"skipped_count : {envelope.get('skipped_count')}")
        print(f"status        : {envelope.get('status')}")

    # klt's own `status` is the source of truth (see run_flow.py's `run_klt`
    # for why a raw exit code is never trusted on its own); fall back to the
    # exit code only if the envelope carries no explicit status field.
    status = envelope.get("status")
    if status is not None:
        return 0 if status == "pass" else 1
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
