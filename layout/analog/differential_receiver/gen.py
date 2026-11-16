#!/usr/bin/env python3
"""Generate layout/analog/differential_receiver/differential_receiver.gds.

Layout for the `differential_receiver` leaf of the analog partition, drawn
from base layers with `klayout.db` and nothing else. Every device is
re-derived for sky130 from `design/netlist/differential_receiver.spice`
(issue #167); no gf180 geometry is consumed. The conventions it implements
(rails, guard rings, pin labels, routing layers) are written down in
`layout/analog/README.md`; the rule numbers it draws to are sky130's.

    python3 layout/analog/differential_receiver/gen.py            # write GDS
    python3 layout/analog/differential_receiver/gen.py --check    # no write,
        # exit 1 if the regenerated stream differs from the committed one

The stream is byte-reproducible: no timestamps are written and every shape is
emitted in a fixed order, so `--check` compares sha256 of the whole file.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_common import (  # noqa: E402
    GRID,
    L,
    PAD,
    STRIP_W,
    Canvas,
    Ports,
    mos,
    run_gds,
    tap_ring,
    xhigh_resistor,
)

HERE = Path(__file__).resolve().parent
GDS = HERE / "differential_receiver.gds"
TOP = "differential_receiver"


# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
V1 = 0.15  # via1 edge
V2 = 0.20  # via2 edge
TRUNK_W = 0.40  # met3 trunk width
TRUNK_PITCH = 0.70  # met3 trunk pitch
V2_PAD = 0.38  # met2 pad around via2 (0.09 enclosure on the sides)
RES_L = 140.0  # netlist L (um of body, centreline)
RES_LEGS = 14

# Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
# every labelled net into a circuit pin, so labelling internal nets would give
# the layout ten pins against the schematic's five.
PIN_NETS = {"DP", "DM", "RXD", "VDD", "VSS"}


def build() -> Canvas:
    cv = Canvas(TOP, L)
    ports = Ports()

    # ---------------------------------------------------------------- floorplan
    # y bands (um). NMOS row at the bottom, channel in the middle, PMOS above.
    N_RING_Y0 = 0.0
    N_DIFF_Y = N_RING_Y0 + STRIP_W + 0.8
    N_WMAX = 10.0
    N_RING_Y1 = N_DIFF_Y + N_WMAX + 0.6 + 1.2 + STRIP_W
    CH_Y0 = N_RING_Y1 + 0.5
    CH_Y1 = CH_Y0 + 8 * TRUNK_PITCH + 1.2
    NW_Y0 = CH_Y1 + 0.5
    P_RING_Y0 = NW_Y0 + 0.5
    P_WMAX = 10.0
    P_DIFF_TOP = P_RING_Y0 + STRIP_W + 1.2 + 0.6 + P_WMAX + 0.0
    P_RAIL_Y = P_DIFF_TOP + 0.8
    P_RING_Y1 = P_RAIL_Y + STRIP_W
    NW_Y1 = P_RING_Y1 + 0.5

    # ---------------------------------------------------------------- NMOS row
    x = 0.8 + STRIP_W  # inside the left ring strip
    gap = 0.8
    rail_top_n = N_RING_Y0 + STRIP_W  # top edge of the VSS rail (ring bottom strip)
    # MNBIAS: W4 m1 -> 1 finger. D=G=IBIASN.
    x = mos(cv, ports, "n", x, N_DIFF_Y, 4.0, ["VSS", "IBIASN"], ["IBIASN"], "VSS", rail_top_n) + gap
    # MTAIL: W4 m2 -> 2 fingers. D=TAIL, G=IBIASN.
    x = mos(cv, ports, "n", x, N_DIFF_Y, 4.0, ["VSS", "TAIL", "VSS"], ["IBIASN", "IBIASN"], "VSS", rail_top_n) + gap
    # MN_INA/MN_INB: W10, 2 fingers each, interdigitated A B B A, common TAIL source.
    x = mos(
        cv, ports, "n", x, N_DIFF_Y, 10.0,
        ["LOADDIODE", "TAIL", "AMPOUT", "TAIL", "LOADDIODE"],
        ["DP", "DM", "DM", "DP"], "VSS", rail_top_n,
    ) + gap
    # MN_B1: W2 m1. D=BUF1 G=AMPOUT.
    x = mos(cv, ports, "n", x, N_DIFF_Y, 2.0, ["VSS", "BUF1"], ["AMPOUT"], "VSS", rail_top_n) + gap
    # MN_B2: W5 m1. D=RXD G=BUF1.
    x = mos(cv, ports, "n", x, N_DIFF_Y, 5.0, ["VSS", "RXD"], ["BUF1"], "VSS", rail_top_n)
    n_x1 = x

    # ---------------------------------------------------------------- resistor
    res_x0 = n_x1 + 1.5
    head_a, head_b, _ = xhigh_resistor(cv, res_x0, N_DIFF_Y, RES_L, RES_LEGS)
    ports.add("IBIASN", head_a[0], head_a[1], "n")
    res_x1 = head_b[0] + 1.0

    ring_x1 = res_x1 + 0.8
    tap_ring(cv, "n", 0.0, N_RING_Y0, ring_x1, N_RING_Y1, ("b",))

    # ---------------------------------------------------------------- PMOS row
    p_diff_y = P_DIFF_TOP - 10.0
    pgap = 0.8
    # MP_LOADA (diode, D=G=LOADDIODE) / MP_LOADB (mirror, D=AMPOUT): pairs of
    # gates share a drain column: gates [A A | B B | B B | A A].
    loadcols = ["VDD", "LOADDIODE", "VDD", "AMPOUT", "VDD", "AMPOUT", "VDD", "LOADDIODE", "VDD"]
    loadgates = ["LOADDIODE"] * 8

    def place_p(c: Canvas, pts: Ports, start: float) -> float:
        px = mos(c, pts, "p", start, p_diff_y, 10.0, loadcols, loadgates, "VDD", P_RAIL_Y) + pgap
        # MP_B1: W20 -> 2 x 10. D=BUF1 G=AMPOUT S=VDD.
        px = mos(c, pts, "p", px, p_diff_y, 10.0, ["VDD", "BUF1", "VDD"], ["AMPOUT", "AMPOUT"], "VDD", P_RAIL_Y) + pgap
        # MP_B2: W10. D=RXD G=BUF1.
        return mos(c, pts, "p", px, p_diff_y, 10.0, ["VDD", "RXD"], ["BUF1"], "VDD", P_RAIL_Y)

    # Shift the PMOS row until no PMOS landing column's met2 vertical comes
    # within met2 space of an NMOS one that shares channel y-range.
    nets_order = ["IBIASN", "TAIL", "LOADDIODE", "AMPOUT", "BUF1", "DP", "DM", "RXD"]
    ty_of = {n: CH_Y0 + 0.6 + i * TRUNK_PITCH for i, n in enumerate(nets_order)}

    def conflicts(a_, b_) -> bool:
        (na, xa, ya, _sa), (nb, xb, yb, _sb) = a_, b_
        lo_a, hi_a = sorted((ya, ty_of[na]))
        lo_b, hi_b = sorted((yb, ty_of[nb]))
        if max(lo_a, lo_b) > min(hi_a, hi_b) + 0.14:
            return False  # verticals never share a y-range
        return abs(xa - xb) < (0.45 if na == nb else 0.52)

    start = 0.8 + STRIP_W + 0.9
    while True:
        scratch = Ports()
        place_p(Canvas(TOP, L), scratch, start)
        if not any(conflicts(a_, b_) for a_ in scratch.items for b_ in ports.items):
            break
        start += GRID
    print(f"PMOS row placed at x={start:.3f}", file=sys.stderr)
    p_x1 = place_p(cv, ports, start)

    nw_x0 = start - 0.9 - STRIP_W  # ring outer edge hugs the PMOS row
    nw_x1 = p_x1 + 0.9 + STRIP_W + 0.5
    tap_ring(cv, "p", nw_x0, P_RING_Y0, nw_x1 - 0.5, P_RING_Y1, ("t",))
    cv.rect("nwell", nw_x0 - 0.5, NW_Y0, nw_x1, NW_Y1)
    cv.rect("hvi", -0.4, N_RING_Y0 - 0.4, max(ring_x1, nw_x1) + 0.4, NW_Y1 + 0.4)
    # VDD feeder: rail extended past the well, then down to the resistor's far head.
    hb_x, hb_y = head_b
    cv.rect("met1", nw_x1 - 0.5 - 0.1, P_RAIL_Y, hb_x + 0.145, P_RAIL_Y + STRIP_W)
    cv.rect("met1", hb_x - 0.145, hb_y - 0.175, hb_x + 0.145, P_RAIL_Y + STRIP_W)

    # ---------------------------------------------------------------- routing
    by_net: dict[str, list[tuple[float, float, str]]] = {}
    for net, px_, py_, side in ports.items:
        by_net.setdefault(net, []).append((px_, py_, side))
    for net, pts in by_net.items():
        if net in ("VSS", "VDD"):
            continue
        ty = ty_of[net]
        xs_ = [p[0] for p in pts]
        cv.rect("met3", min(xs_) - 0.3, ty - TRUNK_W / 2, max(xs_) + 0.3, ty + TRUNK_W / 2)
        for (vx, vy, _side) in pts:
            cv.centred("via1", vx, vy, V1, V1)
            cv.centred("met1", vx, vy, PAD, PAD)
            cv.rect("met2", vx - PAD / 2, min(vy, ty) - PAD / 2, vx + PAD / 2, max(vy, ty) + PAD / 2)
            cv.centred("met2", vx, ty, V2_PAD, V2_PAD)
            cv.centred("via2", vx, ty, V2, V2)
        if net in PIN_NETS:
            cv.label("met3_label", net, min(xs_), ty)
    # supply pins and labels
    cv.label("met1_label", "VSS", 1.0, N_RING_Y0 + STRIP_W / 2)
    cv.label("met1_label", "VDD", nw_x0 + 1.0, P_RAIL_Y + STRIP_W / 2)
    return cv


if __name__ == "__main__":
    sys.exit(run_gds(GDS, build, __doc__.splitlines()[0]))
