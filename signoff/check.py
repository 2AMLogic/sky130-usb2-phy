#!/usr/bin/env python3
"""Re-grade this block against the klayout-tools T1 checklist, and fail on rot.

    python3 signoff/check.py            # the gate CI runs
    python3 signoff/check.py --regen    # rewrite signoff/signoff-report.json

`signoff/block-manifest.json` is this block's machine-readable T1 claim and
`signoff/signoff-report.json` is the verdict `klt signoff --manifest` rendered
against it at commit time. Neither is worth anything if nobody re-runs it: a
manifest citation is a claim about *that* evidence file against *that* input
revision, and the moment either moves without the claim moving with it, the
committed verdict is a statement about a tree that no longer exists.

This script is what stops that. Six distinct checks, because `klt signoff`
alone cannot cover all of them:

1. **The grader is the pinned released wheel.** `klt` on PATH must be the
   PyPI registry wheel of klayout-tools recorded in `signoff/toolchain.json`
   (checked by version string AND by the build identity `klt version
   --format json` reports: `git_tag`/`is_release`). Under the same version
   number, a git snapshot or a full-repo install can grade differently --
   observed live for 0.5.0 (klayout-tools#2216) -- and the committed report
   is only byte-reproducible with the distribution it was graded with.
2. **Hand-rolled evidence is self-consistent.** A generic evidence envelope
   (`"kind": "generic"`) is written by hand, and so is the `content_hash`
   inside it. `klt signoff` compares the manifest's pin against *the
   envelope's own recorded hash* -- it never opens the underlying artifact,
   so two hand-written hashes agreeing with each other proves nothing. This
   re-hashes the file the envelope's `source` names and requires it to match.
3. **Artifact-anchored inventories are fresh.** Items 9 and 10 are cited
   through an artifact-anchored generic envelope (klayout-tools#2718): the
   envelope declares `"t1_item"` and pins ONE audited artifact
   (`provenance.input`), here a committed inventory under
   `signoff/inventory/`. The grader re-hashes that inventory, but not the
   files the inventory lists, so this check re-hashes every listed member
   too. Mutating an inventoried file fails the gate until the inventory is
   refreshed (`--regen`), which moves the inventory hash and with it the
   envelope and manifest pins. Item 1 (digital) is cited through a
   `klt signoff --attest` envelope instead; `check_attested` re-hashes the
   files that envelope recorded (re-attest to refresh it).
4. **The item-6 digital statement is bound to the spec.** The grader hashes
   the rows file and the statement but never opens `spec/usb2-phy.md`; this
   re-hashes the markdown against the rows file's recorded source.
5. **The grader itself runs clean.** Exit 0 (`tier: "T1"`) or 3 (`tier: null`,
   at least one item unmet) are both fine -- an all-`unmet` report is a
   correct result. Exit 1/2 mean the manifest is malformed,
   which is a real failure.
6. **The committed report still matches the rendered one.** Compared on a
   normalized projection (per-item `status`/`reason`, counts, tier, source
   doc), so a `klt` release that merely adds a field does not trip it -- but
   a citation going stale, a check starting to fail, or the T1 checklist
   itself growing an item all do.

Future native citations must grow their own gate here: `klt` through 0.5.0
does not re-hash the artifact behind a *native* envelope either (`input_verified`
arrives upstream in klayout-tools#2196), so a manifest that starts citing
`klt drc`/`lvs`/`pex` output must add a repo-side re-hash of the cited input
artifact to check 2 before such a citation can be trusted to not rot.

Pure stdlib; no PDK, no simulator, no Icarus. Only `klt` on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNOFF_DIR = REPO_ROOT / "signoff"
MANIFEST = SIGNOFF_DIR / "block-manifest.json"
REPORT = SIGNOFF_DIR / "signoff-report.json"
TOOLCHAIN = SIGNOFF_DIR / "toolchain.json"
EVIDENCE_DIR = SIGNOFF_DIR / "evidence"
INVENTORY_DIR = SIGNOFF_DIR / "inventory"

# The single artifact the item-8 generic envelope wraps today. Keep in one
# place: --regen re-derives both pins (the envelope's and the manifest's)
# from this file's current hash, exactly like gf180-sram's regenerate.sh.
CHARACTERIZATION_SOURCE = "docs/characterization.md"
CHARACTERIZATION_ENVELOPE = "signoff/evidence/characterization-report.json"

# Artifact-anchored citations (klayout-tools#2718): T1 item -> (inventory,
# envelope, what the envelope attests). The inventory is the single audited
# artifact the envelope pins; its members are re-hashed by
# check_inventory_members. Item 1 (digital) is not here: its envelope is
# produced by `klt signoff --attest` (see ATTESTED), not rewritten by --regen.
ANCHORED = {
    "9": (
        "signoff/inventory/item-9-testbenches.json",
        "signoff/evidence/item-9-testbenches.json",
        "every cocotb suite in verification/ and every analog testbench under "
        "sim/*/testbench/ is committed, with its cold-start invocation and the "
        "pinned PDK revision",
    ),
    "10": (
        "signoff/inventory/item-10-hygiene.json",
        "signoff/evidence/item-10-hygiene.json",
        "README.md, LICENSE and the CI workflow are committed, and the CI "
        "commands that keep the harness and evidence formats valid are named",
    ),
}
# Item 6 (digital): a bound `not_applicable` statement (klayout-tools#2865).
# The grader cannot parse spec/usb2-phy.md, so the ratified digital rows live
# in ITEM6_SPEC (machine-readable) with the markdown's content hash recorded
# in its `source`; check_item6_binding re-hashes the markdown against it.
ITEM6_KEY = "6.digital"
ITEM6_SPEC = "signoff/spec/digital-rows.json"
ITEM6_STATEMENT = "signoff/evidence/item-6-digital-not-applicable.json"

# Citations produced by `klt signoff --attest` (klt >= 0.8.0, newer than the
# 0.7.0 grader): manifest key -> (inventory, envelope). The inventory carries
# no per-file hashes; the envelope's `present` checks record them, so
# check_attested re-hashes against those. --regen does not rewrite these --
# re-run the attest command in signoff/README.md and commit the envelope.
ATTESTED = {
    "1.digital": (
        "signoff/inventory/item-1-digital-sources.json",
        "signoff/evidence/item-1-digital-sources.json",
    ),
}

# `klt signoff --manifest` exit codes that mean "the grader ran": 0 is
# tier T1, 3 is "ran fine, at least one item unmet". Anything else is a
# malformed manifest / usage error.
RAN_CLEAN = (0, 3)

# The grading build identity, asserted two ways (see check 1 above). Keep in
# sync with signoff/toolchain.json and the `signoff` CI job's pip pin.
GRADER_PACKAGE_VERSION = "0.8.0"
GRADER_GIT_TAG = "v0.8.0"


def fail(msg: str) -> None:
    print(f"FAIL {msg}", file=sys.stderr)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def check_toolchain_pin() -> bool:
    """The grading klt must be the pinned released registry wheel."""
    if not TOOLCHAIN.is_file():
        fail("signoff/toolchain.json is missing -- no grading-build pin recorded")
        return False
    try:
        pinned = json.loads(TOOLCHAIN.read_text())["klt"]["package_version"]
    except (OSError, ValueError, KeyError) as exc:
        fail(f"{TOOLCHAIN.name}: unreadable grading pin ({exc})")
        return False
    if pinned != GRADER_PACKAGE_VERSION:
        fail(
            f"signoff/toolchain.json pins klt {pinned!r} but check.py pins "
            f"{GRADER_PACKAGE_VERSION!r} -- these pins must move together, "
            "with the CI job's pip install"
        )
        return False
    proc = subprocess.run(
        ["klt", "version", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail(f"klt version exited {proc.returncode}:\n{proc.stderr.strip()}")
        return False
    try:
        identity = json.loads(proc.stdout)
    except ValueError as exc:
        fail(f"klt version produced output that is not valid JSON: {exc}")
        return False
    got = (
        identity.get("package_version"),
        identity.get("git_tag"),
        bool(identity.get("is_release")),
    )
    want = (GRADER_PACKAGE_VERSION, GRADER_GIT_TAG, True)
    if got != want:
        fail(
            "the klt on PATH is not the pinned grading build.\n"
            f"     wanted: released wheel {want[0]} (git_tag {want[1]}, "
            "is_release true)\n"
            f"     found : version {got[0]!r}, git_tag {got[1]!r}, "
            f"is_release {got[2]}\n"
            "     A same-version git snapshot or full-repo install grades "
            "differently from the\n"
            "     registry wheel (klayout-tools#2216): the committed report "
            "is only comparable\n"
            "     when graded with the distribution it was committed from. "
            "Install the pin:\n"
            f"       pip install klayout-tools=={GRADER_PACKAGE_VERSION}"
        )
        return False
    print(f"ok   grader is the pinned released wheel (klt {got[0]}, {got[1]})")
    return True


def load_manifest() -> dict | None:
    try:
        manifest = json.loads(MANIFEST.read_text())
    except (OSError, ValueError) as exc:
        fail(f"{MANIFEST.relative_to(REPO_ROOT)}: unreadable ({exc})")
        return None
    if not isinstance(manifest.get("evidence"), dict):
        fail(f"{MANIFEST.relative_to(REPO_ROOT)}: no evidence map")
        return None
    return manifest


def check_generic_envelopes(manifest: dict) -> bool:
    """Every hand-rolled generic envelope's pinned hash matches its source."""
    ok = True
    if not EVIDENCE_DIR.is_dir():
        return ok
    # The manifest's pin for a generic citation must equal the wrapped
    # artifact's hash, because that is what the envelope records in
    # provenance.input.content_hash and what the grader compares the
    # manifest pin against.
    manifest_pins: dict[str, str | None] = {}
    for item_id, entry in manifest["evidence"].items():
        if isinstance(entry, dict) and entry.get("file"):
            manifest_pins[str(entry["file"])] = entry.get("content_hash")
    for path in sorted(EVIDENCE_DIR.glob("*.json")):
        rel = path.relative_to(REPO_ROOT)
        try:
            envelope = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            fail(f"{rel}: unreadable ({exc})")
            ok = False
            continue
        if not isinstance(envelope, dict) or envelope.get("kind") != "generic":
            continue
        source = envelope.get("source")
        pinned = (envelope.get("provenance") or {}).get("input", {}).get(
            "content_hash"
        )
        if not source:
            fail(
                f"{rel}: a generic envelope must name the artifact it wraps in "
                '"source", so its freshness can be re-derived'
            )
            ok = False
            continue
        if not pinned:
            fail(
                f"{rel}: no provenance.input.content_hash -- an unpinned generic "
                "envelope's freshness cannot be verified at all"
            )
            ok = False
            continue
        source_path = REPO_ROOT / source
        if not source_path.is_file():
            fail(f"{rel}: source {source!r} does not exist")
            ok = False
            continue
        actual = sha256_file(source_path)
        if actual != pinned:
            fail(
                f"{rel}: pinned {pinned} but {source} now hashes to {actual}.\n"
                f"     {source} changed since this characterization claim was "
                "made. Re-read it, update the envelope's summary\n"
                "     if the disclosed result moved, then re-pin the hash "
                "(python3 signoff/check.py --regen) and update\n"
                "     signoff/README.md's claimed verdict to match."
            )
            ok = False
            continue
        pin_in_manifest = manifest_pins.get(str(rel))
        if pin_in_manifest is not None and pin_in_manifest != pinned:
            fail(
                f"{rel}: the manifest pins {pin_in_manifest} but the envelope "
                f"records {pinned} -- the citation renders stale_evidence"
            )
            ok = False
            continue
        print(f"ok   {rel}: pinned hash matches {source}")
    return ok


