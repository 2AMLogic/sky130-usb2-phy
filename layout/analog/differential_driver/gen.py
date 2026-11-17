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

import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_common import (  # noqa: E402
    GC_Y,
    L,
    LIC,
    PAD,
    POLY_ENDCAP,
    POLY_TOP,
    Ports,
    SD_W,
    STRIP_W,
    Canvas,
    contacts_y,
    mos,
    res_generic_po,
    run_gds,
    tap_ring,
    xhigh_resistor,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
GDS = HERE / "differential_driver.gds"
NETLIST = REPO / "design" / "netlist" / "differential_driver.spice"
TOP = "differential_driver"


# --- drawn dimensions, um (all on the 0.005 grid) ---------------------------
V1 = 0.15  # via1 edge
V2 = 0.20  # via2 edge
V3 = 0.20  # via3 edge
TRUNK_W = 0.40  # met3 trunk width
TRUNK_PITCH = 0.70  # met3 trunk pitch
V2_PAD = 0.38  # met2 pad around via2 (0.09 enclosure on the sides)
M4_W = 0.40  # met4 strip / pad width
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
        return mos(
            cv, ports, kind, x, y_diff, wf, cols, [gn] * nf,
            "VSS" if kind == "n" else "VDD", rail_y, gl=d["p"]["l"], supply=SUPPLY,
        )

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
            rys = contacts_y(r["p"]["w"])
            mx = res_generic_po(cv, ports, mx + 1.0, my, r["p"]["w"], r["p"]["l"], tuple(r["nodes"]),
                                rys, 0.145, rys[0], "m1") + 4.0
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


if __name__ == "__main__":
    sys.exit(run_gds(GDS, build, __doc__.splitlines()[0]))
