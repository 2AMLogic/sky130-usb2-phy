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

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

import klayout.db as db

HERE = Path(__file__).resolve().parent
GDS = HERE / "differential_receiver.gds"
TOP = "differential_receiver"

DBU = 0.001  # um per database unit
GRID = 0.005  # sky130 manufacturing grid, um

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
GATE_L = 0.5  # sky130_fd_pr__{n,p}fet_g5v0d10v5 minimum L, per the netlist
SD_W = 0.54  # source/drain column width (licon + 0.185 each side)
LIC = 0.17  # licon1 / mcon edge
LIC_PITCH = 0.36  # licon1 / mcon pitch (mcon.2 needs 0.19 space)
LIC_ENC_Y = 0.06  # diff enclosure of licon along the column
POLY_ENDCAP = 0.25  # poly extension past diff, both ends
GC_Y = 0.35  # gate licon bottom, above diff edge
POLY_TOP = 0.60  # poly end above the diff edge on the contact side
PAD = 0.35  # met1 / met2 landing pad edge
V1 = 0.15  # via1 edge
V2 = 0.20  # via2 edge
TRUNK_W = 0.40  # met3 trunk width
TRUNK_PITCH = 0.70  # met3 trunk pitch
V2_PAD = 0.38  # met2 pad around via2 (0.09 enclosure on the sides)
STRIP_W = 0.29  # tap strip width (rails, guard rings)
RES_W = 1.41  # sky130_fd_pr__res_xhigh_po_1p41 body width
RES_L = 140.0  # netlist L (um of body, centreline)
RES_GAP = 0.50  # poly space between serpentine legs
RES_LEGS = 14

# Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
# every labelled net into a circuit pin, so labelling internal nets would give
# the layout ten pins against the schematic's five.
PIN_NETS = {"DP", "DM", "RXD", "VDD", "VSS"}


def snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 6)


