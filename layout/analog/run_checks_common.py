"""Shared runner for the per-leaf `layout/analog/<block>/run_checks.py` entry points.

Each leaf directory keeps a thin `run_checks.py` that builds a `LeafConfig` and calls
`main(cfg)`; the command `python3 layout/analog/<block>/run_checks.py [--record]` is
unchanged. Shared code, per-leaf outputs: the reports, GDS, requests and append-only
records stay in the leaf (and flow/analog-layout-<block>/); only this logic is shared
(operator ruling on #238, which covers #233).

Five steps, every one driven through `klt` (never a raw `klayout`):

  1. `gen.py --check`  the committed GDS is what the generator emits.
  2. `klt drc`         klt's curated sky130 deck          -> drc-report.json
  3. `klt drc`         the PDK-native sky130A_mr.drc deck -> drc-native-report.json
  4. `klt lvs`         the PDK's sky130.lvs runset vs the leaf's reference netlist
                                                          -> lvs-report.json
  5. `klt erc`         supply islands + well/substrate ties -> erc-supply-report.json

The reports are `klt`'s own JSON, written verbatim. The PDK tree is resolved by
`flow/run_flow.py`'s `resolve_pdk_root`, which refuses a tree whose open_pdks
revision differs from the repo's pin (sim/corners.json, #151).

`--record` mints one append-only record under flow/analog-layout-<block>/ (see
flow/README.md, "Analog layout records"). This module's path and digest are
deliberately NOT in a record's `provenance.inputs` (they are the same list as before
the extraction). Exit codes: 0 every check passed, 1 a check failed, 2 the
environment failed.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FLOW_DIR = REPO_ROOT / "flow"
sys.path.insert(0, str(FLOW_DIR))

import run_flow  # noqa: E402  (resolve_pdk_root, git_revision, rebuild_manifest)

RECORD_SCHEMA = "usb2phy.flow.record/1"
RECORD_KIND = "analog-layout"

REPORTS = {
    "drc_curated": "drc-report.json",
    "drc_native": "drc-native-report.json",
    "lvs": "lvs-report.json",
    "erc": "erc-supply-report.json",
}

# The PDK-native deck is run with every rule group on except the seal ring (this is a
# block, not a die) and floating-metal (a die-level fill check). The category count is
# the deck's own, from its first run's `coverage.rule_categories`; `klt drc` accepts a
# zero-finding native run as clean only against that assertion.
NATIVE_DECK = "libs.tech/klayout/drc/sky130A_mr.drc"
NATIVE_DECK_VARS = {
    "feol": "true",
    "beol": "true",
    "offgrid": "true",
    "seal": "false",
    "floating_met": "false",
    "thr": "2",
}
NATIVE_RULE_CATEGORIES = 244

BASE_TOOL_GAPS = [
    "https://github.com/2AMLogic/klayout-tools/issues/3987",
    "https://github.com/2AMLogic/klayout-tools/issues/3988",
    "https://github.com/2AMLogic/klayout-tools/issues/3989",
    "https://github.com/2AMLogic/klayout-tools/issues/2934",
]


@dataclass
class LeafConfig:
    """Everything that differs between leaves. Prose fields are inserted verbatim."""

    here: Path                      # the leaf directory (Path(__file__).resolve().parent)
    block: str
    issue: int
    supply_nets: tuple[str, str]    # the two nets the ERC island check expects (1 island each)
    claim_subject: str              # "the first analog leaf's" / "this leaf's" / ...
    bulk_note_tail: str             # sentence tail after "still extracted and compared"
    doc: str = ""                   # the wrapper's __doc__ (first line used for --help)
    inputs_after_common: list[str] = field(default_factory=list)  # after gen_common.py
    inputs_after_netlist: list[str] = field(default_factory=list)  # after the netlist
    extra_tool_gaps: list[str] = field(default_factory=list)  # appended to BASE_TOOL_GAPS
    lvs_reference: str | None = None            # repo-relative path written before LVS
    derive_lvs_reference: Callable[[], str] | None = None

    @property
    def experiment(self) -> str:
        return f"analog-layout-{self.block}"

    @property
    def rel(self) -> str:
        return self.here.relative_to(REPO_ROOT).as_posix()

    @property
    def gds(self) -> str:
        return f"{self.rel}/{self.block}.gds"

    @property
    def netlist(self) -> str:
        return f"design/netlist/{self.block}.spice"

    @property
    def generator(self) -> str:
        return f"{self.rel}/gen.py"

    @property
    def erc_spec(self) -> str:
        return f"{self.rel}/erc-supply-spec.json"

    @property
    def lvs_request(self) -> str:
        return f"{self.rel}/request-lvs.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def klt(args: list[str], env: dict[str, str], out: Path) -> tuple[int, dict]:
    """Run one `klt` verb from the repo root; write its stdout verbatim to `out`."""
    log(f"    $ klt {' '.join(args)}")
    proc = subprocess.run(["klt", *args], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise SystemExit(f"klt {args[0]} wrote no JSON (rc={proc.returncode}): {proc.stderr[-800:]}")
    out.write_text(proc.stdout if proc.stdout.endswith("\n") else proc.stdout + "\n", encoding="utf-8")
    return proc.returncode, json.loads(proc.stdout)


def run_all(cfg: LeafConfig, env: dict[str, str], pdk_root: str) -> tuple[dict[str, dict], list[str]]:
    """Run steps 1-5. Returns ({stage: report}, [failure messages])."""
    failures: list[str] = []
    reports: dict[str, dict] = {}

    log("  [1/5] generator reproduces the committed GDS")
    gen = subprocess.run([sys.executable, str(cfg.here / "gen.py"), "--check"], capture_output=True, text=True)
    if gen.returncode != 0:
        failures.append(f"gen.py --check: {gen.stdout.strip()}")

    log("  [2/5] klt drc, curated sky130 deck")
    rc, rep = klt(["drc", "--deck", "sky130", cfg.gds, "--top", cfg.block, "--format", "json"], env, cfg.here / REPORTS["drc_curated"])
    reports["drc_curated"] = rep
    if rep.get("status") != "clean":
        failures.append(f"curated DRC status {rep.get('status')!r} (rc={rc})")

    log("  [3/5] klt drc, PDK-native sky130A_mr.drc")
    native_args = ["drc", cfg.gds, "--top", cfg.block, "--engine", "klayout", "--pdk", "sky130A",
                   "--deck-file", f"{pdk_root}/sky130A/{NATIVE_DECK}",
                   "--expect-rule-categories", str(NATIVE_RULE_CATEGORIES), "--format", "json"]
    for name, value in NATIVE_DECK_VARS.items():
        native_args += ["--deck-var", f"{name}={value}"]
    rc, rep = klt(native_args, env, cfg.here / REPORTS["drc_native"])
    reports["drc_native"] = rep
    if rep.get("status") != "clean":
        failures.append(f"native DRC status {rep.get('status')!r} (rc={rc})")

    log("  [4/5] klt lvs, PDK runset sky130.lvs")
    if cfg.derive_lvs_reference is not None:
        (REPO_ROOT / cfg.lvs_reference).write_text(cfg.derive_lvs_reference(), encoding="utf-8")
    request = json.loads((REPO_ROOT / cfg.lvs_request).read_text(encoding="utf-8"))
    request.pop("_comment", None)
    request["layout"]["file"] = str(REPO_ROOT / request["layout"]["file"])
    request["reference"]["netlist"] = str(REPO_ROOT / request["reference"]["netlist"])
    request["deck_file"] = request["deck_file"].replace("$PDK_ROOT", pdk_root)
    with tempfile.TemporaryDirectory(prefix="klt-lvs-request-") as scratch:
        scratch_request = Path(scratch) / "request-lvs.json"
        scratch_request.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        rc, rep = klt(["lvs", str(scratch_request), "--format", "json"], env, cfg.here / REPORTS["lvs"])
    reports["lvs"] = rep
    # The runset writes its extracted netlist next to the input layout, not into klt's
    # scratch directory (klayout-tools#3752 notes the same side effect). It is a by-product.
    (cfg.here / f"{cfg.block}_extracted.cir").unlink(missing_ok=True)
    if rep.get("status") != "match":
        failures.append(f"LVS status {rep.get('status')!r} (rc={rc})")

    log("  [5/5] klt erc, supply islands and ties")
    rc, rep = klt(["erc", cfg.gds, cfg.erc_spec, "--top", cfg.block, "--pdk", "sky130", "--format", "json"], env, cfg.here / REPORTS["erc"])
    reports["erc"] = rep
    islands = {n["name"]: n["matched_islands"] for n in rep.get("nets", [])}
    sa, sb = cfg.supply_nets
    if islands != {sa: 1, sb: 1}:
        failures.append(f"ERC supply islands {islands} (want {sa} and {sb} exactly 1 each)")
    if rep.get("erc_finding_count") != 0:
        failures.append(f"ERC findings: {rep.get('erc_findings')}")
    return reports, failures


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------
def build_meta(cfg: LeafConfig, reports: dict[str, dict], pdk_root: str, record_id: str, supersedes: str | None) -> dict:
    drc, nat, lvs, erc = (reports[k] for k in ("drc_curated", "drc_native", "lvs", "erc"))
    cov = drc["coverage"]
    lvs_runset = lvs["provenance"]["runset"]
    native_deck = Path(pdk_root) / "sky130A" / NATIVE_DECK
    erc_cov = erc["erc_coverage"]
    pin = json.loads((REPO_ROOT / "sim" / "pdk-pins.json").read_text(encoding="utf-8"))["current"]
    inputs = [
        cfg.gds, cfg.generator, "layout/analog/gen_common.py", *cfg.inputs_after_common,
        cfg.netlist, *cfg.inputs_after_netlist, cfg.erc_spec, cfg.lvs_request, "sim/pdk-pins.json",
    ]
    return {
        "schema": RECORD_SCHEMA,
        "record_kind": RECORD_KIND,
        "record_id": record_id,
        "experiment": cfg.experiment,
        "block": cfg.block,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": run_flow.git_revision(),
        "supersedes": supersedes,
        "design": {
            "block": cfg.block,
            "netlist": cfg.netlist,
            "gds": cfg.gds,
            "generator": cfg.generator,
            "anchors_design_claim": False,
            "claim_note": (
                f"One leaf of the analog partition. This record is {cfg.claim_subject} evidence "
                "for T1 items 2 (layout), 3 (DRC), 4 (LVS) and the supply half of 11; the analog "
                "partition's rows stay unmet until every leaf has the same, and nothing here is "
                f"cited from signoff/block-manifest.json (issue #{cfg.issue}, out of scope)."
            ),
        },
        "reproducibility": {
            "generator": cfg.generator,
            "gds_sha256": sha256_file(REPO_ROOT / cfg.gds),
            "regenerated_identical": True,
        },
        "stages": {
            "drc_curated": {
                "status": drc["status"],
                "violation_count": drc["violation_count"],
                "deck": {"name": drc["provenance"]["deck"]["name"], "content_hash": drc["provenance"]["deck"]["content_hash"]},
                "coverage": {
                    "layers_in_stream_without_rules": cov["layers_in_stream_without_rules"],
                    "rules_checked_count": len(cov["rules_checked"]),
                    "rules_skipped": cov["rules_skipped"],
                    "deck_scope": cov["deck_scope"],
                    "unmodeled_rules": cov["unmodeled_rules"],
                    "voltage_domain_warnings": cov["voltage_domain_warnings"],
                },
            },
            "drc_native": {
                "status": nat["status"],
                "violation_count": nat["violation_count"],
                "engine": nat["engine"],
                "deck_file": f"sky130A/{NATIVE_DECK}",
                "deck_sha256": sha256_file(native_deck),
                "deck_vars": NATIVE_DECK_VARS,
                "expected_rule_categories": NATIVE_RULE_CATEGORIES,
                "declared_rule_categories": len(nat["coverage"]["rule_categories"]),
            },
            "lvs": {
                "status": lvs["status"],
                "engine": lvs["engine"],
                "counts": lvs["counts"],
                "device_census": lvs["device_census"],
                "warnings_only_mismatches": [m for m in lvs["mismatches"] if m.get("severity") == "warning"],
                "mismatch_count": lvs["mismatch_count"],
                "body_verification": lvs["body_verification"],
                "body_verification_note": (
                    "null: the klayout-runset engine does not compute it. The bulk terminal is "
                    "still extracted and compared" + cfg.bulk_note_tail
                ),
                "power_connectivity": {
                    "status": lvs["power_connectivity"]["status"],
                    "reason": lvs["power_connectivity"]["reason"],
                },
                "runset": {
                    "name": lvs["provenance"]["deck"]["name"],
                    "content_hash": lvs["provenance"]["deck"]["content_hash"],
                    "deck_vars": lvs_runset["deck_vars"],
                    "klayout_application_version": lvs_runset["klayout_application_version"],
                },
                "declared_not_recognized_count": len(lvs["coverage"]["declared_not_recognized"]),
            },
            "erc": {
                "status": erc["status"],
                "erc_status": erc["erc_status"],
                "erc_finding_count": erc["erc_finding_count"],
                "supply_islands": {n["name"]: n["matched_islands"] for n in erc["nets"]},
                "ties_checked": [c for c in erc_cov["checked"] if c.startswith("erc.missing_tie")],
                "ties_skipped": [s for s in erc_cov["skipped"] if s["id"].startswith("erc.missing_tie")],
                "ties_checked_by_well_assertion": erc_cov["checked_by_well_assertion"],
                "status_note": (
                    "the overall status is clean_partial because the antenna table has no met3 "
                    "limit (antenna coverage.skipped: missing_antenna_limit); item 11 is graded "
                    "from the supply findings, not from this status."
                ),
            },
        },
        "provenance": {
            "klt_version": drc["provenance"]["klt_version"],
            "klayout_version": drc["provenance"]["klayout_version"],
            "pdk": {"name": "sky130A", "open_pdks_commit": pin["open_pdks_commit"]},
            "inputs": [{"path": p, "content_hash": sha256_file(REPO_ROOT / p)} for p in inputs],
            "artifacts": [],
        },
        "tool_gaps": BASE_TOOL_GAPS + cfg.extra_tool_gaps,
    }


def render_record(cfg: LeafConfig, meta: dict) -> str:
    st = meta["stages"]
    drc, nat, lvs, erc = st["drc_curated"], st["drc_native"], st["lvs"], st["erc"]
    cov = drc["coverage"]
    counts = lvs["counts"]
    body = f"""<!-- record-meta
{json.dumps(meta, indent=2)}
-->

