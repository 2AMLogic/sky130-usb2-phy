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

Issue #414 restructure: the first post-layout extraction (#403) measured
1.6-2.1 kohm of parasitic series resistance on every ladder node -- the
resistor heads sat in their own row 20 um from the switches and every switch
S/D column carried a full-height li1 strap (12.8 ohm/sq), so the extraction's
per-net star assigned each head a kilo-ohm-class stub and no trim code could
reach the ratified 1.5 kohm +/-5 % window. This layout keeps the netlist and
the trunk router but moves the ladder into a vertical poly spine that passes
through the middle of one switch-row gap (every ladder net's terminals then
cluster around the spine, collapsing the star weights), interleaves the five
switches into ten identical finger groups so every ladder net's device cloud
spans the whole row (the weight dilution the small bypass switches could
never provide alone), and contacts each switch column with two pad-side
licon rows under a square li1 pad instead of a full-height strap.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_common import (  # noqa: E402
    L,
    LIC,
    LIC_PITCH,
    STRIP_W,
    TRUNK_PITCH,
    Canvas,
    Ports,
    find_row_x,
    mos,
    route_nets,
    run_gds,
    tap_ring,
)

HERE = Path(__file__).resolve().parent
GDS = HERE / "dplus_pullup.gds"
TOP = "dplus_pullup"


# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
RES_W = 2.0  # sky130_fd_pr__res_generic_po body width (netlist W)
RES_HEAD = 1.2  # poly head past each end of the body, holds the contact array
SW_GROUPS = 10  # interleaved finger groups across the switch row
SUB_GAP = 0.8  # poly space between neighbouring sub-blocks in a group
SPINE_GAP = 2.5  # poly space between neighbouring resistor bars in the spine
CONTACT_ROWS = 2  # licon rows per non-rail switch column, at the pad end
LI1_HW = 0.345  # switch-column li1 half-width: ~square pad over 2 licon rows

# Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
# every labelled net into a circuit pin, so labelling internal nets would give
# the layout more pins than the schematic's eight.
PIN_NETS = {"DP", "VPU", "VSS", "PU_EN", "TRIM0", "TRIM1", "TRIM2", "TRIM3"}

# One switch sub-block per group: (wf, nf, source net, drain net, gate). The
# ten groups multiply out to the netlist's W100 m{10,8,4,2,1} devices.
SW_BLOCK = (
    (10.0, 10, "VPU", "N0", "PU_ENB"),  # XMP_ENSW
    (10.0, 8, "N2", "N1", "TRIM0B"),  # XMP_B0
    (10.0, 4, "N3", "N2", "TRIM1B"),  # XMP_B1
    (5.0, 4, "N4", "N3", "TRIM2B"),  # XMP_B2
    (5.0, 2, "DP", "N4", "TRIM3B"),  # XMP_B3
)

# The ladder: (marker length, lower net, upper net). RBASE and R3 fold into
# U shapes so their bodies clear the top supply rail; both folded heads sit at
# the bottom of the spine.
LADDER = (
    ("RBASE", 40.3, "N0", "N1", True),
    ("R3", 19.2, "N4", "DP", True),
    ("R2", 9.6, "N3", "N4", False),
    ("R1", 4.8, "N2", "N3", False),
    ("R0", 2.4, "N1", "N2", False),
)


def res_head(cv: Canvas, ports: Ports, xh: float, yh: float, net: str,
             port_dx: float = 0.0) -> None:
    """One contacted head: a 3x3 licon/mcon array under a square-ish li1/met1
    pad, on the 1.2 um poly head at (`xh`, `yh`) = the head's centre. The
    router drop lands at `port_dx` off the centre, so the two heads of one
    bar -- which share an x -- keep their met2 verticals apart."""
    for dx in (-LIC_PITCH, 0.0, LIC_PITCH):
        for dy in (-LIC_PITCH, 0.0, LIC_PITCH):
            cv.centred("licon", xh + dx, yh + dy, LIC, LIC)
            cv.centred("mcon", xh + dx, yh + dy, LIC, LIC)
    cv.rect("npc", xh - 0.545, yh - 0.545, xh + 0.545, yh + 0.545)
    cv.rect("li1", xh - 0.545, yh - 0.61, xh + 0.545, yh + 0.61)
    cv.rect("met1", xh - 0.595, yh - 0.66, xh + 0.595, yh + 0.66)
    ports.add(net, xh + port_dx, yh)


def res_bar_v(cv: Canvas, ports: Ports, x: float, y0: float, length: float,
              bot: str, top: str) -> None:
    """Straight vertical res_generic_po body: `length` (y) by RES_W (x) under
    the marker, one head past each end."""
    cv.rect("poly", x, y0 - RES_HEAD, x + RES_W, y0 + length + RES_HEAD)
    cv.rect("poly_res", x, y0, x + RES_W, y0 + length)
    res_head(cv, ports, x + RES_W / 2, y0 - RES_HEAD / 2, bot, -0.3)
    res_head(cv, ports, x + RES_W / 2, y0 + length + RES_HEAD / 2, top, +0.3)


