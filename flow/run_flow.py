#!/usr/bin/env python3
"""Drive this repo's digital physical flow and write one evidence record per corner.

Stages, in order, all through `klt` -- never a raw `openroad`/`klayout`
subprocess (CLAUDE.md):

    klt synthesize  ->  klt place-and-route  ->  klt sta
                                             ->  klt extract  ->  klt lvs
                                             ->  klt drc

Each stage is driven by a committed request document under `flow/`. This
script does exactly three things to those documents: it substitutes the
corner, it rewrites relative paths to absolute (so a per-corner build
directory cannot change what a request means), and it chains one stage's
output path into the next stage's input. It never invents a parameter that
is not in a committed file.

Two of the six stages -- `klt extract` and `klt drc` -- have no
request-document surface in `klt` at all (argv only; filed upstream as
klayout-tools#1867), so their committed documents carry a repo-local
`usb2phy.flow.*-invocation/1` schema that this script translates into argv.
They are deliberately NOT labelled as `klt` schemas.

Usage:

    PDK=sky130A python3 flow/run_flow.py                 # every committed corner
    PDK=sky130A python3 flow/run_flow.py --corners tt_025C_1v80
    python3 flow/run_flow.py --dry-run                   # print the plan, run nothing

Exit codes: 0 all corners recorded and every gate passed, 1 a gate failed
(negative WNS with no waiver, DRC violations, LVS mismatch, ...), 2 a stage
or the environment failed outright.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_DIR = REPO_ROOT / "flow"
BUILD_DIR = FLOW_DIR / "build"  # gitignored scratch
LAYOUT_DIR = REPO_ROOT / "layout"

sys.path.insert(0, str(FLOW_DIR))
from check_records import (  # noqa: E402  (path set above on purpose)
    UNCONSTRAINED_SENTINEL_FLOOR,
    is_sentinel,
    sha256_file,
)

RECORD_SCHEMA = "usb2phy.flow.record/1"
EXPERIMENT = "smoke-utmi_stub"

TOOL_GAPS = [
    "https://github.com/2AMLogic/klayout-tools/issues/1865",
    "https://github.com/2AMLogic/klayout-tools/issues/1866",
    "https://github.com/2AMLogic/klayout-tools/issues/1867",
    "https://github.com/2AMLogic/klayout-tools/issues/1868",
    "https://github.com/2AMLogic/klayout-tools/issues/2073",
    "https://github.com/2AMLogic/klayout-tools/issues/2076",
]

UNCONSTRAINED_NOTE = (
    "No constrained timing path exists in this design, at any corner. "
    "`utmi_stub` is nine flip-flops whose D inputs are primary input ports and "
    "whose Q outputs are primary output ports -- there is no register-to-register "
    "path anywhere in it. Neither `klt place-and-route` nor `klt sta` has any "
    "surface for `set_input_delay`/`set_output_delay` or a caller-supplied SDC "
    "(both emit `create_clock` and nothing else), so the input and output ports "
    "carry no arrival or required time and OpenSTA has no startpoint or endpoint "
    "to time. Every timing field in this record is therefore OpenSTA's "
    "unconstrained sentinel -- literally `1e+39` -- and NOT a measured margin. "
    "It is a positive number, so a naive `wns >= 0` gate would read it as an "
    "enormous margin; this flow classifies it as its own verdict instead, and "
    "`flow/check_records.py` refuses any record that calls it a pass. Filed "
    "upstream as klayout-tools#1865. This record makes no timing-closure claim "
    "at this or any corner: the per-corner numbers are evidence that the "
    "multi-corner plumbing runs and reports, not evidence that anything closed."
)


class StageError(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def run_klt(args: list[str], cwd: Path, env: dict[str, str]) -> dict:
    """Run a klt subcommand with --format json and return the parsed envelope."""
    cmd = ["klt", *args, "--format", "json"]
    log(f"    $ (cd {cwd.relative_to(REPO_ROOT)} && {' '.join(cmd)})")
    result = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    stdout = result.stdout.strip()
    if not stdout:
        raise StageError(
            f"`{' '.join(cmd)}` produced no JSON on stdout (exit {result.returncode})\n"
            f"{result.stderr.strip()}"
        )
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise StageError(f"`{' '.join(cmd)}` emitted unparseable JSON: {exc}\n{stdout[:400]}")
    if isinstance(envelope, dict) and "error" in envelope:
        raise StageError(
            f"`{' '.join(cmd)}` failed: {envelope['error'].get('message', envelope['error'])}"
        )
    # `klt lvs` exits 3 on a mismatch and still emits a valid envelope -- that
    # is a verdict, not a crash, so it is handled by the caller, not here.
    if result.returncode not in (0, 3):
        raise StageError(
            f"`{' '.join(cmd)}` exited {result.returncode}\n{result.stderr.strip()}"
        )
    return envelope


def resolve_pdk_root(env: dict[str, str]) -> str | None:
    """Resolve the PDK root klt will actually use, and pin it into the env.

    Workaround for klayout-tools#1868: `klt place-and-route` can resolve a PDK
    through its own search order (e.g. ~/.volare) with `$PDK_ROOT` unset, but
    the documented container wrapper for `openroad` only bind-mounts
    `$PDK_ROOT`. The stage then dies on an opaque `cannot read file <liberty>`
    from inside the container. Asking `klt pdk find` which root won and
    exporting it makes the two agree. Remove once #1868 is fixed.
    """
    if env.get("PDK_ROOT"):
        return env["PDK_ROOT"]
    if shutil.which("klt") is None:
        return None
    cmd = ["klt", "pdk", "find", "--format", "json"]
    if env.get("PDK"):
        cmd = ["klt", "pdk", "find", "--pdk", env["PDK"], "--format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return None
    try:
        root = json.loads(result.stdout).get("root")
    except json.JSONDecodeError:
        return None
    if root:
        env["PDK_ROOT"] = root
        log(f"  PDK_ROOT was unset; pinned to klt's own resolved root: {root}")
        log("    (workaround for klayout-tools#1868 -- see flow/README.md)")
    return root


def openroad_version() -> str | None:
    if shutil.which("openroad") is None:
        return None
    result = subprocess.run(["openroad", "-version"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip().splitlines()[0].strip() if result.stdout.strip() else None


def git_revision() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=False)
        handle.write("\n")


def abs_from_flow(value: str) -> str:
    """Resolve a path written relative to flow/ into an absolute path."""
    return str((FLOW_DIR / value).resolve())


def rel_to_repo(path: str | Path) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def envelope_path(value, field: str) -> str:
    """Resolve one `klt` response path field to an absolute filesystem path.

    Two shapes are in the wild for the same field, and this flow has to chain
    whichever one the installed `klt` emits into the next stage:

    * a plain absolute path string -- every stage emitted this before
      klayout-tools#1844, and `klt place-and-route`'s `def_path`/`gds_path`/
      `verilog_path` still do;
    * a `{"path": <repo-relative POSIX path>, "scope": "repo"|"external"|
      "absent"}` object -- `klt synthesize`'s `netlist_path`/`script_path`
      since klayout-tools#1844, with `schema_version` left at 1, so a
      consumer cannot detect the change from the envelope and must accept
      both shapes. Filed upstream as klayout-tools#2073.

    The object form is repo-relative to the *invoking* repo, which is this
    repo -- `run_flow.py` always runs `klt` with a cwd inside `flow/build/`.
    """
    if isinstance(value, str) and value:
        return str(Path(value).resolve())
    if isinstance(value, dict):
        scope = value.get("scope")
        path = value.get("path")
        if scope == "repo" and isinstance(path, str) and path:
            return str((REPO_ROOT / path).resolve())
        raise StageError(
            f"`{field}` is a path object this flow cannot resolve: {value!r}. "
            "Only `scope: \"repo\"` is chainable -- an `external`/`absent` "
            "scope carries no path at all (klayout-tools#2073)."
        )
    raise StageError(f"`{field}` is missing from the stage response: {value!r}")


# --------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------
def stage_synthesize(corner: str, work: Path, env: dict[str, str]) -> dict:
    template = load_json(FLOW_DIR / "request-synth-utmi_stub.json")
    request = copy.deepcopy(template)
    request["pdk"]["corner"] = corner
    request["sources"] = [abs_from_flow(src) for src in request["sources"]]
    path = work / "request-synth.json"
    write_json(path, request)
    return run_klt(["synthesize", path.name], work, env)


def stage_place_and_route(
    corner: str, work: Path, netlist_path: str, env: dict[str, str]
) -> dict:
    template = load_json(FLOW_DIR / "request-par-utmi_stub.json")
    request = copy.deepcopy(template)
    request["pdk"]["corner"] = corner
    # `pdk.sweep_corners` is left exactly as committed: the request asks the
    # built-at-this-corner design to be re-timed across the whole committed
    # matrix in one OpenSTA session. Its per-corner rows are recorded as a
    # cross-check against the separate per-corner `klt sta` run, which is the
    # only way to get per-corner TNS (klayout-tools#1866).
    request["netlist"] = netlist_path
    path = work / "request-par.json"
    write_json(path, request)
    return run_klt(["place-and-route", path.name], work, env)


def stage_sta(corner: str, work: Path, def_path: str, env: dict[str, str]) -> dict:
    template = load_json(FLOW_DIR / "request-sta-utmi_stub.json")
    request = copy.deepcopy(template)
    request["pdk"]["corner"] = corner
    request["def"] = def_path
    path = work / "request-sta.json"
    write_json(path, request)
    return run_klt(["sta", path.name], work, env)


def stage_extract(work: Path, gds_path: str, env: dict[str, str]) -> tuple[dict, str]:
    doc = load_json(FLOW_DIR / "request-extract-utmi_stub.json")
    output = str((work / ".klt" / "extract" / Path(doc["output"]).name).resolve())
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    args = [
        "extract",
        gds_path,
        "--deck",
        doc["deck"],
        "--top",
        doc["top"],
        "-o",
        output,
    ]
    if doc.get("abstract_cells"):
        args += ["--abstract-cells", doc["abstract_cells"]]
    if doc.get("abstract_cell_lef"):
        args += ["--abstract-cell-lef", doc["abstract_cell_lef"]]
    if doc.get("def_net_names"):
        args += ["--def-net-names"]
    for key, value in (doc.get("deck_options") or {}).items():
        args += ["--deck-option", f"{key}={value}"]
    return run_klt(args, work, env), output


def stage_lvs(
    work: Path, layout_netlist: str, reference_netlist: str, env: dict[str, str]
) -> dict:
    template = load_json(FLOW_DIR / "request-lvs-utmi_stub.json")
    request = copy.deepcopy(template)
    request["layout"]["netlist"] = layout_netlist
    request["reference"]["netlist"] = reference_netlist
    path = work / "request-lvs.json"
    write_json(path, request)
    return run_klt(["lvs", path.name], work, env)


def stage_drc(work: Path, gds_path: str, env: dict[str, str]) -> dict:
    doc = load_json(FLOW_DIR / "request-drc-utmi_stub.json")
    args = ["drc", gds_path, "--deck", doc["deck"], "--engine", doc.get("engine", "curated")]
    if doc.get("top"):
        args += ["--top", doc["top"]]
    for key, value in (doc.get("deck_vars") or {}).items():
        args += ["--deck-var", f"{key}={value}"]
    if doc.get("timeout_s"):
        args += ["--timeout-s", str(doc["timeout_s"])]
    return run_klt(args, work, env)


# --------------------------------------------------------------------------
# Timing gate
# --------------------------------------------------------------------------
def evaluate_timing(wns, tns, waiver: dict | None) -> tuple[str, str]:
    """Classify one corner's timing result. Pure function -- unit tested.

    Returns `(verdict, note)` where verdict is one of pass / fail / waived /
    unconstrained. This is the gate issue #11 requires the flow to own:
    `klt place-and-route` reports scalar WNS/TNS and has no pass/fail concept.
    """
    if not isinstance(wns, (int, float)) or not isinstance(tns, (int, float)):
        return "fail", "STA reported no numeric slack at this corner."
    if is_sentinel(wns):
        return "unconstrained", UNCONSTRAINED_NOTE
    if wns < 0:
        if waiver:
            return (
                "waived",
                f"Negative setup WNS ({wns} ns, TNS {tns} ns) waived: "
                f"{waiver.get('reason', '').strip()}",
            )
        return (
            "fail",
            f"Negative setup WNS ({wns} ns, TNS {tns} ns) at this corner and no waiver "
            "in flow/waivers.json.",
        )
    return (
        "pass",
        f"Setup WNS {wns} ns, TNS {tns} ns -- non-negative at this corner, measured "
        "against a real constrained path.",
    )


# --------------------------------------------------------------------------
# Record writing
# --------------------------------------------------------------------------
def gap_digest(coverage: dict) -> list[dict]:
    return [
        {"id": gap["id"], "kind": gap["kind"], "summary": gap["summary"]}
        for gap in coverage.get("known_gaps", [])
        if isinstance(gap, dict)
    ]


def warnings_only_mismatches(lvs: dict) -> list[dict]:
    return [
        {
            "category": m.get("category"),
            "severity": m.get("severity"),
            "description": m.get("description"),
        }
        for m in lvs.get("mismatches", [])
        if m.get("severity") != "error"
    ]


def latest_record_for_corner(records_dir: Path, corner: str) -> str | None:
    """The newest already-committed record id for this corner, or `None`.

    Records are append-only: a re-run never edits or deletes what came before,
    it mints a new record that names its predecessor in `supersedes`. Filling
    that field in is what lets `flow/check_records.py` tell a *frozen* record
    (evidence of what the flow reported against an earlier revision of its own
    committed request documents) from a *stale* one (a standing claim whose
    inputs have since changed underneath it). Leaving it `None` -- as this
    script did before issue #59 -- meant any deliberate request change, such
    as adding the `power` block, retro-failed the freshness check on every
    record ever written.

    Record ids are `<YYYYMMDD>-<HHMMSS>-<sha>-<corner>`, so a lexical max over
    the same corner's ids is a chronological max.
    """
    if not records_dir.is_dir():
        return None
    ids = sorted(
        p.stem for p in records_dir.glob(f"*-{corner}.md") if p.stem.endswith(f"-{corner}")
    )
    return ids[-1] if ids else None


POWER_CONNECTIVITY_UNREPORTED_NOTE = (
    "This run's `klt lvs` emitted no `power_connectivity` block at all, so the "
    "power/ground half of LVS was NOT verified by this record. `klt lvs`'s "
    "reference form here is `gate-level-verilog`, whose reference netlist "
    "carries no supply pins; the signal compare therefore drops the layout's "
    "supply nets rather than failing on them, and a bare `status: \"match\"` "
    "from that compare says nothing whatsoever about whether the design is "
    "powered. The separate check that does say something -- "
    "`power_connectivity`, klayout-tools#1964 -- is missing from this klt "
    "build. Treat this as UNVERIFIED, never as a pass: that conflation is the "
    "exact defect issue #59 was filed about."
)

POWER_CONNECTIVITY_NOTE = (
    "`klt lvs`'s power/ground half of the verdict (klayout-tools#1964), "
    "reported beside `status` and never folded into it. A signal-only "
    "`gate-level-verilog` compare cannot see supply nets at all, so "
    "`status: \"match\"` alone is NOT a full-LVS pass -- this flow gates on "
    "both, and treats a `mismatch` here as a gate failure and an `unchecked` "
    "or absent block as UNVERIFIED. `expected_nets` comes from the committed "
    "`request-lvs-utmi_stub.json`: it makes the check absolute (each supply "
    "pin must reach the net named here) rather than merely self-consistent "
    "across instances. `unchecked_expected_pins` names any declared pin the "
    "check never resolved -- a non-empty list means part of this verdict was "
    "silently not asked (klayout-tools#1978) and this flow fails on it. Note "
    "that `power_pins` can also over-report: klayout-tools#2076 -- a dangling "
    "signal output is admitted as a power pin when the design has no other "
    "carrier of that pin name, which is why `Y` appears there."
)


def power_connectivity_meta(lvs: dict) -> dict:
    """Extract `klt lvs`'s power/ground verdict, distinguishing 'not reported'.

    `klt lvs` gained the `power_connectivity` block in klayout-tools#1964. A
    klt build predating it emits no such key -- which must NOT be read as
    "power is fine", so it is recorded as its own `"unreported"` status with
    the klt version that produced it, rather than defaulting to a pass.
    """
    block = lvs.get("power_connectivity")
    if not isinstance(block, dict):
        return {
            "status": "unreported",
            "reason": (
                "this `klt lvs` build emits no `power_connectivity` block "
                "(predates klayout-tools#1964)"
            ),
            "klt_version": (lvs.get("provenance") or {}).get("klt_version"),
            "power_pins": None,
            "instance_count": None,
            "expected_nets": None,
            "unchecked_expected_pins": None,
            "finding_count": None,
            "findings": [],
            "note": POWER_CONNECTIVITY_UNREPORTED_NOTE,
        }
    return {
        "status": block.get("status"),
        "reason": block.get("reason"),
        "klt_version": (lvs.get("provenance") or {}).get("klt_version"),
        "power_pins": block.get("power_pins"),
        "instance_count": block.get("instance_count"),
        "expected_nets": block.get("expected_nets"),
        "unchecked_expected_pins": block.get("unchecked_expected_pins"),
        "finding_count": block.get("finding_count"),
        "findings": [
            {
                "category": f.get("category"),
                "severity": f.get("severity"),
                "description": f.get("description"),
            }
            for f in (block.get("findings") or [])
            if isinstance(f, dict)
        ],
        "note": POWER_CONNECTIVITY_NOTE,
    }


def build_record_meta(
    *,
    record_id: str,
    corner: str,
    corners_run: list[str],
    corners_cfg: dict,
    subset_justification: str | None,
    synth: dict,
    par: dict,
    par_paths: dict[str, str],
    sta: dict,
    extract: dict,
    lvs: dict,
    drc: dict,
    coverage: dict,
    verdict: str,
    note: str,
    waiver: dict | None,
    inputs: list[dict],
    artifacts: list[dict],
    or_version: str | None,
    committed_copies: dict | None,
    supersedes: str | None,
) -> dict:
    return {
        "schema": RECORD_SCHEMA,
        "record_id": record_id,
        "experiment": EXPERIMENT,
        "corner": corner,
        "created_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": git_revision(),
        "supersedes": supersedes,
        "design": {
            "hdl_toplevel": synth.get("hdl_toplevel", "utmi_stub"),
            "sources": ["rtl/utmi_stub.v"],
            "anchors_design_claim": False,
            "what_this_is": (
                "Toolchain plumbing only. rtl/utmi_stub.v is nine flip-flops with no "
                "combinational logic and no USB protocol behaviour whatsoever. This "
                "record anchors no design claim about the USB 2.0 PHY."
            ),
        },
        "corner_matrix": {
            "committed": list(corners_cfg.get("committed", [])),
            "run": list(corners_run),
            "subset_justification": subset_justification,
            "source": corners_cfg.get("source"),
        },
        "timing": {
            "corner": corner,
            "worst_slack_ns": sta.get("worst_slack_ns"),
            "total_negative_slack_ns": sta.get("total_negative_slack_ns"),
            "worst_hold_slack_ns": sta.get("worst_hold_slack_ns"),
            "total_negative_hold_slack_ns": sta.get("total_negative_hold_slack_ns"),
            "setup_violation_count": sta.get("setup_violation_count"),
            "hold_violation_count": sta.get("hold_violation_count"),
            "verdict": verdict,
            "waiver": waiver,
            "note": note,
            "measured_by": "klt sta against this corner's own routed DEF",
        },
        "stages": {
            "synthesize": {
                "status": "ok",
                "engine": synth.get("engine"),
                "engine_version": synth.get("engine_version"),
                "instance_count": synth.get("instance_count"),
                "area_um2": synth.get("area_um2"),
                "sequential_area_um2": synth.get("sequential_area_um2"),
                "instance_counts_by_type": synth.get("instance_counts_by_type"),
                "liberty_deck": synth.get("provenance", {}).get("deck"),
            },
            "place_and_route": {
                "status": par.get("status"),
                "stage_reached": par.get("stage_reached"),
                "engine": par.get("engine"),
                "engine_version": par.get("engine_version"),
                "seed": par.get("seed"),
                "die_area_um2": par.get("die_area_um2"),
                "core_area_um2": par.get("core_area_um2"),
                "utilization_pct": par.get("utilization_pct"),
                "wirelength_um": par.get("wirelength_um"),
                "route_drc_violation_count": par.get("route_drc_violation_count"),
                "antenna_violation_count": par.get("antenna_violation_count"),
                "clock_skew_ns": par.get("clock_skew_ns"),
                "def_path": rel_to_repo(par_paths.get("def") or ""),
                "gds_path": rel_to_repo(par_paths.get("gds") or ""),
                "as_built_netlist_path": rel_to_repo(par_paths.get("verilog") or ""),
                "layer_map": par.get("layer_map"),
                "power": par.get("power"),
                "power_note": (
                    "`klt place-and-route`'s own echo of what request.power actually "
                    "applied: the PDN straps/global-connect rules/tapcell and filler "
                    "masters this build was configured with. `pdn: false` means no "
                    "power grid was generated at all -- only the request.power-"
                    "independent row-rail followpin fallback (`row_rail.emitted`), "
                    "which alone leaves every row's rail on its own island."
                ),
                "committed_copies": committed_copies,
                "committed_copies_note": (
                    "Only the nominal corner's physical artifacts are copied into the "
                    "repo under layout/. Every other corner's DEF/GDS live in gitignored "
                    "scratch (flow/build/<corner>/), so the paths above are provenance, "
                    "not retrievable files -- regenerate them with flow/run_flow.py."
                ),
                "native_corner_sweep": par.get("corners"),
                "native_corner_sweep_note": (
                    "klt place-and-route's own pdk.sweep_corners breakdown for this "
                    "physical build: worst setup/hold slack per corner, no per-corner "
                    "TNS (klayout-tools#1866). Recorded as a cross-check against the "
                    "per-corner klt sta runs, which do report TNS."
                ),
            },
            "sta": {
                "status": sta.get("status"),
                "engine": sta.get("engine"),
                "engine_version": sta.get("engine_version"),
                "geometry_source": sta.get("geometry_source"),
                "liberty_deck": sta.get("provenance", {}).get("deck"),
            },
            "extract": {
                "status": extract.get("status"),
                "deck": extract.get("provenance", {}).get("deck"),
                "net_count": extract.get("net_count"),
                "pin_count": extract.get("pin_count"),
                "device_count": extract.get("device_count"),
                "abstracted_cells": extract.get("abstracted_cells"),
                "netlist_sha256": extract.get("netlist_sha256"),
            },
            "lvs": {
                "status": lvs.get("status"),
                "engine": lvs.get("engine"),
                "engine_version": lvs.get("environment", {}).get("engine_version"),
                "error_count": lvs.get("error_count"),
                "mismatch_count": lvs.get("mismatch_count"),
                "category_counts": lvs.get("category_counts"),
                "counts": lvs.get("counts"),
                "warnings_only_mismatches": warnings_only_mismatches(lvs),
                "power_connectivity": power_connectivity_meta(lvs),
                "reference": (
                    "klt place-and-route's own as-built write_verilog netlist for this "
                    "corner (post-CTS, post-resize, post-antenna-repair), converted by "
                    "klt lvs's gate-level-verilog reference form -- NOT the pre-CTS "
                    "synthesis netlist"
                ),
            },
            "drc": {
                "status": drc.get("status"),
                "violation_count": drc.get("violation_count"),
                "rule_counts": drc.get("rule_counts"),
                "deck": {
                    "name": drc.get("deck"),
                    "engine": "curated",
                    "content_hash": drc.get("provenance", {}).get("deck", {}).get(
                        "content_hash"
                    ),
                    "klt_release": coverage.get("klt_release"),
                    "known_coverage_gaps": gap_digest(coverage),
                    "full_enumeration": "flow/drc-deck-coverage.json",
                },
                "coverage": drc.get("coverage", {}),
            },
        },
        "provenance": {
            "klt_version": drc.get("provenance", {}).get("klt_version"),
            "klayout_version": drc.get("provenance", {}).get("klayout_version"),
            "openroad_version": or_version,
            "yosys_version": synth.get("engine_version"),
            "pdk": par.get("provenance", {}).get("pdk"),
            "inputs": inputs,
            "artifacts": artifacts,
        },
        "tool_gaps": TOOL_GAPS,
    }


def render_lvs_counts(counts) -> str:
    if not isinstance(counts, dict):
        return f"- Counts: {counts}"
    rows = ["| | layout | reference | matched |", "| --- | --- | --- | --- |"]
    for kind in ("nets", "devices", "pins"):
        entry = counts.get(kind) or {}
        rows.append(
            f"| {kind} | {entry.get('layout')} | {entry.get('reference')} | "
            f"{entry.get('matched')} |"
        )
    return "\n".join(rows)


def committed_copies_line(par_stage: dict) -> str:
    copies = par_stage.get("committed_copies")
    if not copies:
        return (
            "none — this is not the nominal corner, so its DEF/GDS stay in gitignored "
            "scratch; the hashes above are provenance for a file you regenerate, not a "
            "file you retrieve"
        )
    return ", ".join(f"`{path}`" for path in sorted(copies))


def render_functional_verification(fv: dict) -> str:
    """Render the optional seventh stage's prose from its own record-meta block.

    `run_flow.py` never produces this stage -- `flow/postlayout_verify_utmi_stub.py`
    does, and then mints its record through `build_record_meta`/`render_record`
    here rather than hand-writing a second one. That is the whole point: per
    `flow/README.md`'s "Required fields", the JSON is what the lint reads and
    the prose is what a human reads, and they are generated together from one
    source so they cannot drift apart. Everything below is read out of the
    `functional_verification` stage dict; nothing is restated independently.
    """
    dut = fv.get("design_under_test") or {}
    library = fv.get("cell_library") or {}
    testbench = fv.get("testbench") or {}
    sources = library.get("sources") or {}
    source_lines = "\n".join(f"  - `{name}` — `{digest}`" for name, digest in sorted(sources.items()))
    copied_from = fv.get("physical_stages_copied_from")
    copied_line = (
        f"""
