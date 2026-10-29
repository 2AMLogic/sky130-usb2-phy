#!/usr/bin/env python3
"""Generate layout/analog/differential_driver/differential_driver.gds.

Layout for the `differential_driver` leaf of the analog partition, drawn from
base layers with `klayout.db` and nothing else. Every device is read from
`design/netlist/differential_driver.spice` and re-derived for sky130 (issue
#220); no gf180 geometry is consumed. The conventions it implements (rails,
guard rings, pin labels, routing layers) are the receiver's, written down in
`layout/analog/README.md`; the rule numbers it draws to are sky130's.

    python3 layout/analog/differential_driver/gen.py            # write GDS
    python3 layout/analog/differential_driver/gen.py --check    # no write,
        # exit 1 if the regenerated stream differs from the committed one

The stream is byte-reproducible: no timestamps are written and every shape is
emitted in a fixed order, so `--check` compares sha256 of the whole file.

Floorplan (x zones are disjoint, so no two met2 drops of different nets can
share a y-range within spacing -- there is no placement search):

    left zone    NMOS row + xhigh_po bias resistor, inside one p-tap ring
    middle zone  MIM caps and the series poly resistors, above the channel
    right zone   PMOS row, in one n-well with its tap ring
    channel      one met3 trunk per signal net, between the rows' y bands
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
import tempfile
from pathlib import Path

import klayout.db as db

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_common import (  # noqa: E402
    DBU,
    GC_Y,
    LIC,
    LIC_PITCH,
    PAD,
    POLY_ENDCAP,
    POLY_TOP,
    SD_W,
    STRIP_W,
    Canvas,
    contacts_y,
    snap,
    tap_ring,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
GDS = HERE / "differential_driver.gds"
NETLIST = REPO / "design" / "netlist" / "differential_driver.spice"
TOP = "differential_driver"


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

# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
V1 = 0.15  # via1 edge
V2 = 0.20  # via2 edge
V3 = 0.20  # via3 edge
TRUNK_W = 0.40  # met3 trunk width
TRUNK_PITCH = 0.70  # met3 trunk pitch
V2_PAD = 0.38  # met2 pad around via2 (0.09 enclosure on the sides)
M4_W = 0.40  # met4 strip / pad width
RES_W = 1.41  # sky130_fd_pr__res_xhigh_po_1p41 body width
RES_GAP = 0.50  # poly space between serpentine legs
FINGER_MAX = 10.0  # widest single finger, um
MIM_ENC = 0.14  # met3 bottom plate enclosure of capm
MIM_VIA_IN = 0.50  # via3 centre inset from the capm corner
MIM_TAB = 1.0  # bottom-plate tab below the plate, carries the via2

# Nets that are cell pins. Only these are labelled: the SKY130 LVS runset turns
# every labelled net into a circuit pin.
PIN_NETS = {"VDD", "VSS", "TXDP", "TXDM", "DRVEN", "OE", "DP", "DM"}
SUPPLY = {"VDD", "VSS"}


# --- the netlist: the only source of devices ---------------------------------
def parse_netlist(path: Path) -> list[dict]:
    """Return one dict per `X` line: name, nodes, model and numeric params."""
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("+") and lines:
            lines[-1] += " " + raw[1:].strip()
        elif raw.startswith("X"):
            lines.append(raw.strip())
    devs = []
    for ln in lines:
        toks = ln.split()
        idx = next(i for i, t in enumerate(toks) if t.startswith("sky130_fd_pr__"))
        params = {}
        for t in toks[idx + 1 :]:
            k, _, v = t.partition("=")
            params[k.lower()] = float(v)
        devs.append({"name": toks[0], "nodes": toks[1:idx], "model": toks[idx], "p": params})
    return devs


def fingers(w: float, mult: float) -> tuple[int, float]:
    """(finger count, width of each finger) for a device of width w, mult copies."""
    k = math.ceil(w / FINGER_MAX - 1e-9)
    return k * int(mult), w / k


class Ports:
    """Collects (net, x, y, kind) landing points for the channel router.

    kind: 'm1' met1 landing (via1 goes on it), 'm3' met3 landing (via2 goes on
    it), 'm4' MIM top plate (via3 on the capm, met4 strip down to the trunk).
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
    gl: float,
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
    pitch = gl + SD_W
    width = (nf + 1) * SD_W + nf * gl
    up = kind == "n"
    dop = "nsdm" if up else "psdm"
    assert not (SUPPLY - {rail_net}) & set(cols + gates), "supply on a foreign rail or gate"
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


def xhigh_resistor(cv: Canvas, x0: float, y0: float, length: float, legs: int) -> tuple:
    """Serpentine sky130_fd_pr__res_xhigh_po_1p41, centreline length `length`.

    Both terminal heads are at the top, outside the `poly_res` marker, so the
    SKY130 runset sees exactly two terminals. Returns the (x, y) centre of each
    head's met1 pad.
    """
    w = RES_W
    pitch = w + RES_GAP
    n = legs
    leg = snap((length - (n - 1) * pitch) / n)
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


