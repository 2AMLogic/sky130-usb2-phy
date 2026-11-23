# `layout/analog/` — analog leaf layouts and the conventions they share

One directory per analog leaf, named after its subcircuit in
`design/netlist/`. Today `differential_receiver/` (issue #167),
`differential_driver/` (issue #220), the two single-ended receivers
`se_receiver_dp/` and `se_receiver_dm/` (issue #221), and `dplus_pullup/`
(issue #222) exist; all analog leaves in the porting plan now follow **these
conventions**. The two single-ended receivers differ only in the input and
output pin names. Each directory owns its outputs (GDS, reports, request and
spec files); the generator helpers are shared in `gen_common.py` (see below).

**This directory's frozen records are cited from `signoff/block-manifest.json`.**
The five layout streams supply item 2 (analog, `met`). The latest frozen DRC,
curated LVS and supply-ERC reports supply items 3, 4 and 11. The pinned klt
0.9.2 grader reports `met` for DRC, `unmet / check_failed` for LVS, and
`unmet / lvs_did_not_pass` for power delivery.
See the [signoff verdicts](../../signoff/README.md). No layout here
is post-layout verified (item 7 is not started) and none is matched-layout or
density closed.

Everything is re-derived for sky130 from the committed netlists. A gf180
placement plan is source evidence for *topology*, never geometry
(`CLAUDE.md`, scope discipline).

## Shared generator helpers: `gen_common.py`

`snap`, `Canvas`, `contacts_y`, `Ports`, `mos`, `tap_ring`, the sky130A layer
table `L`, the `--check`/`-o` GDS CLI (`run_gds`, per-leaf `--help` description
passed in) and the poly-resistor builders `xhigh_resistor` and `res_generic_po`
(with the dimensions they depend on) live once in `gen_common.py`; operator
ruling 2026-10-29 (#238) allowed shared *code* while outputs stay per leaf, and
asked that the module "reconcile the mos/resistor variants explicitly". A change
there must leave every committed GDS byte-identical: run `python3
layout/analog/<block>/gen.py --check` for all five leaves — CI-enforced: the
`signoff` job of `.github/workflows/ci.yml` globs `layout/analog/*/gen.py` and
runs `--check` on each under the pinned grader, so drift fails the PR. Each
`gen.py` keeps
its own `TOP` and `build()`, except the two se_receiver leaves (below).

## Shared check runner: `run_checks_common.py`

The DRC / LVS / ERC runner and the record writer live once in
`run_checks_common.py` (same #238 ruling: shared *code*, per-leaf *outputs*). Each
`<block>/run_checks.py` is a thin entry point holding only a `LeafConfig` (block,
issue, supply-net pair, record prose, extra provenance inputs) and, for
`differential_driver`, its `derive_lvs_reference` hook. The command
`python3 layout/analog/<block>/run_checks.py [--record]` is unchanged, and the
runner's path is deliberately not in a record's `provenance.inputs`. A change to the
runner must leave every leaf's reports byte-identical for unchanged inputs.

The poly-resistor family was reconciled into the shared helpers per ruling
#238 ("reconciles the mos/resistor variants explicitly"): the
`res_xhigh_po` serpentine is `gen_common.xhigh_resistor` (carrying the
two-leg `urpm.width.1` marker guard), and the `res_generic_po` bar is
`gen_common.res_generic_po`, parameterised over the two leaves' head
geometries.

`se_receiver_dm` and `se_receiver_dp` are the same circuit with two net names,
so their drawing (`build()`) lives once in `gen_se_receiver.py`, parameterised
by (leaf, input net, output net); the layer table and the resistor builders
come from `gen_common.py`. Each leaf's `gen.py` is a thin entry point and both
records pin both modules as provenance inputs (#240, #293).

`differential_receiver` is the same drawing with its second input (`DM`) a pin
instead of the VREF divider: `build(..., differential=True)` draws the lone
`XRBIAS` beside the NMOS row ahead of the PMOS row, where the single-ended
leaves put three resistors east of the n-well. The shape order and a 0.005 um
ring margin differ between the two modes on purpose, so the committed GDS of
all three leaves stays byte-identical (#336).

## What a leaf directory contains

| File | What it is |
|---|---|
| `<block>.gds` | The layout. Top cell is named after the subcircuit, so the LVS top matches. |
| `gen.py` | The generator: the block-specific `build()` plus the shared helpers imported from `../gen_common.py`. `klayout.db` only, sky130 layer numbers inline, **no timestamps**: `gen.py --check` re-emits the stream and compares sha256 with the committed file. A hand-edited GDS is not acceptable here: it cannot be reproduced. |
| `request-lvs.json` | `klt lvs` request (`klayout-runset`, the PDK's own `sky130.lvs`). Repo-relative paths and a `$PDK_ROOT` placeholder; `run_checks.py` writes the absolute copy. |
| `request-lvs-curated.json` | Standalone curated sky130 LVS request against the design netlist. Paths resolve from the leaf directory. |
| `erc-supply-spec.json` | `klt erc` supply spec: supply nets, `ties[]`, the resistor `devices[]` carve-out. Every field is justified in its `_comment`. |
| `drc-report.json`, `drc-native-report.json`, `lvs-report.json`, `lvs-curated-baseline-report.json`, `lvs-curated-report.json`, `erc-supply-report.json` | `klt`'s own JSON, verbatim, from the last `run_checks.py` run. The frozen copy that evidence cites lives under `flow/analog-layout-<block>/artifacts/<record-id>/`. |
| `run_checks.py` | Runs `gen.py --check`, both DRC decks, runset and curated LVS, and ERC through `klt`; `--record` mints the append-only record (see `flow/README.md`, "Analog layout records"). |

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
  centreline is the netlist's `L`. Snapping one leg height to the 0.005 um grid
  used to leave the drawn length 0.01-0.02 um off (30.01/139.98 um, #406);
  `gen_common.xhigh_resistor` now moves the first bottom U-turn by half the
  snap residual, which changes both its adjoining legs equally, and the
  area/width length lands exactly on the netlist `L` (30.00 and 140.00 um
  measured on the regenerated streams, the 14/19 um two-leg dividers
  unchanged).
* The runset needs `convert_subckts=true scale=true` to read the xschem netlists
  (set in `request-lvs.json`; klayout-tools#3989).

## Curated LVS by leaf

The records use the producer from the initial probe, klt
`0.9.2.dev111+g978f7464fae1`. Its curated DRC lists 54 unmodelled rules.
The preceding records from `0.9.3.dev310+ga638216e7fea` list 347. The
records minted for the #406 bias-resistor repair (and the D+ pull-up control
re-run that the shared-generator change made stale) use klt
`0.9.3.dev2626+g0e5dd121c7d2` with KLayout 0.30.12, whose curated DRC also
lists 347 unmodelled rules. The curated DRC rules checked and skipped, native
DRC rule categories and ERC checks are identical for each leaf across these
sets of records.

Both curated comparisons use the committed GDS and `design/netlist/<leaf>.spice`
with the sky130 subcircuit-call reader. The first preserves the default comparison
in `lvs-curated-baseline-report.json`. Its layout counts include individual MOS
fingers. For example, the differential receiver compares one 10 µm PFET finger
against a 20 µm reference PFET and reports the second 10 µm finger as unmatched.

The cited comparison checks MOS flavour and combines only parallel
`nfet__hvi` and `pfet__hvi` devices on each side. It compares resistor R, L
and W, and requests C, area and perimeter for the driver's MIM capacitors.
Without the passive geometry checks all five folded circuits match on topology.
Each leaf uses the same cited report for items 4 and 11. Both columns of counts
give layout / reference / matched devices.

| Leaf | Curated baseline (all mismatch) | Cited curated LVS | Device class unrecognised | Open issue |
|---|---:|---|---|---|
| `differential_driver` | 356/244/82 | [match (80/80/80)](../../flow/analog-layout-differential_driver/artifacts/20261122-001306-eb818d5-differential_driver/lvs-curated-report.json) | None | None |
| `differential_receiver` | 21/20/19 | [match (11/11/11)](../../flow/analog-layout-differential_receiver/artifacts/20261122-001342-eb818d5-differential_receiver/lvs-curated-report.json) | None | None |
| `dplus_pullup` | 265/40/10 | [match (20/20/20)](../../flow/analog-layout-dplus_pullup/artifacts/20261122-001541-eb818d5-dplus_pullup/lvs-curated-report.json) | None | None |
| `se_receiver_dm` | 23/22/21 | [match (13/13/13)](../../flow/analog-layout-se_receiver_dm/artifacts/20261122-001414-eb818d5-se_receiver_dm/lvs-curated-report.json) | None | None |
| `se_receiver_dp` | 23/22/21 | [match (13/13/13)](../../flow/analog-layout-se_receiver_dp/artifacts/20261122-001442-eb818d5-se_receiver_dp/lvs-curated-report.json) | None | None |

The curated LVS envelopes report aggregate counts. For the per-class census
below, each pair gives SPICE X-card instances before multiplier expansion /
drawn devices from `klt extract --deck sky130 --top <leaf> --no-netlist --format
json layout/analog/<leaf>/<leaf>.gds` (`device_counts`). The five source models
carry the `sky130_fd_pr__` prefix. The extractor labels their families `nfet`,
`pfet`, `res_generic_po`, `res_xhigh_po` and `sky130_fd_pr__model__cap_mim`.
The curated requests distinguish the high-voltage MOS flavours during LVS.
The frozen runset `device_census` independently gives counts after combining.

| Leaf | nfet_g5v0d10v5 | pfet_g5v0d10v5 | res_generic_po | res_xhigh_po_1p41 | cap_mim_m3_1 |
|---|---:|---:|---:|---:|---:|
| `differential_driver` | 37/139 | 36/210 | 2/2 | 1/1 | 4/4 |
| `differential_receiver` | 6/9 | 4/11 | 0/0 | 1/1 | 0/0 |
| `dplus_pullup` | 5/5 | 10/255 | 5/5 | 0/0 | 0/0 |
| `se_receiver_dm` | 6/9 | 4/11 | 0/0 | 3/3 | 0/0 |
| `se_receiver_dp` | 6/9 | 4/11 | 0/0 | 3/3 | 0/0 |

- **Bias resistor.** The generator now draws the exact netlist lengths: XRB
  measures 30.00 µm and each XRBIAS 140.00 µm at the 1.41 µm width (#406's
  first-bottom-U-turn correction in `gen_common.xhigh_resistor`), so every
  selected report reads `match` with complete device counts and no
  `device.property` or bias-net `topology` errors. The two-leg 14 and 19 µm
  VREF dividers and the D+ pull-up control are unchanged.
- **Driver MIM reference.** The curated reader accepts all four original
  X-cards (two 42 × 42 µm and two 24 × 24 µm plates) and compares their area
  and perimeter. Its `device_parameter_coverage` records four devices on each
  side. Reference capacitance is a placeholder. The derived runset reference
  also parses, but its scale convention changes the comparison. With the same
  geometry-aware options it matches 75/80 devices versus 79/80 with the
  design source (e.g. area 1,764 versus 1.764 × 10¹⁵ for a large plate).
- **D+ pull-up.** All 20 devices, 18 nets and 8 pins match with resistor
  geometry enabled. The five generic poly resistors compare on R, L and W.
  The envelope lists four warnings. Resistor area and perimeter are secondary
  parameters outside this comparison. The three topology warnings name empty
  base `nfet`, `pfet` and `pnp` classes.

Every runset report remains frozen as `lvs-report.json`. All five read
`match`. The open grader issue concerns that route. [klayout-tools #6902](https://github.com/2AMLogic/klayout-tools/issues/6902)

## Checks and what each one does not say

* `klt drc` with the **curated** sky130 deck is the committed verdict and is
  `clean`. Its `coverage` block is quoted in the record: it cannot see the
  5 V rule columns (`voltage_domain_warnings`), so a second run with the
  **PDK-native** `sky130A_mr.drc` (`--expect-rule-categories` pins its 244
  categories; without it a zero-finding native run is `coverage_unknown`)
  is committed beside it. Neither is a foundry signoff run.
* Runset LVS matches the leaf reference netlist. `body_verification`
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
* **The runset needs a derived reference for the MIM caps.** The PDK's `sky130.lvs`
  extracts a MIM as `sky130_fd_pr__model__cap_mim` but its `convert_subckts`
  device list does not contain the xschem export's `sky130_fd_pr__cap_mim_m3_1`,
  so reading `design/netlist/differential_driver.spice` directly drops the four
  caps from the reference (klayout-tools#4519 now makes that loud). `run_checks.py`
  therefore writes `lvs-reference.spice`: the design netlist with only those four
  lines rewritten to the extracted model as two-terminal `C` elements with
  `A = W*L` and `P = 2*(W+L)` in micrometres. `design/` is not edited and the
  runset is not changed. With it the report is `match` (80/80 devices, 8/8 pins,
  0 mismatches); `power_connectivity` is `unchecked` (the runset's extraction
  carries no instance-level power pins). A runset mismatch prevents record creation.

