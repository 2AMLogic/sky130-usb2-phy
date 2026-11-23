#!/usr/bin/env python3
"""Render the single-ended receiver testbench inputs from one shared source (stdlib only).

The D+ and D- threshold experiments (`sim/se-receiver-dp-thresholds`,
`sim/se-receiver-dm-thresholds`) and the D+ / D- Monte Carlo decks of
`sim/se-receiver-mismatch` carry specs that differ only by the leaf identity.
This renders all six files from one per-leaf parameterisation, the testbench-side
counterpart of `layout/analog/gen_se_receiver.py` on the layout side of the same
pair. The sibling cross-reference in the threshold decks is its own parameter:
each deck points at the *other* experiment, so the pair is not producible by any
uniform dp->dm substitution of one file.

    python3 make_se_receiver_tb.py           # rewrite the six files
    python3 make_se_receiver_tb.py --check   # exit 1 if a committed file is stale
"""

import json
import sys
from pathlib import Path

SIM = Path(__file__).resolve().parent
DERIVED_BY = "* Derived by sim/make_se_receiver_tb.py; do not edit by hand."

# leaf -> (line node, output node, polarity, sibling leaf). The sibling identity is
# data, not a substitution: it is what the threshold decks cross-reference.
LEAVES = {
    "dp": ("DP", "RXDP", "D+", "dm"),
    "dm": ("DM", "RXDM", "D-", "dp"),
}


def params(leaf):
    din, rxout, pol, sib = LEAVES[leaf]
    return {
        "leaf": leaf,
        "din": din,                      # DP / DM, the swept line node
        "rxout": rxout,                  # RXDP / RXDM, the logic output
        "rxl": "rx" + leaf,             # rxdp / rxdm, the .meas node
        "rxdd": "rxdd" + leaf[-1],      # rxddp / rxddm, the MC deck instance node
        "pol": pol,                      # D+ / D-
        "cell": f"se_receiver_{leaf}",
        "exp": f"se-receiver-{leaf}-thresholds",
        "sib": sib,
        "sib_pol": LEAVES[sib][2],
        "sib_exp": f"se-receiver-{sib}-thresholds",
    }


