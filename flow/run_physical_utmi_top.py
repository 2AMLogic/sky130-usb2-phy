#!/usr/bin/env python3
"""Drive stages 2-6 (PAR, STA, extract, LVS, DRC) for the real UTMI top, per corner.

Sibling of `flow/run_synth_utmi_top.py` (stage 1) and `flow/run_flow.py` (the
`smoke-utmi_stub` driver, left untouched). This script is plumbing only: it
substitutes the corner into committed requests, chains one stage's resolved
output path into the next stage's input, keeps every resolved request and raw
`klt` envelope, and applies gates. It writes NO evidence record and commits
nothing: everything lands under the gitignored `flow/build/utmi-top-physical/
<corner>/`, including a `summary.json` whose `claims` block is always all
false. A physical record, a signoff citation or a timing-closure statement is a
later, separate step.

Input netlist: `design/netlist/usb_utmi_top.v` (committed by issue #104); this
driver never re-runs synthesis.

Timing coverage (disclosed in every summary): only `clk_144` (144 MHz,
6.944 ns) is constrained, because `klt place-and-route` / `klt sta` carry a
single `clock_port` / `clock_period_ns`. `clk_utmi` (30 MHz) has no constraint
and the clk_144 <-> clk_utmi CDC is not timed. An OpenSTA sentinel
(`wns >= 1e+30`, "unconstrained") is NOT closure and fails this driver's exit
status. A numeric pass covers the clk_144 domain only.

Usage:

    PDK=sky130A python3 flow/run_physical_utmi_top.py --corners tt_025C_1v80
    python3 flow/run_physical_utmi_top.py --dry-run               # all six corners
    python3 flow/run_physical_utmi_top.py --dry-run --corners tt_025C_1v80

Exit codes: 0 every stage ran and every gate passed, 1 a gate failed or timing
was not a constrained pass, 2 a stage/environment failed outright (the summary
still records the stages that did run, and the failure).
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable

FLOW_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FLOW_DIR))
import run_flow  # noqa: E402  (path set above on purpose)

REPO_ROOT = run_flow.REPO_ROOT
EXPERIMENT = "utmi-top"
TOP = "usb_utmi_top"
NETLIST = REPO_ROOT / "design" / "netlist" / "usb_utmi_top.v"
BUILD_ROOT = run_flow.BUILD_DIR / "utmi-top-physical"
SUMMARY_SCHEMA = "usb2phy.flow.physical-run-summary/1"

STUB_PAR = FLOW_DIR / "request-par-utmi_stub.json"
STUB_LVS = FLOW_DIR / "request-lvs-utmi_stub.json"

REQUESTS = {
    "place_and_route": FLOW_DIR / f"request-par-{TOP}.json",
    "sta": FLOW_DIR / f"request-sta-{TOP}.json",
    "extract": FLOW_DIR / f"request-extract-{TOP}.json",
    "lvs": FLOW_DIR / f"request-lvs-{TOP}.json",
    "drc": FLOW_DIR / f"request-drc-{TOP}.json",
}
STAGE_ORDER = ["place_and_route", "sta", "extract", "lvs", "drc"]

CLOCK_PORT = "clk_144"
CLOCK_PERIOD_NS = 6.944

TIMING_COVERAGE = {
    "constrained": [{"port": CLOCK_PORT, "frequency_mhz": 144, "period_ns": CLOCK_PERIOD_NS}],
    "unconstrained": [
        {
            "port": "clk_utmi",
            "frequency_mhz": 30,
            "reason": "klt place-and-route / klt sta accept one clock_port; no second clock.",
        }
    ],
    "cdc_covered": False,
    "note": (
        "Only clk_144 is constrained. clk_utmi (30 MHz) has no constraint and the "
        "clk_144 <-> clk_utmi CDC paths are not timed. No I/O delays are applied "
        "(klayout-tools#1865). Nothing here is a closure claim for either domain."
    ),
}

NO_CLAIMS = {
    "timing_closure": False,
    "signoff": False,
    "physical_success": False,
    "note": "Plumbing run only; see module docstring.",
}


# ---------------------------------------------------------------------------
# Request resolution (pure; unit tested)
# ---------------------------------------------------------------------------
def committed_corners() -> list[str]:
    return list(run_flow.load_json(FLOW_DIR / "corners.json")["committed"])


def resolve_par(corner: str, netlist: str) -> dict:
    req = copy.deepcopy(run_flow.load_json(REQUESTS["place_and_route"]))
    req["pdk"]["corner"] = corner  # sweep_corners deliberately left as committed
    req["netlist"] = netlist
    return req


def resolve_sta(corner: str, def_path: str) -> dict:
    req = copy.deepcopy(run_flow.load_json(REQUESTS["sta"]))
    req["pdk"]["corner"] = corner
    req["def"] = def_path
    return req


def resolve_lvs(layout_netlist: str, reference_netlist: str) -> dict:
    req = copy.deepcopy(run_flow.load_json(REQUESTS["lvs"]))
    req["layout"]["netlist"] = layout_netlist
    req["reference"]["netlist"] = reference_netlist
    return req


def extract_argv(gds_path: str, output: str) -> list[str]:
    doc = run_flow.load_json(REQUESTS["extract"])
    args = ["extract", gds_path, "--deck", doc["deck"], "--top", doc["top"], "-o", output]
    if doc.get("abstract_cells"):
        args += ["--abstract-cells", doc["abstract_cells"]]
    if doc.get("abstract_cell_lef"):
        args += ["--abstract-cell-lef", doc["abstract_cell_lef"]]
    if doc.get("def_net_names"):
        args += ["--def-net-names"]
    for key, value in (doc.get("deck_options") or {}).items():
        args += ["--deck-option", f"{key}={value}"]
    return args


def drc_argv(gds_path: str) -> list[str]:
    doc = run_flow.load_json(REQUESTS["drc"])
    args = ["drc", gds_path, "--deck", doc["deck"], "--engine", doc.get("engine", "curated")]
    if doc.get("top"):
        args += ["--top", doc["top"]]
    for key, value in (doc.get("deck_vars") or {}).items():
        args += ["--deck-var", f"{key}={value}"]
    if doc.get("timeout_s"):
        args += ["--timeout-s", str(doc["timeout_s"])]
    return args


def static_gate_problems(corner: str) -> list[str]:
    """Check the committed templates still honour the issue's invariants."""
    problems: list[str] = []
    par = resolve_par(corner, str(NETLIST))
    stub_par = run_flow.load_json(STUB_PAR)
    if par.get("hdl_toplevel") != TOP:
        problems.append(f"PAR hdl_toplevel is {par.get('hdl_toplevel')!r}, expected {TOP!r}")
    if par.get("power") != stub_par.get("power"):
        problems.append("PAR `power` (PDN) block differs from request-par-utmi_stub.json")
    for key in ("floorplan", "io"):
        if par.get(key) != stub_par.get(key):
            problems.append(f"PAR `{key}` block differs from request-par-utmi_stub.json")
    cons = par.get("constraints") or {}
    if cons.get("clock_port") != CLOCK_PORT or cons.get("clock_period_ns") != CLOCK_PERIOD_NS:
        problems.append(f"PAR constraints are not {CLOCK_PORT} @ {CLOCK_PERIOD_NS} ns")
    sta_cons = (resolve_sta(corner, "x.def").get("constraints")) or {}
    if sta_cons != cons:
        problems.append("STA constraints differ from PAR constraints")
    lvs = resolve_lvs("a", "b")
    if (lvs.get("options") or {}).get("power_connectivity") != (
        run_flow.load_json(STUB_LVS).get("options") or {}
    ).get("power_connectivity"):
        problems.append("LVS power_connectivity gate differs from request-lvs-utmi_stub.json")
    if lvs["layout"]["top"] != TOP or lvs["reference"]["top"] != TOP:
        problems.append("LVS tops are not the real top")
    return problems


