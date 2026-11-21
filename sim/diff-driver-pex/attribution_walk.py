#!/usr/bin/env python3
"""Independent attribution of the extracted pad-lead resistance. See sim/README.md.

Reproduces, without `klt extract`, the lumped series resistance the curated
sky130 parasitics model assigns to one named net of the committed
differential_driver GDS: walks the net's conductor geometry (met3 label ->
via2 -> met2 -> via1 -> met1 -> mcon -> li1 -> licon -> poly, stopping at
device-marked regions: poly_res 66/13 and urpm 79/20), then applies the
documented per-fragment kernel (klayout_tools extract_parasitics.py
`_n_squares`: equivalent rectangle from each fragment's own area and
perimeter, squares = L/W >= 1) with the deck's published per-role sheet
resistances (poly 48.2, li1 12.8, met1 0.125, met2 0.125, met3 0.047,
met4 0.047 ohm/sq) and prints the per-layer, per-fragment contribution.

    python3 sim/diff-driver-pex/attribution_walk.py DM DP

Used by records/20261121-013701-e0b9d95-static.md: the walk's totals match
the extractor's own R<NET>_t0 cards to 0.03 ohm, and the per-fragment detail
attributes ~99% of the pad-lead resistance to the directional square-count
of two device-head fragments (a 0.8 x 20 um poly head charged as 25 squares
and a 0.33 x 20 um li1 head charged as 60 squares -- current crosses each
fragment's short axis, so the true count is ~W/L, not L/W).
"""

import math
import sys

import klayout.db as kdb

GDS = "layout/analog/differential_driver/differential_driver.gds"
CONDUCTORS = ["66/20", "67/20", "68/20", "69/20", "70/20", "71/20"]  # poly li1 met1..met4
CUTS = {"66/44": ("66/20", "67/20"), "67/44": ("67/20", "68/20"), "68/44": ("68/20", "69/20"),
        "69/44": ("69/20", "70/20"), "70/44": ("70/20", "71/20")}
SHEET = {"66/20": 48.2, "67/20": 12.8, "68/20": 0.125, "69/20": 0.125, "70/20": 0.047, "71/20": 0.047}
DEVICE_MARKS = {"66/13": "poly_res", "79/20": "urpm"}  # device-consumed poly, not net conductor


def main(argv=None) -> int:
    names = (argv[1:] if argv else None) or ["DM", "DP"]
    layout = kdb.Layout()
    layout.read(GDS)
    dbu = layout.dbu
    top = layout.top_cell()
    ly = {f"{layout.get_info(li).layer}/{layout.get_info(li).datatype}": li
          for li in layout.layer_indexes()}

    def regions(layer):
        r = kdb.Region()
        it = top.begin_shapes_rec(ly[layer])
        while not it.at_end():
            s = it.shape()
            if s.is_polygon() or s.is_box() or s.is_path():
                r.insert(s.polygon)
            it.next()
        return r.merged()

    cond = {c: regions(c) for c in CONDUCTORS}
    marked = sum((regions(m) for m in DEVICE_MARKS), kdb.Region())
    cond["66/20"] = cond["66/20"] - marked  # device bodies are not net conductor
    cuts = {c: regions(c) for c in CUTS}

    def squares(region):
        out = []
        for p in region.each():
            a, per = p.area() * dbu * dbu, p.perimeter() * dbu
            if a <= 0 or per <= 0:
                continue
            disc = (per / 2) ** 2 - 4 * a
            if disc < 0:
                sq = 1.0
            else:
                long_ = (per / 2 + math.sqrt(disc)) / 2
                sq = max(long_ / (a / long_), 1.0)
            out.append((a, sq))
        return out

    labels = {}
    for li in layout.layer_indexes():
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            s = it.shape()
            if s.is_text() and s.text.string in names:
                lp = layout.get_info(li)
                labels[s.text.string] = (s.text.trans.disp.x * dbu, s.text.trans.disp.y * dbu,
                                         f"{lp.layer}/{lp.datatype}")
            it.next()

    for name in names:
        lx, ly_, layer = labels[name]
        assert layer == "70/5", f"{name} label on {layer}, expected the met3 label layer"
        box = kdb.Box(int((lx - 0.2) / dbu), int((ly_ - 0.2) / dbu),
                      int((lx + 0.2) / dbu), int((ly_ + 0.2) / dbu))
        touched = {"70/20": cond["70/20"].interacting(kdb.Region(box))}
        frontier = ["70/20"]
        while frontier:
            cur = frontier.pop()
            for cut, (a, b) in CUTS.items():
                other = b if cur == a else (a if cur == b else None)
                if other is None:
                    continue
                hit = cuts[cut].interacting(touched[cur])
                if hit.is_empty():
                    continue
                new = cond[other].interacting(hit) - touched.get(other, kdb.Region())
                if new.is_empty():
                    continue
                touched[other] = touched.get(other, kdb.Region()) + new
                frontier.append(other)
        total = 0.0
        print(f"net {name} (device regions {sorted(DEVICE_MARKS.values())} excluded):")
        for c in CONDUCTORS:
            if c not in touched or touched[c].is_empty():
                continue
            frags = squares(touched[c])
            r_ = sum(sq for _, sq in frags) * SHEET[c]
            total += r_
            for a, sq in frags:
                print(f"  {c}: fragment area={a:.2f} um2 squares={sq:.2f} -> {sq * SHEET[c]:.2f} ohm")
        print(f"  TOTAL {total:.2f} ohm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
