# `layout/analog/` — analog leaf layouts and the conventions they share

One directory per analog leaf, named after its subcircuit in
`design/netlist/`. Today `differential_receiver/` (issue #167),
`differential_driver/` (issue #220), the two single-ended receivers
`se_receiver_dp/` and `se_receiver_dm/` (issue #221), and `dplus_pullup/`
(issue #222) exist; all analog leaves in the porting plan now follow **these
conventions**. The two single-ended receivers differ only in the input and
output pin names. Each directory owns its outputs (GDS, reports, request and
spec files); the generator helpers are shared in `gen_common.py` (see below).

**This directory anchors no sign-off claim yet.** The analog rows of
`signoff/signoff-report.json` cover the whole analog partition, so items 2
(layout), 3 (DRC), 4 (LVS) and the supply half of 11 stay unmet until every
leaf has evidence like `differential_receiver`'s. Nothing here is cited from
`signoff/block-manifest.json`. No layout here is post-layout verified (item 7
is not started) and none is matched-layout or density closed.

Everything is re-derived for sky130 from the committed netlists. A gf180
placement plan is source evidence for *topology*, never geometry
(`CLAUDE.md`, scope discipline).

## Shared generator helpers: `gen_common.py`

`snap`, `Canvas`, `contacts_y`, `Ports`, `mos` and `tap_ring` (with the
dimensions they depend on) live once in `gen_common.py`; operator ruling
2026-10-29 (#238) allowed shared *code* while outputs stay per leaf. A change
there must leave every committed GDS byte-identical: run `python3
layout/analog/<block>/gen.py --check` for all five leaves. Each `gen.py` keeps
its own layer table, `TOP` and `build()`.

Deliberate leaf-local variants, not yet reconciled into the shared helpers:

- `differential_driver/gen.py` keeps its own `Ports` and `mos` (per-gate
  length `gl`, supply-net asserts, `m1`/`m3`/`m4` landing kinds).
- `resistor`: three variants (`differential_receiver`, `dplus_pullup`, and the
  identical `se_receiver_dp`/`se_receiver_dm` pair) plus the driver's
  `xhigh_resistor`/`generic_poly_resistor`, each tied to its block's geometry.

## What a leaf directory contains

| File | What it is |
|---|---|
| `<block>.gds` | The layout. Top cell is named after the subcircuit, so the LVS top matches. |
| `gen.py` | The generator: the block-specific `build()` plus the shared helpers imported from `../gen_common.py`. `klayout.db` only, sky130 layer numbers inline, **no timestamps**: `gen.py --check` re-emits the stream and compares sha256 with the committed file. A hand-edited GDS is not acceptable here: it cannot be reproduced. |
| `request-lvs.json` | `klt lvs` request (`klayout-runset`, the PDK's own `sky130.lvs`). Repo-relative paths and a `$PDK_ROOT` placeholder; `run_checks.py` writes the absolute copy. |
| `erc-supply-spec.json` | `klt erc` supply spec: supply nets, `ties[]`, the resistor `devices[]` carve-out. Every field is justified in its `_comment`. |
| `drc-report.json`, `drc-native-report.json`, `lvs-report.json`, `erc-supply-report.json` | `klt`'s own JSON, verbatim, from the last `run_checks.py` run. The frozen copy that evidence cites lives under `flow/analog-layout-<block>/artifacts/<record-id>/`. |
| `run_checks.py` | Runs `gen.py --check`, both DRC decks, LVS and ERC through `klt`; `--record` mints the append-only record (see `flow/README.md`, "Analog layout records"). |

```bash
PDK=sky130A python3 layout/analog/differential_receiver/run_checks.py            # reports only
PDK=sky130A python3 layout/analog/differential_receiver/run_checks.py --record   # + the record
```

`run_checks.py` resolves the PDK through `flow/run_flow.py`'s
`resolve_pdk_root`, which refuses an open_pdks tree that differs from the repo
pin (`sim/corners.json`, #151). It never calls `klayout` directly.

## Floorplan

```
 +--------------------------------------------------+  nwell + hvi, tap ring, VDD rail on top
 |  PMOS row (diff top-aligned, S columns up to VDD)|
 +--------------------------------------------------+
        channel: met3 trunks, one per signal net, 0.70 um pitch
 +--------------------------------------------------+  p-tap ring, VSS rail on the bottom
 |  NMOS row (diff bottom-aligned, S columns down)  |  (also encloses the poly resistor)
 +--------------------------------------------------+
```

* NMOS at the bottom, PMOS above in its own n-well, signals between. Every
  device's S/D columns and gates exit **toward the channel**; sources tied to a
  supply exit **toward that supply's rail** instead, so the rails need no
  other routing.
* Devices are folded: `m` in the netlist becomes that many fingers, each at
  most 10 um wide (`W = 20, m = 1` is two 10 um fingers). Fingers share
  diffusion, so `XMN_INA` (`W = 10, m = 2`) and `XMN_INB` are one four-gate
  diffusion, **interdigitated A B B A** with a common source column.
  The load mirror (`XMP_LOADA`/`XMP_LOADB`, `m = 4` each) is one eight-gate
  diffusion laid **A A B B B B A A** (gate pairs share a drain column). The bias
  mirror (`XMNBIAS`/`XMTAIL`) is two separate diffusions, not interdigitated.
  A formal matching analysis is not claimed for any of them.
* A multi-finger device is one drawn shape of diffusion, with one li1 + mcon +
  met1 stripe per source/drain column and an individually contacted poly
  stripe per gate. There is no poly bar: parallel gates are joined by the
  channel route.

## Rails and guard rings

* **VSS** is the met1 strip on the bottom of the p-tap ring; **VDD** is the met1
  strip on the top of the n-tap ring inside the n-well. These strips are the
  rails and the pins; both carry the pin label.
* Each region (NMOS row plus resistor; PMOS row) is enclosed by a **closed
  tap ring**: `tap` (65/44) strips 0.29 um wide with `nsdm` (n-well) or `psdm`
  (substrate), li1 over the whole ring, licon every 0.72 um, and mcon + met1
  only on the rail side. The ring is what the `klt erc` ties declare.
* The n-well extends 0.5 um beyond its ring. `hvi` (75/20) covers the whole
  block (both rows, both rings), because the n-well is a high-voltage well
  (`nwell.enclosed.hvi.1`) and every device is the 5 V-gate class.
* The poly resistor sits inside the substrate ring so its bulk terminal reaches
  VSS through the same tap.

## Routing layers

| Layer | Use |
|---|---|
| li1 / mcon / met1 | inside a device: column stripes, gate pads, rails |
| met2 | vertical drops from a device landing pad to its net's trunk |
| met3 | horizontal **trunk**, one per signal net, 0.40 um wide, 0.70 um pitch, labelled if the net is a pin |
| via1 / via2 | pad to met2, met2 to trunk, one stack per landing pad |

`gen.py` shifts the PMOS row until no PMOS and NMOS landing pad lie within met2
spacing of each other where their drops share a y-range. Adding a landing pad
means re-running that search, not hand-placing it.

## Pin labels

* Only **cell pins** are labelled: `VDD`/`VSS` on met1 (68/5) of their rail,
  signal pins on met3 (70/5) of their trunk.
* **Internal nets are never labelled.** `sky130.lvs` turns every labelled net
  into a circuit pin, so labelling `TAIL` gives the layout one more pin than the
  schematic and nothing matches.
* Pin names are the schematic's, upper case, exactly.

## Device recognition (what the SKY130 LVS runset needs)

* 5 V devices: `diff` + `poly` + `nsdm`/`psdm`, `hvi` over the gate. n-well for p-devices.
  `sky130_fd_pr__{n,p}fet_g5v0d10v5`, L = 0.5 um.
* Poly contacts need `npc` (95/20) around the licon; diffusion contacts must not
  have it.
* Poly resistor `sky130_fd_pr__res_xhigh_po_1p41`: poly 1.41 um wide, `poly_res`
  (66/13) and `urpm` (79/20) over the body but **not** over the two contact heads,
  `psdm` over everything. The runset reads `L` as area / width, so a serpentine
  is fine and its mitred corners count once; `gen.py` sizes the legs so the
  centreline is the netlist's `L` (checked: 139.98 um against 140 um, inside the
  runset's 0.5 % tolerance).
* The runset needs `convert_subckts=true scale=true` to read the xschem netlists
  (set in `request-lvs.json`; klayout-tools#3989).

## Checks and what each one does not say

* `klt drc` with the **curated** sky130 deck is the committed verdict and is
  `clean`. Its `coverage` block is quoted in the record: it cannot see the
  5 V rule columns (`voltage_domain_warnings`), so a second run with the
  **PDK-native** `sky130A_mr.drc` (`--expect-rule-categories` pins its 244
  categories; without it a zero-finding native run is `coverage_unknown`)
  is committed beside it. Neither is a foundry signoff run.
* `klt lvs` is `match` only against the schematic netlist; `body_verification`
  is `null` for the runset engine, and `power_connectivity` is `unchecked`
  because the extraction is flat transistor-level.
* `klt erc` reads VDD and VSS as one island each. The well tie is checked from
  the drawn n-well; the substrate tie is checked from the region *outside* the
  n-well (`well_complement_of`), an assertion about where substrate is, not a
  drawn well layer. The overall status is `clean_partial` because the antenna
  table has no met3 limit: item 11 is graded from the supply findings, not the status.
* Not done and not claimed: dummy devices, density/fill, antenna closure above
  met2, parasitic extraction, matched-layout analysis, any simulation of the layout.

## `differential_driver/` differences

The driver (issue #220) follows the conventions above; what is new:

* **Floorplan.** Three disjoint x zones: NMOS row (+ the `res_xhigh_po_1p41`
  bias resistor) in one p-tap ring, then the MIM caps and series poly resistors
  above the channel, then the PMOS row in one n-well. Disjoint zones mean no
  NMOS and PMOS met2 drop can share a y-range within spacing, so there is no
  placement search. `gen.py` reads every device (nets, `W`, `L`, `mult`) from
  `design/netlist/differential_driver.spice` and folds `W > 10 um` and `mult`
  into fingers of at most 10 um.
* **VDD is a routed net.** The bias resistor sits in the p-substrate ring but
  ties to VDD, so the n-well ring's bottom strip is also a rail (met1) and a
  met3 trunk carries VDD to the resistor head.
* **MIM caps** (`sky130_fd_pr__cap_mim_m3_1`): met3 bottom plate (the shared
  `OUTI_*` net, with a tab carrying the via2 outside the `capm`), `capm`
  (89/44), and a met4 strap from a via3 on the `capm` down to the net's trunk.
* **Generic poly resistor** (`res_generic_po`): poly bar under the `poly_res`
  marker only (no `urpm`), contacted heads outside the marker.
* **LVS is not a match today.** The PDK's `sky130.lvs` extracts a MIM as
  `sky130_fd_pr__model__cap_mim` but its `convert_subckts` device list does not
  contain the xschem export's `sky130_fd_pr__cap_mim_m3_1`, so the reference
  loses the four caps (and merges the nets they bridge) while the layout has
  four unmatched capacitors. The other 76 devices and all 8 pins pair. The
  committed `lvs-report.json` says `mismatch`; no record is minted until it
  matches (`run_checks.py --record` refuses a failing run).