def plan(corner: str, work: Path) -> list[dict]:
    """The stage plan with placeholder chained paths (what --dry-run prints)."""
    par_dir = ".klt/place-and-route"
    out = work / ".klt" / "extract" / f"{TOP}.gate.spice"
    return [
        {"stage": "place_and_route", "cmd": ["place-and-route", "request-par.json"],
         "request": resolve_par(corner, str(NETLIST))},
        {"stage": "sta", "cmd": ["sta", "request-sta.json"],
         "request": resolve_sta(corner, f"<PAR def_path under {par_dir}>")},
        {"stage": "extract", "cmd": extract_argv("<PAR gds_path>", str(out)), "request": None},
        {"stage": "lvs", "cmd": ["lvs", "request-lvs.json"],
         "request": resolve_lvs(str(out), "<PAR verilog_path>")},
        {"stage": "drc", "cmd": drc_argv("<PAR gds_path>"), "request": None},
    ]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
Runner = Callable[[list, Path, dict], dict]


def _save(work: Path, name: str, data) -> str:
    path = work / name
    run_flow.write_json(path, data)
    return name


def gate_findings(corner: str, results: dict) -> tuple[list[str], dict]:
    """Apply gates to whatever envelopes exist. Returns (findings, timing)."""
    findings: list[str] = []
    timing: dict = {"verdict": "not_run"}
    sta = results.get("sta")
    if sta is not None:
        verdict, note = run_flow.evaluate_timing(
            sta.get("worst_slack_ns"), sta.get("total_negative_slack_ns"), None
        )
        timing = {
            "verdict": verdict,
            "note": note,
            "worst_slack_ns": sta.get("worst_slack_ns"),
            "total_negative_slack_ns": sta.get("total_negative_slack_ns"),
            "coverage": TIMING_COVERAGE,
        }
        if verdict != "pass":
            findings.append(f"{corner}: timing verdict {verdict!r} is not a constrained pass")
    lvs = results.get("lvs")
    if lvs is not None:
        if lvs.get("status") != "match" or lvs.get("error_count"):
            findings.append(
                f"{corner}: LVS is {lvs.get('status')!r} with {lvs.get('error_count')} error(s)"
            )
        power = run_flow.power_connectivity_meta(lvs)
        if power["status"] != "match":
            findings.append(f"{corner}: LVS power connectivity is {power['status']!r}, not 'match'")
        if power.get("unchecked_expected_pins"):
            findings.append(
                f"{corner}: LVS power connectivity left pin(s) "
                f"{', '.join(power['unchecked_expected_pins'])} unchecked"
            )
    drc = results.get("drc")
    if drc is not None and drc.get("status") != "clean":
        findings.append(
            f"{corner}: DRC is {drc.get('status')!r} with {drc.get('violation_count')} violation(s)"
        )
    return findings, timing


