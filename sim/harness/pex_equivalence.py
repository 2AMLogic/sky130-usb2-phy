"""Exact-pair schematic-leg equivalence gate for the klt pex leaf runners.

Shared by sim/se-receiver-dp-pex, sim/se-receiver-dm-pex and sim/dplus-pullup-pex
(`run.py`); sim/diff-receiver-pex predates it and keeps its inline gate. The lesson
that shaped this helper: the committed schematic reference report covers far more
corners than a two-corner `klt pex` bench requests (225 versus 2 here), so a delta
with the right *number* of rows and the reference value in each is not evidence the
requested bench ran -- rows lifted from unrequested corners would pass a count-only
check. The expected (corner id, raw measurement name) pairs are therefore derived
from the pex bench's own requested units, and the schematic leg is equivalent only
when the envelope's delta carries every expected pair exactly once, nothing extra,
finite values throughout, and each schematic_value equal to the committed record's
value at relative deviation <= 1e-6. Toolchain-free: pure functions over committed
JSON, nothing written, no klt.
"""

from __future__ import annotations

import math

REL_TOL = 1e-6


def unit_corner_id(unit: dict) -> str:
    """The klt corner id of one request unit, e.g. ``ff_lh/3.000V/100C``.

    Same spelling the committed sim reports use: ``<process>/<supply:.3f>V/<temp:g>C``.
    """
    supply = unit.get("supply_v") or {}
    if len(supply) != 1:
        raise ValueError(f"expected exactly one supply in unit {unit!r}, got {sorted(supply)}")
    volt = float(next(iter(supply.values())))
    return f"{unit['process']}/{volt:.3f}V/{float(unit['temperature_c']):g}C"


def expected_pairs(tb: dict) -> list[tuple[str, str]]:
    """Every (corner id, measurement name) the requested bench must report:
    corners x measurements of the pex request's own tb.json, nothing broader."""
    units = (tb.get("corners") or {}).get("units") or []
    names = [m["name"] for m in tb.get("measurements") or []]
    if not units or not names:
        raise ValueError("tb.json declares no corner units or no measurements")
    return [(unit_corner_id(u), n) for u in units for n in names]


def committed_values(reference_report: dict) -> dict[tuple[str, str], float]:
    """(corner id, measurement name) -> value, from the committed schematic record's
    raw report (raw report units; no bench display scaling applied here or anywhere
    in this gate)."""
    out: dict[tuple[str, str], float] = {}
    for corner in reference_report.get("corners") or []:
        for m in corner.get("measurements") or []:
            out[(corner["corner_id"], m["name"])] = m.get("value")
    return out


def check_equivalence(envelope: dict, tb: dict, reference_report: dict,
                      rel_tol: float = REL_TOL) -> tuple[bool, list[dict]]:
    """Grade a klt pex envelope's schematic leg against the committed record.

    Equivalent (True) only when: the envelope status is ``pass``; the delta's
    (corner_id, spec_row) set is exactly the requested bench's expected pairs, each
    appearing exactly once (missing, duplicate and unexpected rows all fail); every
    schematic_value is a finite number; and each is within rel_tol (relative) of the
    committed value for the same pair. Returns (ok, rows) where rows describe every
    failure and one row per expected pair otherwise (verdict ``ok`` with the
    relative deviation recorded).
    """
    expected = expected_pairs(tb)
    committed = committed_values(reference_report)
    rows: list[dict] = []
    ok = True

    def fail(cid, name, verdict, want=None, got=None):
        nonlocal ok
        ok = False
        rows.append({"corner_id": cid, "measurement": name, "committed": want,
                     "schematic": got, "verdict": verdict})

    if envelope.get("status") != "pass":
        fail("-", "(envelope)", f"envelope status {envelope.get('status')!r} != 'pass'")

    seen: dict[tuple[str, str], dict] = {}
    for row in envelope.get("delta") or []:
        key = (row.get("corner_id"), row.get("spec_row"))
        if key in seen:
            fail(key[0], key[1], "duplicate delta row", committed.get(key),
                 row.get("schematic_value"))
            continue
        seen[key] = row
    for key in sorted(set(seen) - set(expected), key=lambda k: (k[0] or "", k[1] or "")):
        fail(key[0], key[1], "delta row is not a requested (corner, measurement) pair of "
             "testbench/tb.json", committed.get(key), seen[key].get("schematic_value"))

    for key in expected:
        row = seen.get(key)
        want = committed.get(key)
        got = (row or {}).get("schematic_value")
        if want is None or not isinstance(want, (int, float)) or not math.isfinite(want):
            fail(key[0], key[1], "no finite committed value in the reference record", want, got)
            continue
        if row is None:
            fail(key[0], key[1], "missing delta row (requested pair absent from the envelope)",
                 want, None)
            continue
        if not isinstance(got, (int, float)) or not math.isfinite(got):
            fail(key[0], key[1], f"schematic value missing or non-finite ({got!r})", want, got)
            continue
        dev = abs(got - want) / max(abs(want), 1e-300)
        if dev <= rel_tol:
            rows.append({"corner_id": key[0], "measurement": key[1], "committed": want,
                         "schematic": got, "rel_dev": dev, "verdict": "ok"})
        else:
            fail(key[0], key[1], "MISMATCH", want, got)
            rows[-1]["rel_dev"] = dev
    return ok, rows
