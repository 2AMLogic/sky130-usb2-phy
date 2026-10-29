"""Helpers shared by every `layout/analog/<block>/gen.py`.

Operator ruling 2026-10-29 (#238): the generator helpers that were copy-pasted
into each leaf live here, one copy, so a fix to `mos` or `tap_ring` is made
once. The leaf directories still own their outputs: each `gen.py` keeps its
own layer table, `TOP`, GDS, and block-specific `build()`, and `gen.py --check`
still compares sha256 of the regenerated stream against the committed GDS, so
sharing code does not weaken reproducibility.

Variants that genuinely differ stay in their leaf and are named in
`layout/analog/README.md`: `differential_driver`'s `Ports`/`mos` (per-gate
length, supply asserts, landing kinds) and the `resistor` family.

`klayout.db` only, no timestamps. A change here must leave every committed GDS
byte-identical (`gen.py --check` for all five leaves).
"""

from __future__ import annotations

from pathlib import Path

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