def _members(node):
    """Every {"path", "sha256"} member recorded anywhere in an inventory."""
    if isinstance(node, dict):
        if "path" in node and "sha256" in node:
            yield node
        for value in node.values():
            yield from _members(value)
    elif isinstance(node, list):
        for value in node:
            yield from _members(value)


def check_inventory_members() -> bool:
    """Every file an inventory lists still hashes to what it recorded."""
    ok = True
    names = [v[0] for v in ANCHORED.values()]
    for name in names:
        path = REPO_ROOT / name
        try:
            inventory = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            fail(f"{name}: unreadable ({exc})")
            ok = False
            continue
        members = list(_members(inventory))
        bad = False
        for member in members:
            member_path = REPO_ROOT / member["path"]
            if not member_path.is_file():
                fail(f"{name}: inventoried file {member['path']} does not exist")
                bad = True
            elif sha256_file(member_path) != member["sha256"]:
                fail(
                    f"{name}: inventoried file {member['path']} changed since "
                    "the inventory was taken (stale).\n"
                    "     Re-read the change, then refresh the pins "
                    "(python3 signoff/check.py --regen) and update "
                    "signoff/README.md if a claim moved."
                )
                bad = True
        if bad:
            ok = False
        else:
            print(f"ok   {name}: {len(members)} inventoried files re-hash")
    return ok


