#!/usr/bin/env python3
"""Synthesize the real UTMI datapath (`usb_utmi_top`) and write one synthesis-only record.

This is the sibling of `flow/run_flow.py`, not a mode of it: `run_flow.py` is
the six-stage driver for the `smoke-utmi_stub` toolchain experiment and is
left untouched (its records must stay byte-identical). This driver runs only
stage 1 -- `klt synthesize` -- for the experiment `utmi-top`, plus a
gate-level re-run of `verification/test_usb_utmi_top.py` against the
resulting netlist. It does no place-and-route, STA, extraction, LVS or DRC;
the record it writes says so (`record_kind: "synthesis-only"`,
`stages.<stage>.status: "not_run"`), and `flow/check_records.py` refuses a
synthesis-only record that carries any result for a stage that did not run.

Steps:

  1. `klt synthesize` the committed request `flow/request-synth-usb_utmi_top.json`
     twice, from two clean scratch directories under `flow/build/utmi-top/`,
     and require the two netlists to be byte-identical (no normalisation is
     applied -- the Yosys output carries no host paths or timestamps).
  2. Copy the netlist to `design/netlist/usb_utmi_top.v`.
  3. Run the existing RTL suite and the same suite against the netlist
     (`klt functional-verification`, sky130_fd_sc_hd behavioural models
     supplied as extra sources) and keep the exact outcomes.
  4. Write the envelope(s), the gate-level request, the record, and refresh
     `flow/utmi-top/records/MANIFEST.sha256`.

Usage:

    PDK=sky130A python3 flow/run_synth_utmi_top.py
    python3 flow/run_synth_utmi_top.py --dry-run

`klt functional-verification` needs cocotb in klt's own environment, which the
shared worker's `klt` does not have and this repo does not install into host
tools. The default `--fv-klt` is therefore a throwaway uvx environment:
`uvx --from klayout-tools==0.7.0 --with cocotb==2.0.1 klt`.

Exit codes: 0 recorded, 2 a stage or the environment failed outright, 1 the
two synthesis runs disagreed.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

FLOW_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FLOW_DIR))
import run_flow  # noqa: E402  (path set above on purpose)
from check_records import RECORD_SCHEMA, sha256_file  # noqa: E402

REPO_ROOT = run_flow.REPO_ROOT
EXPERIMENT = "utmi-top"
TOP = "usb_utmi_top"
SYNTH_REQUEST = FLOW_DIR / "request-synth-usb_utmi_top.json"
FV_TEMPLATE = FLOW_DIR / EXPERIMENT / "gatelevel-fv-request.template.json"
RTL_FV_REQUEST = REPO_ROOT / "verification" / "request-usb-utmi_top.json"
NETLIST_REL = "design/netlist/usb_utmi_top.v"
CELL_LIBRARY = "sky130_fd_sc_hd"
DEFAULT_FV_KLT = "uvx --from klayout-tools==0.7.0 --with cocotb==2.0.1 klt"
SCRATCH = run_flow.BUILD_DIR / EXPERIMENT

FLIP_FLOP_RE = re.compile(r"^sky130_fd_sc_hd__(s?e?df|dlx|dlr|dlxb|dlrb|dfx)")

CLOCKS = [
    {
        "port": "clk_144",
        "frequency_mhz": 144,
        "period_ns": 6.944,
        "role": "bit-recovery / RX framing / TX serialiser domain",
    },
    {
        "port": "clk_utmi",
        "frequency_mhz": 30,
        "period_ns": 33.333,
        "role": "UTMI interface domain (RxValid/DataIn/TxReady/...)",
    },
]

CLOCK_NOTE = (
    "The design has TWO clocks -- `clk_144` at 144 MHz and `clk_utmi` at 30 MHz, "
    "asynchronous to each other and joined by the CDC in rtl/usb_rx_cdc.v and the "
    "2-flop synchronisers in rtl/usb_utmi_top.v. `klt synthesize`'s request carries "
    "a single `constraints.clock_period_ns`; the committed request sets 33.333 "
    "(the 30 MHz period) and that value only steers ABC's delay target. It does not "
    "describe the 144 MHz domain, and no per-clock constraint was applied. Nothing "
    "in this record is a timing claim for either domain."
)

TOOL_GAPS = [
    # `klt synthesize` has one clock_period_ns for a two-clock design.
    "https://github.com/2AMLogic/klayout-tools/issues/2883",
    # `options.defines` with a null value fails in released klt 0.7.0.
    "https://github.com/2AMLogic/klayout-tools/issues/2884",
]

STAGES_NOT_RUN_REASON = (
    "Out of scope for this record: issue #104 is synthesis only. Place and route, "
    "timing, extraction, LVS and DRC for the real top are the follow-on issue #105; "
    "nothing here is a result for this stage."
)

SUBSET_JUSTIFICATION = (
    "Nominal-corner synthesis only (tt_025C_1v80). Logic synthesis here is not "
    "PVT-dependent in the way timing is: Yosys/ABC map against one liberty deck "
    "(the nominal one `klt synthesize` selects) and the resulting netlist is the "
    "same structural object at every corner. The other five corners of the "
    "committed matrix matter for STA, which was not run; this record therefore "
    "establishes no six-corner timing claim and no timing claim at all."
)

GATE_LEVEL_NOTES = [
    "Zero-delay functional models only: sky130_fd_sc_hd primitives.v + "
    "sky130_fd_sc_hd.v compiled with -DFUNCTIONAL and without USE_POWER_PINS "
    "(the synthesised netlist instantiates cells without VPWR/VGND). No SDF, no "
    "timing, no power-aware simulation.",
    "The suite is the unmodified verification/test_usb_utmi_top.py. Its CDC "
    "structure tests read RTL-internal nets by name (`dut.term_select_144` etc.). "
    "A name that synthesis optimised away is an AttributeError, reported as a "
    "failure -- the test was not weakened to hide it.",
]


def say(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
def liberty_cell_areas(pdk_root: str, variant: str, deck_name: str) -> dict[str, float]:
    lib = Path(pdk_root) / variant / "libs.ref" / CELL_LIBRARY / "lib" / f"{deck_name}.lib"
    if not lib.is_file():
        raise run_flow.StageError(f"liberty file not found for area-by-cell: {lib}")
    areas: dict[str, float] = {}
    current = None
    cell_re = re.compile(r'^\s*cell\s*\(\s*"?([^")\s]+)"?\s*\)')
    area_re = re.compile(r"^\s*area\s*:\s*([0-9.eE+-]+)\s*;")
    for line in lib.read_text(encoding="utf-8", errors="replace").splitlines():
        m = cell_re.match(line)
        if m:
            current = m.group(1)
            continue
        m = area_re.match(line)
        if m and current and current not in areas:
            areas[current] = float(m.group(1))
    return areas


def synth_once(tag: str, env: dict[str, str]) -> tuple[dict, Path, Path]:
    work = SCRATCH / tag
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    request = copy.deepcopy(run_flow.load_json(SYNTH_REQUEST))
    request["sources"] = [run_flow.abs_from_flow(s) for s in request["sources"]]
    req_path = work / "request-synth.json"
    run_flow.write_json(req_path, request)
    envelope = run_flow.run_klt(["synthesize", req_path.name], work, env)
    netlist = Path(run_flow.envelope_path(envelope.get("netlist_path"), "synthesize.netlist_path"))
    return envelope, netlist, req_path


def fv_run(fv_klt: list[str], request: dict, env: dict[str, str], name: str) -> tuple[dict, int]:
    """Run `klt functional-verification`; the testbench module resolves from verification/."""
    req_path = REPO_ROOT / "verification" / f"_{name}.tmp.json"
    run_flow.write_json(req_path, request)
    try:
        cmd = [*fv_klt, "functional-verification", req_path.name, "--format", "json"]
        say(f"    $ (cd verification && {' '.join(cmd)})")
        result = subprocess.run(
            cmd, cwd=str(REPO_ROOT / "verification"), env=env, capture_output=True, text=True
        )
    finally:
        req_path.unlink(missing_ok=True)
    try:
        return json.loads(result.stdout), result.returncode
    except json.JSONDecodeError:
        raise run_flow.StageError(
            f"functional-verification emitted no JSON (exit {result.returncode}): "
            f"{result.stderr.strip()[:400]}"
        )


def fv_summary(report: dict, rc: int) -> dict:
    failed = [
        {"name": t["name"], "error_type": t.get("error_type"), "error_message": t.get("error_message")}
        for t in report.get("tests", [])
        if t.get("status") != "passed"
    ]
    return {
        "status": report.get("status"),
        "exit_code": rc,
        "test_count": report.get("test_count"),
        "passed_count": report.get("passed_count"),
        "failed_count": report.get("failed_count"),
        "skipped_count": report.get("skipped_count"),
        "failing_tests": failed,
        "engine": report.get("engine"),
        "engine_version": (report.get("environment") or {}).get("engine_version"),
        "cocotb_version": (report.get("environment") or {}).get("cocotb_version"),
    }


def sources_in_request() -> list[str]:
    doc = run_flow.load_json(SYNTH_REQUEST)
    return [str((FLOW_DIR / s).resolve().relative_to(REPO_ROOT)) for s in doc["sources"]]


def read_klt_version(klt_cmd: list[str], env: dict[str, str]) -> str | None:
    r = subprocess.run([*klt_cmd, "--version"], capture_output=True, text=True, env=env)
    return r.stdout.strip() if r.returncode == 0 else None


def render(meta: dict) -> str:
    s = meta["stages"]["synthesize"]
    fv = meta["stages"]["gate_level_functional_verification"]
    rtl = meta["stages"]["rtl_functional_verification"]
    rows = "\n".join(
        f"| `{c}` | {n} | {s['area_by_cell_um2'][c]:.4f} |"
        for c, n in sorted(s["instance_counts_by_type"].items())
    )
    failing = (
        "\n".join(f"  - `{t['name']}`: {t['error_type']}: {t['error_message']}" for t in fv["failing_tests"])
        or "  - none"
    )
    artifacts = "\n".join(f"- `{a['path']}` `{a['content_hash']}`" for a in meta["provenance"]["artifacts"])
    return f"""<!-- record-meta
{json.dumps(meta, indent=2)}
-->

