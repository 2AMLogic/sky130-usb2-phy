#!/usr/bin/env python3
"""Generate layout/analog/dplus_pullup/dplus_pullup.gds.

Layout for the `dplus_pullup` leaf of the analog partition, drawn
from base layers with `klayout.db` and nothing else. Every device is
re-derived for sky130 from `design/netlist/dplus_pullup.spice`
(issue #222); no gf180 geometry is consumed. The conventions it implements
(rails, guard rings, pin labels, routing layers) are written down in
`layout/analog/README.md`; the rule numbers it draws to are sky130's.

    python3 layout/analog/dplus_pullup/gen.py            # write GDS
    python3 layout/analog/dplus_pullup/gen.py --check    # no write,
        # exit 1 if the regenerated stream differs from the committed one

The stream is byte-reproducible: no timestamps are written and every shape is
emitted in a fixed order, so `--check` compares sha256 of the whole file.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_common import (  # noqa: E402
    L,
    LIC_PITCH,
    STRIP_W,
    TRUNK_PITCH,
    Canvas,
    Ports,
    find_row_x,
    mos,
    res_generic_po,
    route_nets,
    run_gds,
    tap_ring,
)

HERE = Path(__file__).resolve().parent
GDS = HERE / "dplus_pullup.gds"
TOP = "dplus_pullup"


# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
RES_W = 2.0  # sky130_fd_pr__res_generic_po body width (netlist W)
RES_HEAD = 0.8  # poly head past each end of the body, holds the contact column
RES_GAP = 1.2  # poly space between neighbouring resistors
FINGER_MAX = 10.0  # widest single finger, um

# Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
# every labelled net into a circuit pin, so labelling internal nets would give
# the layout more pins than the schematic's eight.
PIN_NETS = {"DP", "VPU", "VSS", "PU_EN", "TRIM0", "TRIM1", "TRIM2", "TRIM3"}


def build() -> Canvas:
    cv = Canvas(TOP, L)
    ports = Ports()

    # Trunk order, bottom to top. The resistor-chain nets sit lowest so the
    # met2 drops of the NMOS-side resistor heads never share a y-range with a
    # PMOS-side drop of another net.
    nets_order = ["N0", "N1", "N2", "N3", "N4", "DP",
                  "PU_ENB", "TRIM0B", "TRIM1B", "TRIM2B", "TRIM3B",
                  "PU_EN", "TRIM0", "TRIM1", "TRIM2", "TRIM3"]

    # ---------------------------------------------------------------- floorplan
    # y bands (um). NMOS row and resistors at the bottom, channel in the middle,
    # PMOS above. Every NMOS/resistor is 2 um tall, every PMOS up to 10 um.
    N_RING_Y0 = 0.0
    N_DIFF_Y = N_RING_Y0 + STRIP_W + 0.8
    N_WMAX = 2.0
    N_RING_Y1 = N_DIFF_Y + N_WMAX + 0.6 + 1.2 + STRIP_W
    CH_Y0 = N_RING_Y1 + 0.5
    CH_Y1 = CH_Y0 + len(nets_order) * TRUNK_PITCH + 0.5
    NW_Y0 = CH_Y1 + 0.5
    P_RING_Y0 = NW_Y0 + 0.5
    P_WMAX = 10.0
    P_DIFF_TOP = P_RING_Y0 + STRIP_W + 1.2 + 0.6 + P_WMAX
    P_RAIL_Y = P_DIFF_TOP + 0.8
    P_RING_Y1 = P_RAIL_Y + STRIP_W
    NW_Y1 = P_RING_Y1 + 0.5
    p_diff_y = P_DIFF_TOP - P_WMAX
    ty_of = {n: CH_Y0 + 0.6 + i * TRUNK_PITCH for i, n in enumerate(nets_order)}

    # ---------------------------------------------------------------- NMOS row
    rail_top_n = N_RING_Y0 + STRIP_W  # top edge of the VSS rail (ring bottom strip)
    gap = 0.8
    x = 0.8 + STRIP_W
    # Enable inverter and the four trim inverters: W2 nf1, G = pin, D = *B, S = VSS.
    for gate, drain in (("PU_EN", "PU_ENB"), ("TRIM0", "TRIM0B"), ("TRIM1", "TRIM1B"),
                        ("TRIM2", "TRIM2B"), ("TRIM3", "TRIM3B")):
        x = mos(cv, ports, "n", x, N_DIFF_Y, 2.0, ["VSS", drain], [gate], "VSS", rail_top_n) + gap

    # ---------------------------------------------------------------- resistors
    # The chain N0 - RBASE - N1 - R0 - N2 - R1 - N3 - R2 - N4 - R3 - DP, left to right.
    rx = x + 0.7
    for length, left, right in ((40.3, "N0", "N1"), (2.4, "N1", "N2"), (4.8, "N2", "N3"),
                                (9.6, "N3", "N4"), (19.2, "N4", "DP")):
        head_ys = [RES_W / 2 + (k - 1.5) * LIC_PITCH for k in range(4)]
        rx = res_generic_po(cv, ports, rx + RES_HEAD, N_DIFF_Y, RES_W, length, (left, right),
                            head_ys, 0.175, RES_W / 2, "n") + RES_GAP
    ring_x1 = rx - RES_GAP + 0.8
    tap_ring(cv, "n", 0.0, N_RING_Y0, ring_x1, N_RING_Y1, ("b",))

    # ---------------------------------------------------------------- PMOS row
    def place_small(c: Canvas, pts: Ports, start: float) -> float:
        px = start
        for gate, drain in (("PU_EN", "PU_ENB"), ("TRIM0", "TRIM0B"), ("TRIM1", "TRIM1B"),
                            ("TRIM2", "TRIM2B"), ("TRIM3", "TRIM3B")):
            px = mos(c, pts, "p", px, p_diff_y, 4.0, ["VPU", drain], [gate], "VPU", P_RAIL_Y) + gap
        return px - gap

    # Shift the small PMOS row until none of its met2 drops comes within met2
    # space of an NMOS/resistor drop that shares a channel y-range.
    start = find_row_x(place_small, ports, ty_of, 0.8 + STRIP_W + 0.9)
    print(f"small PMOS row placed at x={start:.3f}", file=sys.stderr)
    nw_x0 = start - 0.9 - STRIP_W
    place_small(cv, ports, start)

    # The switch devices sit clear of every NMOS/resistor drop, so they need no search.
    def switch(px: float, nf: int, s_net: str, d_net: str, gate: str) -> float:
        cols = [s_net if i % 2 == 0 else d_net for i in range(nf + 1)]
        return mos(cv, ports, "p", px, p_diff_y, FINGER_MAX, cols, [gate] * nf, "VPU", P_RAIL_Y) + gap

    px = ring_x1 + 1.5
    px = switch(px, 100, "VPU", "N0", "PU_ENB")  # XMP_ENSW  W100 m10
    px = switch(px, 80, "N2", "N1", "TRIM0B")  # XMP_B0  W100 m8
    px = switch(px, 40, "N3", "N2", "TRIM1B")  # XMP_B1  W100 m4
    px = switch(px, 20, "N4", "N3", "TRIM2B")  # XMP_B2  W100 m2
    p_x1 = switch(px, 10, "DP", "N4", "TRIM3B") - gap  # XMP_B3  W100 m1

    nw_x1 = p_x1 + 0.9 + STRIP_W + 0.5
    tap_ring(cv, "p", nw_x0, P_RING_Y0, nw_x1 - 0.5, P_RING_Y1, ("t",))
    cv.rect("nwell", nw_x0 - 0.5, NW_Y0, nw_x1, NW_Y1)
    cv.rect("hvi", -0.4, N_RING_Y0 - 0.4, max(ring_x1, nw_x1) + 0.4, NW_Y1 + 0.4)

    # ---------------------------------------------------------------- routing
    route_nets(cv, ports, ty_of, ("VSS", "VPU"), PIN_NETS)
    # supply pins and labels
    cv.label("met1_label", "VSS", 1.0, N_RING_Y0 + STRIP_W / 2)
    cv.label("met1_label", "VPU", nw_x0 + 1.0, P_RAIL_Y + STRIP_W / 2)
    return cv


if __name__ == "__main__":
    sys.exit(run_gds(GDS, build, __doc__.splitlines()[0]))