def tb_spec(p):
    method = [
        f"Stimulus: the line input {p['din']} swept 0 V to 3.0 V, 1 mV step (3001 points), ideal source; supply = swept I/O rail vsup (3.0 / 3.3 / 3.6 V). 3.0 V is the lowest matrix supply, so the input never exceeds the rail.",
        f"Output polarity: non-inverting, {p['rxout']}=1 (high) when {p['din']} is above the internal VREF threshold. Output decision level: {p['rxout']} crosses VDD/2 of the corner supply (node `half`).",
        f"Switching threshold `vth_v`: the first rising crossing of {p['rxout']} through VDD/2 (`.meas dc ... WHEN v({p['rxl']})=v(half) RISE=1`), resolved by interpolation between 1 mV points. Ratified row VIH > 2.0 V, VIL < 0.8 V: read as 'an input at or above 2.0 V reads high and an input at or below 0.8 V reads low', so the crossing must lie strictly inside (0.8 V, 2.0 V); checked with exclusive bounds (`gt` 0.8 / `lt` 2.0), so an endpoint value fails. A missing or non-finite crossing fails the corner; an inverted receiver has no rising crossing and fails.",
        "Single crossing / monotonic: `vth_last_v` is the last crossing in either direction (`CROSS=LAST`); it must equal `vth_v` within one sweep step (1 mV, check `same_as`). A response that crosses more than once (non-monotonic, or rising then falling) fails.",
        f"Valid levels beyond the window (correct polarity throughout, not a single crossing): `rxd_low_max_v` = maximum of {p['rxout']} over {p['din']} in [0, 0.8] V must be <= 0.1 x VDD; `rxd_high_min_v` = minimum of {p['rxout']} over {p['din']} in [2.0, 3.0] V must be >= 0.9 x VDD. `rxd_at_vil_v` / `rxd_at_vih_v` are the boundary probes at exactly 0.8 V and 2.0 V, checked with the same bounds.",
        f"Output bounds (engineering criteria for the 3.3 V-domain {p['rxout']}, not USB driver VOH/VOL limits): high >= 0.9 x VDD and low <= 0.1 x VDD of the corner supply.",
        "`vref_v`: the internal divider reference (node `xrx.vref`) at input 0 V, checked as a fraction of the corner supply against a 0.35-0.50 sanity bound (design value about 0.425); not a spec row.",
        "`isup_ua`: receiver supply current (bias + divider) at input 1.4 V; sanity bound 1-500 uA, not a spec row.",
    ]
    variant_extra = [
        "Resistor coverage: each point's process section is one of 25 pinned-library sections = 5 MOS corners x {typical, ll, hh, hl, lh}; the section -> (MOS file, resistor set, capacitor set) mapping and the resolved library includes are recorded in evidence.json (`sections`) and checked by the lint against the approved map. The bare sections `ll`, `hh`, `hl`, `lh` carry the tt MOS corner.",
        "Compatibility: this record is a supplement to, not a replacement for, the 45-point records (res_typical only); those records are unchanged and keep their own frozen matrix.",
        "Coverage: all 225 unique PVT/section points are judged with the unchanged exclusive (0.8 V, 2.0 V) crossing bounds, single-crossing, output-level, reference and current checks above.",
    ]
    return {
        "name": p["exp"],
        "description": f"sky130 single-ended {p['pol']} receiver (design/{p['cell']}.sch) with the line input {p['din']} swept 0...3.0 V, across the 45-point PVT matrix.",
        "claim": f"Switching threshold and output logic levels of the sky130 single-ended {p['pol']} receiver over the 45-point PVT matrix (spec/usb2-phy.md section 6 row 'Single-ended receiver thresholds': VIH > 2.0 V, VIL < 0.8 V). Schematic-level, deterministic, no mismatch (no Monte Carlo), no layout parasitics; not a signoff or catalog-tier claim.",
        "netlist": f"se_rx_{p['leaf']}_tb.spice",
        "include": [f"../../../design/netlist/{p['cell']}.spice"],
        "analysis": {"kind": "dc", "args": "vin 0 3.0 0.001"},
        "timeout_s": 900,
        "measure": {
            "vth_v": {"spice": f".meas dc vth_v WHEN v({p['rxl']})=v(half) RISE=1"},
            "vth_last_v": {"spice": f".meas dc vth_last_v WHEN v({p['rxl']})=v(half) CROSS=LAST"},
            "rxd_low_max_v": {"spice": f".meas dc rxd_low_max_v MAX v({p['rxl']}) FROM=0 TO=0.8"},
            "rxd_high_min_v": {"spice": f".meas dc rxd_high_min_v MIN v({p['rxl']}) FROM=2.0 TO=3.0"},
            "rxd_at_vil_v": {"spice": f".meas dc rxd_at_vil_v FIND v({p['rxl']}) AT=0.8"},
            "rxd_at_vih_v": {"spice": f".meas dc rxd_at_vih_v FIND v({p['rxl']}) AT=2.0"},
            "vref_v": {"spice": ".meas dc vref_v FIND v(xrx.vref) AT=0"},
            "isup_ua": {"spice": ".meas dc isup_ua FIND i(vi) AT=1.4", "scale": 1000000.0},
        },
        "checks": {
            "vth_v": {"gt": 0.8, "lt": 2.0},
            "vth_last_v": {"gt": 0.8, "lt": 2.0, "same_as": {"measure": "vth_v", "tol": 0.001}},
            "rxd_low_max_v": {"max": 0.1, "per_supply": True},
            "rxd_high_min_v": {"min": 0.9, "per_supply": True},
            "rxd_at_vil_v": {"max": 0.1, "per_supply": True},
            "rxd_at_vih_v": {"min": 0.9, "per_supply": True},
            "vref_v": {"min": 0.35, "max": 0.5, "per_supply": True},
            "isup_ua": {"min": 1.0, "max": 500.0},
        },
        "record": {
            "netlist_provenance": f"schematic-derived netlist: xschem export of design/{p['cell']}.sch (design/netlist/{p['cell']}.spice, byte-identical to the deck frozen in the snapshot below) plus the testbench deck; no layout, no parasitic extraction",
            "statistical_convention": "deterministic PVT corners only (5 process x 3 temperature x 3 supply); mismatch / Monte Carlo was NOT run, so comparator offset and VREF divider mismatch are not covered by this record",
            "bounds": "the ratified limits and engineering criteria in the Method section (tb.json checks)",
            "footer": "Scope: schematic-level electrical evidence for one block against the ratified single-ended receiver threshold row. It does not claim layout, DRC/LVS, mismatch, level shifting or signoff, and does not relax any target. A FAIL record is evidence of failure, not compliance.",
            "detailed": True,
            "method": method,
        },
        "variants": {
            "resistor-sets": {
                "matrix_id": "pvt225-mos-rc",
                "claim": f"Switching threshold and output logic levels of the sky130 single-ended {p['pol']} receiver over the 225-point resistor-set matrix (the 45 temperature/supply/MOS points of the base experiment repeated for each of the five pinned-library resistor/capacitor parameter sets typical, ll, hh, hl, lh; sim/corners-resistor-sets.json, spec/decision-records/0005-resistor-sheet-resistance-corner-coverage.md) (spec/usb2-phy.md section 6 row 'Single-ended receiver thresholds': VIH > 2.0 V, VIL < 0.8 V). Schematic-level, deterministic, no mismatch (no Monte Carlo), no layout parasitics; not a signoff or catalog-tier claim.",
                "record": {
                    "statistical_convention": "deterministic corners only (5 MOS corners x 5 resistor/capacitor parameter sets x 3 temperature x 3 supply); mismatch / Monte Carlo was NOT run, so comparator offset and VREF divider mismatch is not covered. The suffixed sections (ll, hh, hl, lh) select the pinned library's res_low/res_high and cap_low/cap_high sets together with the matching drawn-width tolerances (tol_*); the VREF divider (R1/R2, whose ratio sets the threshold) and the bias resistor respond through the PDK's global resistor parameters, so these are the PDK's own sheet-resistance corners but they are not resistor-only sections, and the PDK ships them as global corners (all resistors and capacitors move together), not as per-device spread. Independent mismatch between the divider resistors R1 and R2 is therefore NOT covered",
                    "method": method + variant_extra,
                    "footer": "Scope: schematic-level electrical evidence for one block against the ratified single-ended receiver threshold row. It covers the PDK's global resistor/capacitor corner sets only (deterministic schematic evidence). It does not claim per-device resistor or MOS mismatch, Monte Carlo, layout parasitics, layout, DRC/LVS, level shifting or signoff, and does not relax any target. A FAIL record is evidence of failure, not compliance."
                }
            }
        }
    }


