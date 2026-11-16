#!/usr/bin/env python3
"""Freshness check for design/netlist/<cell>.spice (exit 0 current, 3 stale).

    python3 design/check_netlist.py differential_receiver

Re-exports design/<cell>.sch through `klt netlist --block` (headless, bounded,
never raw xschem) and compares it to the committed netlist. Both sides are
reduced to what design/export_netlist.sh does not change: its two comment
header lines and the `** sch_path:` line are dropped, and `+` continuation
lines are joined, because xschem wraps device lines differently from the
committed files. Every device, node and parameter must otherwise match.

Both klt netlist call sites (here and design/export_netlist.sh) pass
`--no-provenance-header`: the committed netlists predate klt's
`** klt-netlist-inputs:` provenance line and their content hashes are pinned
in signoff/evidence/item-1-analog-sources.json, so neither the checker nor
the exporter may let klt write that line. The flag needs klayout-tools
newer than 0.8.0 (which signoff/toolchain.json pins for grading and which
predates the flag).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE.parent / "sim" / "harness"))
import pdk_pin  # noqa: E402  (path set above on purpose; the shared pinned-PDK search, #304)


def pdk_rcfile() -> str:
    """The pinned sky130A xschemrc; exits nonzero if no tree or a tree off the pin is found (shared search: sim/harness/pdk_pin.py)."""
    try:
        rc = pdk_pin.resolve_pinned_tree("sky130A", pdk_pin.xschem_rcfile)[0]
    except pdk_pin.PdkPinError as exc:
        sys.exit(f"check_netlist: {exc}")
    return str(rc)


def normalize(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("+") and lines:
            lines[-1] += " " + line[1:]
        else:
            lines.append(line)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in lines]
    return [ln for ln in lines if not ln.startswith(("* ", "** sch_path:"))]


def main() -> int:
    cell = sys.argv[1]
    committed = (HERE / "netlist" / f"{cell}.spice").read_text()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"{cell}.spice"
        subprocess.run(
            ["klt", "netlist", str(HERE / f"{cell}.sch"), "-o", str(out), "--block",
             "--no-provenance-header", "--rcfile", pdk_rcfile(), "--pdk", "sky130A"],
            check=True, capture_output=True,
        )
        fresh = out.read_text()
    if normalize(committed) != normalize(fresh):
        print(f"STALE design/netlist/{cell}.spice: differs from design/{cell}.sch", file=sys.stderr)
        return 3
    print(f"ok design/netlist/{cell}.spice matches design/{cell}.sch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