def generic_poly_resistor(cv: Canvas, ports: Ports, x0: float, y0: float, w: float, length: float, nets: tuple[str, str]) -> float:
    """sky130_fd_pr__res_generic_po: a poly bar `length` (x) by `w` (y) under the
    `poly_res` marker, a contacted poly head on each end outside the marker.
    Returns the x of the right edge of the right head."""
    head = 0.8  # poly head length beyond the marker
    cv.rect("poly", x0 - head, y0, x0 + length + head, y0 + w)
    cv.rect("poly_res", x0, y0, x0 + length, y0 + w)
    for xh, net in ((x0 - head / 2, nets[0]), (x0 + length + head / 2, nets[1])):
        ys = [y0 + y for y in contacts_y(w)]
        for y in ys:
            cv.centred("licon", xh, y, LIC, LIC)
            cv.centred("mcon", xh, y, LIC, LIC)
        cv.rect("npc", xh - 0.185, ys[0] - 0.185, xh + 0.185, ys[-1] + 0.185)
        cv.rect("li1", xh - 0.165, ys[0] - 0.165, xh + 0.165, ys[-1] + 0.165)
        cv.rect("met1", xh - 0.145, ys[0] - 0.175, xh + 0.145, ys[-1] + 0.175)
        ports.add(net, xh, ys[0], "m1")
    return x0 + length + head


def mim_cap(cv: Canvas, ports: Ports, x0: float, y0: float, side: float, bot_net: str, top_net: str) -> float:
    """sky130_fd_pr__cap_mim_m3_1: met3 bottom plate, capm, met4 top contact.
    `side` x `side` um capm. The bottom plate takes a via2 landing, the top
    plate a via3 landing on the capm at its lower-left corner."""
    cv.rect("met3", x0 - MIM_ENC, y0 - MIM_ENC, x0 + side + MIM_ENC, y0 + side + MIM_ENC)
    cv.rect("capm", x0, y0, x0 + side, y0 + side)
    # The via2 lands on a tab of the bottom plate outside the capm: the PDK's
    # met3 for via2 enclosure checks does not count the met3 under the capm.
    tab_y = y0 - MIM_ENC - MIM_TAB
    cv.rect("met3", x0 + side - MIM_VIA_IN - 0.4, tab_y, x0 + side - MIM_VIA_IN + 0.4, y0)
    ports.add(bot_net, x0 + side - MIM_VIA_IN, tab_y + 0.4, "m3")
    vx, vy = x0 + MIM_VIA_IN, y0 + MIM_VIA_IN
    cv.centred("via3", vx, vy, V3, V3)
    cv.centred("met4", vx, vy, M4_W, M4_W)
    ports.add(top_net, vx, vy, "m4")
    return x0 + side + MIM_ENC


