"""Shared generator for the single-ended receiver leaves (`se_receiver_dm`, `se_receiver_dp`).

The two leaves are the same circuit with different net names, so the layout
is drawn once here, parameterised by (leaf name, input net, output net); each
leaf's `gen.py` is a thin entry point. Drawn from base layers with
`klayout.db` and nothing else. Every device is re-derived for sky130 from
`design/netlist/<leaf>.spice` (issue #221); no gf180 geometry is consumed. The
conventions (rails, guard rings, pin labels, routing layers) are written down
in `layout/analog/README.md`; the rule numbers drawn to are sky130's.

The stream is byte-reproducible: no timestamps are written and every shape is
emitted in a fixed order, so `gen.py --check` compares sha256 of the whole file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gen_common import (
    L,
    STRIP_W,
    TRUNK_PITCH,
    Canvas,
    Ports,
    find_row_x,
    mos,
    route_nets,
    run_gds,
    tap_ring,
    xhigh_resistor,
)


# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
# (netlist instance, L in um, serpentine legs). Legs are even so both heads sit at the top.
RESISTORS = (("XR2", 14.0, 2), ("XR1", 19.0, 2), ("XRBIAS", 140.0, 14))
RES_SPACE = 1.2  # poly space between neighbouring resistors


# The differential receiver's bias is a single XRBIAS (no VREF divider), drawn beside the
# NMOS row ahead of the PMOS row instead of east of the n-well.
BIAS_ONLY = (("XRBIAS", 140.0, 14),)


def build(top: str, din: str, rxout: str, vref: str = "VREF", *, differential: bool = False) -> Canvas:
    """Draw the receiver leaf `top` with input net `din` and output net `rxout`.

    The single-ended leaves tie the second input to a VREF divider (three resistors, east of the
    n-well). With `differential` the second input `vref` is a pin (DM) and the lone bias
    resistor sits beside the NMOS row; that floorplan is a different shape order and a
    0.005 um different ring margin, kept so the committed GDS stays byte-identical.
    """
    # Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
    # every labelled net into a circuit pin, so labelling internal nets would give
    # the layout ten pins against the schematic's four (five for the differential leaf).
    pin_nets = {din, rxout, "VDD", "VSS"} | ({vref} if differential else set())
    cv = Canvas(top, L)
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
        [din, vref, vref, din], "VSS", rail_top_n,
    ) + gap
    # MN_B1: W2 m1. D=BUF1 G=AMPOUT.
    x = mos(cv, ports, "n", x, N_DIFF_Y, 2.0, ["VSS", "BUF1"], ["AMPOUT"], "VSS", rail_top_n) + gap
    # MN_B2: W5 m1. D=RXOUT G=BUF1.
    x = mos(cv, ports, "n", x, N_DIFF_Y, 5.0, ["VSS", rxout], ["BUF1"], "VSS", rail_top_n)
    n_x1 = x

    # ---------------------------------------------------------------- resistor
    # Terminal nets (left head, right head) per netlist instance. R2 and R1 share VREF
    # on adjacent heads; the VREF trunk joins them to the input pair's gates.
    res_nets = {"XR2": ("VSS", "VREF"), "XR1": ("VREF", "VDD"), "XRBIAS": ("IBIASN", "VDD")}
    vdd_heads: list[tuple[float, float]] = []

    def draw_resistors(res_x0: float) -> float:
        """Draw the resistor block from `res_x0`; return the ring's east edge."""
        rx = res_x0
        for name, res_l, legs in BIAS_ONLY if differential else RESISTORS:
            head_l, head_r, _ = xhigh_resistor(cv, rx, N_DIFF_Y, res_l, legs)
            for head, net in zip((head_l, head_r), res_nets[name]):
                if net == "VDD":
                    vdd_heads.append(head)
                elif net == "VSS":
                    # met1 drop on the resistor's left, straight down to the VSS rail strip
                    hx, hy = head
                    cv.rect("met1", rx - 0.5, N_RING_Y0, rx - 0.21, hy + 0.175)
                    cv.rect("met1", rx - 0.5, hy - 0.175, hx - 0.4, hy + 0.175)
                else:
                    ports.add(net, head[0], head[1], "n")
            rx = head_r[0] + 0.705 + RES_SPACE
        res_x1 = rx - RES_SPACE + (0.295 if differential else 0.3)
        ring_x1 = res_x1 + 0.8
        tap_ring(cv, "n", 0.0, N_RING_Y0, ring_x1, N_RING_Y1, ("b",))
        return ring_x1

    if differential:
        ring_x1 = draw_resistors(n_x1 + 1.5)

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
        # MP_B2: W10. D=RXOUT G=BUF1.
        return mos(c, pts, "p", px, p_diff_y, 10.0, ["VDD", rxout], ["BUF1"], "VDD", P_RAIL_Y)

    # Shift the PMOS row until no PMOS landing column's met2 vertical comes
    # within met2 space of an NMOS one that shares channel y-range.
    nets_order = ["IBIASN", "TAIL", "LOADDIODE", "AMPOUT", "BUF1", din, vref, rxout]
    ty_of = {n: CH_Y0 + 0.6 + i * TRUNK_PITCH for i, n in enumerate(nets_order)}

    start = find_row_x(place_p, ports, ty_of, 0.8 + STRIP_W + 0.9)
    print(f"PMOS row placed at x={start:.3f}", file=sys.stderr)
    p_x1 = place_p(cv, ports, start)

    nw_x0 = start - 0.9 - STRIP_W  # ring outer edge hugs the PMOS row
    nw_x1 = p_x1 + 0.9 + STRIP_W + 0.5
    tap_ring(cv, "p", nw_x0, P_RING_Y0, nw_x1 - 0.5, P_RING_Y1, ("t",))
    cv.rect("nwell", nw_x0 - 0.5, NW_Y0, nw_x1, NW_Y1)

    if not differential:
        res_x0 = nw_x1 + 1.5  # right of the n-well: the VDD drops run up its east side
        ring_x1 = draw_resistors(res_x0)

    cv.rect("hvi", -0.4, N_RING_Y0 - 0.4, max(ring_x1, nw_x1) + 0.4, NW_Y1 + 0.4)
    # VDD feeder: rail extended past the well, then down to the resistor's far head.
    assert differential or min(h[0] for h in vdd_heads) - 0.7 > nw_x1, "VDD drops must clear the n-well"
    cv.rect("met1", nw_x1 - 0.5 - 0.1, P_RAIL_Y, max(h[0] for h in vdd_heads) + 0.145, P_RAIL_Y + STRIP_W)
    for hb_x, hb_y in vdd_heads:
        cv.rect("met1", hb_x - 0.145, hb_y - 0.175, hb_x + 0.145, P_RAIL_Y + STRIP_W)

    # ---------------------------------------------------------------- routing
    route_nets(cv, ports, ty_of, ("VSS", "VDD"), pin_nets)
    # supply pins and labels
    cv.label("met1_label", "VSS", 1.0, N_RING_Y0 + STRIP_W / 2)
    cv.label("met1_label", "VDD", nw_x0 + 1.0, P_RAIL_Y + STRIP_W / 2)
    return cv


def run(leaf: str, din: str, rxout: str, here: Path, vref: str = "VREF", *, differential: bool = False) -> int:
    """Command-line entry shared by the receiver leaf generators."""
    return run_gds(
        here / f"{leaf}.gds",
        lambda: build(leaf, din, rxout, vref, differential=differential),
        f"Generate layout/analog/{leaf}/{leaf}.gds.",
    )
