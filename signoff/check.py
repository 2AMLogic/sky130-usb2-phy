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

This script is what stops that. Five distinct checks, because `klt signoff`
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
3. **The vendored tiers doc is present and row-counted.** T1 item 11
   ("Power delivery (structural)", klayout-tools#2025) exists in no released
   `klt` bundle yet: the pinned 0.5.0 wheel's bundled checklist stops at item
   10. `signoff/design-evidence-tiers.md` is the vendored upstream copy the
   grader is pointed at via `--tiers-doc` so every item -- item 11 included --
   gets its row. Grading without it would silently render a 20-row report
   instead of the 22 mixed-signal rows `signoff/README.md` describes.
4. **The grader itself runs clean.** Exit 0 (`tier: "T1"`) or 3 (`tier: null`,
   at least one item unmet) are both fine -- an all-`unmet` report is a
   correct result. Exit 1/2 mean the manifest or the tiers doc is malformed,
   which is a real failure.
5. **The committed report still matches the rendered one.** Compared on a
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
TIERS_DOC = SIGNOFF_DIR / "design-evidence-tiers.md"
EVIDENCE_DIR = SIGNOFF_DIR / "evidence"

# The single artifact the item-8 generic envelope wraps today. Keep in one
# place: --regen re-derives both pins (the envelope's and the manifest's)
# from this file's current hash, exactly like gf180-sram's regenerate.sh.
CHARACTERIZATION_SOURCE = "docs/characterization.md"
CHARACTERIZATION_ENVELOPE = "signoff/evidence/characterization-report.json"

# `klt signoff --manifest` exit codes that mean "the grader ran": 0 is
# tier T1, 3 is "ran fine, at least one item unmet". Anything else is a
# malformed manifest / unparsable tiers doc / usage error.
RAN_CLEAN = (0, 3)

# The grading build identity, asserted two ways (see check 1 above). Keep in
# sync with signoff/toolchain.json and the `signoff` CI job's pip pin.
GRADER_PACKAGE_VERSION = "0.5.0"
GRADER_GIT_TAG = "v0.5.0"


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


def check_tiers_doc() -> bool:
    """The vendored checklist must be present and carry item 11."""
    if not TIERS_DOC.is_file():
        fail(
            f"{TIERS_DOC.relative_to(REPO_ROOT)} is missing. The pinned "
            f"klt {GRADER_PACKAGE_VERSION} bundle's checklist stops at item "
            "10; the vendored upstream copy is what makes item 11 render a "
            "row (klayout-tools#2025). Re-copy it from klayout-tools main "
            "and record its provenance in signoff/README.md"
        )
        return False
    text = TIERS_DOC.read_text()
    for needle in ("11. **Power delivery (structural)**",):
        if needle not in text:
            fail(
                f"{TIERS_DOC.relative_to(REPO_ROOT)} does not contain "
                f"{needle!r} -- a stale vendored copy would silently drop "
                "item 11's rows from the report"
            )
            return False
    print(
        f"ok   {TIERS_DOC.relative_to(REPO_ROOT)} vendored copy carries the "
        "11-item checklist"
    )
    return True


def run_grader() -> tuple[str, dict, bool]:
    argv = [
        "klt",
        "signoff",
        "--manifest",
        str(MANIFEST.relative_to(REPO_ROOT)),
        "--tiers-doc",
        str(TIERS_DOC.relative_to(REPO_ROOT)),
        "--format",
        "json",
    ]
    proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode not in RAN_CLEAN:
        fail(
            f"klt signoff --manifest exited {proc.returncode} (expected 0 or 3). "
            "The manifest or the tiers doc is malformed:"
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
        manifest = load_manifest()
        if manifest is None:
            return 1

    if manifest is None:
        return 1

    ok = check_generic_envelopes(manifest) and ok
    ok = check_tiers_doc() and ok

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
