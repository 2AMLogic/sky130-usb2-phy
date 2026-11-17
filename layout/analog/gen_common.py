"""Helpers shared by every `layout/analog/<block>/gen.py`.

Operator ruling 2026-10-29 (#238): the generator helpers that were copy-pasted
into each leaf live here, one copy, so a fix to `mos` or `tap_ring` is made
once — and, in the ruling's words, this module "reconciles the mos/resistor
variants explicitly". The leaf directories still own their outputs: each
`gen.py` keeps its `TOP`, GDS, and block-specific `build()`, and `gen.py
--check` still compares sha256 of the regenerated stream against the committed
GDS, so sharing code does not weaken reproducibility.

Shared here: the sky130A drawn-layer table `L`, the `--check` / `-o` GDS CLI
(`run_gds`, with the per-leaf `--help` description passed in), the landing-pad
collector `Ports`, the device builder `mos`, and the two poly-resistor builders
`xhigh_resistor` (serpentine `res_xhigh_po`, carrying the two-leg `urpm.width.1`
marker guard) and `res_generic_po` (straight bar).

`klayout.db` only, no timestamps. A change here must leave every committed GDS
byte-identical (`gen.py --check` for all five leaves).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Callable

import klayout.db as db

DBU = 0.001  # um per database unit
GRID = 0.005  # sky130 manufacturing grid, um
GATE_L = 0.5  # sky130_fd_pr__{n,p}fet_g5v0d10v5 minimum L, per the netlist
SD_W = 0.54  # source/drain column width (licon + 0.185 each side)
LIC = 0.17  # licon1 / mcon edge
LIC_PITCH = 0.36  # licon1 / mcon pitch (mcon.2 needs 0.19 space)
LIC_ENC_Y = 0.06  # diff enclosure of licon along the column
POLY_ENDCAP = 0.25  # poly extension past diff, both ends
GC_Y = 0.35  # gate licon bottom, above diff edge
POLY_TOP = 0.60  # poly end above the diff edge on the contact side
PAD = 0.35  # met1 / met2 landing pad edge
STRIP_W = 0.29  # tap strip width (rails, guard rings)

# --- sky130A drawn-layer table (GDS layer/datatype) --------------------------
# The driver's superset: `via3`, `met4` and `capm` (its MIM cap) exist in every
# leaf's namespace, and klayout writes no bytes for a layer holding no shapes,
# so the extra entries are output-neutral for the other four leaves (#293).
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
    "via3": (70, 44),
    "met4": (71, 20),
    "nsdm": (93, 44),
    "psdm": (94, 20),
    "npc": (95, 20),
    "hvi": (75, 20),
    "urpm": (79, 20),
    "capm": (89, 44),
    "poly_res": (66, 13),
    "met1_label": (68, 5),
    "met3_label": (70, 5),
}

XHIGH_W = 1.41  # sky130_fd_pr__res_xhigh_po_1p41 body width
XHIGH_GAP = 0.50  # poly space between serpentine legs


def snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 6)


class Canvas:
    """Thin wrapper over a klayout.db cell. Coordinates are um."""

    def __init__(self, top: str, layers: dict[str, tuple[int, int]]) -> None:
        self.ly = db.Layout()
        self.ly.dbu = DBU
        self.top = top
        self.cell = self.ly.create_cell(top)
        self.idx = {k: self.ly.layer(*v) for k, v in layers.items()}

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
        opt.gds2_libname = self.top
        self.ly.write(str(path), opt)


def contacts_y(w: float) -> list[float]:
    """Centre y (from diff bottom) of each licon in a column of height w."""
    n = int((w - 2 * LIC_ENC_Y + LIC) / LIC_PITCH + 1e-9)
    span = n * LIC_PITCH - LIC
    y0 = (w - span) / 2 + LIC / 2
    return [y0 + i * LIC_PITCH for i in range(n)]


class Ports:
    """Collects (net, x, y, kind) landing pads for the channel router.

    kind: 'm1' met1 landing (via1 goes on it), 'm3' met3 landing (via2 goes
    on it), 'm4' MIM top plate (via3 on the capm, met4 strip down to the
    trunk).
    """

    def __init__(self) -> None:
        self.items: list[tuple[str, float, float, str]] = []

    def add(self, net: str, x: float, y: float, kind: str = "m1") -> None:
        self.items.append((net, x, y, kind))


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
    *,
    gl: float = GATE_L,
    supply: frozenset[str] = frozenset(),
) -> float:
    """Draw one multi-finger g5v0d10v5 MOSFET with its diff-bottom at `y_diff`.

    cols[i] / gates[i] are net names. Columns whose net is `rail_net` are
    stubbed straight to the supply rail at `rail_y`; every other column and
    every gate gets a met1 landing pad on the channel side. Returns the x of
    the right edge of the diffusion.

    `gl` is the drawn gate length (the default `GATE_L` unless the leaf's
    netlist asks for another); `supply`, when given, asserts none of its nets
    lands on a foreign rail or a gate.

    NMOS exits upward (channel above), PMOS exits downward (channel below);
    the supply rail is on the opposite side in each case.
    """
    nf = len(gates)
    assert len(cols) == nf + 1
    pitch = gl + SD_W
    width = (nf + 1) * SD_W + nf * gl
    up = kind == "n"
    dop = "nsdm" if up else "psdm"
    assert not (supply - {rail_net}) & set(cols + gates), "supply on a foreign rail or gate"
    assert rail_net not in gates

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
            ports.add(net, xc, yp)

    # gates: poly stripe, contact on the channel-side extension
    for g, net in enumerate(gates):
        xg = x0 + SD_W + gl / 2 + g * pitch
        if up:
            yl = y_diff + wf + GC_Y + LIC / 2
            cv.rect("poly", xg - gl / 2, y_diff - POLY_ENDCAP, xg + gl / 2, y_diff + wf + POLY_TOP)
            ports.add(net, xg, yl)
        else:
            yl = y_diff - GC_Y - LIC / 2
            cv.rect("poly", xg - gl / 2, y_diff - POLY_TOP, xg + gl / 2, y_diff + wf + POLY_ENDCAP)
            ports.add(net, xg, yl)
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


def xhigh_resistor(
    cv: Canvas, x0: float, y0: float, length: float, legs: int
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Serpentine sky130_fd_pr__res_xhigh_po_1p41, centreline length `length`, `legs` legs.

    Both terminal heads are at the top, outside the `poly_res` marker, so the
    SKY130 runset sees exactly two terminals. Returns the (x, y) centre of each
    head's met1 pad and the x of the right edge of the body.
    """
    w = XHIGH_W
    pitch = w + XHIGH_GAP
    n = legs
    # centreline: n legs of `leg` + (n-1) links of `pitch`
    leg = snap((length - (n - 1) * pitch) / n)
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
    # With two legs there is no top link: the marker ends at the head edge, or the gap
    # between the two cut-outs would leave a sliver narrower than urpm.width.1.
    marker = db.Region(db.DBox(x0, y0, xs[-1] + w / 2, yt + (0 if n == 2 else w / 2)).to_itype(DBU))
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
    print(f"xhigh resistor body area {area_um2:.3f} um2 -> L = {area_um2 / w:.3f} um (target {length})", file=sys.stderr)
    return head_pads[0], head_pads[1], xs[-1] + w / 2 + 0.3