This record **supersedes** `{copied_from}` (per the append-only convention —
that record is untouched on disk, never edited or deleted). The
synthesis/place-and-route/STA/extraction/LVS/DRC measurements below are
copied from it **unchanged**, regenerated from its own committed `klt`
envelopes rather than restated by hand; the only new work this record adds is
the `functional_verification` stage.
"""
        if copied_from
        else ""
    )
    return f"""
## Post-layout functional verification — verdict: **{str(fv.get('status')).upper()}**
{copied_line}
**Claim**: `{testbench.get('source')}` — the same cocotb testbench that already
passed against the pre-layout RTL — also passes against `{dut.get('path')}`,
the post-layout as-built gate-level netlist this flow committed.

**Result**: **{str(fv.get('status')).upper()}** — {fv.get('passed_count')}/{fv.get('test_count')} tests, \
{fv.get('failed_count')} failed, {fv.get('skipped_count')} skipped.

- Engine: `{fv.get('engine')}` `{fv.get('engine_version')}`, cocotb \
`{fv.get('cocotb_version')}`, random seed `{fv.get('random_seed')}`.
- Design under test: `{dut.get('path')}` (`{dut.get('content_hash')}`) — {dut.get('role')}
- Testbench: `{testbench.get('module')}` from `{testbench.get('source')}`. {testbench.get('note')}
- Cell library: `{library.get('name')}` for `{library.get('pdk')}` \
(`{library.get('pdk_version')}`), model: {library.get('model')}.
- `USE_POWER_PINS`: **{'yes' if library.get('power_pins_modeled') else 'no'}**. \
{library.get('power_pins_note')}
- PDK-external sources, cited by content hash (not under `provenance.inputs`,
  which is reserved for files this repo's own freshness check can re-hash):

{source_lines}

**Why `{Path(str(dut.get('path'))).name}` and not the extracted SPICE netlist**: \
{dut.get('why_not_the_extracted_spice_netlist')}

**SDF back-annotation: {'yes' if fv.get('sdf_back_annotation') else 'no'}.** {fv.get('sdf_note')}

**Scope**: {fv.get('scope_note')}

**Driver**: `{fv.get('driver_script')}`. {fv.get('driver_script_note')}
"""


def render_record(meta: dict) -> str:
    timing = meta["timing"]
    stages = meta["stages"]
    drc = stages["drc"]
    lvs = stages["lvs"]
    functional = stages.get("functional_verification")
    functional_section = render_functional_verification(functional) if functional else ""
    physical_evidence_id = (functional or {}).get("physical_stages_copied_from")
    if physical_evidence_id:
        raw_evidence = f"""Every `klt` JSON envelope behind the *physical-flow* numbers above is
committed verbatim under
`flow/{EXPERIMENT}/artifacts/{physical_evidence_id}/` — the superseded
record's own artifact directory. Those files are unchanged and this record
does not duplicate them. This record's own new envelope is committed at
`{functional.get('raw_envelope_artifact')}`."""
    else:
        raw_evidence = f"""Every `klt` JSON envelope behind the numbers above is committed verbatim under
`flow/{EXPERIMENT}/artifacts/{meta['record_id']}/`."""

    gap_lines = "\n".join(
        f"  - `{gap['id']}` ({gap['kind']}) — {gap['summary']}"
        for gap in drc["deck"]["known_coverage_gaps"]
    )
    warn_lines = (
        "\n".join(
            f"  - `{m['category']}` ({m['severity']}) — {m['description']}"
            for m in lvs["warnings_only_mismatches"]
        )
        or "  - none"
    )
    skipped = drc["coverage"].get("rules_skipped") or []
    unruled = drc["coverage"].get("layers_in_stream_without_rules") or []

    power = lvs["power_connectivity"]
    power_finding_lines = (
        "\n".join(
            f"  - `{f['category']}` ({f['severity']}) — {f['description']}"
            for f in power["findings"]
        )
        or "  - none"
    )
    power_pins = power.get("power_pins")
    power_pin_text = ", ".join(f"`{p}`" for p in power_pins) if power_pins else "—"

    return f"""<!-- record-meta
{json.dumps(meta, indent=2)}
-->

# Record {meta['record_id']}

- **Record ID**: `{meta['record_id']}`
- **Corner**: `{meta['corner']}` (one of {len(meta['corner_matrix']['committed'])} committed corners)
- **Created**: {meta['created_utc']} at git revision `{meta['git_revision'][:12]}`
- **Supersedes**: {meta['supersedes'] or '—'}

## What this record is, and is not

**`rtl/utmi_stub.v` is toolchain plumbing. This record anchors no design
claim.** The design under test is nine flip-flops with no combinational
logic — a registered pass-through using UTMI signal *names* and none of UTMI's
behaviour. The point of running it through the full physical flow is to make
every tool failure unambiguously a *tool* failure. Nothing here says anything
about the USB 2.0 PHY's eventual area, timing, or correctness.
{functional_section}
## Design provenance

- Source: `rtl/utmi_stub.v`
- Top: `{meta['design']['hdl_toplevel']}`
- Synthesized cells: **{stages['synthesize']['instance_count']}** \
({stages['synthesize']['area_um2']} µm²)
- Liberty corner: `{(stages['synthesize']['liberty_deck'] or {}).get('name')}`

## Physical implementation

- `klt place-and-route` status `{stages['place_and_route']['status']}`, \
`stage_reached: {stages['place_and_route']['stage_reached']}`, seed \
`{stages['place_and_route']['seed']}`
- Die {stages['place_and_route']['die_area_um2']} µm², core \
{stages['place_and_route']['core_area_um2']} µm², utilization \
{stages['place_and_route']['utilization_pct']}%, wirelength \
{stages['place_and_route']['wirelength_um']} µm
- Routing DRC violations (TritonRoute): \
{stages['place_and_route']['route_drc_violation_count']}; post-repair antenna \
violations: {stages['place_and_route']['antenna_violation_count']}
- DEF: `{stages['place_and_route']['def_path']}`
- GDS: `{stages['place_and_route']['gds_path']}`
- As-built netlist: `{stages['place_and_route']['as_built_netlist_path']}`
- Committed copies in this repo: {committed_copies_line(stages['place_and_route'])}

## Timing — verdict: **{timing['verdict'].upper()}**

| Field | Value |
| --- | --- |
| `worst_slack_ns` (setup WNS) | `{timing['worst_slack_ns']}` |
| `total_negative_slack_ns` (setup TNS) | `{timing['total_negative_slack_ns']}` |
| `worst_hold_slack_ns` | `{timing['worst_hold_slack_ns']}` |
| `total_negative_hold_slack_ns` | `{timing['total_negative_hold_slack_ns']}` |
| setup / hold violation count | {timing['setup_violation_count']} / {timing['hold_violation_count']} |

{timing['note']}

Measured by: {timing['measured_by']}.

## DRC — verdict: **{str(drc['status']).upper()}** ({drc['violation_count']} violations)

- Deck: `{drc['deck']['name']}` (`{drc['deck']['engine']}` engine), content hash
  `{drc['deck']['content_hash']}`, shipped by klt
  `{(drc['deck']['klt_release'] or {}).get('package_version')}`
  (`{(drc['deck']['klt_release'] or {}).get('git_tag')}`).
- **Known coverage gaps of this deck revision** (full text, with sources, in
  `flow/drc-deck-coverage.json`):

{gap_lines}

- Per-run coverage, from this run's own envelope: {len(skipped)} rule(s) never
  executed because their layers are absent from this stream; {len(unruled)}
  layer(s) present in the stream that no rule in the deck references. Read the
  clean verdict together with both numbers, never alone.

## LVS — verdict: **{str(lvs['status']).upper()}**

- Engine: **`{lvs['engine']}`** (KLayout `{lvs['engine_version']}`,
  `NetlistComparer` graph-isomorphism compare, in-process).
- Errors: {lvs['error_count']}; total mismatch entries: {lvs['mismatch_count']}.
- Reference: {lvs['reference']}.

{render_lvs_counts(lvs['counts'])}

- Warnings-only mismatches (non-`error` severity), listed in full:

{warn_lines}

### Power/ground connectivity — verdict: **{str(power['status']).upper()}**

Read together with the LVS verdict above, never instead of it. The verdict
above is the **signal** compare only: its reference is a `gate-level-verilog`
netlist, which carries no supply pins, so that compare drops the layout's
supply nets rather than failing on them. A `MATCH` there is not evidence the
design is powered.

- Power/ground pins checked: {power_pin_text}
- Instances covered: {power['instance_count'] if power['instance_count'] is not None else '—'}
- Findings: {power['finding_count'] if power['finding_count'] is not None else '—'}
- Reason (only set when the check did not run): {power['reason'] or '—'}
- Reported by `klt` `{power['klt_version'] or 'unknown'}`.

{power_finding_lines}

- {power['note']}

## Extraction

- `klt extract` status `{stages['extract']['status']}`, deck
  `{(stages['extract']['deck'] or {}).get('name')}`
  (`{(stages['extract']['deck'] or {}).get('content_hash')}`)
- {stages['extract']['net_count']} nets, {stages['extract']['pin_count']} pins,
  {stages['extract']['device_count']} devices (zero by construction — every
  standard cell is a pin-only black box at this granularity).

## Corner matrix

- Committed: {', '.join(f'`{c}`' for c in meta['corner_matrix']['committed'])}
- Run: {', '.join(f'`{c}`' for c in meta['corner_matrix']['run'])}
- Subset justification: {meta['corner_matrix']['subset_justification'] or '— (full matrix run)'}
- Source: {meta['corner_matrix']['source']}

## Toolchain provenance

- `klt` {meta['provenance']['klt_version']}, KLayout
  {meta['provenance']['klayout_version']}, OpenROAD
  {meta['provenance']['openroad_version']}, Yosys
  {meta['provenance']['yosys_version']}
- PDK: {meta['provenance']['pdk']}

## Tool gaps filed upstream while producing this record

{chr(10).join(f'- {url}' for url in meta['tool_gaps'])}

## Raw evidence

{raw_evidence}
"""


def rebuild_manifest(records_dir: Path) -> None:
    lines = [
        "# Append-only record manifest. One line per record: <sha256>  <filename>.",
        "# flow/check_records.py fails if a listed record is missing or its hash has",
        "# changed, and (against origin/main) if a line here was removed or rewritten.",
    ]
    for record in sorted(records_dir.glob("*.md")):
        lines.append(f"{sha256_file(record)}  {record.name}")
    (records_dir / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--corners",
        help="comma-separated corner subset to run (default: the full committed matrix)",
    )
    parser.add_argument(
        "--subset-justification",
        default=None,
        help="required when --corners names fewer than the full committed matrix",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    parser.add_argument(
        "--keep-build",
        action="store_true",
        help="keep flow/build/<corner>/ from a previous run instead of clearing it",
    )
    args = parser.parse_args(argv)

    corners_cfg = load_json(FLOW_DIR / "corners.json")
    coverage = load_json(FLOW_DIR / "drc-deck-coverage.json")
    waivers = load_json(FLOW_DIR / "waivers.json").get("waivers", {})
    committed = list(corners_cfg["committed"])
    nominal = corners_cfg["nominal"]

    corners_run = [c.strip() for c in args.corners.split(",")] if args.corners else committed
    unknown = [c for c in corners_run if c not in committed]
    if unknown:
        print(f"run_flow: corner(s) not in the committed matrix: {unknown}", file=sys.stderr)
        return 2

    subset_justification = args.subset_justification
    if len(corners_run) < len(committed) and not subset_justification:
        print(
            "run_flow: --corners names a subset of the committed matrix; "
            "--subset-justification is required (flow/check_records.py enforces it too)",
            file=sys.stderr,
        )
        return 2

    log("flow/run_flow.py")
    log(f"  experiment : {EXPERIMENT}")
    log(f"  corners    : {', '.join(corners_run)}")
    log(f"  nominal    : {nominal} (its DEF/GDS/as-built netlist are committed to layout/)")
    if args.dry_run:
        log("  dry run -- nothing executed")
        return 0

    if shutil.which("klt") is None:
        print("run_flow: `klt` is not on PATH -- see docs/environment-setup.md", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env.setdefault("PDK", "sky130A")
    if resolve_pdk_root(env) is None:
        print(
            "run_flow: could not resolve a PDK root (klt pdk find failed). "
            "Set PDK_ROOT explicitly -- see docs/environment-setup.md",
            file=sys.stderr,
        )
        return 2
    or_version = openroad_version()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_sha = git_revision()[:7]

    experiment_dir = FLOW_DIR / EXPERIMENT
    records_dir = experiment_dir / "records"
    artifacts_root = experiment_dir / "artifacts"
    records_dir.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    # Input hashes are identical for every corner in one sweep -- the corner is
    # a parameter substituted into these files, not a different set of files.
    input_paths = [
        REPO_ROOT / "rtl" / "utmi_stub.v",
        FLOW_DIR / "request-synth-utmi_stub.json",
        FLOW_DIR / "request-par-utmi_stub.json",
        FLOW_DIR / "request-sta-utmi_stub.json",
        FLOW_DIR / "request-extract-utmi_stub.json",
        FLOW_DIR / "request-lvs-utmi_stub.json",
        FLOW_DIR / "request-drc-utmi_stub.json",
        FLOW_DIR / "corners.json",
        FLOW_DIR / "drc-deck-coverage.json",
    ]

    gate_failures: list[str] = []
    power_unverified: list[str] = []
    written: list[Path] = []
    verdict_tally: dict[str, list[str]] = {}

    for corner in corners_run:
        log("")
        log(f"== corner {corner} ==")
        work = BUILD_DIR / corner
        if work.exists() and not args.keep_build:
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)

        try:
            log("  [1/6] klt synthesize")
            synth = stage_synthesize(corner, work, env)

            log("  [2/6] klt place-and-route")
            par = stage_place_and_route(
                corner,
                work,
                envelope_path(synth.get("netlist_path"), "synthesize.netlist_path"),
                env,
            )
            if not par.get("gds_path"):
                raise StageError(
                    f"place-and-route reached {par.get('stage_reached')!r} but emitted no "
                    "gds_path -- nothing downstream can run"
                )
            par_paths = {
                "def": envelope_path(par.get("def_path"), "place-and-route.def_path"),
                "gds": envelope_path(par.get("gds_path"), "place-and-route.gds_path"),
                "verilog": envelope_path(
                    par.get("verilog_path"), "place-and-route.verilog_path"
                ),
            }

            log("  [3/6] klt sta")
            sta = stage_sta(corner, work, par_paths["def"], env)

            log("  [4/6] klt extract")
            extract, extracted_netlist = stage_extract(work, par_paths["gds"], env)

            log("  [5/6] klt lvs")
            lvs = stage_lvs(work, extracted_netlist, par_paths["verilog"], env)

            log("  [6/6] klt drc")
            drc = stage_drc(work, par_paths["gds"], env)
        except StageError as exc:
            print(f"\nrun_flow: stage failed at corner {corner}:\n  {exc}", file=sys.stderr)
            return 2

        record_id = f"{stamp}-{short_sha}-{corner}"
        supersedes = latest_record_for_corner(records_dir, corner)
        artifacts_dir = artifacts_root / record_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for name, envelope in (
            ("synthesize-report.json", synth),
            ("place-and-route-report.json", par),
            ("sta-report.json", sta),
            ("extract-report.json", extract),
            ("lvs-report.json", lvs),
            ("drc-report.json", drc),
        ):
            write_json(artifacts_dir / name, envelope)
        for name in (
            "request-synth.json",
            "request-par.json",
            "request-sta.json",
            "request-lvs.json",
        ):
            if (work / name).exists():
                shutil.copy2(work / name, artifacts_dir / name)

        committed_copies: dict | None = None
        if corner == nominal:
            LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(par_paths["gds"], LAYOUT_DIR / "utmi_stub.gds")
            shutil.copy2(par_paths["def"], LAYOUT_DIR / "utmi_stub.def")
            shutil.copy2(par_paths["verilog"], LAYOUT_DIR / "utmi_stub.asbuilt.v")
            shutil.copy2(extracted_netlist, LAYOUT_DIR / "utmi_stub.extracted.spice")
            committed_copies = {
                "layout/utmi_stub.gds": "routed GDS (DEF merged with the standard-cell GDS views)",
                "layout/utmi_stub.def": "routed DEF",
                "layout/utmi_stub.asbuilt.v": "as-built gate-level netlist (the LVS reference)",
                "layout/utmi_stub.extracted.spice": "layout-derived netlist (the LVS layout side)",
            }
            log(f"  committed nominal-corner artifacts to {rel_to_repo(LAYOUT_DIR)}/")

        verdict, note = evaluate_timing(
            sta.get("worst_slack_ns"),
            sta.get("total_negative_slack_ns"),
            waivers.get(corner),
        )

        artifacts = [
            {
                "path": f"flow/{EXPERIMENT}/artifacts/{record_id}/{p.name}",
                "content_hash": sha256_file(p),
            }
            for p in sorted(artifacts_dir.iterdir())
            if p.is_file()
        ]
        inputs = [
            {"path": rel_to_repo(p), "content_hash": sha256_file(p)}
            for p in input_paths
            if p.exists()
        ]
        if corner == nominal:
            for name in (
                "utmi_stub.gds",
                "utmi_stub.def",
                "utmi_stub.asbuilt.v",
                "utmi_stub.extracted.spice",
            ):
                artifacts.append(
                    {
                        "path": f"layout/{name}",
                        "content_hash": sha256_file(LAYOUT_DIR / name),
                    }
                )

        meta = build_record_meta(
            record_id=record_id,
            corner=corner,
            corners_run=corners_run,
            corners_cfg=corners_cfg,
            subset_justification=subset_justification,
            synth=synth,
            par=par,
            par_paths=par_paths,
            sta=sta,
            extract=extract,
            lvs=lvs,
            drc=drc,
            coverage=coverage,
            verdict=verdict,
            note=note,
            waiver=waivers.get(corner) if verdict == "waived" else None,
            inputs=inputs,
            artifacts=artifacts,
            or_version=or_version,
            committed_copies=committed_copies,
            supersedes=supersedes,
        )
        record_path = records_dir / f"{record_id}.md"
        record_path.write_text(render_record(meta), encoding="utf-8")
        written.append(record_path)
        log(f"  record -> {rel_to_repo(record_path)}")

        power_meta = meta["stages"]["lvs"]["power_connectivity"]
        power_status = power_meta["status"]
        log(
            f"  verdicts: timing={verdict}  drc={drc.get('status')}"
            f"({drc.get('violation_count')})  lvs={lvs.get('status')}"
            f"(errors={lvs.get('error_count')})  power_connectivity={power_status}"
        )
        verdict_tally.setdefault(verdict, []).append(corner)
        if verdict == "fail":
            gate_failures.append(f"{corner}: timing gate failed -- {note}")
        if drc.get("status") != "clean":
            gate_failures.append(
                f"{corner}: DRC is {drc.get('status')!r} with "
                f"{drc.get('violation_count')} violation(s)"
            )
        if lvs.get("status") != "match" or lvs.get("error_count"):
            gate_failures.append(
                f"{corner}: LVS is {lvs.get('status')!r} with "
                f"{lvs.get('error_count')} error(s)"
            )
        # The power/ground half of LVS is a verdict in its own right -- a
        # signal-only `match` is NOT evidence the design is powered (issue #59).
        if power_status == "mismatch":
            gate_failures.append(
                f"{corner}: LVS power connectivity is 'mismatch' with "
                f"{power_meta.get('finding_count')} finding(s)"
            )
        elif power_status != "match":
            power_unverified.append(f"{corner} ({power_status})")
        # A declared `expected_nets` pin the check never resolved produces no
        # finding at all -- indistinguishable from "checked and correct"
        # without this field (klayout-tools#1978). Gate on it, or declaring a
        # pin name with a typo in it would quietly buy a weaker verdict.
        unchecked_pins = power_meta.get("unchecked_expected_pins")
        if unchecked_pins:
            gate_failures.append(
                f"{corner}: LVS power connectivity never resolved declared "
                f"pin(s) {', '.join(unchecked_pins)} -- that half of "
                "request-lvs-utmi_stub.json's expected_nets went unchecked"
            )

    rebuild_manifest(records_dir)
    log("")
    log(f"wrote {len(written)} record(s); refreshed {rel_to_repo(records_dir)}/MANIFEST.sha256")

    log("")
    log("timing verdicts by corner:")
    for verdict in ("pass", "waived", "unconstrained", "fail"):
        corners_with = verdict_tally.get(verdict)
        if corners_with:
            log(f"  {verdict:<14} {', '.join(corners_with)}")

    if gate_failures:
        print("\nrun_flow: GATE FAILURES", file=sys.stderr)
        for failure in gate_failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    unconstrained = verdict_tally.get("unconstrained", [])
    if unconstrained:
        log("")
        log(
            f"no gate failed, but {len(unconstrained)} corner(s) are UNCONSTRAINED: "
            "STA had no constrained timing path to measure, so this run closed no "
            "timing at those corners. That is not a pass -- see each record's "
            "timing.note and klayout-tools#1865."
        )
    if power_unverified:
        log("")
        log(
            f"no gate failed, but LVS power connectivity is UNVERIFIED at "
            f"{len(power_unverified)} corner(s): {', '.join(power_unverified)}. "
            "The LVS `match` above is the signal compare only; its "
            "gate-level-verilog reference carries no supply pins, so it cannot "
            "see whether the design is powered. That is not a pass -- see each "
            "record's stages.lvs.power_connectivity and klayout-tools#1964."
        )
    if not unconstrained and not power_unverified:
        log("all gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
