#!/usr/bin/env python3
"""Lint for this repo's digital-flow evidence records.

`flow/README.md` is the authoritative statement of the convention; this file
is its enforcement. Where the two disagree, README.md wins and this file is
the thing that gets fixed.

The three conditions this lint exists to fail on -- the ones issue #11 names
explicitly -- are:

  1. A record missing a required field.
  2. An existing record that was edited or deleted (the append-only rule).
  3. A record whose corner set is a subset of the committed matrix with no
     stated justification.

It additionally enforces four rules the convention needs in order to mean
anything (each is reported under its own check name so a failure is never
ambiguous about which rule it broke):

  4. Freshness -- a recorded input hash must still match the file it names.
  5. The timing gate -- a negative WNS needs an explicit written waiver, and
     OpenSTA's unconstrained sentinel is never a pass.
  6. DRC deck pinning -- a DRC record's deck content hash must equal the hash
     `flow/drc-deck-coverage.json` enumerates gaps for, and the record must
     carry that enumeration.
  7. Request validity -- every committed `flow/request-*.json` must parse and
     carry the fields its stage actually needs.

Pure standard library, no `klt` and no PDK required, so CI can run it on
every PR without provisioning an EDA toolchain. `--klt-check` opts into the
deeper tier (re-verifying committed `klt` reports through `klt drc --check` /
`klt lvs --check`) when a toolchain happens to be present.

Exit codes: 0 clean, 1 one or more findings, 2 usage/internal error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOW_DIR = REPO_ROOT / "flow"

RECORD_SCHEMA = "usb2phy.flow.record/1"

# OpenSTA reports 1e+39 when a design has no constrained timing path at all.
# It is a positive number, so a naive `wns >= 0` gate reads it as an enormous
# margin. Anything at or beyond this magnitude is the sentinel, not a slack.
UNCONSTRAINED_SENTINEL_FLOOR = 1e30

RECORD_ID_RE = re.compile(
    r"^(?P<date>\d{8})-(?P<time>\d{6})-(?P<sha>[0-9a-f]{7,40})-(?P<corner>[A-Za-z0-9_]+)$"
)

# Dotted paths into a record's `record-meta` JSON block. A missing path, or a
# `None` where `None` is not allowed, is condition 1.
REQUIRED_FIELDS: tuple[tuple[str, bool], ...] = (
    # (dotted path, may_be_null)
    ("schema", False),
    ("record_id", False),
    ("experiment", False),
    ("corner", False),
    ("created_utc", False),
    ("git_revision", False),
    ("supersedes", True),
    ("design.hdl_toplevel", False),
    ("design.sources", False),
    ("design.anchors_design_claim", False),
    ("corner_matrix.committed", False),
    ("corner_matrix.run", False),
    ("corner_matrix.subset_justification", True),
    ("timing.corner", False),
    ("timing.worst_slack_ns", False),
    ("timing.total_negative_slack_ns", False),
    ("timing.verdict", False),
    ("timing.waiver", True),
    ("timing.note", False),
    ("stages.synthesize.status", False),
    ("stages.synthesize.instance_count", False),
    ("stages.place_and_route.status", False),
    ("stages.place_and_route.stage_reached", False),
    ("stages.place_and_route.gds_path", False),
    ("stages.extract.status", False),
    ("stages.lvs.status", False),
    ("stages.lvs.engine", False),
    ("stages.lvs.warnings_only_mismatches", False),
    ("stages.drc.status", False),
    ("stages.drc.violation_count", False),
    ("stages.drc.deck.name", False),
    ("stages.drc.deck.content_hash", False),
    ("stages.drc.deck.known_coverage_gaps", False),
    ("stages.drc.coverage.rules_skipped", False),
    ("stages.drc.coverage.layers_in_stream_without_rules", False),
    ("provenance.klt_version", False),
    ("provenance.klayout_version", False),
    ("provenance.openroad_version", False),
    ("provenance.pdk", False),
    ("provenance.inputs", False),
    ("provenance.artifacts", False),
    ("tool_gaps", False),
)

VALID_TIMING_VERDICTS = {"pass", "fail", "waived", "unconstrained"}

# Committed request documents, and the fields each one must actually carry for
# the stage it drives to be reproducible from the file alone.
REQUEST_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "request-synth-utmi_stub.json": (
        "schema",
        "engine",
        "sources",
        "hdl_toplevel",
        "pdk.cell_library",
        "pdk.corner",
    ),
    "request-par-utmi_stub.json": (
        "schema",
        "engine",
        "netlist",
        "hdl_toplevel",
        "pdk.cell_library",
        "pdk.corner",
        "floorplan.method",
        "io.layer_h",
        "io.layer_v",
        # Without `power`, `klt place-and-route` generates no PDN at all: every
        # standard cell's VPWR/VGND pin belongs to no net, no tapcells are
        # inserted, and LVS's signal-only compare still reports `match`
        # because its gate-level-verilog reference carries no supply pins.
        # Requiring these three here is what stops that hole reappearing
        # silently in this template (issue #59).
        "power.power_net",
        "power.ground_net",
        "power.straps",
        "constraints.clock_port",
        "constraints.clock_period_ns",
        "seed",
        "target_stage",
    ),
    "request-sta-utmi_stub.json": (
        "schema",
        "def",
        "hdl_toplevel",
        "pdk.cell_library",
        "pdk.corner",
        "constraints.clock_port",
        "constraints.clock_period_ns",
    ),
    "request-extract-utmi_stub.json": (
        "schema",
        "file",
        "deck",
        "top",
        "output",
        "abstract_cells",
    ),
    "request-lvs-utmi_stub.json": (
        "schema",
        "engine",
        "layout.netlist",
        "layout.top",
        "reference.netlist",
        "reference.top",
        "reference.form",
        "reference.library",
        # Omitted, `klt lvs` still runs the power/ground check, but only as a
        # *relative* one: every instance's same-named pin must reach the same
        # net as every other instance's. That passes on a design where all of
        # them agree on the wrong net -- which is exactly how the pre-#59
        # evidence came to correspond `VGND` to the signal net `TXREADY` while
        # reporting `match`. Naming the nets makes it absolute: each supply
        # pin must reach the net the P&R request's `power` block declares.
        "options.power_connectivity.expected_nets",
    ),
    "request-drc-utmi_stub.json": (
        "schema",
        "file",
        "deck",
        "engine",
    ),
}


class Findings:
    """Collects failures, each tagged with the check that produced it."""

    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add(self, check: str, message: str) -> None:
        self.items.append((check, message))

    def __bool__(self) -> bool:
        return bool(self.items)

    def report(self, stream=sys.stdout) -> None:
        if not self.items:
            return
        width = max(len(check) for check, _ in self.items)
        for check, message in self.items:
            print(f"  [{check.ljust(width)}]  {message}", file=stream)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def dotted_get(data, path: str):
    """Fetch `a.b.c` out of nested dicts. Raises KeyError if any hop is absent."""
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def extract_record_meta(text: str, path: Path, findings: Findings):
    """Pull the `<!-- record-meta ... -->` JSON block out of a record."""
    start = text.find("<!-- record-meta")
    if start == -1:
        findings.add("record-meta", f"{path.name}: no `<!-- record-meta ... -->` block")
        return None
    end = text.find("-->", start)
    if end == -1:
        findings.add("record-meta", f"{path.name}: unterminated `<!-- record-meta` block")
        return None
    blob = text[start + len("<!-- record-meta") : end]
    try:
        return json.loads(blob)
    except json.JSONDecodeError as exc:
        findings.add("record-meta", f"{path.name}: record-meta is not valid JSON: {exc}")
        return None


# --------------------------------------------------------------------------
# Condition 1 -- required fields
# --------------------------------------------------------------------------
def check_required_fields(meta: dict, path: Path, findings: Findings) -> None:
    for dotted, may_be_null in REQUIRED_FIELDS:
        try:
            value = dotted_get(meta, dotted)
        except KeyError:
            findings.add("required-field", f"{path.name}: missing required field `{dotted}`")
            continue
        if value is None and not may_be_null:
            findings.add(
                "required-field",
                f"{path.name}: required field `{dotted}` is null (null is not allowed here)",
            )
        elif isinstance(value, str) and not value.strip() and not may_be_null:
            findings.add(
                "required-field", f"{path.name}: required field `{dotted}` is empty"
            )

    if meta.get("schema") not in (None, RECORD_SCHEMA):
        findings.add(
            "required-field",
            f"{path.name}: schema is {meta.get('schema')!r}, expected {RECORD_SCHEMA!r}",
        )

    record_id = meta.get("record_id")
    if isinstance(record_id, str):
        if path.stem != record_id:
            findings.add(
                "record-id",
                f"{path.name}: record_id {record_id!r} does not match the filename stem",
            )
        match = RECORD_ID_RE.match(record_id)
        if not match:
            findings.add(
                "record-id",
                f"{path.name}: record_id {record_id!r} does not match "
                "<YYYYMMDD>-<HHMMSS>-<short-sha>-<corner-id>",
            )
        elif match.group("corner") != meta.get("corner"):
            findings.add(
                "record-id",
                f"{path.name}: record_id corner field {match.group('corner')!r} "
                f"does not match `corner` ({meta.get('corner')!r})",
            )


# --------------------------------------------------------------------------
# Condition 2 -- append-only
# --------------------------------------------------------------------------
def parse_manifest(path: Path, findings: Findings) -> dict[str, str] | None:
    if not path.exists():
        findings.add("append-only", f"{path.name} is missing -- records cannot be verified")
        return None
    entries: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            findings.add("append-only", f"{path.name}:{lineno}: malformed entry {raw!r}")
            continue
        digest, name = parts
        entries[name] = digest
    return entries


def check_append_only_manifest(
    records_dir: Path, record_paths: list[Path], findings: Findings
) -> None:
    manifest_path = records_dir / "MANIFEST.sha256"
    entries = parse_manifest(manifest_path, findings)
    if entries is None:
        return

    on_disk = {p.name for p in record_paths}

    for name, expected in sorted(entries.items()):
        record = records_dir / name
        if not record.exists():
            findings.add(
                "append-only",
                f"{name} is listed in MANIFEST.sha256 but is not on disk -- "
                "records are append-only and are never deleted",
            )
            continue
        actual = sha256_file(record)
        if actual != expected:
            findings.add(
                "append-only",
                f"{name} has been edited in place (manifest {expected}, on disk {actual}) -- "
                "a correction mints a new record that names the old one in `supersedes`",
            )

    for name in sorted(on_disk - set(entries)):
        findings.add(
            "append-only",
            f"{name} is on disk but absent from MANIFEST.sha256 -- "
            "every record must be registered when it is added",
        )


def git_available(base_ref: str) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "--quiet", base_ref],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def git_show(base_ref: str, rel_path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{base_ref}:{rel_path}"],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def git_ls_records(base_ref: str, rel_dir: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", base_ref, rel_dir],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.endswith(".md")]


def check_append_only_git(records_dir: Path, base_ref: str, findings: Findings) -> str:
    """The real append-only enforcement: compare against a base ref.

    The manifest alone cannot stop an edit that also rewrites the manifest
    line. Comparing every record blob that exists in the base ref against the
    working tree can, because the base ref is not writable from this PR.
    """
    if not git_available(base_ref):
        return f"skipped (base ref {base_ref!r} not available in this checkout)"

    rel_dir = records_dir.relative_to(REPO_ROOT).as_posix()
    base_records = git_ls_records(base_ref, rel_dir)
    for rel_path in base_records:
        base_blob = git_show(base_ref, rel_path)
        if base_blob is None:
            continue
        live = REPO_ROOT / rel_path
        if not live.exists():
            findings.add(
                "append-only",
                f"{rel_path} exists in {base_ref} but has been deleted -- "
                "records are append-only",
            )
            continue
        if live.read_bytes() != base_blob:
            findings.add(
                "append-only",
                f"{rel_path} differs from {base_ref} -- an existing record was edited; "
                "mint a new record with `supersedes` instead",
            )

    # The manifest itself is append-only in the weaker sense that lines may be
    # added but never removed or rewritten.
    rel_manifest = (records_dir / "MANIFEST.sha256").relative_to(REPO_ROOT).as_posix()
    base_manifest = git_show(base_ref, rel_manifest)
    if base_manifest is not None:
        live_manifest = records_dir / "MANIFEST.sha256"
        base_entries = {}
        for line in base_manifest.decode("utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and not line.startswith("#"):
                base_entries[parts[1]] = parts[0]
        live_entries = {}
        if live_manifest.exists():
            for line in live_manifest.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and not line.startswith("#"):
                    live_entries[parts[1]] = parts[0]
        for name, digest in sorted(base_entries.items()):
            if name not in live_entries:
                findings.add(
                    "append-only",
                    f"MANIFEST.sha256: entry for {name} present in {base_ref} was removed",
                )
            elif live_entries[name] != digest:
                findings.add(
                    "append-only",
                    f"MANIFEST.sha256: entry for {name} was rewritten "
                    f"({digest} -> {live_entries[name]})",
                )

    return f"compared {len(base_records)} record(s) against {base_ref}"


# --------------------------------------------------------------------------
# Condition 3 -- corner subset without justification
# --------------------------------------------------------------------------
def check_corner_matrix(
    meta: dict, path: Path, committed: list[str], findings: Findings
) -> None:
    matrix = meta.get("corner_matrix")
    if not isinstance(matrix, dict):
        return  # already reported by the required-field check

    declared = matrix.get("committed")
    run = matrix.get("run")
    justification = matrix.get("subset_justification")

    if not isinstance(declared, list) or not isinstance(run, list):
        findings.add(
            "corner-matrix",
            f"{path.name}: corner_matrix.committed and .run must both be lists",
        )
        return

    if sorted(declared) != sorted(committed):
        findings.add(
            "corner-matrix",
            f"{path.name}: corner_matrix.committed does not match flow/corners.json "
            f"(record: {sorted(declared)}, repo: {sorted(committed)})",
        )

    missing = [corner for corner in committed if corner not in run]
    if missing:
        if not (isinstance(justification, str) and justification.strip()):
            findings.add(
                "corner-matrix",
                f"{path.name}: run covers {len(run)} of {len(committed)} committed corners "
                f"(missing {missing}) and corner_matrix.subset_justification is empty -- "
                "a reduced corner set must state why",
            )
    elif isinstance(justification, str) and justification.strip():
        # Not fatal, but a justification for a full run is noise that will
        # mislead the next reader.
        findings.add(
            "corner-matrix",
            f"{path.name}: corner_matrix.subset_justification is set but the run covers "
            "every committed corner -- remove it or record the real subset",
        )

    unknown = [corner for corner in run if corner not in committed]
    if unknown:
        findings.add(
            "corner-matrix",
            f"{path.name}: corner_matrix.run names corner(s) not in the committed "
            f"matrix: {unknown}",
        )

    if meta.get("corner") not in run:
        findings.add(
            "corner-matrix",
            f"{path.name}: this record's own corner {meta.get('corner')!r} is not in "
            "corner_matrix.run",
        )


# --------------------------------------------------------------------------
# Rule 4 -- freshness
# --------------------------------------------------------------------------
def superseded_record_ids(metas: list[dict]) -> set[str]:
    """Every record id that some other record names in its `supersedes` field.

    Freshness is a claim about the *current* tree, so it can only sensibly be
    asked of records that still stand. A superseded record is frozen evidence
    of what the flow reported at an earlier revision of its own committed
    inputs -- it is append-only precisely so it can go on saying that, and
    re-running the flow after a deliberate request change (e.g. adding the
    `power` block, issue #59) must not retro-fail it.
    """
    ids: set[str] = set()
    for meta in metas:
        prior = meta.get("supersedes")
        if isinstance(prior, str) and prior.strip():
            ids.add(prior.strip())
    return ids


def check_freshness(
    meta: dict, path: Path, findings: Findings, superseded: set[str] | None = None
) -> None:
    if superseded and meta.get("record_id") in superseded:
        return
    inputs = meta.get("provenance", {}).get("inputs")
    if not isinstance(inputs, list):
        return
    for entry in inputs:
        if not isinstance(entry, dict) or "path" not in entry or "content_hash" not in entry:
            findings.add(
                "freshness",
                f"{path.name}: provenance.inputs entry must carry `path` and `content_hash`: "
                f"{entry!r}",
            )
            continue
        target = REPO_ROOT / entry["path"]
        if not target.exists():
            findings.add(
                "freshness",
                f"{path.name}: provenance input {entry['path']} no longer exists -- "
                "the record cites a file that is gone",
            )
            continue
        actual = sha256_file(target)
        if actual != entry["content_hash"]:
            findings.add(
                "freshness",
                f"{path.name}: provenance input {entry['path']} has changed since this "
                f"record was written (recorded {entry['content_hash']}, now {actual}) -- "
                "the record is stale; re-run the flow and mint a new record",
            )


# --------------------------------------------------------------------------
# Rule 5 -- the timing gate
# --------------------------------------------------------------------------
def is_sentinel(value) -> bool:
    return isinstance(value, (int, float)) and abs(value) >= UNCONSTRAINED_SENTINEL_FLOOR


def check_timing_gate(meta: dict, path: Path, findings: Findings) -> None:
    timing = meta.get("timing")
    if not isinstance(timing, dict):
        return

    verdict = timing.get("verdict")
    wns = timing.get("worst_slack_ns")
    tns = timing.get("total_negative_slack_ns")
    waiver = timing.get("waiver")
    note = timing.get("note")

    if verdict not in VALID_TIMING_VERDICTS:
        findings.add(
            "timing-gate",
            f"{path.name}: timing.verdict {verdict!r} is not one of "
            f"{sorted(VALID_TIMING_VERDICTS)}",
        )
        return

    if not isinstance(wns, (int, float)) or not isinstance(tns, (int, float)):
        findings.add(
            "timing-gate",
            f"{path.name}: timing.worst_slack_ns and .total_negative_slack_ns must both "
            "be numbers",
        )
        return

    sentinel = is_sentinel(wns)

    if sentinel and verdict != "unconstrained":
        findings.add(
            "timing-gate",
            f"{path.name}: worst_slack_ns is OpenSTA's unconstrained sentinel ({wns}) but "
            f"timing.verdict is {verdict!r} -- a design with no constrained timing path has "
            "not closed timing, and this record must not read as if it had",
        )
    if verdict == "unconstrained":
        if not sentinel:
            findings.add(
                "timing-gate",
                f"{path.name}: timing.verdict is 'unconstrained' but worst_slack_ns ({wns}) "
                "is a real measurement",
            )
        if not (isinstance(note, str) and note.strip()):
            findings.add(
                "timing-gate",
                f"{path.name}: an 'unconstrained' verdict must carry a non-empty timing.note "
                "explaining what was (and was not) measured",
            )
        if waiver is not None:
            findings.add(
                "timing-gate",
                f"{path.name}: a waiver cannot apply to an 'unconstrained' verdict -- "
                "there is no violation to waive, only a measurement that did not happen",
            )

    if verdict == "fail":
        findings.add(
            "timing-gate",
            f"{path.name}: timing.verdict is 'fail' (WNS {wns} ns, TNS {tns} ns) with no "
            "waiver -- the flow does not accept a negative-WNS corner unwaived",
        )

    if verdict == "waived":
        if not (isinstance(waiver, dict) and str(waiver.get("reason", "")).strip()):
            findings.add(
                "timing-gate",
                f"{path.name}: timing.verdict is 'waived' but timing.waiver carries no "
                "`reason` -- a waiver must be written down, not implied",
            )
        elif not str(waiver.get("author", "")).strip() or not str(
            waiver.get("date", "")
        ).strip():
            findings.add(
                "timing-gate",
                f"{path.name}: timing.waiver must name an `author` and a `date`",
            )
        if not sentinel and wns >= 0:
            findings.add(
                "timing-gate",
                f"{path.name}: timing.verdict is 'waived' but WNS ({wns}) is not negative",
            )

    if verdict == "pass":
        if sentinel:
            findings.add(
                "timing-gate",
                f"{path.name}: a 'pass' verdict on the unconstrained sentinel is a false claim",
            )
        elif wns < 0:
            findings.add(
                "timing-gate",
                f"{path.name}: timing.verdict is 'pass' but WNS is negative ({wns})",
            )
        elif tns < 0:
            findings.add(
                "timing-gate",
                f"{path.name}: timing.verdict is 'pass' but TNS is negative ({tns})",
            )


# --------------------------------------------------------------------------
# Rule 5b -- a record that claims a PDN must carry a power/ground verdict
# --------------------------------------------------------------------------
VALID_POWER_CONNECTIVITY_STATUSES = {"match", "mismatch", "unchecked", "unreported"}


def check_power_connectivity(
    meta: dict, path: Path, findings: Findings, superseded: set[str] | None = None
) -> None:
    """`klt lvs`'s signal verdict says nothing about power -- issue #59.

    The LVS reference this flow uses is `klt place-and-route`'s as-built
    gate-level Verilog, which carries no supply pins. The signal compare
    therefore drops the layout's supply nets instead of failing on them, and
    reports `status: "match"` on a layout with no power grid at all. The
    power/ground half is a separate verdict (`power_connectivity`,
    klayout-tools#1964) and this repo must never let the first stand in for
    the second.

    Scoped to records that actually claim a PDN
    (`stages.place_and_route.power.pdn` is true). `stages.place_and_route.power`
    is deliberately *not* in `REQUIRED_FIELDS`, because records minted before
    `request-par-utmi_stub.json` grew its `power` block predate the verdict
    entirely -- they are append-only evidence of exactly that, and the PDN
    itself is enforced at the request level by `REQUEST_REQUIREMENTS`.

    But that exemption must not become a way to make the check silently
    decline to run: a *standing* (non-superseded) record that omits the
    `power` echo entirely cannot say whether it generated a PDN, and issue #67
    is exactly that hole -- an absent echo taking the same code path as a
    genuine pre-`power`-block vintage record. The vintage exemption is
    therefore scoped the same way `check_freshness`'s supersession exemption
    is: only a record some other record `supersedes` is frozen evidence of an
    earlier schema and stays exempt. A standing record with no `power` key is
    a finding, not a pass-by-omission.
    """
    if superseded and meta.get("record_id") in superseded:
        return

    try:
        par = dotted_get(meta, "stages.place_and_route")
    except KeyError:
        return  # already reported by check_required_fields
    if not isinstance(par, dict):
        return

    if "power" not in par:
        findings.add(
            "power-connectivity",
            f"{path.name}: stages.place_and_route carries no `power` echo at all -- a "
            "standing record that cannot say whether it generated a PDN does not pass "
            "the PDN check (issue #67); a record that genuinely predates the `power` "
            "echo must be superseded, not left standing without one",
        )
        return

    power_echo = par.get("power")
    if not isinstance(power_echo, dict):
        findings.add(
            "power-connectivity",
            f"{path.name}: stages.place_and_route.power must be an object",
        )
        return

    pdn = power_echo.get("pdn")
    if pdn is not True:
        return

    try:
        power = dotted_get(meta, "stages.lvs.power_connectivity")
    except KeyError:
        findings.add(
            "power-connectivity",
            f"{path.name}: place_and_route reports a generated PDN but the record carries "
            "no `stages.lvs.power_connectivity` verdict -- a signal-only LVS `match` is "
            "not evidence that the design is powered (issue #59)",
        )
        return
    if not isinstance(power, dict):
        findings.add(
            "power-connectivity",
            f"{path.name}: `stages.lvs.power_connectivity` must be an object",
        )
        return

    status = power.get("status")
    if status not in VALID_POWER_CONNECTIVITY_STATUSES:
        findings.add(
            "power-connectivity",
            f"{path.name}: stages.lvs.power_connectivity.status {status!r} is not one of "
            f"{sorted(VALID_POWER_CONNECTIVITY_STATUSES)}",
        )
        return

    if status == "mismatch":
        findings.add(
            "power-connectivity",
            f"{path.name}: stages.lvs.power_connectivity.status is 'mismatch' "
            f"({power.get('finding_count')} finding(s)) -- the power/ground half of LVS "
            "failed and this record must not read as a clean LVS result",
        )
    if status in ("unchecked", "unreported") and not str(power.get("note", "")).strip():
        findings.add(
            "power-connectivity",
            f"{path.name}: stages.lvs.power_connectivity.status is {status!r} but the "
            "record carries no note saying power connectivity went unverified -- an "
            "unverified half of LVS must be written down, not implied",
        )

    # `klt lvs` produces no finding for an `expected_nets` pin it never
    # resolved, so a typo'd or absent pin name reads exactly like a pin that
    # was checked and found correct (klayout-tools#1978). The report names
    # them; a record that carries names here is not a clean verdict.
    unchecked_pins = power.get("unchecked_expected_pins")
    if unchecked_pins:
        findings.add(
            "power-connectivity",
            f"{path.name}: stages.lvs.power_connectivity.unchecked_expected_pins is "
            f"{unchecked_pins!r} -- request-lvs-utmi_stub.json declares an expected net "
            "for a pin the check never resolved, so that part of the verdict was never "
            "asked rather than answered",
        )


# --------------------------------------------------------------------------
# Rule 6 -- DRC deck pinning and gap enumeration
# --------------------------------------------------------------------------
def check_drc_deck(meta: dict, path: Path, coverage: dict, findings: Findings) -> None:
    try:
        deck = dotted_get(meta, "stages.drc.deck")
    except KeyError:
        return
    if not isinstance(deck, dict):
        return

    pinned = coverage.get("content_hash")
    if deck.get("content_hash") != pinned:
        findings.add(
            "drc-deck",
            f"{path.name}: DRC deck content_hash {deck.get('content_hash')!r} does not match "
            f"flow/drc-deck-coverage.json's pinned {pinned!r} -- the committed gap "
            "enumeration describes a different deck revision than this record used",
        )

    gaps = deck.get("known_coverage_gaps")
    if not isinstance(gaps, list) or not gaps:
        findings.add(
            "drc-deck",
            f"{path.name}: stages.drc.deck.known_coverage_gaps is empty -- a clean DRC "
            "verdict from a deck with undisclosed gaps is a false claim",
        )
        return

    expected_ids = {g["id"] for g in coverage.get("known_gaps", []) if isinstance(g, dict)}
    recorded_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    missing = sorted(expected_ids - recorded_ids)
    if missing:
        findings.add(
            "drc-deck",
            f"{path.name}: known_coverage_gaps omits gap(s) the pinned deck coverage "
            f"declares: {missing}",
        )

    status = meta.get("stages", {}).get("drc", {}).get("status")
    count = meta.get("stages", {}).get("drc", {}).get("violation_count")
    if status == "clean" and isinstance(count, int) and count != 0:
        findings.add(
            "drc-deck",
            f"{path.name}: DRC status is 'clean' but violation_count is {count}",
        )


# --------------------------------------------------------------------------
# Rule 7 -- committed request documents
# --------------------------------------------------------------------------
def check_requests(flow_dir: Path, findings: Findings) -> int:
    checked = 0
    for name, required in sorted(REQUEST_REQUIREMENTS.items()):
        path = flow_dir / name
        if not path.exists():
            findings.add("request", f"{name} is missing -- every stage must be committed data")
            continue
        try:
            doc = load_json(path)
        except json.JSONDecodeError as exc:
            findings.add("request", f"{name}: not valid JSON: {exc}")
            continue
        checked += 1
        if not isinstance(doc, dict):
            findings.add("request", f"{name}: top level must be a JSON object")
            continue
        for dotted in required:
            try:
                value = dotted_get(doc, dotted)
            except KeyError:
                findings.add("request", f"{name}: missing required field `{dotted}`")
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                findings.add("request", f"{name}: field `{dotted}` is empty")

    # Stray request files that nothing knows how to validate are a trap: they
    # look authoritative and are not checked by anything.
    for path in sorted(flow_dir.glob("request-*.json")):
        if path.name not in REQUEST_REQUIREMENTS:
            findings.add(
                "request",
                f"{path.name} is not in check_records.py's REQUEST_REQUIREMENTS table -- "
                "add it there (with the fields its stage needs) or remove the file",
            )
    return checked


def check_corner_requests_agree(flow_dir: Path, corners: dict, findings: Findings) -> None:
    """Every request's `pdk.corner` must name a corner in the committed matrix."""
    committed = set(corners.get("committed", []))
    for name in ("request-synth-utmi_stub.json", "request-par-utmi_stub.json",
                 "request-sta-utmi_stub.json"):
        path = flow_dir / name
        if not path.exists():
            continue
        try:
            doc = load_json(path)
        except json.JSONDecodeError:
            continue
        corner = doc.get("pdk", {}).get("corner")
        if corner is not None and corner not in committed:
            findings.add(
                "request",
                f"{name}: pdk.corner {corner!r} is not in flow/corners.json's committed "
                "matrix -- the request template's default corner must be one the repo "
                "actually commits to",
            )
        library = doc.get("pdk", {}).get("cell_library")
        if library is not None and library != corners.get("cell_library"):
            findings.add(
                "request",
                f"{name}: pdk.cell_library {library!r} does not match flow/corners.json's "
                f"{corners.get('cell_library')!r}",
            )


# --------------------------------------------------------------------------
# Optional deeper tier
# --------------------------------------------------------------------------
def run_klt_checks(artifacts_root: Path, findings: Findings) -> str:
    if shutil.which("klt") is None:
        return "skipped (klt is not on PATH)"
    checked = 0
    for report in sorted(artifacts_root.glob("*/drc-report.json")):
        result = subprocess.run(
            ["klt", "drc", "--check", str(report), "--format", "json"],
            capture_output=True,
            text=True,
        )
        checked += 1
        if result.returncode != 0:
            findings.add(
                "klt-check",
                f"klt drc --check {report.relative_to(REPO_ROOT)} exited "
                f"{result.returncode}: {result.stdout.strip() or result.stderr.strip()}",
            )
    for report in sorted(artifacts_root.glob("*/lvs-report.json")):
        result = subprocess.run(
            ["klt", "lvs", "--check", str(report), "--format", "json"],
            capture_output=True,
            text=True,
        )
        checked += 1
        if result.returncode != 0:
            findings.add(
                "klt-check",
                f"klt lvs --check {report.relative_to(REPO_ROOT)} exited "
                f"{result.returncode}: {result.stdout.strip() or result.stderr.strip()}",
            )
    return f"re-verified {checked} committed klt report(s)"


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None, findings: Findings | None = None) -> int:
    """Run the lint. `findings` lets a caller (the test suite) inspect results."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--flow-dir",
        type=Path,
        default=FLOW_DIR,
        help="the flow/ directory to lint (default: this repo's)",
    )
    parser.add_argument(
        "--experiment",
        default="smoke-utmi_stub",
        help="experiment directory under flow/ holding records/ and artifacts/",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="git ref to enforce the append-only rule against (default: origin/main)",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="skip the git-based append-only comparison (manifest check still runs)",
    )
    parser.add_argument(
        "--klt-check",
        action="store_true",
        help="additionally re-verify committed klt reports via `klt drc/lvs --check`",
    )
    args = parser.parse_args(argv)

    flow_dir: Path = args.flow_dir.resolve()
    if findings is None:
        findings = Findings()

    corners_path = flow_dir / "corners.json"
    coverage_path = flow_dir / "drc-deck-coverage.json"
    for path in (corners_path, coverage_path):
        if not path.exists():
            print(f"check_records: missing {path}", file=sys.stderr)
            return 2
    corners = load_json(corners_path)
    coverage = load_json(coverage_path)
    committed = corners.get("committed", [])

    print("flow/check_records.py")
    print(f"  flow dir     : {flow_dir.relative_to(REPO_ROOT) if flow_dir.is_relative_to(REPO_ROOT) else flow_dir}")
    print(f"  experiment   : {args.experiment}")
    print(f"  corners      : {len(committed)} committed ({', '.join(committed)})")

    n_requests = check_requests(flow_dir, findings)
    check_corner_requests_agree(flow_dir, corners, findings)
    print(f"  requests     : {n_requests} committed request document(s) validated")

    records_dir = flow_dir / args.experiment / "records"
    if not records_dir.is_dir():
        findings.add(
            "records", f"{records_dir} does not exist -- there is no evidence to lint"
        )
        print()
        print("FAIL")
        findings.report()
        return 1

    record_paths = sorted(p for p in records_dir.glob("*.md"))
    if not record_paths:
        findings.add("records", f"{records_dir} contains no records")

    check_append_only_manifest(records_dir, record_paths, findings)
    if args.no_git:
        git_status = "skipped (--no-git)"
    else:
        git_status = check_append_only_git(records_dir, args.base_ref, findings)
    print(f"  append-only  : {len(record_paths)} record(s); git {git_status}")

    parsed: list[tuple[Path, dict]] = []
    for path in record_paths:
        meta = extract_record_meta(path.read_text(encoding="utf-8"), path, findings)
        if meta is None:
            continue
        parsed.append((path, meta))

    superseded = superseded_record_ids([meta for _, meta in parsed])

    for path, meta in parsed:
        check_required_fields(meta, path, findings)
        check_corner_matrix(meta, path, committed, findings)
        check_freshness(meta, path, findings, superseded)
        check_timing_gate(meta, path, findings)
        check_power_connectivity(meta, path, findings, superseded)
        check_drc_deck(meta, path, coverage, findings)

    if args.klt_check:
        klt_status = run_klt_checks(flow_dir / args.experiment / "artifacts", findings)
        print(f"  klt --check  : {klt_status}")

    print()
    if findings:
        print(f"FAIL -- {len(findings.items)} finding(s):")
        findings.report()
        return 1
    print(f"OK -- {len(record_paths)} record(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