# {meta['record_id']}

Physical checks of the `{meta['block']}` layout leaf (issue #{cfg.issue}), generated by
`{cfg.rel}/run_checks.py` from the committed GDS.
Every `klt` JSON envelope is committed verbatim under
`flow/{cfg.experiment}/artifacts/{meta['record_id']}/`.

**Scope.** {meta['design']['claim_note']}

## Layout

`{meta['design']['gds']}` (`sha256:{meta['reproducibility']['gds_sha256'].split(':')[1]}`) is emitted by
`{meta['design']['generator']}`; regenerating it reproduces that hash byte for byte.
All devices are drawn for sky130 from `{meta['design']['netlist']}`; no gf180 geometry is used.

## DRC

- **Curated deck** (`klt drc --deck sky130`): `status: {drc['status']}`, {drc['violation_count']} violations.
  Deck content hash `{drc['deck']['content_hash']}`.
  - `layers_in_stream_without_rules`: {', '.join(cov['layers_in_stream_without_rules'])}
  - `rules_skipped`: {len(cov['rules_skipped'])} of the deck's rules (layers absent from the stream), {cov['rules_checked_count']} rules checked
  - `deck_scope`: {', '.join(cov['deck_scope'])}
  - `unmodeled_rules` ({len(cov['unmodeled_rules'])}): {', '.join(cov['unmodeled_rules'])}
  - `voltage_domain_warnings`: {json.dumps(cov['voltage_domain_warnings'])}
- **PDK-native deck** (`klt drc --engine klayout`, `{nat['deck_file']}`, `{nat['deck_sha256']}`):
  `status: {nat['status']}`, {nat['violation_count']} violations, against
  `--expect-rule-categories {nat['expected_rule_categories']}` ({nat['declared_rule_categories']} declared). This is the
  stronger check: the curated deck cannot see the 5V (`hvi`) rule columns, the native one does.
  It is not a foundry signoff run.

## LVS

`klt lvs` engine `{lvs['engine']}`, runset `{lvs['runset']['name']}` (`{lvs['runset']['content_hash']}`),
deck vars {json.dumps(lvs['runset']['deck_vars'])}, standalone klayout {lvs['runset']['klayout_application_version']}.

- `status: {lvs['status']}`; devices {counts['devices']['matched']}/{counts['devices']['reference']}, nets {counts['nets']['matched']}/{counts['nets']['reference']}, pins {counts['pins']['matched']}/{counts['pins']['reference']}
- warnings-only mismatches: {json.dumps(lvs['warnings_only_mismatches']) if lvs['warnings_only_mismatches'] else 'none'}
- `body_verification`: {json.dumps(lvs['body_verification'])} -- {lvs['body_verification_note']}
- `power_connectivity`: `{lvs['power_connectivity']['status']}` -- {lvs['power_connectivity']['reason']}
- {lvs['declared_not_recognized_count']} runset device classes are declared but not present in this block (not a gap for this block).

## ERC (supply, T1 item 11)

`klt erc` overall `status: {erc['status']}`, `erc_status: {erc['erc_status']}`, {erc['erc_finding_count']} findings.
{erc['status_note']}

- supply islands: {json.dumps(erc['supply_islands'])} (`{cfg.supply_nets[0]}` and `{cfg.supply_nets[1]}` one island each)
- `erc.missing_tie` checked: {', '.join(erc['ties_checked'])}; skipped: {json.dumps(erc['ties_skipped']) if erc['ties_skipped'] else 'none'}
- the substrate tie is graded by the region assertion `well_complement_of: [nwell]`
  (`checked_by_well_assertion`: {json.dumps(erc['ties_checked_by_well_assertion'])}), not by a drawn well layer.

## Tool gaps filed while producing this record

""" + "\n".join(f"- {url}" for url in meta["tool_gaps"]) + "\n"
    return body


def mint_record(cfg: LeafConfig, reports: dict[str, dict], pdk_root: str) -> Path:
    records_dir = FLOW_DIR / cfg.experiment / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.stem for p in records_dir.glob("*.md"))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    record_id = f"{stamp}-{run_flow.git_revision()[:7]}-{cfg.block}"
    meta = build_meta(cfg, reports, pdk_root, record_id, existing[-1] if existing else None)
    art_dir = FLOW_DIR / cfg.experiment / "artifacts" / record_id
    art_dir.mkdir(parents=True, exist_ok=True)
    for name in REPORTS.values():
        shutil.copy2(cfg.here / name, art_dir / name)
        meta["provenance"]["artifacts"].append(
            {"path": (art_dir / name).relative_to(REPO_ROOT).as_posix(), "content_hash": sha256_file(art_dir / name)}
        )
    record = records_dir / f"{record_id}.md"
    record.write_text(render_record(cfg, meta), encoding="utf-8")
    run_flow.rebuild_manifest(records_dir)
    return record


def main(cfg: LeafConfig) -> int:
    ap = argparse.ArgumentParser(description=(cfg.doc or __doc__).splitlines()[0])
    ap.add_argument("--record", action="store_true", help="also mint the append-only record")
    args = ap.parse_args()

    env = dict(os.environ, PDK="sky130A")
    try:
        pdk_root = run_flow.resolve_pdk_root(env)
    except run_flow.StageError as exc:
        print(f"environment: {exc}", file=sys.stderr)
        return 2
    if not pdk_root:
        print("environment: no sky130A PDK found; see docs/environment-setup.md", file=sys.stderr)
        return 2

    reports, failures = run_all(cfg, env, pdk_root)
    if failures:
        print("\nFAILED:\n  " + "\n  ".join(failures))
        return 1
    log("\nall checks passed")
    if args.record:
        record = mint_record(cfg, reports, pdk_root)
        log(f"record: {record.relative_to(REPO_ROOT)}")
    return 0