def res_u_v(cv: Canvas, ports: Ports, x: float, y0: float, length: float,
            net_a: str, net_b: str) -> float:
    """Folded (U) vertical res_generic_po body: two legs joined by a link at
    the top, both heads at the bottom. The marker union's area is exactly
    `length` * RES_W (the extractor derives l = area / w), so the legs are
    (length - gap) / 2 tall. Returns the spine x just past the U."""
    gap = 0.5
    leg_h = (length - gap) / 2
    x2 = x + RES_W + gap
    for xl in (x, x2):
        cv.rect("poly", xl, y0 - RES_HEAD, xl + RES_W, y0 + leg_h)
        cv.rect("poly_res", xl, y0, xl + RES_W, y0 + leg_h)
    cv.rect("poly", x, y0 + leg_h - RES_W, x2 + RES_W, y0 + leg_h)
    cv.rect("poly_res", x, y0 + leg_h - RES_W, x2 + RES_W, y0 + leg_h)
    res_head(cv, ports, x + RES_W / 2, y0 - RES_HEAD / 2, net_a)
    res_head(cv, ports, x2 + RES_W / 2, y0 - RES_HEAD / 2, net_b)
    return x2 + RES_W


def ring_side(cv: Canvas, kind: str, x0: float, y0: float, x1: float,
              y1: float, rail: bool) -> None:
    """One tap/li1 guard-ring strip (the `tap_ring` recipe for a single run);
    `rail` adds the mcon column and the met1 supply rail on top of it."""
    dop = "psdm" if kind == "n" else "nsdm"
    cv.rect("tap", x0, y0, x1, y1)
    cv.rect(dop, x0 - 0.125, y0 - 0.125, x1 + 0.125, y1 + 0.125)
    cv.rect("li1", x0, y0, x1, y1)
    horiz = x1 - x0 >= y1 - y0
    lo, hi = ((x0, x1) if horiz else (y0 + STRIP_W + 0.1, y1 - STRIP_W - 0.1))
    n = int((hi - lo - 2 * 0.1) / (2 * LIC_PITCH))
    for i in range(n + 1):
        p = lo + 0.1 + LIC / 2 + i * 2 * LIC_PITCH
        if p + LIC / 2 > hi - 0.1:
            break
        cx, cy = (p, (y0 + y1) / 2) if horiz else ((x0 + x1) / 2, p)
        cv.centred("licon", cx, cy, LIC, LIC)
        if rail:
            cv.centred("mcon", cx, cy, LIC, LIC)
    if rail:
        cv.rect("met1", x0, y0, x1, y1)