def thresholds_deck(p):
    return f"""{DERIVED_BY}
* {p['exp']} -- sky130 single-ended {p['pol']} receiver switching threshold and output levels
*
* Circuit body for `klt sim`. The design netlist (design/netlist/{p['cell']}.spice)
* is appended by the runner (tb.json "include") and frozen into the immutable snapshot.
* The request supplies the .lib corner section, .temp and the supply sweep (vsup).
*
* Row (spec/usb2-phy.md section 6, "Single-ended receiver thresholds"): VIH > 2.0 V,
* VIL < 0.8 V. Read as: an input at or above 2.0 V must read high and an input at or
* below 0.8 V must read low, so the switching threshold must sit strictly inside
* (0.8 V, 2.0 V) and the output must be a valid logic level (not merely past mid-rail)
* everywhere in [0, 0.8] V and [2.0, 3.0] V. Both halves are measured (tb.json).
*
* Stimulus: one DC sweep of the line input {p['din']} from 0 V to 3.0 V in 1 mV steps
* (3001 points). 3.0 V is the lowest supply of the matrix, so the input never exceeds
* the receiver's own rail. The line source is ideal (zero source impedance).
* The {p['sib_pol']} receiver is a separate cell with its own experiment
* (sim/{p['sib_exp']}/).

vsup vdd 0 dc 3.3
vi vdd vddr dc 0
vin in 0 dc 0
ehalf half 0 vol='v(vdd)/2'
xrx vddr 0 in {p['rxl']} {p['cell']}
"""


def mc_deck(p):
    return f"""{DERIVED_BY}
* se-receiver-mismatch ({p['pol']}) -- sky130 single-ended {p['pol']} receiver switching threshold under local device mismatch
*
* Circuit body for `klt sim` Monte Carlo (sim/run_mismatch.py). The design netlist
* (design/netlist/{p['cell']}.spice) is appended by the runner (mc.json "include") and
* frozen into the immutable per-campaign snapshot. The request supplies the `*_mm` .lib
* section (mc_mm_switch=1), .temp, the supply (vsup) and the per-sample seed.
*
* Same stimulus and measurements as sim/{p['exp']}: the line input is swept
* 0 - 3.0 V in 1 mV steps. The threshold depends on the R1/R2 divider ratio (both
* res_xhigh_po_1p41, independent mismatch per instance) and on the comparator offset (MOS
* mismatch). The deterministic negative control replaces exactly the XR2 length 14 in the
* appended design netlist with 60 (a fixed divider-ratio skew that moves VREF past 2.0 V).

vsup vdd 0 dc 3.3
vi vdd vddr dc 0
vin in 0 dc 0
ehalf half 0 vol='v(vdd)/2'
xrx vddr 0 in {p['rxdd']} {p['cell']}
"""


def targets():
    for leaf in LEAVES:
        p = params(leaf)
        yield f"se-receiver-{leaf}-thresholds/testbench/tb.json", json.dumps(tb_spec(p), indent=2) + "\n"
        yield f"se-receiver-{leaf}-thresholds/testbench/se_rx_{leaf}_tb.spice", thresholds_deck(p)
        yield f"se-receiver-mismatch/testbench/se_rx_{leaf}_mc_tb.spice", mc_deck(p)


def main(argv):
    check = "--check" in argv
    stale = []
    for rel, text in targets():
        dst = SIM / rel
        if check:
            if dst.read_text() != text:
                stale.append(rel)
        else:
            dst.write_text(text)
    if stale:
        print("stale testbench inputs (rerun without --check to rewrite):", file=sys.stderr)
        for rel in stale:
            print(f"  sim/{rel}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