def res_generic_po(
    cv: Canvas,
    ports: Ports,
    x0: float,
    y0: float,
    w: float,
    length: float,
    nets: tuple[str, str],
    head_ys: list[float],
    pad_hw: float,
    port_y: float,
    kind: str,
) -> float:
    """sky130_fd_pr__res_generic_po: a poly bar `length` (x) by `w` (y) under the
    `poly_res` marker, a contacted poly head on each end outside the marker.

    `x0` is the marker's left edge; the heads extend 0.8 um past it each side.
    `head_ys` are the head-contact centres as offsets from `y0`; `pad_hw` is
    the met1 pad's x half-width; the landing pads are (xh, y0 + `port_y`,
    `kind`). Returns the x of the right edge of the right head.
    """
    head = 0.8  # poly head length beyond the marker
    cv.rect("poly", x0 - head, y0, x0 + length + head, y0 + w)
    cv.rect("poly_res", x0, y0, x0 + length, y0 + w)
    for xh, net in ((x0 - head / 2, nets[0]), (x0 + length + head / 2, nets[1])):
        for y in head_ys:
            cv.centred("licon", xh, y0 + y, LIC, LIC)
            cv.centred("mcon", xh, y0 + y, LIC, LIC)
        cv.rect("npc", xh - 0.185, y0 + head_ys[0] - 0.185, xh + 0.185, y0 + head_ys[-1] + 0.185)
        cv.rect("li1", xh - 0.165, y0 + head_ys[0] - 0.165, xh + 0.165, y0 + head_ys[-1] + 0.165)
        cv.rect("met1", xh - pad_hw, y0 + head_ys[0] - 0.175, xh + pad_hw, y0 + head_ys[-1] + 0.175)
        ports.add(net, xh, y0 + port_y, kind)
    return x0 + length + head


def run_gds(gds: Path, build: Callable[[], Canvas], description: str) -> int:
    """The `--check` / `-o` GDS-writer CLI shared by every leaf generator.

    The description is a parameter: each leaf passes its own docstring's first
    line, so `--help` stays per leaf instead of resolving to this module's.
    """
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--check", action="store_true", help="compare, do not write")
    ap.add_argument("-o", "--output", type=Path, default=gds)
    args = ap.parse_args()
    cv = build()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="gen-check-") as scratch:
            tmp = Path(scratch) / gds.name
            cv.write(tmp)
            same = hashlib.sha256(tmp.read_bytes()).hexdigest() == hashlib.sha256(gds.read_bytes()).hexdigest()
        print("reproducible" if same else "DIFFERS from committed stream")
        return 0 if same else 1
    cv.write(args.output)
    print(f"wrote {args.output} sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}")
    return 0