def build() -> Canvas:
    cv = Canvas(TOP, L)
    ports = Ports()

    # Trunk order, bottom to top. The resistor-chain nets sit lowest so their
    # spine drops are the shortest.
    nets_order = ["N0", "N1", "N2", "N3", "N4", "DP",
                  "PU_ENB", "TRIM0B", "TRIM1B", "TRIM2B", "TRIM3B",
                  "PU_EN", "TRIM0", "TRIM1", "TRIM2", "TRIM3"]

    # ---------------------------------------------------------------- floorplan
    # y bands (um). NMOS row and trunks at the bottom, PMOS row above: the
    # resistor spine rises out of the trunk band through the switch-row gap.
    N_RING_Y0 = 0.0
    N_DIFF_Y = N_RING_Y0 + STRIP_W + 0.8
    N_WMAX = 2.0
    N_RING_Y1 = N_DIFF_Y + N_WMAX + 0.6 + 1.2 + STRIP_W
    CH_Y0 = N_RING_Y1 + 0.5
    CH_Y1 = CH_Y0 + len(nets_order) * TRUNK_PITCH + 0.5
    NW_Y0 = CH_Y1 + 0.5
    P_RING_Y0 = NW_Y0 + 0.5
    ROW_Y = P_RING_Y0 + STRIP_W + 1.2 + 0.6
    P_WMAX = 10.0
    P_DIFF_TOP = ROW_Y + P_WMAX
    P_RAIL_Y = P_DIFF_TOP + 0.8
    P_RING_Y1 = P_RAIL_Y + STRIP_W
    NW_Y1 = P_RING_Y1 + 0.5
    ty_of = {n: CH_Y0 + 0.6 + i * TRUNK_PITCH for i, n in enumerate(nets_order)}

    # ---------------------------------------------------------------- NMOS row
    rail_top_n = N_RING_Y0 + STRIP_W  # top edge of the VSS rail (ring bottom strip)
    gap = SUB_GAP
    x = 0.8 + STRIP_W
    # Enable inverter and the four trim inverters: W2 nf1, G = pin, D = *B, S = VSS.
    for gate, drain in (("PU_EN", "PU_ENB"), ("TRIM0", "TRIM0B"), ("TRIM1", "TRIM1B"),
                        ("TRIM2", "TRIM2B"), ("TRIM3", "TRIM3B")):
        x = mos(cv, ports, "n", x, N_DIFF_Y, 2.0, ["VSS", drain], [gate], "VSS", rail_top_n) + gap
    n_ring_x1 = x - gap + 0.8

    # ---------------------------------------------------------------- PMOS row
    # Small inverter pull-ups first (W4), placed clear of the NMOS drops.
    def place_small(c: Canvas, pts: Ports, start: float) -> float:
        px = start
        for gate, drain in (("PU_EN", "PU_ENB"), ("TRIM0", "TRIM0B"), ("TRIM1", "TRIM1B"),
                            ("TRIM2", "TRIM2B"), ("TRIM3", "TRIM3B")):
            px = mos(c, pts, "p", px, ROW_Y, 4.0, ["VPU", drain], [gate], "VPU", P_RAIL_Y) + gap
        return px - gap

    # Shift the small PMOS row until none of its met2 drops comes within met2
    # space of an NMOS/resistor drop that shares a channel y-range.
    start = find_row_x(place_small, ports, ty_of, 0.8 + STRIP_W + 0.9)
    print(f"small PMOS row placed at x={start:.3f}", file=sys.stderr)
    nw_x0 = start - 0.9 - STRIP_W
    x = place_small(cv, ports, start) + gap

    # ---------------------------------------------------------------- switches
    # Ten interleaved groups of the five switch sub-blocks. Every ladder net's
    # columns then span the whole row, so each net's terminal cloud -- and the
    # star-weight dilution of the spine heads -- is as wide as the row itself.
    spine_w = 2 * (2 * RES_W + 0.5) + 3 * RES_W + 4 * SPINE_GAP  # U,U,bar,bar,bar
    spine_x = 0.0
    for g in range(SW_GROUPS):
        if g == SW_GROUPS // 2:
            spine_x = x + SUB_GAP  # the resistor spine interrupts the row here
            x = spine_x + spine_w + SUB_GAP
        for wf, nf, s_net, d_net, gate in SW_BLOCK:
            cols = [s_net if i % 2 == 0 else d_net for i in range(nf + 1)]
            x = mos(cv, ports, "p", x, ROW_Y, wf, cols, [gate] * nf,
                    "VPU", P_RAIL_Y, contact_rows=CONTACT_ROWS, li1_hw=LI1_HW) + gap
    sw_end = x - gap

    # ---------------------------------------------------------------- spine
    # The five ladder bodies, bottom nets named per the chain N0-...-DP. RBASE
    # (legs down into the trunk band) and R3 fold; the short bars sit inside
    # the switch-row band. All of them pass through the row's middle gap, so
    # every ladder net's terminals cluster around the spine.
    ybase = {"RBASE": 11.0, "R3": 20.6, "R2": 20.1, "R1": 22.5, "R0": 23.1}
    rbase_x0, rbase_x1 = spine_x, spine_x + 2 * RES_W + 0.5
    sx = spine_x
    for name, length, lo, hi, folded in LADDER:
        if folded:
            sx = res_u_v(cv, ports, sx, ybase[name], length, lo, hi)
        else:
            res_bar_v(cv, ports, sx, ybase[name], length, lo, hi)
            sx += RES_W
        sx += SPINE_GAP

    # ---------------------------------------------------------------- rings
    tap_ring(cv, "n", 0.0, N_RING_Y0, n_ring_x1, N_RING_Y1, ("b",))
    rx0, rx1 = nw_x0 - 0.5, sw_end + 0.9 + STRIP_W + 0.5
    # The p-ring's bottom strip runs around RBASE's legs (the legs descend
    # into the trunk band); the left, right and top runs close the ring, and
    # the top run is the VPU rail.
    cut0, cut1 = rbase_x0 - 0.3, rbase_x1 + 0.3
    ring_side(cv, "p", rx0, P_RING_Y0, cut0, P_RING_Y0 + STRIP_W, False)
    ring_side(cv, "p", cut1, P_RING_Y0, rx1, P_RING_Y0 + STRIP_W, False)
    ring_side(cv, "p", rx0, P_RING_Y0 + STRIP_W, rx0 + STRIP_W, P_RING_Y1, False)
    ring_side(cv, "p", rx1 - STRIP_W, P_RING_Y0 + STRIP_W, rx1, P_RING_Y1, False)
    ring_side(cv, "p", rx0, P_RING_Y1 - STRIP_W, rx1, P_RING_Y1, True)
    cv.rect("nwell", rx0, NW_Y0, rx1, NW_Y1)
    cv.rect("hvi", -0.4, N_RING_Y0 - 0.4, max(n_ring_x1, rx1) + 0.4, NW_Y1 + 0.4)

    # ---------------------------------------------------------------- routing
    route_nets(cv, ports, ty_of, ("VSS", "VPU"), PIN_NETS)
    # supply pins and labels
    cv.label("met1_label", "VSS", 1.0, N_RING_Y0 + STRIP_W / 2)
    cv.label("met1_label", "VPU", nw_x0 + 1.0, P_RAIL_Y + STRIP_W / 2)
    return cv


if __name__ == "__main__":
    sys.exit(run_gds(GDS, build, __doc__.splitlines()[0]))