def check_attested(manifest: dict) -> bool:
    """`klt signoff --attest` envelopes still describe the tree.

    The 0.7.0 grader re-hashes only the inventory, and the `--attest --check`
    re-attestation needs klt >= 0.8.0, so this re-derives what it can with the
    stdlib: the envelope binds this inventory by hash, lists exactly the
    inventory's sources, and every `present` check's recorded hash still holds.
    The `local_only` freshness command is NOT re-run here (it needs the PDK);
    re-run `klt signoff --attest 1 --check` where klt >= 0.8.0 and the PDK exist.
    """
    ok = True
    for key, (inventory_rel, envelope_rel) in ATTESTED.items():
        try:
            inventory = json.loads((REPO_ROOT / inventory_rel).read_text())
            envelope = json.loads((REPO_ROOT / envelope_rel).read_text())
        except (OSError, ValueError) as exc:
            fail(f"{inventory_rel} / {envelope_rel}: unreadable ({exc})")
            ok = False
            continue
        refresh = (
            "     Re-attest and commit the envelope: uvx --from "
            f'"klayout-tools==0.8.0" klt signoff --attest {key.split(".")[0]} '
            f"--inventory {inventory_rel} -o {envelope_rel}"
        )
        bad = False
        if str((manifest["evidence"].get(key) or {}).get("file")) != envelope_rel:
            fail(f"signoff/block-manifest.json: {key} must cite {envelope_rel}")
            bad = True
        attestation = envelope.get("attestation") or {}
        if envelope.get("status") != "pass" or not attestation.get("check_count"):
            fail(f"{envelope_rel}: not a passing --attest envelope")
            bad = True
        present = [
            c for c in attestation.get("checks", []) if c.get("check") == "present"
        ]
        listed = set(inventory.get("sources", []))
        recorded = {c.get("path") for c in present if c.get("role") == "source"}
        if listed != recorded:
            fail(
                f"{envelope_rel}: attests {sorted(recorded ^ listed)} differently "
                f"from the sources {inventory_rel} lists (stale).\n{refresh}"
            )
            bad = True
        for check in present:
            path = REPO_ROOT / check["path"]
            if not path.is_file():
                fail(f"{envelope_rel}: attested file {check['path']} does not exist")
                bad = True
            elif sha256_file(path) != check.get("content_hash"):
                fail(
                    f"{envelope_rel}: attested file {check['path']} changed since "
                    f"it was attested (stale).\n{refresh}"
                )
                bad = True
        for check in attestation.get("checks", []):
            if check.get("check") == "command" and not check.get("passed"):
                fail(f"{envelope_rel}: freshness command {check.get('argv')} failed")
                bad = True
        if not bad:
            print(f"ok   {envelope_rel}: {len(present)} attested files re-hash")
        ok = ok and not bad
    return ok