def build() -> Canvas:
    devs = parse_netlist(NETLIST)
    nets = {n for d in devs for n in d["nodes"]}
    # One trunk per net except VSS (rail-only). VDD is a routed net too: its
    # rail strip is tied to the bias resistor's head through the channel.
    trunk_nets = sorted(nets - {"VSS"})
    n_tr = len(trunk_nets)

    cv = Canvas(TOP, L)
    ports = Ports()

    # ---------------------------------------------------------------- floorplan
    N_RING_Y0 = 0.0
    N_DIFF_Y = N_RING_Y0 + STRIP_W + 0.8
    N_WMAX = 10.0
    N_RING_Y1 = N_DIFF_Y + N_WMAX + 0.6 + 1.2 + STRIP_W
    CH_Y0 = N_RING_Y1 + 0.5
    CH_Y1 = CH_Y0 + n_tr * TRUNK_PITCH + 1.2
    NW_Y0 = CH_Y1 + 0.5
    P_RING_Y0 = NW_Y0 + 0.5
    P_WMAX = 10.0
    P_DIFF_TOP = P_RING_Y0 + STRIP_W + 1.2 + 0.6 + P_WMAX
    P_RAIL_Y = P_DIFF_TOP + 0.8
    P_RING_Y1 = P_RAIL_Y + STRIP_W
    NW_Y1 = P_RING_Y1 + 0.5
    ty_of = {n: CH_Y0 + 0.6 + i * TRUNK_PITCH for i, n in enumerate(trunk_nets)}

    mosfets = [d for d in devs if d["model"].endswith(("nfet_g5v0d10v5", "pfet_g5v0d10v5"))]

    def draw(d: dict, x: float, y_diff: float, rail_y: float) -> float:
        dn, gn, sn, _bn = d["nodes"]
        nf, wf = fingers(d["p"]["w"], d["p"]["mult"])
        kind = "n" if "nfet" in d["model"] else "p"
        cols = [sn if i % 2 == 0 else dn for i in range(nf + 1)]
        return mos(cv, ports, kind, x, y_diff, wf, d["p"]["l"], cols, [gn] * nf, "VSS" if kind == "n" else "VDD", rail_y)

    # ---------------------------------------------------------------- NMOS row
    x = 0.8 + STRIP_W
    gap = 0.8
    rail_top_n = N_RING_Y0 + STRIP_W
    for d in mosfets:
        if "nfet" in d["model"]:
            x = draw(d, x, N_DIFF_Y, rail_top_n) + gap

    # ---------------------------------------------------------------- bias resistor
    xres = next(d for d in devs if "res_xhigh" in d["model"])
    res_x0 = x + 0.7
    head_a, head_b, res_right = xhigh_resistor(cv, res_x0, N_DIFF_Y, xres["p"]["l"], 4)
    ports.add(xres["nodes"][0], head_a[0], head_a[1])
    ports.add(xres["nodes"][1], head_b[0], head_b[1])
    ring_x1 = res_right + 0.8
    tap_ring(cv, "n", 0.0, N_RING_Y0, ring_x1, N_RING_Y1, ("b",))

    # ---------------------------------------------------------------- middle zone
    # Above the channel, to the right of the p-tap ring: per half, the two MIM
    # caps (bottom plate = shared OUTI net) and the series poly resistor.
    mx = ring_x1 + 4.0
    my = CH_Y1 + 3.0
    caps = [d for d in devs if "cap_mim" in d["model"]]
    sers = [d for d in devs if "res_generic_po" in d["model"]]
    for half in ("_DP", "_DM"):
        for c in (c for c in caps if c["name"].endswith(half)):
            side = c["p"]["w"]
            assert c["p"]["w"] == c["p"]["l"]
            # nodes: top-plate net, bottom-plate net (a symmetric device; the
            # shared OUTI net takes the bottom plate)
            a, b = c["nodes"]
            bot, top = (b, a) if b.startswith("OUTI") else (a, b)
            mx = mim_cap(cv, ports, mx, my, side, bot, top) + 3.0
        for r in (r for r in sers if r["name"].endswith(half)):
            mx = generic_poly_resistor(cv, ports, mx + 1.0, my, r["p"]["w"], r["p"]["l"], tuple(r["nodes"])) + 4.0
    mid_x1 = mx

    # ---------------------------------------------------------------- PMOS row
    pstart = mid_x1 + 0.9 + STRIP_W + 0.5
    p_diff_y = P_DIFF_TOP - P_WMAX
    px = pstart
    for d in mosfets:
        if "pfet" in d["model"]:
            px = draw(d, px, p_diff_y, P_RAIL_Y) + gap
    p_x1 = px - gap
    nw_x0 = pstart - 0.9 - STRIP_W
    nw_x1 = p_x1 + 0.9 + STRIP_W + 0.5
    tap_ring(cv, "p", nw_x0, P_RING_Y0, nw_x1 - 0.5, P_RING_Y1, ("t", "b"))
    cv.rect("nwell", nw_x0 - 0.5, NW_Y0, nw_x1, NW_Y1)
    # 5 V devices: hvi over each region (n-well is a high-voltage well)
    cv.rect("hvi", -0.4, N_RING_Y0 - 0.4, ring_x1 + 0.4, N_RING_Y1 + 0.4)
    cv.rect("hvi", nw_x0 - 0.9, NW_Y0 - 0.4, nw_x1 + 0.4, NW_Y1 + 0.4)
    # VDD reaches the channel through the n-well ring's bottom rail strip
    ports.add("VDD", nw_x0 + 0.65, P_RING_Y0 + STRIP_W / 2)

    # ---------------------------------------------------------------- routing
    by_net: dict[str, list[tuple[float, float, str]]] = {}
    for net, px_, py_, kind in ports.items:
        by_net.setdefault(net, []).append((px_, py_, kind))
    assert set(by_net) == set(trunk_nets), set(by_net) ^ set(trunk_nets)
    for net in trunk_nets:
        pts = by_net[net]
        ty = ty_of[net]
        xs_ = [p[0] for p in pts]
        cv.rect("met3", min(xs_) - 0.3, ty - TRUNK_W / 2, max(xs_) + 0.3, ty + TRUNK_W / 2)
        for vx, vy, kind in pts:
            if kind == "m4":
                cv.centred("via3", vx, ty, V3, V3)
                cv.rect("met4", vx - M4_W / 2, min(vy, ty) - M4_W / 2, vx + M4_W / 2, max(vy, ty) + M4_W / 2)
                continue
            if kind == "m1":
                cv.centred("via1", vx, vy, V1, V1)
                cv.centred("met1", vx, vy, PAD, PAD)
            else:
                cv.centred("via2", vx, vy, V2, V2)
                cv.centred("met2", vx, vy, V2_PAD, V2_PAD)
            cv.rect("met2", vx - PAD / 2, min(vy, ty) - PAD / 2, vx + PAD / 2, max(vy, ty) + PAD / 2)
            cv.centred("met2", vx, ty, V2_PAD, V2_PAD)
            cv.centred("via2", vx, ty, V2, V2)
        if net in PIN_NETS:
            cv.label("met3_label", net, min(xs_), ty)
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
