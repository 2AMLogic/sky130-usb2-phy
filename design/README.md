# design

Analog schematics (xschem). One block per port issue (so far: `differential_receiver`, `se_receiver_dp` / `se_receiver_dm`, `dplus_pullup` and `differential_driver`, below): the analog blocks are ported here from `gf180-usb2-phy` (operator ruling 2026-10-08, #40) — see [`docs/porting-plan.md`](../docs/porting-plan.md).

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
   resistor model, but the five bare sections `tt ff ss fs sf` all load the
   typical resistor set, so the 45-corner grid does **not** cover its
   sheet-resistance spread (#126, `sim/README.md` "Resistor-set coverage").
   The supplemental 225-point resistor-set sweep (#136, record `20261010-094000-0d51889`,
   675 point x common-mode combinations) passes with the same bounds: threshold
   -76.5 to -12.5 mV. It covers the PDK's global resistor/capacitor sets (with their drawn-width
   tolerances), not per-device mismatch, Monte Carlo or layout parasitics. Measured supply current for the whole receiver at
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
   across the grid. The supplemental 225-point resistor-set records (#136: D+
   `20261010-074010-0d51889`, D- `20261010-090217-0d51889`) keep the threshold at
   1.250-1.514 V and `VREF` at 0.4249-0.4254 x `VDD` (1.275-1.531 V) with the PDK's
   global resistor/capacitor sets, all bounds unchanged and passing; the global sets
   move R1, R2 and `RBIAS` together, so independent R1/R2 mismatch is not covered.
   `res_high_po` and `res_generic_po` were considered and
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
   exists for. It is now covered by a **recorded** supplemental sweep (#126,
   `spec/decision-records/0005-resistor-sheet-resistance-corner-coverage.md`,
   `sim/dplus-pullup-tolerance/records/20261010-014615-8ebfb55.md`): all 16
   codes at 225 points = 5 MOS corners x {typical, `ll`, `hh`, `hl`, `lh`} x
   3 temperatures x 3 supplies, batch job `klt-sim-10dfd5d87262`. The suffixed
   sections also change the capacitor set and the `tol_*` width tolerances, and
   they are the PDK's global corners, not per-device spread. The two
   single-corner local runs that this item used to carry as an unrecorded
   check are reproduced exactly by that record:

   | Condition | R(code 0) | R(code 15) |
   |---|---|---|
   | `ss_hh`, 100 C, 3.0 V (was "`ss` + `res_high`") | 2283 ohm | 1380 ohm |
   | `ff_ll`, -40 C, 3.6 V (was "`ff` + `res_low`") | 1607 ohm | 926 ohm |

   Over the 225 points the extremes are set by the mixed `hl` / `lh` sets, not
   `hh` / `ll`: the highest code-15 resistance is 1443.9 ohm (`sf_hl`, 100 C,
   3.0 V) and the lowest code-0 resistance is 1531.7 ohm (`fs_lh`, -40 C,
   3.6 V). Both are inside the 1425 to 1575 ohm window, by 19 ohm and 43 ohm:
   the code range brackets the target at every point but the margin at the
   high-resistance end is thin, so a wider sheet spread than the PDK's global
   corners would break it. At every point at least two codes are in the
   window (minimum `n_in_window` = 2, e.g. `tt` 27 C 3.6 V) and the best code
   is between 1 and 14 (never an end code), and the per-point best resistance
   is 1467 to 1531 ohm (computed from the stored raw V(DP)). Per-device
   resistor spread, mismatch and Monte Carlo remain unrun, and the best code is
   still chosen per point, not as one calibration code.
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
the resistor sheet-resistance spread (item 2 above; the supplemental 225-point
record covers the PDK's global resistor sets). (3) Schematic level:
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

## `differential_driver.sch` (issue #112)

Sky130 port of the `gf180-usb2-phy` full-speed line driver (source pinned at
`0aab24943aa1379026ccebb8e5746580f1eb7947`: `design/differential_driver.sch`,
its netlist, `design/README.md` section "`differential_driver.sch`" and
`sim/driver-signal-quality/testbench/`, all read and stamped in
`reuse.lock.json`). Carried: the voltage-mode structure (complementary output
stage per line, series resistor to the pad), the 50 pF per line test load, the
stimulus and the measurement definitions. **Not carried: the gate-slew
mechanism and every size.** The source's poly gate resistor was replaced (item
3 below), an output-enable path was added (the source has none), and every
device was re-derived for sky130. Nothing from the gf180 evidence (record
`20260817-203552-a408cb6`, four FAIL rows) is a sky130 claim; the four rows
were re-measured.

**Status: schematic level only** (no layout, no parasitics, no mismatch, no
passive-process spread, no level shifter). Evidence: "What the grids show"
below. Regenerate the netlist with `design/export_netlist.sh
differential_driver`; two consecutive exports are byte-identical to the
committed `design/netlist/differential_driver.spice` (xschem 3.4.4, installed
open_pdks `sky130A` symbols), and only `sky130_fd_pr__*` devices appear.

### Pin contract

`differential_driver VDD VSS TXDP TXDM DRVEN OE DP DM` (the source's
`VDD VSS TXDP TXDM DP DM` plus `DRVEN` and `OE`).

| Pin | Dir | Domain / meaning |
|---|---|---|
| `VDD` | inout (power) | 3.3 V I/O rail, 3.0-3.6 V (`spec/usb2-phy.md` section 5, DR-0001 Decision 5); supply and bulk of every PMOS. An input, not generated here |
| `VSS` | inout (ground) | ground; all NMOS bulks |
| `TXDP`, `TXDM` | in | **`VDD`-domain CMOS logic** (0 = `VSS`, 1 = `VDD`). `TXDx` = 1 drives `Dx` high, 0 drives it low; `TXDP` = `TXDM` = 0 is SE0, `TXDP` = `TXDM` = 1 drives both lines high |
| `DRVEN` | in | differential drive enable, `VDD` domain, active high (`usb_utmi_top.v` `tx_drive_en`) |
| `OE` | in | output enable, `VDD` domain, active high (`tx_oe`) |
| `DP`, `DM` | inout (analog) | the USB D+ / D- lines at the pad. Driven while enabled; high impedance while disabled |

**Enable truth table.** `EN` = `DRVEN` AND `OE` (a NAND, `ENB`, then an
inverter). `EN` = 1: each line is driven by its `TXDx`. `EN` = 0 (either
control low): the pull-up gate is held at `VDD` and the pull-down gate at
`VSS` through dedicated off switches, so **both the pull-up and the pull-down
output FETs of both lines are off** and `DP` / `DM` are high impedance
whatever `TXDP` / `TXDM` are. All 16 combinations of
`TXDP`/`TXDM`/`DRVEN`/`OE` (including both SE0 and both-high) are in the
`driver-static` experiment.

**Input domain.** The eventual controls come from 1.8 V core logic
(`rtl/usb_utmi_top.v`). A thick-oxide gate at `VDD` needs a `VDD`-swing input
(a 1.8 V "1" is not above the 3.3 V inverter trip point with margin, and would
leave the PMOS conducting), so the standalone cell takes **`VDD`-domain
inputs** and the 1.8 V to `VDD` level shifter is an integration item outside
this cell, exactly as for the receivers' outputs (#110, #111). The testbenches
drive the cell at the documented cell-side levels (logic 1 = the corner
supply); no level shifter is designed or modelled. The pad is not
current-limited or ESD-protected here.

### Sky130 device choices and reasons

| Part | Device | Size |
|---|---|---|
| Output stage, per line (`MP_OUT` / `MN_OUT`) | `sky130_fd_pr__pfet_g5v0d10v5` / `nfet_g5v0d10v5` | P 20 um x 40, N 20 um x 13, L 0.5 um (P:N = 800:260 um) |
| Series resistor (`RSER`) | `sky130_fd_pr__res_generic_po` | W 20 / L 10.8 um (about 26 ohm nominal) |
| Edge-rate control | switched current sources into the output-device gates plus MIM Miller capacitors | `cap_mim_m3_1` 42x42 um (P gate) and 24x24 um (N gate) to the internal output node `OUTI`; mirrored currents from one `res_xhigh_po_1p41` bias |
| Enable / predriver / bias logic | `pfet_g5v0d10v5` / `nfet_g5v0d10v5` | L 0.5 um logic, L 1 um mirrors |

1. **MOS flavour: `pfet_g5v0d10v5` / `nfet_g5v0d10v5` throughout.** The pad
   swings 0-3.6 V, above what the core `*_01v8*` devices tolerate, so those are
   excluded. The native `nfet_03v3_nvt` has no complementary PMOS and a
   near-zero threshold (leakage in the disabled state, no clean off switch),
   so it was considered and not used. The thick-oxide pair is the same choice
   as the receivers and pull-up (#110, #111, #113), keeps one oxide on the
   cell, and its model bins start at L = 0.5 um, so every device is L >= 0.5
   um (gf180 was 0.28 um). **P:N is not 2:1.** It was re-derived from the
   sky130 models so that the pull-up and pull-down on-resistance match: about
   3:1 in width (P 800 um : N 260 um), because sky130 thick-oxide hole mobility
   is lower than electron mobility. The measured result is a high-side output
   resistance of 29.8-40.2 ohm and a low-side one of 29.4-42.2 ohm over the 45
   corners (record below).
2. **Series resistor: `res_generic_po`, W = 20 um.** The 28-44 ohm row is the
   total including FET on-resistance (FET Ron is about 8 ohm at `tt`/27 C, so
   RSER is sized at 26 ohm). `res_generic_po` was chosen over `res_generic_m1`
   (0.125 ohm/sq, so about 208 squares, i.e. a 1 um wide track hundreds of um
   long or a very large meander, for a resistor whose only job is area-cheap
   ohms) and over `res_generic_l1` (li1, 12.2 ohm/sq, about 2 squares: smallest
   area but the widest stated spread, 9.5-14.8 ohm/sq, and a thin film in a
   path that carries the full drive current). Poly in a wide 20 um strip keeps
   the current density low. The resistor's temperature behaviour is in the
   grid (the -40/27/100 C axis); **its process sheet-resistance spread is not**:
   the five sky130 process sections all load the typical resistor parameters
   (the same limit as the pull-up, #113). The 28-44 ohm margin (1.4 ohm on the
   low side) would be consumed by a wider `rp1` spread; that is not claimed
   either way.
3. **Edge-rate control: not the source's poly gate resistor.** The source
   slows the gates with a poly RC and into a fixed ~36 ohm metal resistor; the
   source evidence shows that this gives a corner-dependent edge (22.3 ns at
   its weakest corner) and a pull-up weaker than pull-down. Here the output
   gates are driven by **switched, mirrored constant currents** (`MN_PSRC` for
   the P gate, `MP_NSRC` for the N gate; bias `RB` into diode `MNB`, with
   `MNB2`/`MPB` deriving the PMOS bias) with a **MIM Miller capacitor from each
   output-device gate to `OUTI`**, so while the output slews the gate current
   sets dV/dt = I/C largely independent of the output FET's strength. A fast
   gate-kick (`MN_KICK1/2`, `MP_KICK1N/2N`, shut off by replica devices
   `MP_KREP` / `MN_KREPN`) brings the gate to threshold quickly. The off
   switches (`MP_POFF`, `MN_NOFF`) are separate and fast. A known artefact of
   a Miller-coupled gate is a pre-edge dip; the testbench reports it
   (`over_*` / `under_*`, 15-24 mV over, 64-107 mV under, no limit).
4. **Input domain:** `VDD`-domain logic at the cell boundary, level shifter
   outside (pin contract above).

### Measurement definitions

(Full formulas and windows are in each experiment's `tb.json` `record.method`
and are repeated in every record.)

- **Rise/fall time:** 10 %-90 % of the corner supply, per line (`D+`, `D-`)
  and per edge direction, 50 pF to ground on each line, no resistor.
- **Matching:** `t_rise / t_fall`, within [0.9, 1.1], four pairings (D+ own,
  D- own, D+ rise vs D- fall, D- rise vs D+ fall), so no single pairing hides
  a failing half.
- **Crossover:** `v(DP)` at `v(DP)` = `v(DM)`, separately at the rising and
  the falling crossing.
- **Monotonic single crossing:** the first, second and last D+/D- crossings
  must coincide with the rising/falling crossings (no extra crossing), and the
  slope (V/ns, masked to the 10-90 % band of each line's edge) must keep its
  sign, for both lines and both directions.
- **VOH / VOL:** driven high (VOH) / low (VOL) statically. Loads: VOL into
  1.5 kohm to 3.6 V and VOH into 15 kohm to ground, taken from the USB 2.0
  Chapter 7 DC characteristics for the full-speed driver (**not re-verified
  against the specification text in this environment**; see DR-0004); VOH into
  1.5 kohm to 3.6 V is measured too, as the ratified row's parenthetical reads
  literally. The record states both. A conflict between the two readings is
  for [DR-0004](../spec/decision-records/0004-fs-driver-voh-vol-load-conditions.md)
  (proposed); no threshold is changed.
- **Output resistance (total, enabled):** the pad is forced by an ideal source
  0.3 V from the rail the driver pulls to; `R = 0.3 V / |I(pad)|`, current out
  of the pad when high, into it when low; includes FET Ron and `RSER`.
- **Disabled-pad leakage (engineering data, no ratified limit, none applied):**
  disabled by `OE` = 0 (D+) and by `DRVEN` = 0 (D-), the pad forced 0-3.6 V by
  an independent source while the other line is held at `VDD`/2; and, at an
  enable/disable transition, the pad forced to `VDD`/2 with the pad current
  reported before, during and after (enable time, release time, wrong-polarity
  peak). Pad current is reported separately from the enabled output
  resistance.

### What the grids show

45-corner runs, `klt sim` on the Spot batch fleet (tt/ff/ss/fs/sf x -40/27/100
C x 3.0/3.3/3.6 V; deterministic, no mismatch, no resistor/capacitor spread).
Fleet runner klt 0.5.0 against client 0.7.0 (`runner_compatibility:
mismatch`, version check `warn`; the same skew as #111). Each record's
`report.json` shows 45 results, all finite.

**Signal quality**, record `20261009-182102-e232b2f` (batch job
`klt-sim-cfe0e1417464`), 50 pF per line: PASS 45/45.

| Row (spec section 6) | Bound | Sky130 result (min / max, corner) | Verdict |
|---|---|---|---|
| Rise time, D+ and D- | 4-20 ns | 8.69 (`ff_100c_3.60v`) / 11.23 (`ss_-40c_3.00v`) | PASS 45/45 |
| Fall time, D+ and D- | 4-20 ns | 8.43 (`ff_100c_3.60v`) / 11.70 (`ss_-40c_3.00v`) | PASS 45/45 |
| Rise/fall matching, all four pairings | 0.9-1.1 | 0.9279 (`fs_100c_3.00v`) / 1.0772 (`sf_-40c_3.60v`) | PASS 45/45 |
| Crossover, rising and falling | 1.3-2.0 V | 1.4844 (`sf_-40c_3.00v`) / **1.9933** (`fs_100c_3.60v`) | PASS 45/45 |
| Monotonic single crossing | first = second = last | all slopes of the right sign; 1 rising and 1 falling crossing | PASS 45/45 |
| Aggregate FS signal quality | all of the above | derived from the rows above | PASS 45/45 |

Margins are thin in two places: crossover 6.7 mV below 2.0 V at the
fast-P/slow-N, hot, high-supply corner, and matching 0.9279 at `fs_100c_3.00v`
(bound 0.9). Mismatch and passive spread, which are not in the grid, could
move both; the PASS is for the deterministic grid only. The four rows that
failed in gf180 pass here; that is a sky130 measurement, not an inference from
gf180.

**Static**, record `20261009-185058-e232b2f` (batch job
`klt-sim-d7588a09de82`): PASS 45/45.

| Row | Bound | Sky130 result (min / max, corner) | Verdict |
|---|---|---|---|
| VOH, 15 kohm to ground | 2.8-3.6 V | 2.992 (`sf_100c_3.00v`) / 3.593 (`fs_-40c_3.60v`) | PASS 45/45 |
| VOH, 1.5 kohm to 3.6 V (literal reading) | 2.8-3.6 V | 3.012 (`fs_-40c_3.00v`) / 3.600 (`tt_27c_3.60v`) | PASS 45/45 (reaches the 3.6 V bound as the driver is pulled toward the 3.6 V load) |
| VOL, 1.5 kohm to 3.6 V | 0.0-0.3 V | 0.069 (`sf_-40c_3.60v`) / 0.097 (`fs_100c_3.00v`) | PASS 45/45 |
| Output resistance, driving high | 28-44 ohm | 29.8 (`fs_-40c_3.60v`) / 40.2 (`sf_100c_3.00v`) | PASS 45/45 |
| Output resistance, driving low | 28-44 ohm | 29.4 (`sf_-40c_3.60v`) / 42.2 (`fs_100c_3.00v`) | PASS 45/45 |
| Enable truth table (16 combinations, both lines) | driven 1 >= 0.95 VDD, driven 0 <= 0.05 VDD, released 0.48-0.52 VDD (engineering criteria) | driven high 2.994-3.595 V, driven low 4.5-7.2 mV, released 1.4999-1.8 V (VDD/2) | PASS 45/45 |

**Disabled-pad leakage (engineering data; no ratified limit exists and none is
applied):** pad forced 0-3.6 V while disabled, current out of the pad: -22.7
nA to +6.3 nA at 0, 1.5 and 3.0 V across the grid; the held line at VDD/2
carries -14.2 nA to +0.05 nA. **Forcing the pad to 3.6 V on a 3.0 V rail
forward-biases the output PMOS drain junction: -259 uA at `fs_100c_3.00v`** (-3
nA at `tt` 27 C 3.3 V). This is real behaviour of the schematic when the pad
can sit above `VDD` while the driver is disabled; no limit exists, so it is
reported, not judged, and is tracked as a follow-up (#130). Enable/disable
transitions into a pad forced to `VDD`/2: disabled current up to 14.2 nA
(`sf_100c_3.60v`), enable at 102.6-106.0 ns after the `OE` edge at 100 ns,
release at 209.9-226.4 ns after the 200 ns edge, enabled current 33-59 mA
(sign correct on all four pad-and-data cases), and a wrong-polarity peak of up
to 3.0 mA (`ff_-40c_3.60v`) during the transition; static supply current
150.8-254.7 uA (bias network).

**Limits of these PASSes.** (1) Schematic level: no mismatch / Monte Carlo, no
extracted parasitics, no layout, no pad or ESD. (2) The grid does not
exercise resistor or MIM capacitor process spread (item 2 above); both are in
the edge rate and the output resistance. (3) The load for VOH/VOL awaits DR-0004
ratification. (4) The harness job ran on a fleet runner older than the client.
(5) Two earlier attempts per experiment that the fleet refused for capacity
(`BATCH_MAX_CONCURRENT_INSTANCES`, then `batch_no_capacity`) are kept as FAIL
records; no local fallback was run.
