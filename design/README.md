# design

Analog schematics (xschem). One block per port issue (so far: `differential_receiver`, `se_receiver_dp` / `se_receiver_dm` and `dplus_pullup`, below): the analog blocks are ported here from `gf180-usb2-phy` (operator ruling 2026-10-08, #40) — see [`docs/porting-plan.md`](../docs/porting-plan.md).

`design/netlist/` holds synthesized gate-level netlists of the digital partition.
`netlist/usb_utmi_top.v` is the Yosys/`sky130_fd_sc_hd` mapping of the real UTMI top
(experiment `utmi-top`, [`flow/README.md`](../flow/README.md)); it is synthesis output
only, not placed, routed or signed off, and the record beside it discloses a combinational
loop found in the RTL.

## `differential_receiver.sch` (issue #111)

Sky130 port of the `gf180-usb2-phy` differential receiver (source pinned at
`0aab24943aa1379026ccebb8e5746580f1eb7947`, `design/differential_receiver.sch`
and its netlist; stamped in `reuse.lock.json`). The topology is carried; every
device was re-chosen for sky130 and every number re-measured. Nothing from the
gf180 evidence (its record `20261008-193113-2e9f63e`) is a sky130 claim.

**Status: measured at schematic level only** (no layout, no parasitics, no
mismatch). Evidence: `sim/diff-receiver-sensitivity/records/20261009-121939-0555da1.md`
(PASS 45/45 PVT corners at each of the common-mode points 0.8 / 1.65 / 2.5 V,
batch job `klt-sim-dc49c715a6f2`). **Mismatch / Monte Carlo was not run**, so
input-offset spread is not covered; the measured input-referred threshold is
the systematic (deterministic) offset only.

Regenerate the netlist from the schematic with
`design/export_netlist.sh differential_receiver` (xschem 3.4.7 with the sky130
symbols of the installed open_pdks `sky130A`; it makes `sch_path` repo-relative
and turns xschem's `**.subckt` wrapper into a real `.subckt`, nothing else).
Re-running it reproduces `design/netlist/differential_receiver.spice` byte for
byte.

### Pin contract

`differential_receiver VDD VSS DP DM RXD` (same order and names as the source).

| Pin | Dir | Domain / meaning |
|---|---|---|
| `VDD` | inout (power) | 3.3 V I/O rail, 3.0-3.6 V (DR-0001 Decision 5, `spec/usb2-phy.md` section 5) |
| `VSS` | inout (ground) | ground; all NMOS bulks |
| `DP`, `DM` | in (analog) | USB D+ / D- after the pad, common mode 0.8-2.5 V; gates of the input pair only |
| `RXD` | out | 3.3 V-domain logic, rail-to-rail `VSS`..`VDD`; `RXD=1` when `DP` is the more positive line (J), `RXD=0` when `DM` is (K) |

No enable / power-down pin (as in the source). The pin names match the other
port issues (`se_receiver_dp VDD VSS DP RXDP`, see `docs/porting-plan.md`).

### Output domain

`RXD` is on the 3.3 V I/O rail. The 1.8 V core RTL (`rtl/usb_utmi_top.v`) has
no differential-receiver input, only `dp`/`dm`. This issue states that domain
and nothing more: **no level shifter is designed and no RTL is changed**; the
3.3 V to 1.8 V crossing and the RTL input are integration items.

### Sky130 device choices and reasons

Topology: self-biased 5T OTA (NMOS input pair, PMOS diode/mirror load, tail
mirrored from a resistor-fed diode NMOS) followed by two inverters, the first
P-heavy. All sizes below are the as-simulated values; L is the smallest bin
of the chosen devices.

| Instance | Device | W (um) x m | L (um) |
|---|---|---|---|
| `MN_INA`, `MN_INB` (input pair) | `sky130_fd_pr__nfet_g5v0d10v5` | 10 x 2 | 0.5 |
| `MP_LOADA`, `MP_LOADB` (diode + mirror load) | `sky130_fd_pr__pfet_g5v0d10v5` | 10 x 4 | 0.5 |
| `MNBIAS` (diode) / `MTAIL` (2x mirror) | `sky130_fd_pr__nfet_g5v0d10v5` | 4 x 1 / 4 x 2 | 0.5 |
| `MP_B1` / `MN_B1` (first inverter, P-heavy 10:1 by W) | `pfet_g5v0d10v5` / `nfet_g5v0d10v5` | 20 / 2 | 0.5 |
| `MP_B2` / `MN_B2` (second inverter, 2:1) | `pfet_g5v0d10v5` / `nfet_g5v0d10v5` | 10 / 5 | 0.5 |
| `RBIAS` | `sky130_fd_pr__res_xhigh_po_1p41` | fixed 1.41 | 140 |

1. **MOS flavour: `g5v0d10v5` (thick-oxide, 5 V-class) N and P.** Every
   device sees up to 3.6 V (V_DS and V_GS) on the I/O rail, so core `*_01v8*`
   devices are excluded; `g5v0d10v5` is the sky130 5 V-rated family (model
   bins start at L = 0.5 um, hence L = 0.5 um everywhere rather than the
   source's 0.28 um). The native `nfet_03v3_nvt` was considered for the
   input pair because its low threshold helps the 0.8 V floor, and **was not
   simulated**: the `g5v0d10v5` pair already resolves 0.8 V common mode at
   every corner (below), so the extra device flavour was not needed. A
   complementary input pair (the issue's fallback) was likewise not needed
   and not evaluated.
   Sizes are the source's total widths mapped onto the sky130 bins using `m`
   (input pair 20 um, load 40 um); only the first inverter was kept P-heavy
   (10:1 by width, the source used 16:1). No sizing sweep or optimisation was
   run; these are the values that were simulated, and the 45-corner grid
   passed with them.
2. **Bias resistor: `sky130_fd_pr__res_xhigh_po_1p41`, L = 140 um.** The
   bias current is set by `(VDD - Vgs(MNBIAS)) / RBIAS` and mirrored 2x into
   the tail, so the absolute resistance spread sets the bias; the
   `xhigh` (highest sheet-resistance) poly is chosen to reach ~10^5 ohm in a
   short run; `res_high_po` was not tried. The device is the model's
   process-corner-aware resistor, so resistor spread rides on the same `tt ff
   ss fs sf` sections. Measured supply current for the whole receiver at
   VDIFF = 0 is 9.7-48.7 uA at 0.8 V common mode, 29.4-66.7 uA at 1.65 V and
   37.1-80.3 uA at 2.5 V over the 45 corners, so the bias scheme keeps working
   at every corner. A different bias scheme was not tried. The nominal
   resistance value was not separately recorded.
3. **Supply pin naming:** `VDD` / `VSS`, unchanged from the source and
   consistent with the other port issues' contracts (`docs/porting-plan.md`).
   The testbench connects `VDD` to the swept source `vsup`.
4. **Output domain:** 3.3 V, see above.

### What the grid shows (record 20261009-121939-0555da1)

Input-referred threshold (`VDIFF = DP - DM` at which `RXD = VDD/2`, rising
sweep, 1 mV step), over all 45 corners:

| Common mode | min | max | worst corner |
|---|---|---|---|
| 0.8 V | -28.8 mV | -15.5 mV | `fs_100c_3.60v` |
| 1.65 V | -29.5 mV | -12.5 mV | `sf_100c_3.60v` |
| 2.5 V | -76.0 mV | -16.5 mV | `sf_100c_3.00v` |

All inside the +/-200 mV bound; the worst-case margin to -200 mV is 124 mV and
to +200 mV is 212 mV (the systematic offset is negative: the receiver
switches to J when DP is still slightly below DM). Output beyond the boundary:
RXD >= 1.0 x VDD (to the printed digits) for every VDIFF in [+200, +400] mV
(the +200.5..+400 mV window and the +200 mV probe agree), and the low output
peaks at 3.85 uV over [-400, -200.5] mV and at 4.13 uV at the -200 mV probe
(both at 2.5 V common mode, `sf_100c_3.00v`), at all 135 PVT x
common-mode combinations. The 2.5 V common-mode
ceiling is the weakest point (largest threshold shift and largest low-level
leakage, both at `sf` 100 C 3.0 V): this is the gf180 failure mechanism's
sky130 counterpart. It does not fail here, with the P-heavy first inverter.

Runner skew: this record's provenance line shows the client (klt 0.7.0), but
the fleet runner that executed it was klt 0.5.0 (`report.json`
`runner_compatibility: mismatch`, requested with the version check in `warn`
mode); all 45 corners still returned finite `.meas` values in the raw ngspice
logs, and a re-run is due once the runner image is updated (tracked at
`2AMLogic/klayout-tools` #2851, #2948, #2917; see `sim/README.md` Known limits).

Single-corner debug probes run locally before the grid (unrecorded
observations, no evidence file; do not cite as measured evidence; tail
node and OTA output at `VDIFF = +/-200 mV`): at 0.8 V common mode the tail
current mirror sits in triode (tail node 1-130 mV, supply current is 35-60 % of its 1.65 V value
in the probed corners) yet the pair still steers; at 2.5 V the
OTA low level is bounded by the tail node (about 1.2-1.4 V) and the first
inverter output reached only 2.61 V (of 3.0 V) at `sf` -40 C 3.0 V before the
second inverter restored the rail. That corner is one of the closest to
failing at the buffer, although the recorded output passed.

Not covered here: mismatch offset, supply/common-mode transients, input
capacitance and pad loading, dynamic behaviour (propagation delay, rise and
fall at the USB data rate), layout parasitics.

## `se_receiver_dp.sch`, `se_receiver_dm.sch` (issue #110)

Sky130 port of the `gf180-usb2-phy` single-ended D+ and D- receivers (source
pinned at `0aab24943aa1379026ccebb8e5746580f1eb7947`, `design/se_receiver_dp.sch`,
`design/se_receiver_dm.sch`, their netlists and the two
`sim/se-receiver-d{p,m}-thresholds/testbench/` files; all stamped `fetched`
with SHA-256 in `reuse.lock.json`, and the fetched bytes re-hashed equal to
the stamps for this port). The topology is carried; every device was
re-chosen for sky130 and every number re-measured. Nothing from the gf180
evidence (records `20260817-203631-a408cb6` / `20260817-203654-a408cb6`) is a
sky130 claim. The two cells are the same circuit and differ only in the
names of the line input and the output pin.

**Status: measured at schematic level only** (no layout, no parasitics, no
mismatch). Evidence:
`sim/se-receiver-dp-thresholds/records/20261009-142213-484240f.md` (D+, PASS
45/45, batch job `klt-sim-a011a5f8e3fc`) and
`sim/se-receiver-dm-thresholds/records/20261009-142853-484240f.md` (D-, PASS
45/45, batch job `klt-sim-00d222e79282`). **Mismatch / Monte Carlo was not
run**: comparator offset from device mismatch and divider-resistor mismatch
are not covered; the measured threshold contains the systematic offset only.

Regenerate the netlists with `design/export_netlist.sh se_receiver_dp` and
`design/export_netlist.sh se_receiver_dm` (run here with xschem 3.4.4 and the
installed open_pdks `sky130A` symbols). Two consecutive exports produced
byte-identical files, and the same host re-exported
`differential_receiver.spice` byte-identically, so the helper is reproducible
across this xschem version.

### Pin contract

`se_receiver_dp VDD VSS DP RXDP` and `se_receiver_dm VDD VSS DM RXDM` (same
order and names as the source).

| Pin | Dir | Domain / meaning |
|---|---|---|
| `VDD` | inout (power) | 3.3 V I/O rail, 3.0-3.6 V (DR-0001 Decision 5, `spec/usb2-phy.md` section 5); also the top of the `VREF` divider |
| `VSS` | inout (ground) | ground; all NMOS bulks and the resistor bodies |
| `DP` / `DM` | in (analog) | the USB D+ / D- line after the pad, 0 V..`VDD`; gate of one input transistor only |
| `RXDP` / `RXDM` | out | 3.3 V-domain logic, rail-to-rail `VSS`..`VDD`; non-inverting: `1` when the line is above the internal threshold (about 0.42 x `VDD`), `0` below it |

No enable / power-down pin (as in the source). The output pin is declared
`iopin` in the schematic, matching `differential_receiver`; electrically it is
an output.

### Output domain

`RXDP` / `RXDM` are on the 3.3 V I/O rail. `rtl/usb_utmi_top.v` takes
`dp`/`dm` as 1.8 V core inputs. **No level shifter is designed and no RTL is
changed here**; the 3.3 V to 1.8 V crossing belongs to the integration issue.

### Sky130 device choices and reasons

Topology: the differential receiver's core (self-biased NMOS-input 5T OTA,
PMOS diode/mirror load, tail mirrored 2x from a resistor-fed diode NMOS, two
inverters with the first P-heavy) with the line on the diode-side input
(`MN_INA`) and `VREF` on the mirror-side input (`MN_INB`); `VREF` is a
ratiometric `R1`/`R2` divider off `VDD`.

| Instance | Device | W (um) x m / L (um) |
|---|---|---|
| `MN_INA` (line), `MN_INB` (`VREF`) | `sky130_fd_pr__nfet_g5v0d10v5` | 10 x 2 / 0.5 |
| `MP_LOADA`, `MP_LOADB` | `sky130_fd_pr__pfet_g5v0d10v5` | 10 x 4 / 0.5 |
| `MNBIAS` / `MTAIL` | `nfet_g5v0d10v5` | 4 x 1 / 4 x 2, L 0.5 |
| `MP_B1` / `MN_B1` (first inverter, 10:1) | `pfet_g5v0d10v5` / `nfet_g5v0d10v5` | 20 / 2, L 0.5 |
| `MP_B2` / `MN_B2` (second inverter) | `pfet_g5v0d10v5` / `nfet_g5v0d10v5` | 10 / 5, L 0.5 |
| `R1` (`VDD`-`VREF`) / `R2` (`VREF`-`VSS`) | `sky130_fd_pr__res_xhigh_po_1p41` | fixed 1.41 wide; L 19 / 14 |
| `RBIAS` | `sky130_fd_pr__res_xhigh_po_1p41` | fixed 1.41 wide; L 140 |

1. **MOS flavour: `g5v0d10v5` N and P, L = 0.5 um**, for the same reason as
   the differential receiver: every device sees up to 3.6 V, so `*_01v8*`
   core devices are excluded, and `g5v0d10v5` is the 5 V-rated family whose
   model bins start at L = 0.5 um (the source used 0.28 um, and 0.5 um for
   `MNBIAS`/`MTAIL`). `nfet_03v3_nvt` (native) was not used: the input pair
   only has to resolve inputs around `VREF` (about 1.27-1.53 V), well above
   the floor where a low threshold would help. The sizing is the
   differential receiver's measured sizing reused unchanged, because the
   single-ended cell is that comparator with one input tied to `VREF`, whose
   1.27-1.53 V range sits inside the 0.8-2.5 V common mode already measured
   for it. No sizing sweep was run.
2. **Resistor flavour: `res_xhigh_po_1p41` for `R1`, `R2` and `RBIAS`.** The
   divider is ratiometric: the threshold tracks `VREF / VDD`, which depends
   only on the ratio of two resistors of the same flavour and width, so
   absolute sheet-resistance spread cancels. The same flavour as `RBIAS`
   keeps one resistor type in the cell. Lengths 19 / 14 um carry the source's
   1900 / 1400 ratio; the model's end resistance shifts it slightly, and the
   measured `VREF` is 0.4250-0.4252 x `VDD` over all 45 corners (1.275 V at
   3.0 V, 1.403 V at 3.3 V, 1.531 V at 3.6 V). The source divider drew about
   1 mA from the 3.3 V rail; the sky130 divider (about 47 kohm in total) drew
   69.8 uA of the cell's 81.9 uA at input 0 V in one local debug probe (`tt`
   27 C 3.3 V, unrecorded, divider current read through a temporary 0 V
   source not present in the committed netlist). The recorded supply current
   at input 1.4 V is 78-156 uA over the grid; it includes buffer crowbar
   current where 1.4 V is close to that corner's threshold. `RBIAS` sets the
   bias current, so its absolute spread matters; it is the same resistor as
   in the differential receiver (L = 140 um), whose bias was shown to work
   across the grid. `res_high_po` and `res_generic_po` were considered and
   not simulated: the ratio, not the absolute value, sets the threshold, and
   `xhigh_po` keeps the divider short at low current.
3. **Supply pin naming:** `VDD` / `VSS`, unchanged from the source and the
   same as `differential_receiver`; the 3.3 V domain is stated in the pin
   contract, not in the names. The testbench connects `VDD` to the swept
   source `vsup`.
4. **Output domain:** 3.3 V, see above.

### What the grids show

The two records are identical in every measured value (same circuit, same
deck apart from names). Over the 45 corners:

| Quantity | min | max | Criterion |
|---|---|---|---|
| Switching threshold `vth_v` (first rising crossing of `VDD/2`) | 1.2505 V (`ff_100c_3.00v`) | 1.5136 V (`ss_-40c_3.60v`) | strictly inside (0.8, 2.0) V |
| Last crossing `vth_last_v` | equal to `vth_v` at every corner (difference 0) | | within 1 mV of `vth_v` |
| Threshold minus `VREF` (systematic offset) | -29.1 mV (`sf_100c_3.60v`) | -12.6 mV (`ss_-40c_3.00v`) | not a criterion |
| Output max over input 0-0.8 V | | 48 nV (`fs_100c_3.60v`) | <= 0.1 x `VDD` |
| Output min over input 2.0-3.0 V | = `VDD` at every corner (to printed digits) | | >= 0.9 x `VDD` |

The worst margin to the ratified window is 450.5 mV above 0.8 V (at
`ff_100c_3.00v`) and 486.4 mV below 2.0 V (at `ss_-40c_3.60v`). The threshold
follows the supply (about 0.42 x `VDD`), so the low-supply corners sit
nearest 0.8 V and the high-supply corners nearest 2.0 V. One rising crossing
and nothing else at every corner: the response is monotonic over the swept
0-3.0 V.

Runner skew: as for the differential receiver, the fleet runner was klt
0.5.0 against client 0.7.0 (`report.json` `runner_compatibility: mismatch`,
version check `warn`); all 45 corners per line returned finite `.meas`
values in the raw ngspice-46 logs. The execution-host PDK identity is
client-reported (see `sim/README.md` Known limits). The D- record shows
`dirty=True` because the D+ evidence was still uncommitted when it ran; both
ran on commit `484240f`.

Single-corner local debug (unrecorded, `--backend local --no-write`,
`tt` 27 C 3.3 V, ngspice-42): threshold 1.383 V, `VREF` 1.403 V for both
lines, matching the fleet result at that corner.

Not covered here: mismatch offset (the 0.45 V margin each side is the budget
for it, but no Monte Carlo was run), input hysteresis (the source has none
and neither does this port), supply and line transients, input capacitance
and pad loading, dynamic behaviour (propagation delay at the USB data rate),
layout parasitics.

## `dplus_pullup.sch` (issue #113)

Sky130 port of the `gf180-usb2-phy` trimmed D+ pull-up (source pinned at
`0aab24943aa1379026ccebb8e5746580f1eb7947`: `design/dplus_pullup.sch`, its
netlist, the `design/README.md` section "`dplus_pullup.sch`" and
`sim/dplus-pullup-tolerance/testbench/`, all read and stamped in
`reuse.lock.json`). The topology is carried (enable switch, series resistor
ladder, a PMOS bypass switch per ladder segment, a small inverter per control
bit, all-zero code = maximum resistance); every device and every number was
re-derived for sky130. Nothing from the gf180 evidence (record
`20260905-185112-6bfe679`, PASS 45/45) is a sky130 claim.

**Status: schematic level only** (no layout, no parasitics, no mismatch, no
regulator, no trim storage). Evidence: see "What the grid shows" below.
Regenerate the netlist with `design/export_netlist.sh dplus_pullup`; two
consecutive exports are byte-identical (xschem 3.4.4, installed open_pdks
`sky130A` symbols).

### Pin contract

`dplus_pullup DP VPU VSS PU_EN TRIM0 TRIM1 TRIM2 TRIM3` (the source's
`VPU_REG` is renamed `VPU` because this repo does not build the regulated rail;
nine pins become eight because the trim word is 4 bits, not 5).

| Pin | Dir | Domain / meaning |
|---|---|---|
| `DP` | inout (analog) | the USB D+ line after the pad; the pull-up's output |
| `VPU` | inout (power) | pull-up supply, **an input**: 3.0-3.6 V (`spec/usb2-phy.md` section 6, DR-0001 Decision 5). Not generated here; also the supply and bulk of the control inverters and of every PMOS switch |
| `VSS` | inout (ground) | ground; all NMOS bulks |
| `PU_EN` | in | `1` (= `VPU`) connects the pull-up to `DP`; `0` (= `VSS`) disables it (high impedance). Active high |
| `TRIM0`..`TRIM3` | in | `TRIM<i>` = `1` shorts ladder segment `i` out of the path (lower resistance); `0` leaves it in. Active high. Code 0000 (all segments in) is the maximum resistance and the fail-safe default; code 1111 the minimum |

Control logic levels are 0 / `VPU` (the inverters are supplied from `VPU`), so
no gate in the cell ever sees more than `VPU`. Level shifting from the 1.8 V
core is an integration item, not designed here.

**`TRIM` is an integration input.** This repository has no OTP / fuse / scan
mechanism and the UTMI interface has no trim port, so the section 6 tolerance
claim is **"with the trim code selected at test"**, exactly as the source's.
Where the code is stored is open (integrator).

**`PU_EN` is the analog end of the section 6 "Control interface from UTMI
layer" pull-up enable row.** `rtl/usb_utmi_top.v` synchronizes `TermSelect`
and has no consumer for it; the intended connection is `TermSelect` (after
the synchronizer) to `PU_EN` through a 1.8 V to `VPU` level shifter. No RTL is
changed here and no connection is made.

**`VPU` source is undecided at the repo level** and not decided here. Options
recorded, not chosen: an integrator-supplied rail; the 3.3 V I/O rail itself
if its envelope is guaranteed to stay inside 3.0-3.6 V (DR-0001 Decision 5
states I/O 3.0-3.6 V, the same window); a regulator from `sky130-ldo`, whose
ratified product is a 3.3 V-in / 1.8 V-out LDO and therefore not a drop-in
(`in_tree` `status: evaluate` in `reuse.lock.json`). No regulator is designed.
The testbench ties `VPU` to the swept source `vsup` (3.0 / 3.3 / 3.6 V), the
conservative choice: the cell sees the full envelope.

**Pull-downs.** Section 6 lists host 15 kohm +/-5 % pull-downs on D+/D-. This
repo is a single-role FS device (section 3): the testbench models the host's
15 kohm as a load on D+ and the cell has no on-die pull-down. Whether the row
applies to this block is the open spec question in DR-0003; section 6 and
DR-0003 are unchanged.

### Sky130 device choices and reasons

| Instance | Device | W (um) x m / L (um) |
|---|---|---|
| `MP_ENSW` (enable switch, `VPU` to ladder) | `sky130_fd_pr__pfet_g5v0d10v5` | 100 x 10 / 0.5 |
| `MP_B0`..`MP_B3` (segment bypass) | `sky130_fd_pr__pfet_g5v0d10v5` | 100 x 8, 4, 2, 1 / 0.5 |
| `MP_EN`, `MP_T0..3` / `MN_EN`, `MN_T0..3` (control inverters) | `pfet_g5v0d10v5` / `nfet_g5v0d10v5` | 4 / 2, L 0.5 |
| `RBASE` | `sky130_fd_pr__res_generic_po` | W 2 / L 40.3 |
| `R0`..`R3` (segments) | `sky130_fd_pr__res_generic_po` | W 2 / L 2.4, 4.8, 9.6, 19.2 |

1. **Ladder resistor: `res_generic_po`, W = 2 um.** Candidates were
   `res_generic_po`, the fixed-width `res_high_po_*` / `res_xhigh_po_*`, and
   diffusion resistors. `res_generic_po` was chosen because its model has no
   voltage coefficient and a plain linear temperature coefficient, so a
   resistor that sits between `VPU` and a line near `VPU` has one number to
   re-derive per corner. The `res_high_po` / `res_xhigh_po` models carry
   body-voltage terms (`vc1_body`, `vc2_body`, `tc1_voltco`) and end/contact
   resistance terms, and the diffusion resistors have junction capacitance to
   the pad and a leaky bulk; none was simulated (considered, not measured).
   Resistance read from the installed model (one local single-corner run,
   unrecorded): `res_generic_po` W = 2 um is 24.79 ohm/um of length at 30 C
   (0 and 100 C factors below).
2. **Resistor corner mapping (read from the installed model files).** In
   `libs.tech/ngspice/sky130.lib.spice` **every** process section (`tt`, `ff`,
   `ss`, `fs`, `sf`) includes `r+c/res_typical__cap_typical.spice`. The
   resistor sheet-resistance parameter sets are in separate files
   (`res_low__*` `rp1` = 42.2 ohm/sq, `res_typical` 48.2, `res_high` 53.52,
   with `tol_poly` of +0.0287 / 0 / -0.0287 um) and are **not selected by any
   of the five process corners**. The 45-corner grid therefore exercises the
   MOS corners and the resistor temperature coefficient (`tc1r` 8.916e-4,
   `tc2r` 8.443e-7, `tnom` 30 C: factor 0.942 at -40 C, 1.067 at 100 C) but not
   the resistor sheet-resistance spread. That spread is what the trim range
   exists for, so it is covered here by a separate **design-basis check, not
   a recorded result**: two single-corner local `ngspice` runs of this netlist
   (code 0000 and 1111) with the extreme resistor sets applied together with
   the slowest / fastest MOS and the temperature that moves the resistor the
   same way:

   | Condition | R(code 0) | R(code 15) |
   |---|---|---|
   | `ss`, 100 C, 3.0 V, `res_high` | 2283 ohm | 1380 ohm |
   | `ff`, -40 C, 3.6 V, `res_low` | 1607 ohm | 926 ohm |

   At both extremes the code range still brackets 1.5 kohm: at the
   hottest, slowest, highest-resistance condition even code 15 is 1380 ohm
   (below 1425), and at the coldest, fastest, lowest-resistance condition
   code 0 is 1607 ohm (above 1575). With about 52 ohm per step, a code then
   lands inside the 150 ohm wide window at any point of the range. Only the
   two end codes were run at these extremes; all codes at every resistor
   set, and a recorded sweep over `res_low` / `res_high`, were **not** run
   and no claim is made for them (adding resistor sets to the harness
   matrix would be a change to `sim/corners.json`, owned by #109, not made
   here).
3. **Base value, LSB and bit count re-derived** (not the source's 1000 ohm +
   5 bits). Required covering range: the resistors alone move roughly -19 %
   to +21 % over the sheet spread (0.875 to 1.11) and temperature (0.942 to
   1.067), plus width tolerance; the switches add a series on-resistance.
   `RBASE` = 40.3 um (about 1.0 kohm at 30 C) puts the lowest code (all segments
   shorted: base + enable switch + the four bypass on-resistances) at 1.1-1.4
   kohm over the grid and 926-1380 ohm at the design-basis extremes; the segment
   total of 15 LSB with LSB = 2.4 um (59.5 ohm) puts the highest code at 1.8-2.0
   kohm. Four bits at about 52 ohm per step (the bypass switch on-resistance
   removes part of each segment's value when it is closed) are enough: the
   largest step on a +21 % resistor is about 63 ohm, well inside the 150 ohm
   window width, so a fifth bit would only add a switch. The source's 5 bits
   with a 30 ohm LSB would need 31 steps for a smaller window.
4. **Switch device: `pfet_g5v0d10v5`, L = 0.5 um** (the thick-oxide family
   whose model bins start at 0.5 um; the source used `pfet_03v3` at 0.28 um).
   Every switch has its source / bulk at `VPU` or on the ladder just below it,
   its gate at 0 or `VPU`: the largest gate-source stress is `VPU` = 3.6 V,
   well inside the 5 V rating. PMOS switches (not NMOS) are used because they
   pass a node near `VPU` with a full gate overdrive of about 2.7-3.6 V.
   **On-resistance re-measured**: a W = 100 um device has about 111 ohm at the
   slowest corner (`ss`, 100 C, `VPU` 3.0 V, node at 2.7 V; one local run), so
   the switches are built from `mult` copies of W = 100 um: enable 1000 um,
   bypass 800 / 400 / 200 / 100 um (each bypass has an on-resistance of about
   14 / 28 / 56 / 111 ohm at that corner, that is a constant 23 % of the
   segment it bypasses; 5-10 % at typical). The segment weights therefore stay
   binary after the switch is taken into account.
5. **Multi-finger check.** Every device uses `nf=1` and the `mult`/`m`
   multiplier, as in the other sky130 blocks, so no multi-finger device
   reaches `klt` and the question raised by the source's klayout-tools#1487
   workaround does not arise at schematic level. Choosing fingers is a layout
   decision (not made here), where it would need its own ingestion check.
6. **Control inverters** (`MP_*` W = 4, `MN_*` W = 2, L 0.5) are minimum-style
   inverters from `VPU` to `VSS`; they exist so `PU_EN` and `TRIM` are
   active-high at the pin while the PMOS switches are active-low.

### What the grid shows

Record `sim/dplus-pullup-tolerance/records/20261009-172948-d85f0dc.md`:
**PASS 45/45**, batch job `klt-sim-92dd587c3e36` (fleet runner klt 0.5.0 against
client 0.7.0, version check `warn`, see `sim/README.md` Known limits).
Two earlier attempts the same day were refused by the batch fleet before any
simulation (`batch_no_capacity`: no capacity in any of the 30 pools); their
FAIL records `20261009-172121-d85f0dc` and `20261009-172711-d85f0dc` are kept
as evidence of the attempts and do not count as coverage.

Method: 16 pull-up instances (one per trim code) at each corner, `PU_EN` = `VPU`,
15 kohm host load from D+ to ground, `VPU` = `vsup`; `I_load = V(DP)/15000`,
`R_eff = (VPU - V(DP))/I_load`, which includes the enable and bypass
switches. PASS is existential **within each corner**: at least one code in
the inclusive 1425-1575 ohm window, with all 16 codes present and finite.

| Quantity | min | max |
|---|---|---|
| Best code (closest to 1500 ohm, ties to the lowest) | 6 (`ff_-40c_3.00v`, 15 corners at code 6) | 10 (`tt_100c_3.60v`); codes used: 6, 7, 8, 9, 10 |
| Best-code resistance | 1474.97 ohm (`tt_100c_3.60v`) | 1527.05 ohm (`ff_100c_3.30v`) |
| Codes inside the window per corner | 2 (`ff_100c_3.00v`) | 3 (`tt_27c_3.30v`) |
| `R_eff` code 0 (maximum) | 1785.67 ohm (`fs_-40c_3.60v`) | 2027.27 ohm (`sf_100c_3.00v`) |
| `R_eff` code 15 (minimum) | 1021.22 ohm (`fs_-40c_3.60v`) | 1241.73 ohm (`sf_100c_3.00v`) |
| Trim range (code 0 minus code 15) | 724.5 ohm (`sf_-40c_3.00v`) | 840.5 ohm (`fs_100c_3.60v`) |
| Trim step (adjacent codes) | 45.57 ohm (`sf_-40c_3.00v`, code 7 to 8) | 56.46 ohm (`fs_100c_3.60v`, code 14 to 15) |
| Non-monotonic adjacent pairs | 0 at every corner | |

The step is 3.0-3.8 % of 1500 ohm, so the 150 ohm window always holds 2-3
codes. The per-corner table (best code, best resistance, steps, range) is in
the record; every raw `V(DP)` and every derived resistance is in
`corners/20261009-172948-d85f0dc/evidence.json` and `report.json`.

**Limits of this PASS.** (1) The code is chosen **per corner**: this proves the
trim range and step cover all 45 corners, not that one calibration code stays
in the window across voltage and temperature after trimming at a single
condition (codes 6 to 10 are best at different corners; the grid does not
show the spread of a single fixed code, although `R_eff` per code is in the
record for anyone who wants to compute it). (2) The grid does not exercise
the resistor sheet-resistance spread (item 2 above). (3) Schematic level:
no mismatch / Monte Carlo, no extracted parasitics, no layout. (4) `VPU` is an
input, there is no regulator and no trim storage; nothing here is an
integrated-PHY claim.

**Disabled state** (`PU_EN` = 0, all 45 corners, same record). Conditions
applied: d1 and d0 = TRIM 1111 / 0000 with the 15 kohm host load to ground;
dz = TRIM 1111 with D+ forced to 0 V; dh = TRIM 1111 with D+ forced to `VPU`.

| Quantity | min | max |
|---|---|---|
| `V(DP)`, loaded by 15 kohm (d1 / d0) | 1.8 uV (`sf_-40c_3.00v`) | 117 uV (`fs_100c_3.60v`) |
| Current delivered into D+ by the pull-up, loaded (d1 / d0) | 0.12 nA | 7.79 nA (`fs_100c_3.60v`) |
| Current delivered into D+, D+ forced to 0 V (dz) | 0.12 nA | 7.79 nA (`fs_100c_3.60v`) |
| Current into D+ with D+ at `VPU` (dh) | -7.8 pA (`fs_100c_3.60v`) | +11.0 pA (`tt_-40c_3.60v`) |
| Current drawn from `VPU` (d1, d0, dz) | 0.14 nA | 12.2 nA (d0, `sf_100c_3.60v`) |
| Current drawn from `VPU` (dh) | 0.018 nA | 2.4 nA (`sf_100c_3.60v`) |

D+ is not pulled up: with the 15 kohm load it stays at or below 117 uV, far
below the sanity criterion of 0.8 V (the ratified single-ended VIL; an
engineering criterion, not a leakage limit). **No leakage limit is ratified
and none is claimed**: the currents are engineering data at schematic level
(model leakage; no ESD structures, no pad, no layout).
