#!/usr/bin/env python3
"""Run the physical checks for layout/analog/differential_driver (issue #220).

    python3 layout/analog/differential_driver/run_checks.py            # run, write reports
    python3 layout/analog/differential_driver/run_checks.py --record   # also mint the record

The five steps, the reports and the record are produced by the shared runner
layout/analog/run_checks_common.py; this file holds only what is specific to this leaf:
step 4 (LVS) runs against lvs-reference.spice, which is
design/netlist/differential_driver.spice with only the MIM cap lines rewritten for the
runset's reader (see derive_lvs_reference).
Reports and records stay in this leaf and flow/analog-layout-differential_driver/.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from run_checks_common import REPO_ROOT, LeafConfig, main, sha256_file  # noqa: E402

BLOCK = "differential_driver"
REL = HERE.relative_to(REPO_ROOT).as_posix()
NETLIST = f"design/netlist/{BLOCK}.spice"
GENERATOR = f"{REL}/gen.py"
LVS_REFERENCE = f"{REL}/lvs-reference.spice"

# The xschem export names the MIM cap `sky130_fd_pr__cap_mim_m3_1` with W/L in micrometres.
# `sky130.lvs` extracts the layout MIM as `sky130_fd_pr__model__cap_mim` (A and P parameters,
# C disabled in its MIMCap class) and only converts `X` calls whose model is in its own
# DEVICE_LIST, which lacks the xschem name, so the reference reader silently drops the four
# caps (klayout-tools#4519 made that loud; pairing them is the part left to the caller).
# The derived reference below rewrites exactly those lines, and nothing else, into the form
# the runset's reader pairs: a two-terminal `C` element of the extracted model with A = W*L
# and P = 2*(W+L) in micrometre units (the reader applies the same 1e12 / 1e6 scale it
# applies to the layout side under `scale=true`). design/ is never edited.
MIM_SCHEMATIC_MODEL = "sky130_fd_pr__cap_mim_m3_1"
MIM_EXTRACTED_MODEL = "sky130_fd_pr__model__cap_mim"
MIM_FF_PER_UM2 = 2.0  # the runset's own extraction constant (capacitor(..., 2e-15, MIMCap))


def derive_lvs_reference() -> str:
    """The reference netlist with only the MIM cap lines rewritten for sky130.lvs's reader."""
    src_path = REPO_ROOT / NETLIST
    out: list[str] = []
    caps = 0
    for line in src_path.read_text(encoding="utf-8").splitlines():
        if MIM_SCHEMATIC_MODEL not in line.split():
            out.append(line)
            continue
        tok = line.split()
        if len(tok) < 4 or not tok[0].startswith("XC") or tok[3] != MIM_SCHEMATIC_MODEL:
            raise SystemExit(f"unrecognised MIM cap line in {NETLIST}: {line!r}")
        params = dict(t.split("=", 1) for t in tok[4:])
        if float(params.get("m", "1")) != 1 or float(params.get("MF", "1")) != 1:
            raise SystemExit(f"MIM cap with a multiplier cannot be folded into A/P: {line!r}")
        w, l = float(params["W"]), float(params["L"])
        out.append(
            f"{tok[0][1:]} {tok[1]} {tok[2]} {MIM_EXTRACTED_MODEL} "
            f"C={w * l * MIM_FF_PER_UM2 * 1e-3:.4g} A={w * l:.6g} P={2 * (w + l):.6g}"
        )
        caps += 1
    if caps == 0 or MIM_SCHEMATIC_MODEL in "\n".join(out):
        raise SystemExit(f"{NETLIST}: expected MIM cap lines to rewrite, rewrote {caps}")
    header = (
        f"* Derived by {GENERATOR.rsplit('/', 1)[0]}/run_checks.py from {NETLIST} ({sha256_file(src_path)}).\n"
        f"* Only the {caps} {MIM_SCHEMATIC_MODEL} lines differ: rewritten to {MIM_EXTRACTED_MODEL} with A/P\n"
        "* (um units) so sky130.lvs's reference reader keeps them. Do not edit by hand.\n"
    )
    return header + "\n".join(out) + "\n"

CONFIG = LeafConfig(
    here=HERE,
    block=BLOCK,
    issue=220,
    supply_nets=("VDD", "VSS"),
    claim_subject="the differential_driver leaf's",
    bulk_note_tail=(
        " -- the runset's MOS4 and resistor-with-bulk "
        "device classes carry B / W -- so the matched devices include their bulk nets."
    ),
    doc=__doc__,
    inputs_after_netlist=[LVS_REFERENCE],
    extra_tool_gaps=["https://github.com/2AMLogic/klayout-tools/issues/4519"],
    lvs_reference=LVS_REFERENCE,
    derive_lvs_reference=derive_lvs_reference,
)


if __name__ == "__main__":
    sys.exit(main(CONFIG))