def expected_item9_files(root: Path) -> set[str]:
    """Every testbench file the item 9 claim says the inventory lists."""
    found = set()
    for pattern in ("verification/test_*.py", "verification/request-*.json"):
        found.update(str(p.relative_to(root)) for p in root.glob(pattern))
    for path in root.glob("sim/*/testbench/*"):
        if path.is_file():
            found.add(str(path.relative_to(root)))
    return found


def check_item9_complete(root: Path | None = None) -> bool:
    """Item 9 claims *every* suite is inventoried: a new one must fail the gate."""
    root = root or REPO_ROOT
    name = ANCHORED["9"][0]
    try:
        inventory = json.loads((root / name).read_text())
    except (OSError, ValueError) as exc:
        fail(f"{name}: unreadable ({exc})")
        return False
    listed = {member["path"] for member in _members(inventory)}
    missing = sorted(expected_item9_files(root) - listed)
    for path in missing:
        fail(
            f"{name}: {path} is a testbench file but is not inventoried.\n"
            "     Add it to the inventory (with its cold-start invocation), then "
            "refresh the pins (python3 signoff/check.py --regen)."
        )
    if not missing:
        print(f"ok   {name}: every verification/ and sim/*/testbench/ file is inventoried")
    return not missing


def check_anchored_envelopes(manifest: dict) -> bool:
    """Items 9/10 envelopes declare their item and bind their inventory."""
    ok = True
    for item_id, (inventory, envelope_rel, _claim) in ANCHORED.items():
        try:
            envelope = json.loads((REPO_ROOT / envelope_rel).read_text())
        except (OSError, ValueError) as exc:
            fail(f"{envelope_rel}: unreadable ({exc})")
            ok = False
            continue
        bound = ((envelope.get("provenance") or {}).get("input") or {}).get("path")
        bound = bound.get("path") if isinstance(bound, dict) else bound
        if envelope.get("t1_item") != int(item_id) or bound != inventory:
            fail(
                f"{envelope_rel}: must declare t1_item {item_id} and bind "
                f"provenance.input.path {inventory!r}"
            )
            ok = False
        if str((manifest["evidence"].get(item_id) or {}).get("file")) != envelope_rel:
            fail(f"signoff/block-manifest.json: item {item_id} must cite {envelope_rel}")
            ok = False
    return ok


