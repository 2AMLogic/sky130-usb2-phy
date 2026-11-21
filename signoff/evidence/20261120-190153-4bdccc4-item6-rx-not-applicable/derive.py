#!/usr/bin/env python3
"""Derive the item-6 receiver sample sets with not_applicable negative controls.

Issue #402 (branch (b) of its "What to do"): the October 2026 receiver
mismatch campaigns seed a deterministic negative control that, on ten
measurement instances, cannot degrade the measurement by construction. The
grader (klt 0.9.1) refuses those reports (`negative_control_not_detected`),
and klayout-tools#4523 gave `klt yield` the per-measurement declaration that
says so. This script re-derives the six committed sample sets with exactly
that declaration on the affected measurements, changing nothing else: every
nominal array, every derivation hash and every detected control is carried
over byte-for-byte (the originals round-trip through json.dumps(indent=2)).

The October campaign directories and records are append-only and are not
touched. Run from this directory; it writes the six derived
<stem>.samples.json files next to itself.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

SOURCES = {
    "diff-tt": "sim/diff-receiver-mismatch/campaigns/20261020-202512-a78d2ac",
    "diff-binding": "sim/diff-receiver-mismatch/campaigns/20261020-202512-a78d2ac",
    "dp-tt": "sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac",
    "dp-binding": "sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac",
    "dm-tt": "sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac",
    "dm-binding": "sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac",
}

# Measurements whose seeded control cannot degrade them by construction, with
# the physical reason a reviewer can check against the testbench record
# (both reasons are quoted from the campaign records' Method sections).
NOT_APPLICABLE = {
    "rxd_p200_cm0p80_v": (
        "one-sided defect: the control's fixed +0.25 V differential input "
        "offset (skew_v) adds to the +200 mV stimulus and only raises RXD at "
        "VDIFF = +200 mV, so it cannot degrade this measurement "
        "(sim/diff-receiver-mismatch/testbench/mc.json; record "
        "sim/diff-receiver-mismatch/records/20261020-202512-a78d2ac.md)"
    ),
    "rxd_p200_cm1p65_v": None,  # same reason, filled from the first entry
    "rxd_p200_cm2p50_v": None,
    "rxd_low_max_v": (
        "one-sided defect: the control's divider skew (R2 length 14 -> 60) "
        "raises VREF past VIH, which only keeps RXD low over the 0-0.8 V "
        "sweep, so it cannot degrade this measurement "
        "(sim/se-receiver-mismatch/testbench/mc.json; record "
        "sim/se-receiver-mismatch/records/20261020-202608-a78d2ac.md)"
    ),
}
_P200 = NOT_APPLICABLE["rxd_p200_cm0p80_v"]
for _k in ("rxd_p200_cm1p65_v", "rxd_p200_cm2p50_v"):
    NOT_APPLICABLE[_k] = _P200


def main() -> None:
    here = Path(__file__).resolve().parent
    for stem, campaign in SOURCES.items():
        src = REPO_ROOT / campaign / f"{stem}.samples.json"
        doc = json.loads(src.read_text())
        replaced = []
        for m in doc["measurements"]:
            reason = NOT_APPLICABLE.get(m["name"])
            if reason is None:
                continue
            if "samples" not in m.get("negative_control", {}):
                raise SystemExit(f"{src}: {m['name']} carries no control samples")
            m["negative_control"] = {"not_applicable": True, "reason": reason}
            replaced.append(m["name"])
        out = here / f"{stem}.samples.json"
        out.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"{stem}: declared not_applicable on {replaced}")


if __name__ == "__main__":
    main()