# {meta['record_id']}

**Synthesis-only record** for experiment `{EXPERIMENT}` (`{meta['design']['hdl_toplevel']}`).
Stages 2-6 (place and route, STA, extraction, LVS, DRC) were NOT run; this record
makes no timing, DRC or LVS claim. `design.anchors_design_claim` is true because
this is the real datapath, not the toolchain-smoke stub.

## Synthesis

- Engine: yosys {s['engine_version']}, deck `{s['liberty_deck']['name']}`, corner `{meta['corner']}`
- Cells: **{s['instance_count']}**, of which **{s['flip_flop_count']}** flip-flops
- Area: {s['area_um2']} um^2 total, {s['sequential_area_um2']} um^2 sequential
- Netlist: `{s['netlist']['path']}` `sha256:{s['netlist']['sha256']}`
- Reproduction: {s['reproduction']['note']}
- Structural verdict: `{json.dumps(s['structural'])}`

### Finding: a combinational loop in the RTL

{s['comb_loop_finding']}

### Clocks

{meta['design']['clock_note']}

### Area by cell

| cell | count | area (um^2) |
|---|---:|---:|
{rows}

## Functional verification

- RTL (`verification/request-usb-utmi_top.json`): {rtl['status']} -- {rtl['passed_count']}/{rtl['test_count']} passed.
- Gate level (this netlist + sky130_fd_sc_hd models): **{fv['status']}** -- {fv['passed_count']}/{fv['test_count']} passed, {fv['failed_count']} failed.
{failing}