def run_grader() -> tuple[str, dict, bool]:
    argv = [
        "klt",
        "signoff",
        "--manifest",
        str(MANIFEST.relative_to(REPO_ROOT)),
        "--format",
        "json",
    ]
    proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode not in RAN_CLEAN:
        fail(
            f"klt signoff --manifest exited {proc.returncode} (expected 0 or 3). "
            "The manifest is malformed:"
        )
        sys.stderr.write(proc.stderr)
        return "", {}, False
    try:
        return proc.stdout, json.loads(proc.stdout), True
    except ValueError as exc:
        fail(f"klt signoff produced output that is not valid JSON: {exc}")
        return "", {}, False


def projection(report: dict) -> dict:
    """The part of a tier report whose drift is a real, actionable change.

    Deliberately excludes `citation` detail and `schema_version`: a klt
    release that adds a citation field (e.g. klayout-tools#2002's DRC
    `coverage` block) is not rot, and should not fail this gate. Per-item
    `status`/`reason`, the item set itself, and the counts are what a reader
    of signoff/signoff-report.json is relying on.
    """
    return {
        "block": report.get("block"),
        "kind": report.get("kind"),
        "tier": report.get("tier"),
        "t1_item_count": report.get("t1_item_count"),
        "t1_met_count": report.get("t1_met_count"),
        "source_doc": report.get("source_doc"),
        "items": [
            {
                "tier": item.get("tier"),
                "id": item.get("id"),
                "partition": item.get("partition"),
                "status": item.get("status"),
                "reason": item.get("reason"),
            }
            for item in report.get("items", [])
        ],
    }


