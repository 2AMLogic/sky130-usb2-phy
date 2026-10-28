#!/usr/bin/env python3
"""Freshness check for design/netlist/<cell>.spice (exit 0 current, 3 stale).

    python3 design/check_netlist.py differential_receiver

Re-exports design/<cell>.sch through `klt netlist --block` (headless, bounded,
never raw xschem) and compares it to the committed netlist. Both sides are
reduced to what design/export_netlist.sh does not change: its two comment
header lines and the `** sch_path:` line are dropped, and `+` continuation
lines are joined, because xschem wraps device lines differently from the
committed files. Every device, node and parameter must otherwise match.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pdk_rcfile() -> str:
    pin = json.loads((HERE.parent / "sim" / "corners.json").read_text())["pdk"]["open_pdks_commit"]
    roots = [os.environ.get("PDK_ROOT", ""), str(Path.home() / ".ciel"), "/usr/share/pdk", "/usr/local/share/pdk", "/opt/pdk"]
    for root in filter(None, roots):
        rc = Path(root) / "sky130A" / "libs.tech" / "xschem" / "xschemrc"
        if rc.is_file():
            sources = Path(root) / "sky130A" / "SOURCES"
            got = next((ln.split()[1] for ln in sources.read_text().splitlines() if ln.startswith("open_pdks ")), "unknown") if sources.is_file() else "unknown"
            if got != pin:
                sys.exit(f"check_netlist: {root} is open_pdks {got}, but sim/corners.json pins {pin}")
            return str(rc)
    sys.exit("check_netlist: sky130A not found (set PDK_ROOT or install it under ~/.ciel)")


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
             "--rcfile", pdk_rcfile(), "--pdk", "sky130A"],
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
