#!/usr/bin/env python3
"""Re-run `verification/test_utmi_stub.py` against the post-layout gate-level
netlist, via `klt functional-verification` (issue #37, T1 checklist item 7),
and mint the evidence record for it (issue #63).

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
flow smoke experiment -- so this script does not *run* `run_flow.py`'s
stages. It augments the *existing* nominal-corner record for the same
design-under-test by minting a new record that supersedes it, adding a
`functional_verification` stage entry; the five other corners' records are
untouched.

## How the record is written

Through `run_flow.py`'s own record machinery -- `build_record_meta`,
`render_record`, `latest_record_for_corner` and `rebuild_manifest` -- never a
second, hand-rolled record writer. `flow/README.md`'s "Required fields"
convention depends on the JSON block a record carries and the prose a human
reads being generated together from one source, so they cannot drift apart;
two writers would be two sources. The six physical-flow stage blocks are
*regenerated* from the superseded record's own committed `klt` envelopes
under `flow/smoke-utmi_stub/artifacts/<id>/` rather than copied out of its
JSON, so "copied unchanged" is a property this script re-derives rather than
a claim it asserts. Everything that could have moved underneath those
measurements -- every `provenance.inputs` hash, every carried
`provenance.artifacts` hash, and the committed netlist itself -- is
re-verified before the record is written, and a mismatch is fatal: a changed
netlist means the flow was re-run and this script must not staple a
functional-verification stage onto measurements that no longer describe it.

Usage:

    PDK=sky130A python3 flow/postlayout_verify_utmi_stub.py
    python3 flow/postlayout_verify_utmi_stub.py --format json
    python3 flow/postlayout_verify_utmi_stub.py --no-record   # run, record nothing

Exit codes: 0 the regression passed (and, unless `--no-record`, a record was
written), 1 the regression ran but failed/had a functional-verification
error, 2 the environment (PDK, klt, netlist) or the record chain could not be
resolved.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_DIR = REPO_ROOT / "flow"
LAYOUT_DIR = REPO_ROOT / "layout"
VERIFICATION_DIR = REPO_ROOT / "verification"

sys.path.insert(0, str(FLOW_DIR))
from check_records import (  # noqa: E402  (path set above on purpose)
    Findings,
    extract_record_meta,
    sha256_file,
)
from run_flow import (  # noqa: E402  (one record writer, not two -- see module docstring)
    EXPERIMENT,
    build_record_meta,
    git_revision,
    latest_record_for_corner,
    rebuild_manifest,
    rel_to_repo,
    render_record,
    resolve_pdk_root,
    write_json,
)

HDL_TOPLEVEL = "utmi_stub"
CELL_LIBRARY = "sky130_fd_sc_hd"
NETLIST_PATH = LAYOUT_DIR / "utmi_stub.asbuilt.v"
TESTBENCH_PATH = VERIFICATION_DIR / "test_utmi_stub.py"
DRIVER_PATH = Path(__file__).resolve()

EXPERIMENT_DIR = FLOW_DIR / EXPERIMENT
RECORDS_DIR = EXPERIMENT_DIR / "records"
ARTIFACTS_ROOT = EXPERIMENT_DIR / "artifacts"

# The one artifact this stage produces, and the physical-flow envelope whose
# presence identifies an artifact directory as holding the six-stage evidence.
FV_ARTIFACT_NAME = "functional-verification-report.json"
PHYSICAL_EVIDENCE_MARKER = "drc-report.json"

# Inputs whose hash is *allowed* to differ from the superseded record's: these
# are this stage's own inputs, and a change to either is exactly the reason
# someone would re-run this script. Every other recorded input hash is a
# physical-flow input, and a change there means the six-stage measurements
# being carried forward are stale -- fatal, not a new record.
RERUNNABLE_INPUTS = {
    "verification/test_utmi_stub.py",
    "flow/postlayout_verify_utmi_stub.py",
}

SUBSET_JUSTIFICATION = (
    "This record does not re-run the 6-corner physical flow -- "
    "synthesis/place-and-route/STA/extraction/LVS/DRC for all 6 corners were "
    "already measured and recorded in {predecessor} (and its 5 sibling "
    "per-corner records, which this record does not touch or supersede) and "
    "are regenerated here unchanged from that record's own committed klt "
    "envelopes; see the freshness-checked provenance.inputs below, which "
    "re-hash identically. The only new work in this record is the "
    "functional_verification stage (issue #37), which by its own acceptance "
    "criteria runs against the nominal corner's committed "
    "layout/utmi_stub.asbuilt.v only -- there is no per-corner variant of that "
    "file, since only the nominal corner's physical artifacts are ever copied "
    "into layout/ (see layout/README.md). A zero-delay FUNCTIONAL-model "
    "gate-level simulation has no PVT dependence in the first place (no SDF is "
    "annotated -- see stages.functional_verification.sdf_note), so there is "
    "nothing a second corner's run would add."
)

SCOPE_NOTE = (
    "This proves functional/structural equivalence of the post-layout "
    "gate-level netlist against the same testbench and stimulus that already "
    "passed pre-layout, for the toolchain-smoke design (`utmi_stub`) only. It "
    "does NOT close T1 checklist item 7 for the real USB 2.0 PHY digital "
    "datapath: only `rtl/utmi_stub.v` -- a deliberately trivial 9-flip-flop "
    "stub with no USB protocol behaviour -- has been through the physical "
    "flow, so none of `verification/test_usb_rx.py`, "
    "`verification/test_usb_tx.py` or `verification/test_usb_utmi_top.py` can "
    "be run against an extracted netlist today; there isn't one. Real RTL gets "
    "its own experiment slug, not this one (`flow/README.md`)."
)

POWER_PINS_NOTE = (
    "`layout/utmi_stub.asbuilt.v` carries no VPWR/VGND connections on its cell "
    "instances -- OpenROAD's as-built `write_verilog` omits supply "
    "connectivity -- so the cell library must be compiled with the "
    "power-pin-free port list to match, i.e. WITHOUT `USE_POWER_PINS`. That is "
    "a property of the netlist format, NOT a statement that the design is "
    "unpowered: since issue #59 the design does carry a real PDN (see "
    "`stages.place_and_route.power`), and the evidence that it is connected is "
    "`stages.lvs.power_connectivity`, not this stage. This simulation sees no "
    "supply nets at all and makes no claim about them either way."
)

TESTBENCH_NOTE = (
    "Unmodified -- the same testbench the pre-layout smoke run "
    "(verification/request-utmi_stub.json) uses, re-targeted at a different "
    "design under test only."
)

WHY_NOT_SPICE = (
    "klt functional-verification's request schema runs Verilog sources through "
    "Icarus/Verilator -- it has no SPICE-simulator path, so it cannot execute "
    "layout/utmi_stub.extracted.spice directly. layout/utmi_stub.asbuilt.v is "
    "the practical, tool-available stand-in: stages.lvs above already proved "
    "it structurally equivalent to the extracted netlist (status: match), so "
    "exercising it through the identical cocotb suite that already passed "
    "against the pre-layout RTL is a genuine post-layout functional "
    "re-verification, chained through LVS's own equivalence proof rather than "
    "an independent transistor-level simulation."
)

SDF_NOTE = (
    "No SDF file exists for this design: issue #11/PR #55's P&R request "
    "(flow/request-par-utmi_stub.json) never set `post_route_sdf`, so there is "
    "nothing to back-annotate. This is a zero/unit-delay functional-only check "
    "-- it proves structural/functional equivalence of the post-layout netlist "
    "under the same stimulus as the pre-layout suite, and it is NOT a "
    "timing-annotated re-verification. `klt functional-verification`'s own "
    "`options.sdf` supports SDF back-annotation when a post-route SDF exists; "
    "this record does not use it."
)

DRIVER_NOTE = (
    "Unlike the six flow/request-*.json documents run_flow.py drives, this "
    "stage's request cannot be a static committed JSON: `sources` must name "
    "the PDK's sky130_fd_sc_hd behavioral Verilog models, which live outside "
    "this repo at a host-resolved path. Committing that absolute path would "
    "silently break on every other machine (and would be auto-swept by "
    "scripts/check-ci.sh's `verification/request-*.json` glob if placed "
    "there), so this script resolves the PDK root itself (the same klt pdk "
    "find workaround run_flow.py's resolve_pdk_root uses for "
    "klayout-tools#1868) and builds the request in memory. The record itself "
    "is written through run_flow.py's own build_record_meta/render_record, so "
    "this stage's JSON and prose come from the same source as every other "
    "record in this experiment."
)

PDK_SOURCES_NOTE = (
    "Resolved from the host's PDK install (klt pdk find), not committed to "
    "this repo -- these are PDK-external files, cited by content hash for "
    "provenance, not tracked under provenance.inputs (which is reserved for "
    "files this repo's freshness check can actually re-hash)."
)


class RecordError(RuntimeError):
    """The record chain could not be resolved, or an input moved underneath it."""


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


def pdk_version(variant: str, env: dict[str, str]) -> str | None:
    """The PDK build `klt` resolved, for the record's cell-library provenance."""
    if shutil.which("klt") is None:
        return None
    result = subprocess.run(
        ["klt", "pdk", "find", "--pdk", variant, "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout).get("version")
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------
# Record minting -- all of it through run_flow.py's machinery
# --------------------------------------------------------------------------
def read_record_meta(path: Path) -> dict:
    findings = Findings()
    meta = extract_record_meta(path.read_text(encoding="utf-8"), path, findings)
    if meta is None:
        raise RecordError(f"{rel_to_repo(path)}: {findings.items[0][1]}")
    return meta


def resolve_physical_evidence(meta: dict) -> tuple[str, Path]:
    """Walk `supersedes` back to the record whose artifact dir holds the six envelopes.

    A functional-verification record's own artifact directory holds only its
    `functional-verification-report.json` -- the physical-flow envelopes stay
    in the directory of the record that actually ran those stages, which is
    the point of the append-only convention (nothing is duplicated). So the
    chain may be one hop (the usual case: the predecessor is a `run_flow.py`
    record) or more (a re-run of *this* script against a record this script
    itself minted).
    """
    seen: set[str] = set()
    current: dict | None = meta
    while current is not None:
        record_id = current.get("record_id")
        if not isinstance(record_id, str):
            break
        directory = ARTIFACTS_ROOT / record_id
        if (directory / PHYSICAL_EVIDENCE_MARKER).is_file():
            return record_id, directory
        prior = current.get("supersedes")
        if not isinstance(prior, str) or not prior.strip() or prior in seen:
            break
        seen.add(prior)
        prior_path = RECORDS_DIR / f"{prior}.md"
        if not prior_path.is_file():
            break
        current = read_record_meta(prior_path)
    raise RecordError(
        f"no artifact directory in the supersedes chain from "
        f"{meta.get('record_id')!r} holds {PHYSICAL_EVIDENCE_MARKER} -- the "
        "six physical-flow envelopes this record must carry forward cannot be "
        "found; re-run flow/run_flow.py"
    )


def reverify_inputs(predecessor: dict) -> list[dict]:
    """Re-hash every input the superseded record names, and refuse any drift.

    A physical-flow input that has changed means the six-stage measurements
    this record carries forward no longer describe the committed requests --
    `flow/check_records.py`'s freshness rule would fail the new record, and it
    should: the fix is to re-run `flow/run_flow.py`, not to mint a record that
    staples a fresh functional-verification stage onto stale physical
    evidence. This stage's own two inputs are exempt, because a change to
    either is precisely why someone re-runs this script.
    """
    inputs: list[dict] = []
    stale: list[str] = []
    for entry in predecessor.get("provenance", {}).get("inputs", []):
        rel = entry.get("path")
        target = REPO_ROOT / rel
        if not target.exists():
            raise RecordError(
                f"provenance input {rel} named by {predecessor['record_id']} no "
                "longer exists -- the record chain cites a file that is gone"
            )
        actual = sha256_file(target)
        if actual != entry.get("content_hash") and rel not in RERUNNABLE_INPUTS:
            stale.append(f"{rel} ({entry.get('content_hash')} -> {actual})")
        inputs.append({"path": rel, "content_hash": actual})
    if stale:
        raise RecordError(
            "physical-flow input(s) have changed since "
            f"{predecessor['record_id']} was written: {'; '.join(stale)}. "
            "Those six-stage measurements are stale -- re-run flow/run_flow.py "
            "and then re-run this script against the record it mints."
        )

    known = {entry["path"] for entry in inputs}
    for path in (NETLIST_PATH, TESTBENCH_PATH, DRIVER_PATH):
        rel = rel_to_repo(path)
        if rel not in known:
            inputs.append({"path": rel, "content_hash": sha256_file(path)})
    return inputs


def carry_artifacts(predecessor: dict) -> list[dict]:
    """Re-hash the superseded record's artifacts and carry them forward.

    Records are append-only, so every one of these files must still be on disk
    with the hash it was recorded under. `layout/utmi_stub.asbuilt.v` is the
    load-bearing one: it is the netlist this script just simulated, and if it
    no longer matches what the superseded record's place-and-route stage
    produced, the two halves of the new record would describe different
    designs. A prior functional-verification envelope is dropped rather than
    carried -- this record supersedes that claim, it does not restate it.
    """
    artifacts: list[dict] = []
    drifted: list[str] = []
    for entry in predecessor.get("provenance", {}).get("artifacts", []):
        rel = entry.get("path")
        if Path(rel).name == FV_ARTIFACT_NAME:
            continue
        target = REPO_ROOT / rel
        if not target.exists():
            raise RecordError(
                f"artifact {rel} named by {predecessor['record_id']} is missing "
                "-- records and their artifacts are append-only"
            )
        actual = sha256_file(target)
        if actual != entry.get("content_hash"):
            drifted.append(f"{rel} ({entry.get('content_hash')} -> {actual})")
        artifacts.append({"path": rel, "content_hash": actual})
    if drifted:
        raise RecordError(
            f"artifact(s) recorded by {predecessor['record_id']} have changed on "
            f"disk: {'; '.join(drifted)}. If layout/ changed, the flow was "
            "re-run: re-run flow/run_flow.py and mint this stage against the "
            "record that produced the committed netlist."
        )
    return artifacts


def build_functional_stage(
    *,
    envelope: dict,
    request: dict,
    cell_sources: list[Path],
    variant: str,
    pdk_root: str,
    pdk_build: str | None,
    physical_record_id: str,
    artifact_rel_path: str,
) -> dict:
    environment = envelope.get("environment", {})
    return {
        "status": envelope.get("status"),
        "engine": envelope.get("engine"),
        "engine_version": environment.get("engine_version"),
        "cocotb_version": environment.get("cocotb_version"),
        "hdl_toplevel": envelope.get("hdl_toplevel"),
        "testbench": {
            "module": request["testbench"]["module"],
            "source": rel_to_repo(TESTBENCH_PATH),
            "note": TESTBENCH_NOTE,
        },
        "test_count": envelope.get("test_count"),
        "passed_count": envelope.get("passed_count"),
        "failed_count": envelope.get("failed_count"),
        "skipped_count": envelope.get("skipped_count"),
        "random_seed": request["options"]["random_seed"],
        "design_under_test": {
            "path": rel_to_repo(NETLIST_PATH),
            "content_hash": sha256_file(NETLIST_PATH),
            "role": (
                "as-built gate-level netlist (the LVS reference; see "
                "stages.lvs.reference above)"
            ),
            "why_not_the_extracted_spice_netlist": WHY_NOT_SPICE,
        },
        "cell_library": {
            "name": CELL_LIBRARY,
            "pdk": variant,
            "pdk_root": pdk_root,
            "pdk_version": pdk_build,
            "model": "FUNCTIONAL define (zero-delay, UDP-based simulation model)",
            "power_pins_modeled": False,
            "power_pins_note": POWER_PINS_NOTE,
            "sources": {p.name: sha256_file(p) for p in cell_sources},
            "sources_note": PDK_SOURCES_NOTE,
        },
        "sdf_back_annotation": False,
        "sdf_note": SDF_NOTE,
        "scope_note": SCOPE_NOTE,
        "anchors_design_claim": False,
        "driver_script": rel_to_repo(DRIVER_PATH),
        "driver_script_note": DRIVER_NOTE,
        "physical_stages_copied_from": physical_record_id,
        "raw_envelope_artifact": artifact_rel_path,
    }


def mint_record(
    *,
    envelope: dict,
    request: dict,
    cell_sources: list[Path],
    variant: str,
    pdk_root: str,
    pdk_build: str | None,
) -> Path:
    """Write the new nominal-corner record, through run_flow.py's own writer."""
    corners_cfg = json.loads((FLOW_DIR / "corners.json").read_text(encoding="utf-8"))
    coverage = json.loads(
        (FLOW_DIR / "drc-deck-coverage.json").read_text(encoding="utf-8")
    )
    nominal = corners_cfg["nominal"]

    predecessor_id = latest_record_for_corner(RECORDS_DIR, nominal)
    if predecessor_id is None:
        raise RecordError(
            f"no existing record for the nominal corner {nominal!r} to supersede "
            "-- run flow/run_flow.py first"
        )
    predecessor = read_record_meta(RECORDS_DIR / f"{predecessor_id}.md")

    physical_id, physical_dir = resolve_physical_evidence(predecessor)
    envelopes = {}
    for key, name in (
        ("synth", "synthesize-report.json"),
        ("par", "place-and-route-report.json"),
        ("sta", "sta-report.json"),
        ("extract", "extract-report.json"),
        ("lvs", "lvs-report.json"),
        ("drc", "drc-report.json"),
    ):
        path = physical_dir / name
        if not path.is_file():
            raise RecordError(
                f"{rel_to_repo(path)} is missing -- the six physical-flow "
                "envelopes this record regenerates its stage blocks from are "
                "incomplete"
            )
        envelopes[key] = json.loads(path.read_text(encoding="utf-8"))

    inputs = reverify_inputs(predecessor)
    artifacts = carry_artifacts(predecessor)

    record_id = "{stamp}-{sha}-{corner}".format(
        stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S"),
        sha=git_revision()[:7],
        corner=nominal,
    )
    artifacts_dir = ARTIFACTS_ROOT / record_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / FV_ARTIFACT_NAME
    write_json(artifact_path, envelope)
    artifact_rel_path = f"flow/{EXPERIMENT}/artifacts/{record_id}/{FV_ARTIFACT_NAME}"
    artifacts.append(
        {"path": artifact_rel_path, "content_hash": sha256_file(artifact_path)}
    )

    par_stage = predecessor["stages"]["place_and_route"]
    meta = build_record_meta(
        record_id=record_id,
        corner=nominal,
        corners_run=[nominal],
        corners_cfg=corners_cfg,
        subset_justification=SUBSET_JUSTIFICATION.format(predecessor=predecessor_id),
        synth=envelopes["synth"],
        par=envelopes["par"],
        par_paths={
            "def": str(REPO_ROOT / par_stage["def_path"]),
            "gds": str(REPO_ROOT / par_stage["gds_path"]),
            "verilog": str(REPO_ROOT / par_stage["as_built_netlist_path"]),
        },
        sta=envelopes["sta"],
        extract=envelopes["extract"],
        lvs=envelopes["lvs"],
        drc=envelopes["drc"],
        coverage=coverage,
        verdict=predecessor["timing"]["verdict"],
        note=predecessor["timing"]["note"],
        waiver=predecessor["timing"]["waiver"],
        inputs=inputs,
        artifacts=artifacts,
        or_version=predecessor["provenance"]["openroad_version"],
        committed_copies=par_stage["committed_copies"],
        supersedes=predecessor_id,
    )
    meta["stages"]["functional_verification"] = build_functional_stage(
        envelope=envelope,
        request=request,
        cell_sources=cell_sources,
        variant=variant,
        pdk_root=pdk_root,
        pdk_build=pdk_build,
        physical_record_id=physical_id,
        artifact_rel_path=artifact_rel_path,
    )

    record_path = RECORDS_DIR / f"{record_id}.md"
    record_path.write_text(render_record(meta), encoding="utf-8")
    rebuild_manifest(RECORDS_DIR)
    return record_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="run the regression and report it, but write no record (a dry check)",
    )
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

    # klt's own `status` is the source of truth (see run_flow.py's `run_klt`
    # for why a raw exit code is never trusted on its own); fall back to the
    # exit code only if the envelope carries no explicit status field.
    status = envelope.get("status")
    passed = status == "pass" if status is not None else result.returncode == 0

    record_path: Path | None = None
    if passed and not args.no_record:
        try:
            record_path = mint_record(
                envelope=envelope,
                request=request,
                cell_sources=cell_sources,
                variant=args.pdk,
                pdk_root=pdk_root,
                pdk_build=pdk_version(args.pdk, env),
            )
        except RecordError as exc:
            print(f"postlayout_verify_utmi_stub: {exc}", file=sys.stderr)
            return 2

    if args.format == "json":
        payload = dict(envelope)
        payload["record"] = rel_to_repo(record_path) if record_path else None
        print(json.dumps(payload, indent=2))
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
        if record_path is not None:
            print(f"record        : {rel_to_repo(record_path)}")
            print(
                f"                refreshed {rel_to_repo(RECORDS_DIR)}/MANIFEST.sha256"
            )
        elif args.no_record:
            print("record        : not written (--no-record)")
        elif not passed:
            print("record        : not written (the regression did not pass)")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