def check_no_stale(report: dict) -> bool:
    stale = [
        item
        for item in report.get("items", [])
        if item.get("reason") == "stale_evidence"
    ]
    if not stale:
        return True
    for item in stale:
        fail(
            f"T1 item {item.get('id')} partition {item.get('partition')}: "
            "stale_evidence -- the cited check ran against a different input "
            "revision than the manifest pins."
        )
    return False


def check_drift(report: dict) -> bool:
    if not REPORT.is_file():
        fail(
            f"{REPORT.relative_to(REPO_ROOT)} is missing. "
            "Run: python3 signoff/check.py --regen"
        )
        return False
    try:
        committed = json.loads(REPORT.read_text())
    except ValueError as exc:
        fail(f"{REPORT.relative_to(REPO_ROOT)} is not valid JSON: {exc}")
        return False
    want, got = projection(committed), projection(report)
    if want == got:
        print(
            f"ok   {REPORT.relative_to(REPO_ROOT)} matches what the current "
            "tree grades to"
        )
        return True
    fail(
        f"{REPORT.relative_to(REPO_ROOT)} no longer matches what the current "
        "tree grades to."
    )
    by_id = {(i["tier"], i["id"], i["partition"]): i for i in want["items"]}
    for item in got["items"]:
        key = (item["tier"], item["id"], item["partition"])
        old = by_id.pop(key, None)
        if old is None:
            print(
                f"     + new checklist row {key}: {item['status']} "
                f"({item['reason']})",
                file=sys.stderr,
            )
        elif old != item:
            print(
                f"     ~ {key}: committed {old['status']}/{old['reason']}"
                f" -> now {item['status']}/{item['reason']}",
                file=sys.stderr,
            )
    for key in by_id:
        print(f"     - checklist row {key} no longer rendered", file=sys.stderr)
    for field in (
        "block",
        "kind",
        "tier",
        "t1_item_count",
        "t1_met_count",
        "source_doc",
    ):
        if want[field] != got[field]:
            print(
                f"     ~ {field}: committed {want[field]!r} -> now {got[field]!r}",
                file=sys.stderr,
            )
    print(
        "     If the new verdict is the correct one, regenerate the evidence "
        "record and commit it:\n"
        "       python3 signoff/check.py --regen\n"
        "     and update signoff/README.md's claim to match -- the prose and "
        "the report are one artifact, not two.",
        file=sys.stderr,
    )
    return False