{chr(10).join('- ' + n for n in fv['notes'])}

## Not run

Place and route, STA, extraction, LVS and DRC: {STAGES_NOT_RUN_REASON}

## Artifacts

{artifacts}
"""


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fv-klt", default=DEFAULT_FV_KLT, help="command prefix for klt functional-verification")
    args = ap.parse_args(argv)

    corners_cfg = run_flow.load_json(FLOW_DIR / "corners.json")
    corner = run_flow.load_json(SYNTH_REQUEST)["pdk"]["corner"]
    say("flow/run_synth_utmi_top.py")
    say(f"  experiment : {EXPERIMENT}")
    say(f"  request    : {run_flow.rel_to_repo(SYNTH_REQUEST)}  (corner {corner})")
    say(f"  sources    : {len(sources_in_request())} rtl/usb_*.v")
    if args.dry_run:
        say("  dry run -- nothing executed")
        return 0

    env = dict(os.environ)
    env.setdefault("PDK", "sky130A")
    pdk_root = run_flow.resolve_pdk_root(env)
    if pdk_root is None:
        print("run_synth_utmi_top: could not resolve a PDK root", file=sys.stderr)
        return 2
    variant = env["PDK"]

    try:
        say("  [1/3] klt synthesize (run A)")
        env_a, net_a, _ = synth_once("run-a", env)
        say("        klt synthesize (run B, fresh scratch dir)")
        env_b, net_b, req_path = synth_once("run-b", env)
        identical = net_a.read_bytes() == net_b.read_bytes()
        if not identical:
            print(
                "run_synth_utmi_top: the two synthesis runs produced DIFFERENT netlists "
                f"({sha256_file(net_a)} vs {sha256_file(net_b)}); refusing to commit. "
                "A normalisation rule must be documented and committed first.",
                file=sys.stderr,
            )
            return 1
        netlist_dest = REPO_ROOT / NETLIST_REL
        netlist_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(net_a, netlist_dest)
        if sha256_file(netlist_dest).split(":")[1] != env_a["netlist_sha256"]:
            raise run_flow.StageError("committed netlist hash != envelope netlist_sha256")

        stats_path = next(net_a.parent.glob(f"{TOP}_stats.json"))
        stats = run_flow.load_json(stats_path)
        areas = liberty_cell_areas(pdk_root, variant, env_a["provenance"]["deck"]["name"])
        counts = env_a["instance_counts_by_type"]
        area_by_cell = {c: round(n * areas[c], 4) for c, n in counts.items()}
        if abs(sum(area_by_cell.values()) - env_a["area_um2"]) > 0.01:
            raise run_flow.StageError("per-cell area does not sum to the envelope area_um2")
        ff = sum(n for c, n in counts.items() if FLIP_FLOP_RE.match(c))

        fv_klt = shlex.split(args.fv_klt)
        say("  [2/3] RTL functional verification")
        rtl_req = run_flow.load_json(RTL_FV_REQUEST)
        rtl_req["sources"] = [str((RTL_FV_REQUEST.parent / s).resolve()) for s in rtl_req["sources"]]
        rtl_rep, rtl_rc = fv_run(fv_klt, rtl_req, env, "rtl")

        say("  [3/3] gate-level functional verification")
        verilog_dir = Path(pdk_root) / variant / "libs.ref" / CELL_LIBRARY / "verilog"
        gl_req = run_flow.load_json(FV_TEMPLATE)
        gl_req["sources"] = [
            str(verilog_dir / "primitives.v"),
            str(verilog_dir / f"{CELL_LIBRARY}.v"),
            str(netlist_dest),
        ]
        gl_rep, gl_rc = fv_run(fv_klt, gl_req, env, "gl")
        fv_klt_version = read_klt_version(fv_klt, env)
    except run_flow.StageError as exc:
        print(f"\nrun_synth_utmi_top: stage failed:\n  {exc}", file=sys.stderr)
        return 2

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    record_id = f"{stamp}-{run_flow.git_revision()[:7]}-{corner}"
    experiment_dir = FLOW_DIR / EXPERIMENT
    records_dir = experiment_dir / "records"
    artifacts_dir = experiment_dir / "artifacts" / record_id
    records_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    run_flow.write_json(artifacts_dir / "synthesize-report.json", env_a)
    shutil.copyfile(req_path, artifacts_dir / "request-synth.json")
    run_flow.write_json(artifacts_dir / "functional-verification-rtl-report.json", rtl_rep)
    run_flow.write_json(artifacts_dir / "functional-verification-gatelevel-report.json", gl_rep)
    run_flow.write_json(artifacts_dir / "request-gatelevel-fv.json", gl_req)

    loop_warn = [
        w for w in (env_a.get("warnings") or {}).get("representatives", []) if w.get("category") == "logic_loop"
    ]
    comb_loops = (env_a.get("structural") or {}).get("comb_loops")
    comb_loop_finding = (
        f"`klt synthesize` exited 3 (structural verdict: {comb_loops} combinational loop(s), "
        f"critical). Yosys reports `found logic loop in module usb_rx_cdc` "
        f"({sum(w['count'] for w in loop_warn)} warning(s)): in rtl/usb_rx_cdc.v, "
        "`wr_en = rx_byte_valid & ~full`, `full` is computed from `wptr_gray_next`, which is "
        "computed from `wptr_bin_next = wptr_bin + wr_en`. The write enable therefore depends "
        "combinationally on itself. This is an RTL property, not a synthesis artefact; the RTL "
        "was not modified by this record (out of scope, and the committed pre-layout evidence "
        "describes this RTL). The netlist was still emitted and is committed as-is so the defect "
        "is visible; it is not a clean netlist and must not be read as one."
    )
    inputs = [
        {"path": p, "content_hash": sha256_file(REPO_ROOT / p)} for p in sources_in_request()
    ] + [
        {"path": run_flow.rel_to_repo(p), "content_hash": sha256_file(p)}
        for p in (
            SYNTH_REQUEST,
            FV_TEMPLATE,
            RTL_FV_REQUEST,
            REPO_ROOT / "verification" / "test_usb_utmi_top.py",
            FLOW_DIR / "corners.json",
        )
    ]
    artifacts = [
        {
            "path": f"flow/{EXPERIMENT}/artifacts/{record_id}/{p.name}",
            "content_hash": sha256_file(p),
        }
        for p in sorted(artifacts_dir.iterdir())
        if p.is_file()
    ] + [{"path": NETLIST_REL, "content_hash": sha256_file(netlist_dest)}]

    not_run = {"status": "not_run", "reason": STAGES_NOT_RUN_REASON}
    sha = env_a["netlist_sha256"]
    meta = {
        "schema": RECORD_SCHEMA,
        "record_kind": "synthesis-only",
        "record_id": record_id,
        "experiment": EXPERIMENT,
        "corner": corner,
        "created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": run_flow.git_revision(),
        "supersedes": run_flow.latest_record_for_corner(records_dir, corner),
        "design": {
            "hdl_toplevel": TOP,
            "sources": sources_in_request(),
            "anchors_design_claim": True,
            "what_this_is": (
                "The real UTMI digital datapath (usb_utmi_top and its submodules) mapped to "
                "sky130_fd_sc_hd by Yosys. Evidence for the gate-level netlist existing and "
                "its size; no timing, physical, DRC or LVS claim."
            ),
            "clocks": CLOCKS,
            "clock_note": CLOCK_NOTE,
        },
        "corner_matrix": {
            "committed": list(corners_cfg["committed"]),
            "run": [corner],
            "subset_justification": SUBSET_JUSTIFICATION,
            "source": corners_cfg.get("source"),
        },
        "stages": {
            "synthesize": {
                "status": "ok",
                "engine": env_a.get("engine"),
                "engine_version": env_a.get("engine_version"),
                "instance_count": env_a["instance_count"],
                "flip_flop_count": ff,
                "area_um2": env_a["area_um2"],
                "sequential_area_um2": env_a["sequential_area_um2"],
                "instance_counts_by_type": counts,
                "area_by_cell_um2": area_by_cell,
                "area_by_cell_note": (
                    "count x the liberty `area` attribute of the deck named below; the sum "
                    "is checked against the envelope's area_um2."
                ),
                "hierarchical_stats": {
                    m.lstrip("\\"): {
                        "num_cells": v.get("num_cells"),
                        "area_um2": v.get("area"),
                        "sequential_area_um2": v.get("sequential_area"),
                    }
                    for m, v in stats["modules"].items()
                },
                "structural": env_a.get("structural"),
                "klt_exit_code": 3 if (env_a.get("structural") or {}).get("has_critical") else 0,
                "comb_loop_finding": comb_loop_finding,
                "warnings": env_a.get("warnings"),
                "critical_path_estimate": {
                    **(env_a.get("timing") or {}),
                    "note": "ABC's own estimate, single clock target; NOT a timing result.",
                },
                "liberty_deck": env_a["provenance"]["deck"],
                "netlist": {"path": NETLIST_REL, "sha256": sha},
                "reproduction": {
                    "runs": 2,
                    "byte_identical": True,
                    "normalisation": "none",
                    "note": (
                        "Two `klt synthesize` runs from the committed request, each in a fresh "
                        "scratch directory (flow/build/utmi-top/run-a, run-b), produced "
                        f"byte-identical netlists (sha256 {sha}). The Yosys header comment "
                        "carries the Yosys version and git sha but no host path or timestamp, "
                        "so no normalisation is applied. A different Yosys build may differ."
                    ),
                },
            },
            "place_and_route": dict(not_run),
            "sta": dict(not_run),
            "extract": dict(not_run),
            "lvs": dict(not_run),
            "drc": dict(not_run),
            "rtl_functional_verification": fv_summary(rtl_rep, rtl_rc),
            "gate_level_functional_verification": {
                **fv_summary(gl_rep, gl_rc),
                "request": f"flow/{EXPERIMENT}/artifacts/{record_id}/request-gatelevel-fv.json",
                "request_template": run_flow.rel_to_repo(FV_TEMPLATE),
                "netlist": NETLIST_REL,
                "cell_models": [
                    f"{CELL_LIBRARY}/verilog/primitives.v",
                    f"{CELL_LIBRARY}/verilog/{CELL_LIBRARY}.v",
                ],
                "fv_klt_version": fv_klt_version,
                "notes": GATE_LEVEL_NOTES,
            },
        },
        "provenance": {
            "klt_version": env_a["provenance"]["klt_version"],
            "klayout_version": env_a["provenance"].get("klayout_version"),
            "openroad_version": None,
            "yosys_version": env_a.get("engine_version"),
            "pdk": env_a["provenance"].get("pdk"),
            "inputs": inputs,
            "artifacts": artifacts,
        },
        "tool_gaps": TOOL_GAPS,
    }

    record_path = records_dir / f"{record_id}.md"
    record_path.write_text(render(meta), encoding="utf-8")
    run_flow.rebuild_manifest(records_dir)
    say(f"  record -> {run_flow.rel_to_repo(record_path)}")
    say(f"  cells {meta['stages']['synthesize']['instance_count']}  ff {ff}  "
        f"gate-level FV {gl_rep.get('status')} ({gl_rep.get('passed_count')}/{gl_rep.get('test_count')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
