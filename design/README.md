# design

Analog schematics (xschem). One block per port issue (so far: `differential_receiver`, below): the analog blocks are ported here from `gf180-usb2-phy` (operator ruling 2026-10-08, #40) — see [`docs/porting-plan.md`](../docs/porting-plan.md).

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