def refresh_item8_source_hash() -> str | None:
    """--regen: re-derive the item-8 pins from the current artifact hash.

    Mirrors gf180-sram's regenerate.sh: the wrapper's pin is a pure
    derivation from the file it wraps, so refreshing it on regen is
    mechanical. The loud warning is the honesty price: a moved hash means
    the characterization REPORT's content changed, and re-pinning without
    re-reading it is how an unexamined change launders itself into a met row.
    """
    source_path = REPO_ROOT / CHARACTERIZATION_SOURCE
    if not source_path.is_file():
        fail(f"{CHARACTERIZATION_SOURCE} does not exist; cannot refresh item 8")
        return None
    new_hash = sha256_file(source_path)

    envelope_path = REPO_ROOT / CHARACTERIZATION_ENVELOPE
    envelope = json.loads(envelope_path.read_text())
    old_hash = (
        (envelope.get("provenance") or {}).get("input", {}).get("content_hash")
    )
    if new_hash != old_hash:
        print(
            f"note {CHARACTERIZATION_SOURCE} changed "
            f"({old_hash} -> {new_hash}).\n"
            "     Re-read the report and update the envelope's summary and\n"
            "     signoff/README.md's disclosed verdict if its content moved\n"
            "     before committing the refreshed pins -- a refreshed hash is\n"
            "     an observation, not an audit.",
            file=sys.stderr,
        )
        envelope["provenance"]["input"]["content_hash"] = new_hash
        envelope_path.write_text(json.dumps(envelope, indent=2) + "\n")

    manifest = json.loads(MANIFEST.read_text())
    entry = manifest["evidence"].get("8")
    if isinstance(entry, dict):
        entry["content_hash"] = new_hash
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return new_hash


def refresh_anchored() -> None:
    """--regen: re-hash inventory members, re-bind envelopes and the manifest.

    Same honesty price as refresh_item8_source_hash: a refreshed hash is an
    observation, not an audit -- re-read what changed first.
    """
    for name in [v[0] for v in ANCHORED.values()]:
        path = REPO_ROOT / name
        inventory = json.loads(path.read_text())
        moved = []
        for member in _members(inventory):
            new = sha256_file(REPO_ROOT / member["path"])
            if new != member["sha256"]:
                moved.append(member["path"])
                member["sha256"] = new
        if moved:
            print(
                f"note {name}: re-hashed {', '.join(moved)}.\n"
                "     Re-read what changed and update signoff/README.md if a "
                "claim moved.",
                file=sys.stderr,
            )
            path.write_text(json.dumps(inventory, indent=2) + "\n")
    manifest = json.loads(MANIFEST.read_text())
    for item_id, (inventory, envelope_rel, claim) in ANCHORED.items():
        pin = sha256_file(REPO_ROOT / inventory)
        envelope = {
            "schema_version": 1,
            "kind": "generic",
            "t1_item": int(item_id),
            "status": "pass",
            "summary": (
                f"T1 item {item_id}: {claim}. The audited artifact is {inventory}; "
                "check.py additionally re-hashes every file it lists. This "
                "asserts the inventory is complete and current; it does not "
                "assert that any test passes or any spec row is met."
            ),
            "source": inventory,
            "provenance": {
                "klt_version": None,
                "klayout_version": None,
                "pdk": None,
                "deck": None,
                "input": {
                    "path": {"path": inventory, "scope": "repo"},
                    "content_hash": pin,
                },
            },
        }
        (REPO_ROOT / envelope_rel).write_text(json.dumps(envelope, indent=2) + "\n")
        manifest["evidence"][item_id] = {"file": envelope_rel, "content_hash": pin}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def check_item6_binding(manifest: dict, root: Path | None = None) -> bool:
    """The item-6 digital statement is bound to the live spec markdown.

    `klt signoff` hash-pins the rows file and the statement but never opens
    spec/usb2-phy.md, so a spec edit would leave the "accounts for every row"
    claim silently stale. This re-hashes the markdown against the rows file's
    recorded source and requires the statement to name exactly the same rows.
    """
    root = root or REPO_ROOT
    try:
        spec = json.loads((root / ITEM6_SPEC).read_text())
        statement = json.loads((root / ITEM6_STATEMENT).read_text())
    except (OSError, ValueError) as exc:
        fail(f"item 6 (digital): rows file or statement unreadable ({exc})")
        return False
    ok = True
    source = spec.get("source") or {}
    source_path = root / str(source.get("file", ""))
    if not source.get("file") or not source_path.is_file():
        fail(f"{ITEM6_SPEC}: source {source.get('file')!r} does not exist")
        return False
    actual = sha256_file(source_path)
    if actual != source.get("content_hash"):
        fail(
            f"{ITEM6_SPEC}: records {source.get('content_hash')} for "
            f"{source['file']} but it now hashes to {actual}.\n"
            "     The spec changed since the digital rows were accounted for. "
            "Re-read it, update the rows file and the statement,\n"
            "     then re-pin (python3 signoff/check.py --regen)."
        )
        ok = False
    spec_ids = sorted(r.get("id") for r in spec.get("rows", []))
    statement_ids = sorted(r.get("id") for r in statement.get("rows", []))
    if spec_ids != statement_ids:
        fail(
            f"{ITEM6_STATEMENT}: must account for exactly the rows of "
            f"{ITEM6_SPEC}; missing {sorted(set(spec_ids) - set(statement_ids))}, "
            f"extra {sorted(set(statement_ids) - set(spec_ids))}"
        )
        ok = False
    cited = ((manifest["evidence"].get(ITEM6_KEY) or {}).get("not_applicable")) or {}
    for part, rel in (("spec", ITEM6_SPEC), ("statement", ITEM6_STATEMENT)):
        if (cited.get(part) or {}).get("file") != rel:
            fail(f"signoff/block-manifest.json: {ITEM6_KEY} must cite {rel} as {part}")
            ok = False
    if ok:
        print(f"ok   {ITEM6_SPEC}: bound to {source['file']}; statement covers {len(spec_ids)} rows")
    return ok