def run_corner(corner: str, work: Path, env: dict, runner: Runner = run_flow.run_klt) -> dict:
    """Run stages 2-6 for one corner; always writes summary.json, even on failure."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    results: dict[str, dict] = {}
    files: dict[str, dict] = {}
    stage_status = {s: "not_run" for s in STAGE_ORDER}
    error: str | None = None
    failed_stage: str | None = None
    current = None

    def need(envelope: dict, key: str, stage: str) -> str:
        return run_flow.envelope_path(envelope.get(key), f"{stage}.{key}")

    try:
        problems = static_gate_problems(corner)
        if problems:
            raise run_flow.StageError("template invariants violated: " + "; ".join(problems))
        if not NETLIST.is_file():
            raise run_flow.StageError(f"input netlist missing: {run_flow.rel_to_repo(NETLIST)}")

        def record(stage, envelope, request_name=None, request=None):
            results[stage] = envelope
            files[stage] = {"envelope": _save(work, f"{stage}-report.json", envelope)}
            if request_name:
                files[stage]["request"] = request_name
            stage_status[stage] = "ran"

        current = "place_and_route"
        req = resolve_par(corner, str(NETLIST))
        _save(work, "request-par.json", req)
        par = runner(["place-and-route", "request-par.json"], work, env)
        record(current, par, "request-par.json")
        paths = {
            "def": need(par, "def_path", current),
            "gds": need(par, "gds_path", current),
            "verilog": need(par, "verilog_path", current),
        }

        current = "sta"
        _save(work, "request-sta.json", resolve_sta(corner, paths["def"]))
        record(current, runner(["sta", "request-sta.json"], work, env), "request-sta.json")

        current = "extract"
        out = (work / ".klt" / "extract" / f"{TOP}.gate.spice").resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = extract_argv(paths["gds"], str(out))
        _save(work, "invocation-extract.json", {"argv": ["klt", *argv]})
        record(current, runner(argv, work, env), "invocation-extract.json")
        if not out.is_file() and results[current].get("netlist_path"):
            out = Path(need(results[current], "netlist_path", current))

        current = "lvs"
        _save(work, "request-lvs.json", resolve_lvs(str(out), paths["verilog"]))
        record(current, runner(["lvs", "request-lvs.json"], work, env), "request-lvs.json")

        current = "drc"
        argv = drc_argv(paths["gds"])
        _save(work, "invocation-drc.json", {"argv": ["klt", *argv]})
        record(current, runner(argv, work, env), "invocation-drc.json")
        current = None
    except run_flow.StageError as exc:
        error = str(exc)
        failed_stage = current
        if current in stage_status and stage_status[current] == "not_run":
            stage_status[current] = "failed"

    findings, timing = gate_findings(corner, results)
    if error:
        findings.append(f"{corner}: stage failure at {failed_stage or 'setup'}: {error}")
    summary = {
        "schema": SUMMARY_SCHEMA,
        "experiment": EXPERIMENT,
        "top": TOP,
        "corner": corner,
        "created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": run_flow.git_revision(),
        "input_netlist": run_flow.rel_to_repo(NETLIST),
        "stage_status": stage_status,
        "files": files,
        "timing": timing,
        "gate_findings": findings,
        "stage_error": error,
        "failed_stage": failed_stage,
        "claims": NO_CLAIMS,
    }
    run_flow.write_json(work / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corners", help="comma-separated subset (default: all committed corners)")
    ap.add_argument("--dry-run", action="store_true", help="print the resolved plan and exit")
    args = ap.parse_args(argv)

    committed = committed_corners()
    corners = [c.strip() for c in args.corners.split(",")] if args.corners else committed
    unknown = [c for c in corners if c not in committed]
    if unknown:
        print(f"run_physical_utmi_top: corner(s) not in the committed matrix: {unknown}", file=sys.stderr)
        return 2

    print("flow/run_physical_utmi_top.py")
    print(f"  top      : {TOP}")
    print(f"  netlist  : {run_flow.rel_to_repo(NETLIST)}")
    print(f"  corners  : {', '.join(corners)}")
    print(f"  timing   : {TIMING_COVERAGE['note']}")
    if args.dry_run:
        for corner in corners:
            bad = static_gate_problems(corner)
            print(f"\n== corner {corner} ==" + (f"  TEMPLATE PROBLEMS: {bad}" if bad else ""))
            for step in plan(corner, BUILD_ROOT / corner):
                print(f"  {step['stage']:<16} klt {' '.join(step['cmd'])}")
        print("\n  dry run -- nothing executed")
        return 0

    if shutil.which("klt") is None:
        print("run_physical_utmi_top: `klt` is not on PATH", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env.setdefault("PDK", "sky130A")
    if run_flow.resolve_pdk_root(env) is None:
        print("run_physical_utmi_top: could not resolve a PDK root", file=sys.stderr)
        return 2

    worst = 0
    for corner in corners:
        print(f"\n== corner {corner} ==")
        summary = run_corner(corner, BUILD_ROOT / corner, env)
        print(f"  timing={summary['timing']['verdict']}  stages={summary['stage_status']}")
        for f in summary["gate_findings"]:
            print(f"  - {f}", file=sys.stderr)
        if summary["stage_error"]:
            worst = 2
        elif summary["gate_findings"]:
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    sys.exit(main())