class Canvas:
    """Thin wrapper over a klayout.db cell. Coordinates are um."""

    def __init__(self) -> None:
        self.ly = db.Layout()
        self.ly.dbu = DBU
        self.cell = self.ly.create_cell(TOP)
        self.idx = {k: self.ly.layer(*v) for k, v in L.items()}

    def rect(self, layer: str, x0: float, y0: float, x1: float, y1: float) -> None:
        x0, x1 = sorted((snap(x0), snap(x1)))
        y0, y1 = sorted((snap(y0), snap(y1)))
        self.cell.shapes(self.idx[layer]).insert(db.DBox(x0, y0, x1, y1))

    def label(self, layer: str, text: str, x: float, y: float) -> None:
        self.cell.shapes(self.idx[layer]).insert(db.DText(text, snap(x), snap(y)))

    def centred(self, layer: str, cx: float, cy: float, w: float, h: float) -> None:
        self.rect(layer, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    def write(self, path: Path) -> None:
        opt = db.SaveLayoutOptions()
        opt.format = "GDS2"
        opt.gds2_write_timestamps = False
        opt.gds2_write_cell_properties = False
        opt.gds2_libname = TOP
        self.ly.write(str(path), opt)


def contacts_y(w: float) -> list[float]:
    """Centre y (from diff bottom) of each licon in a column of height w."""
    n = int((w - 2 * LIC_ENC_Y + LIC) / LIC_PITCH + 1e-9)
    span = n * LIC_PITCH - LIC
    y0 = (w - span) / 2 + LIC / 2
    return [y0 + i * LIC_PITCH for i in range(n)]


class Ports:
    """Collects (net, x, y, side) landing pads for the channel router."""

    def __init__(self) -> None:
        self.items: list[tuple[str, float, float, str]] = []

    def add(self, net: str, x: float, y: float, side: str) -> None:
        self.items.append((net, x, y, side))


def mos(
    cv: Canvas,
    ports: Ports,
    kind: str,
    x0: float,
    y_diff: float,
    wf: float,
    cols: list[str],
    gates: list[str],
    rail_net: str,
    rail_y: float,
) -> float:
    """Draw one multi-finger g5v0d10v5 MOSFET with its diff-bottom at `y_diff`.

    cols[i] / gates[i] are net names. Columns whose net is `rail_net` are
    stubbed straight to the supply rail at `rail_y`; every other column and
    every gate gets a met1 landing pad on the channel side. Returns the x of
    the right edge of the diffusion.

    NMOS exits upward (channel above), PMOS exits downward (channel below);
    the supply rail is on the opposite side in each case.
    """
    nf = len(gates)
    assert len(cols) == nf + 1
    pitch = GATE_L + SD_W
    width = (nf + 1) * SD_W + nf * GATE_L
    up = kind == "n"
    dop = "nsdm" if up else "psdm"

    cv.rect("diff", x0, y_diff, x0 + width, y_diff + wf)
    cv.rect(dop, x0 - 0.125, y_diff - 0.125, x0 + width + 0.125, y_diff + wf + 0.125)

    # column contacts: licon -> li1 -> mcon -> met1
    for i, net in enumerate(cols):
        xc = x0 + SD_W / 2 + i * pitch
        ys = [y_diff + y for y in contacts_y(wf)]
        for y in ys:
            cv.centred("licon", xc, y, LIC, LIC)
            cv.centred("mcon", xc, y, LIC, LIC)
        cv.rect("li1", xc - 0.165, ys[0] - LIC / 2 - 0.08, xc + 0.165, ys[-1] + LIC / 2 + 0.08)
        if net == rail_net:
            lo, hi = (rail_y, ys[-1] + 0.23) if up else (ys[0] - 0.23, rail_y)
            cv.rect("met1", xc - 0.145, lo, xc + 0.145, hi)
        else:
            if up:
                yp = y_diff + wf + GC_Y + LIC / 2
                cv.rect("met1", xc - 0.145, ys[0] - 0.23, xc + 0.145, yp)
            else:
                yp = y_diff - GC_Y - LIC / 2
                cv.rect("met1", xc - 0.145, yp, xc + 0.145, ys[-1] + 0.23)
            ports.add(net, xc, yp, "n" if up else "p")

    # gates: poly stripe, contact on the channel-side extension
    for g, net in enumerate(gates):
        xg = x0 + SD_W + GATE_L / 2 + g * pitch
        if up:
            yl = y_diff + wf + GC_Y + LIC / 2
            cv.rect("poly", xg - GATE_L / 2, y_diff - POLY_ENDCAP, xg + GATE_L / 2, y_diff + wf + POLY_TOP)
            ports.add(net, xg, yl, "n")
        else:
            yl = y_diff - GC_Y - LIC / 2
            cv.rect("poly", xg - GATE_L / 2, y_diff - POLY_TOP, xg + GATE_L / 2, y_diff + wf + POLY_ENDCAP)
            ports.add(net, xg, yl, "p")
        cv.centred("licon", xg, yl, LIC, LIC)
        cv.centred("mcon", xg, yl, LIC, LIC)
        cv.rect("npc", xg - 0.185, yl - 0.185, xg + 0.185, yl + 0.185)
        cv.rect("li1", xg - 0.165, yl - 0.165, xg + 0.165, yl + 0.165)
        cv.centred("met1", xg, yl, PAD, PAD)
    return x0 + width


def tap_ring(
    cv: Canvas,
    kind: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    rail_sides: tuple[str, ...],
) -> None:
    """Closed tap ring whose *outer* box is (x0,y0)-(x1,y1).

    The ring is tap + li1 with licon at every `LIC_PITCH*2` and mcon only on
    the sides in `rail_sides` ('b' bottom, 't' top), which also get a met1
    strip: that strip is the supply rail.
    """
    dop = "psdm" if kind == "n" else "nsdm"
    w = STRIP_W
    strips = {
        "b": (x0, y0, x1, y0 + w),
        "t": (x0, y1 - w, x1, y1),
        "l": (x0, y0, x0 + w, y1),
        "r": (x1 - w, y0, x1, y1),
    }
    for side, (a, b, c, d) in strips.items():
        cv.rect("tap", a, b, c, d)
        cv.rect(dop, a - 0.125, b - 0.125, c + 0.125, d + 0.125)
        cv.rect("li1", a, b, c, d)
        horiz = side in "bt"
        # corner squares belong to the horizontal strips: contacts there once only
        lo, hi = (a, c) if horiz else (b + w + 0.1, d - w - 0.1)
        n = int((hi - lo - 2 * 0.1) / (2 * LIC_PITCH))
        for i in range(n + 1):
            p = lo + 0.1 + LIC / 2 + i * 2 * LIC_PITCH
            if p + LIC / 2 > hi - 0.1:
                break
            cx, cy = (p, (b + d) / 2) if horiz else ((a + c) / 2, p)
            cv.centred("licon", cx, cy, LIC, LIC)
            if side in rail_sides:
                cv.centred("mcon", cx, cy, LIC, LIC)
        if side in rail_sides:
            cv.rect("met1", a, b, c, d)


def resistor(cv: Canvas, ports: Ports, x0: float, y0: float) -> tuple[float, float]:
    """Serpentine sky130_fd_pr__res_xhigh_po_1p41, centreline length RES_L.

    Both terminal heads are at the top, outside the `poly_res` marker, so the
    SKY130 runset sees exactly two terminals. Returns the (x, y) centre of each
    head's met1 pad.
    """
    w = RES_W
    pitch = w + RES_GAP
    n = RES_LEGS
    # centreline: n legs of `leg` + (n-1) links of `pitch`
    leg = snap((RES_L - (n - 1) * pitch) / n)
    # leg centreline x_i; vertical centreline from yb to yt
    xs = [x0 + w / 2 + i * pitch for i in range(n)]
    yb = y0 + w / 2
    yt = yb + leg
    region = db.Region()
    for x in xs:
        region.insert(db.DBox(x - w / 2, yb - w / 2, x + w / 2, yt + w / 2).to_itype(DBU))
    for i in range(n - 1):
        y = yb if i % 2 == 0 else yt
        region.insert(db.DBox(xs[i] - w / 2, y - w / 2, xs[i + 1] + w / 2, y + w / 2).to_itype(DBU))
    region.merge()
    # The first and last leg are free at the top: trim them to the centreline
    # end so area / width is the centreline length (mitred corners count once).
    for x in (xs[0], xs[-1]):
        region -= db.Region(db.DBox(x - w / 2, yt, x + w / 2, yt + w / 2).to_itype(DBU))
    area_um2 = region.area() * DBU * DBU
    cv.cell.shapes(cv.idx["poly"]).insert(region)
    marker = db.Region(db.DBox(x0, y0, xs[-1] + w / 2, yt + w / 2).to_itype(DBU))
    for x in (xs[0], xs[-1]):
        marker -= db.Region(db.DBox(x - w / 2 - 0.01, yt, x + w / 2 + 0.01, yt + w).to_itype(DBU))
    cv.cell.shapes(cv.idx["poly_res"]).insert(marker)
    cv.cell.shapes(cv.idx["urpm"]).insert(marker)
    # heads above the marker edge (marker top == yt): poly contact pads
    head_pads = []
    for x in (xs[0], xs[-1]):
        cv.rect("poly", x - w / 2, yt, x + w / 2, yt + 0.5)
        yl = yt + 0.25
        for k in range(4):
            cx = x + (k - 1.5) * LIC_PITCH
            cv.centred("licon", cx, yl, LIC, LIC)
            cv.centred("mcon", cx, yl, LIC, LIC)
        cv.rect("npc", x - w / 2 + 0.1, yl - 0.185, x + w / 2 - 0.1, yl + 0.185)
        cv.rect("li1", x - 0.64, yl - 0.165, x + 0.64, yl + 0.165)
        cv.rect("met1", x - 0.66, yl - 0.175, x + 0.66, yl + 0.175)
        head_pads.append((x, yl))
    cv.rect("psdm", x0 - 0.3, 0.3, xs[-1] + w / 2 + 0.3, yt + 0.5 + 0.3)
    print(f"resistor body area {area_um2:.3f} um2 -> L = {area_um2 / w:.3f} um (target {RES_L})", file=sys.stderr)
    return head_pads[0], head_pads[1]


def build() -> Canvas:
    cv = Canvas()
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
    head_a, head_b = resistor(cv, ports, res_x0, N_DIFF_Y)
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
        place_p(Canvas(), scratch, start)
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