def refresh_item6() -> None:
    """--regen: re-pin the item-6 citation to the current rows file and statement.

    The spec-markdown hash inside the rows file is deliberately NOT refreshed:
    re-pinning it is the human act of re-reading the spec and re-accounting
    for its rows, not a derivation.
    """
    manifest = json.loads(MANIFEST.read_text())
    entry = (manifest["evidence"].get(ITEM6_KEY) or {}).get("not_applicable")
    if not isinstance(entry, dict):
        return
    for part, rel in (("spec", ITEM6_SPEC), ("statement", ITEM6_STATEMENT)):
        entry[part] = {"file": rel, "content_hash": sha256_file(REPO_ROOT / rel)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--regen",
        action="store_true",
        help=(
            "rewrite signoff/signoff-report.json from the current tree instead "
            "of comparing against it"
        ),
    )
    args = parser.parse_args(argv)

    if shutil.which("klt") is None:
        fail(
            "klt is not on PATH. Install the pinned grader:\n"
            f"       pip install klayout-tools=={GRADER_PACKAGE_VERSION}\n"
            "     (see signoff/toolchain.json for why this pin is what CI "
            "also installs)"
        )
        return 1

    ok = check_toolchain_pin()
    manifest = load_manifest()

    if args.regen and manifest is not None:
        refreshed = refresh_item8_source_hash()
        if refreshed is None:
            return 1
        refresh_anchored()
        refresh_item6()
        manifest = load_manifest()
        if manifest is None:
            return 1

    if manifest is None:
        return 1

    ok = check_generic_envelopes(manifest) and ok
    ok = check_inventory_members() and ok
    ok = check_item9_complete() and ok
    ok = check_anchored_envelopes(manifest) and ok
    ok = check_item6_binding(manifest) and ok
    ok = check_attested(manifest) and ok

    stdout, report, ran = run_grader()
    if not ran:
        return 1

    if args.regen:
        REPORT.write_text(stdout)
        print(f"wrote {REPORT.relative_to(REPO_ROOT)}")
        print(
            f"     tier={report.get('tier')} "
            f"met={report.get('t1_met_count')}/{report.get('t1_item_count')} "
            f"(source_doc={report.get('source_doc')})"
        )
        return 0 if ok else 1

    ok = check_no_stale(report) and ok
    ok = check_drift(report) and ok

    print(
        f"     tier={report.get('tier')} "
        f"met={report.get('t1_met_count')}/{report.get('t1_item_count')} "
        f"(source_doc={report.get('source_doc')})"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
