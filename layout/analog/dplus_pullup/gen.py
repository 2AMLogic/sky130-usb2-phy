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

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_common import (  # noqa: E402
    GRID,
    LIC,
    LIC_PITCH,
    PAD,
    STRIP_W,
    Canvas,
    Ports,
    mos,
    tap_ring,
)

HERE = Path(__file__).resolve().parent
GDS = HERE / "dplus_pullup.gds"
TOP = "dplus_pullup"


# --- sky130A drawn-layer table (GDS layer/datatype) -------------------------
L = {
    "nwell": (64, 20),
    "diff": (65, 20),
    "tap": (65, 44),
    "poly": (66, 20),
    "licon": (66, 44),
    "li1": (67, 20),
    "mcon": (67, 44),
    "met1": (68, 20),
    "via1": (68, 44),
    "met2": (69, 20),
    "via2": (69, 44),
    "met3": (70, 20),
    "nsdm": (93, 44),
    "psdm": (94, 20),
    "npc": (95, 20),
    "hvi": (75, 20),
    "urpm": (79, 20),
    "poly_res": (66, 13),
    "met1_label": (68, 5),
    "met3_label": (70, 5),
}

# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
V1 = 0.15  # via1 edge
V2 = 0.20  # via2 edge
TRUNK_W = 0.40  # met3 trunk width
TRUNK_PITCH = 0.70  # met3 trunk pitch
V2_PAD = 0.38  # met2 pad around via2 (0.09 enclosure on the sides)
RES_W = 2.0  # sky130_fd_pr__res_generic_po body width (netlist W)
RES_HEAD = 0.8  # poly head past each end of the body, holds the contact column
RES_GAP = 1.2  # poly space between neighbouring resistors
FINGER_MAX = 10.0  # widest single finger, um

# Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
# every labelled net into a circuit pin, so labelling internal nets would give
# the layout more pins than the schematic's eight.
PIN_NETS = {"DP", "VPU", "VSS", "PU_EN", "TRIM0", "TRIM1", "TRIM2", "TRIM3"}


def resistor(cv: Canvas, ports: Ports, x0: float, y0: float, length: float, left: str, right: str) -> float:
    """One straight sky130_fd_pr__res_generic_po bar, `length` x RES_W um.

    The `poly_res` marker covers exactly the body; the poly heads either side
    stay outside it, so the SKY130 runset sees two contact terminals. The
    runset reads L as area / width, so a straight bar has L = `length`
    exactly. Returns the x of the right edge of the right head.
    """
    yc = y0 + RES_W / 2
    xb0 = x0 + RES_HEAD
    xb1 = xb0 + length
    x1 = xb1 + RES_HEAD
    cv.rect("poly", x0, y0, x1, y0 + RES_W)
    cv.rect("poly_res", xb0, y0, xb1, y0 + RES_W)
    for xh, net in ((x0 + RES_HEAD / 2, left), (xb1 + RES_HEAD / 2, right)):
        ys = [yc + (k - 1.5) * LIC_PITCH for k in range(4)]
        for y in ys:
            cv.centred("licon", xh, y, LIC, LIC)
            cv.centred("mcon", xh, y, LIC, LIC)
        cv.rect("npc", xh - 0.185, ys[0] - 0.185, xh + 0.185, ys[-1] + 0.185)
        cv.rect("li1", xh - 0.165, ys[0] - 0.165, xh + 0.165, ys[-1] + 0.165)
        cv.rect("met1", xh - 0.175, ys[0] - 0.175, xh + 0.175, ys[-1] + 0.175)
        ports.add(net, xh, yc, "n")
    return x1


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
        rx = resistor(cv, ports, rx, N_DIFF_Y, length, left, right) + RES_GAP
    ring_x1 = rx - RES_GAP + 0.8
    tap_ring(cv, "n", 0.0, N_RING_Y0, ring_x1, N_RING_Y1, ("b",))

    # ---------------------------------------------------------------- PMOS row
    def place_small(c: Canvas, pts: Ports, start: float) -> float:
        px = start
        for gate, drain in (("PU_EN", "PU_ENB"), ("TRIM0", "TRIM0B"), ("TRIM1", "TRIM1B"),
                            ("TRIM2", "TRIM2B"), ("TRIM3", "TRIM3B")):
            px = mos(c, pts, "p", px, p_diff_y, 4.0, ["VPU", drain], [gate], "VPU", P_RAIL_Y) + gap
        return px - gap

    def conflicts(a_, b_) -> bool:
        (na, xa, ya, _sa), (nb, xb, yb, _sb) = a_, b_
        lo_a, hi_a = sorted((ya, ty_of[na]))
        lo_b, hi_b = sorted((yb, ty_of[nb]))
        if max(lo_a, lo_b) > min(hi_a, hi_b) + 0.14:
            return False  # verticals never share a y-range
        return abs(xa - xb) < (0.45 if na == nb else 0.52)

    # Shift the small PMOS row until none of its met2 drops comes within met2
    # space of an NMOS/resistor drop that shares a channel y-range.
    start = 0.8 + STRIP_W + 0.9
    while True:
        scratch = Ports()
        place_small(Canvas(TOP, L), scratch, start)
        if not any(conflicts(a_, b_) for a_ in scratch.items for b_ in ports.items):
            break
        start += GRID
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
    by_net: dict[str, list[tuple[float, float, str]]] = {}
    for net, px_, py_, side in ports.items:
        by_net.setdefault(net, []).append((px_, py_, side))
    for net, pts in by_net.items():
        if net in ("VSS", "VPU"):
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
    cv.label("met1_label", "VPU", nw_x0 + 1.0, P_RAIL_Y + STRIP_W / 2)
    return cv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare, do not write")
    ap.add_argument("-o", "--output", type=Path, default=GDS)
    args = ap.parse_args()
    cv = build()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="gen-check-") as scratch:
            tmp = Path(scratch) / GDS.name
            cv.write(tmp)
            same = hashlib.sha256(tmp.read_bytes()).hexdigest() == hashlib.sha256(GDS.read_bytes()).hexdigest()
        print("reproducible" if same else "DIFFERS from committed stream")
        return 0 if same else 1
    cv.write(args.output)
    print(f"wrote {args.output} sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
