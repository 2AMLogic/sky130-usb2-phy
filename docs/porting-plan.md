# Analog porting plan: gf180-usb2-phy to sky130

Status: planning document, issue #106. Written 2026-10-09. **No analog
circuit exists in this repository yet.** Nothing here is a sky130 electrical
claim: every gf180 result quoted below is *source evidence* about the design
being ported, measured on a different PDK over a different PVT envelope.
sky130 results come only from the per-block port issues listed at the end,
each against this repo's ratified targets in
[`spec/usb2-phy.md`](../spec/usb2-phy.md) §6.

## The ruling this plan implements

Operator ruling, 2026-10-08, on
[#40](https://github.com/2AMLogic/sky130-usb2-phy/issues/40#issuecomment-6066642841):
the analog partition is in scope and is **ported from `gf180-usb2-phy` into
this repository**. No new sibling repositories are created. The PLL stays a
pinned reference to `sky130-pll` and is never designed here. The scope rule in
[`CLAUDE.md`](../CLAUDE.md), the partition in
[`spec/architecture.md`](../spec/architecture.md), the ownership column of
`spec/usb2-phy.md` §6, and
[DR-0003](../spec/decision-records/0003-analog-port-scope-and-squelch-disposition.md)
record the same thing.

Full-speed first still applies. Nothing in this plan, or in the port issues,
is shaped by high-speed requirements.

## Pinned sources

Every source read for this plan, at the commit read. The same files are
stamped (SHA-256 of the upstream bytes at that commit, `mode: fetched`) in
[`reuse.lock.json`](../reuse.lock.json). No gf180 bytes are committed here:
the sky130 schematics will be new designs, not vendored copies.

| Repo | Commit | Read for |
|---|---|---|
| `2AMLogic/gf180-usb2-phy` | [`0aab24943aa1379026ccebb8e5746580f1eb7947`](https://github.com/2AMLogic/gf180-usb2-phy/tree/0aab24943aa1379026ccebb8e5746580f1eb7947) | schematics, netlists, testbenches, current records, evidence index, spec |
| `2AMLogic/sky130-pll` | [`a0af4e4368e72dca764c4a87e292cd6f5aed15f4`](https://github.com/2AMLogic/sky130-pll/blob/a0af4e4368e72dca764c4a87e292cd6f5aed15f4/spec/target-spec.md) | `spec/target-spec.md`: output band, reference input, jitter metric |
| `2AMLogic/sky130-ldo` | [`7907775db9716676511eca1d53055b17b17ba200`](https://github.com/2AMLogic/sky130-ldo/tree/7907775db9716676511eca1d53055b17b17ba200) | README and `spec/target-spec.md`, for the pull-up supply question only (not imported) |
| open_pdks `sky130A` | `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (installed PDK) | which `sky130_fd_pr__*` device and resistor models exist, model L bins, resistor sheet parameters |

Source documents at the gf180 pin:

- Evidence index: [`sim/spec-coverage.md`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/sim/spec-coverage.md)
- Design notes: [`design/README.md`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/README.md)
- Spec: [`spec/usb2-device-phy.md`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/spec/usb2-device-phy.md)

### Fleet edges

The workspace reuse convention
([2am `REUSE.md`](https://github.com/2AMLogic/2am/blob/main/REUSE.md)) puts
map-level edges in `fleet-gitops/repos.yml`, not in this repository. Both
edges this port needs are **already recorded** there (read at
`fleet-gitops` `7105cc67488db53dbd59d79eda798ffc2b8f92a1`):

- `sky130-usb2-phy` `ported_from: [gf180-usb2-phy]`
- `sky130-usb2-phy` `consumes: [sky130-pll]`

No fleet-manifest edit is part of this plan. `reuse.lock.json` gives the
`consumes` edge its pin (the `sky130-pll` spec read for the interface check
below). REUSE.md names `spec/porting-plan.md` as the conventional location;
this plan lives at `docs/porting-plan.md` because issue #106 asked for it
there.

## What the source has, and what it does not

At the pinned commit, `gf180-usb2-phy` has five analog leaf cells, each an
xschem schematic with an exported netlist, and a 45-corner PVT sweep for
each electrical row (5 process corners x -40/27/125 degC x 2.97/3.30/3.63 V,
`gf180mcuD`, ngspice). Its evidence index states:

- **Four index rows fail, all of them driver rows**: rise/fall time,
  crossover voltage, rise/fall matching, and the aggregate full-speed signal
  quality row. Details in the driver section below.
- **Differential receiver sensitivity now passes**, 45/45 at each of three
  common-mode points (record `20261008-193113-2e9f63e`, after that repo's
  issue #97). The earlier 30/45 failure at 2.5 V common mode is superseded
  history and is **not** inherited.
- **No delivered analog layout.** All five blocks have committed layout
  *plans* (`layout/analog/plans/*.json`) but routing is incomplete and no
  analog GDS or analog LVS result is committed under `layout/`. Dated
  experimental GDS artifacts exist under
  `verification/records/analog-layout/artifacts/`; they are experiment
  outputs, not delivered layout. A port inherits none of the layout work
  (different PDK) and should not count it.

## What changes between the two environments

These deltas apply to every block and are why no gf180 number carries over.

| Aspect | gf180-usb2-phy (source) | sky130-usb2-phy (this repo) |
|---|---|---|
| PDK | `gf180mcuD` | `sky130A` |
| Supplies | single 3.3 V rail for logic and analog | 1.8 V core + 3.3 V I/O (`spec/usb2-phy.md` §5) |
| Analog PVT envelope | -40/27/125 degC, 2.97-3.63 V | -40...100 degC, I/O 3.0-3.6 V (DR-0001 Decision 5); corner set fixed by #109 |
| MOS devices | `nfet_03v3` / `pfet_03v3`, L >= 0.28 um | no direct equivalent; see "Device candidates" |
| Digital/analog boundary | same rail, no level shifting | 3.3 V analog <-> 1.8 V core needs level shifting (integration item, not owned by any port issue) |

### Device candidates (sky130, unresolved)

Read from the installed open_pdks `sky130A` library; existence of a model is
all this establishes. **No mapping is decided by this plan.** Each port issue
chooses, measures and records its own devices; voltage-class names alone are
not a mapping.

- MOS devices that see the 3.3 V rail:
  `sky130_fd_pr__nfet_g5v0d10v5` / `sky130_fd_pr__pfet_g5v0d10v5` (thick
  oxide; model bins start at L = 0.5 um, versus gf180's 0.28 um), and the
  native `sky130_fd_pr__nfet_03v3_nvt` (near-zero threshold, also L >= 0.5 um;
  not a drop-in for an enhancement device). The core `*_01v8*` devices are
  not candidates for anything across the 3.3 V rail. `spec/usb2-phy.md` §5
  already names this choice ("native 3.3 V vs. 5 V-tolerant thick-oxide
  devices operated at 3.3 V") as an implementation decision; it is now owed
  by the port issues in this repo.
- Resistors: `sky130_fd_pr__res_generic_po` (sheet parameter `rp1` 48.2
  ohm/sq nominal; the open_pdks parameter sets span 42.2-55.8),
  `sky130_fd_pr__res_high_po_*` and `res_xhigh_po_*` (fixed widths 0.35,
  0.69, 1.41, 2.85, 5.73 um), diffusion resistors (`res_generic_nd`/`pd`,
  with `__hv` variants), and interconnect resistors `res_generic_l1` (li1,
  12.2 ohm/sq nominal; 9.5-14.8) and `res_generic_m1` (met1, 0.125 ohm/sq;
  0.105-0.145). Which parameter set belongs to which process corner has to
  be read from the corner files at design time; the spans above are only
  the min and max values that appear.

## Per-block plan

One row per block. "Inherited failing rows" means rows that fail in the
gf180 evidence index at the pinned commit; a sky130 port starts from the same
topology and must re-measure them, not assume them fixed or failed.

| Block | Source (gf180 @ `0aab249`) | Source devices and resistors | sky130 choices owed (unresolved) | §6 targets at risk on sky130 | Inherited failing rows | Port issue |
|---|---|---|---|---|---|---|
| FS line driver | [`design/differential_driver.sch`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/differential_driver.sch), [`netlist`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/netlist/differential_driver.spice) | `nfet_03v3` x4, `pfet_03v3` x4; gate-slew `ppolyf_u` (W=1u L=2u) x2; series `rm1` (W=2u L=800u, ~36 ohm) x2 | MOS flavour and P:N ratio; series-resistor flavour (met1 / li1 / poly); slew resistor; add OE | rise/fall time, rise/fall matching, crossover, output resistance (28-44 ohm incl. FET Ron), VOH/VOL | **4**: rise/fall time (3/45), crossover voltage (2/45), rise/fall matching (36/45), aggregate FS signal quality | [#112](https://github.com/2AMLogic/sky130-usb2-phy/issues/112) |
| Differential receiver | [`design/differential_receiver.sch`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/differential_receiver.sch), [`netlist`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/netlist/differential_receiver.spice) | `nfet_03v3` x6, `pfet_03v3` x4; bias `ppolyf_u_1k` (W=2u L=400u) x1 | **Resolved (#111):** MOS `sky130_fd_pr__nfet_g5v0d10v5` / `pfet_g5v0d10v5` at L = 0.5 um (`nfet_03v3_nvt` and a complementary pair considered, not needed, not simulated); bias `res_xhigh_po_1p41` L = 140 um; pins `VDD VSS DP DM RXD`; `RXD` on the 3.3 V domain (level shifter and RTL input not designed). Reasons: [`design/README.md`](../design/README.md) | common-mode range 0.8-2.5 V at both ends; sensitivity > 200 mV | none (sensitivity passes 45/45 at the pin) | **Done at schematic level (#111):** [`design/differential_receiver.sch`](../design/differential_receiver.sch), record `20261009-121939-0555da1`, PASS 45/45 at each of 0.8 / 1.65 / 2.5 V (threshold -76...-12.5 mV; no mismatch run) | [#111](https://github.com/2AMLogic/sky130-usb2-phy/issues/111) |
| Single-ended receivers (D+, D-) | [`se_receiver_dp.sch`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/se_receiver_dp.sch), [`se_receiver_dm.sch`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/se_receiver_dm.sch), netlists [`dp`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/netlist/se_receiver_dp.spice) / [`dm`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/netlist/se_receiver_dm.spice) | each: `nfet_03v3` x6, `pfet_03v3` x4; `ppolyf_u_1k` x3 (VREF divider 1900/1400 ohm, bias) | MOS flavour; divider and bias resistor flavour | VIH > 2.0 V / VIL < 0.8 V threshold window under mismatch | none (45/45 each) | [#110](https://github.com/2AMLogic/sky130-usb2-phy/issues/110) |
| D+ pull-up and termination | [`design/dplus_pullup.sch`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/dplus_pullup.sch), [`netlist`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/design/netlist/dplus_pullup.spice) | `pfet_03v3` x66 (switches, 10 x W=100u each), `nfet_03v3` x6; ladder `ppolyf_u` (W=4u) x6: 1000 ohm base + 30/60/120/240/480 ohm binary trim | ladder resistor flavour, base value, LSB, bit count; switch device; VPU source; trim-code source | 1.5 kohm +/-5 % (trim range must cover sky130 sheet spread + temperature + switch Ron) | none (45/45 with best trim code per corner) | [#113](https://github.com/2AMLogic/sky130-usb2-phy/issues/113) |
| Analog sim harness (prerequisite) | **Done (#109):** [`sim/`](../sim/README.md) -- [`sim/corners.json`](../sim/corners.json) (45-point sky130 matrix), [`sim/run_corners.py`](../sim/run_corners.py), [`sim/check_records.py`](../sim/check_records.py); master = `gf180-usb2-phy` @ `0aab249` (immediate lineage; `gf180-bandgap` ancestry), read not vendored (see [`sim/README.md`](../sim/README.md) "Provenance and master"); smoke record [`sim/smoke-inverter/records/`](../sim/smoke-inverter/records/) | n/a | resolved: sky130A `sky130.lib.spice` sections tt/ff/ss/fs/sf, -40/27/100 C, 3.0/3.3/3.6 V | n/a | n/a | [#109](https://github.com/2AMLogic/sky130-usb2-phy/issues/109) |
| PLL | not ported: pinned reference to `sky130-pll` | n/a | n/a | jitter metric and band agreement (see PLL section) | n/a | none in this repo (integration) |
| Squelch / envelope detector | no source block exists (gf180 spec excludes it as HS-only) | n/a | n/a | n/a | n/a | none: disposition proposed in DR-0003 |

### FS line driver (#112)

Source topology per half: CMOS predriver -> poly gate-slew resistor -> large
complementary output stage (P 60u / N 30u) -> `rm1` series resistor (~36 ohm)
-> pad. Pin contract: `differential_driver VDD VSS TXDP TXDM DP DM`, no
output enable.

Inherited failures, from the index at the pin (record
[`20260817-203552-a408cb6`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/sim/driver-signal-quality/records/20260817-203552-a408cb6.md)):

| Row | gf180 verdict | Stated mechanism |
|---|---|---|
| Rise/fall time 4-20 ns | FAIL 3/45, worst `ss_125c_2.97v` 22.33 ns | weakest-drive corner; `tt` is 15.1 ns |
| Crossover voltage 1.3-2.0 V | FAIL 2/45, `fs_27c_2.97v` 1.2935 V, `fs_-40c_2.97v` 1.2968 V | fast-N/slow-P skew |
| Rise/fall matching within 10 % | FAIL 36/45, ratio 0.979-1.402 | pull-up weaker than pull-down |
| Full-speed signal quality (aggregate) | FAIL on the rows above; monotonic single crossing passes 45/45 | aggregate |

Gaps the source does not cover and the port must add: an output-enable path
(§6 "Control interface from UTMI layer" requires drive enable and OE, and
`rtl/usb_utmi_top.v` already drives `tx_drive_en`, `tx_oe`, `tx_dp`,
`tx_dn`); and measurements of VOH/VOL and output resistance, which have no
row in the source index.

Note on naming: §6 calls these "current-mode drivers". The source is a
voltage-mode CMOS driver with a series resistor, which is the usual FS
structure; current-mode drive is the HS technique. This plan does not
rename the ratified row; it records the difference so a reader does not
assume an HS-style driver is being ported.

### Differential receiver (#111)

Source: NMOS 5T OTA plus a two-inverter buffer, with the first inverter made
P-heavy (32u/2u) so its trip point sits near the OTA's balanced output. Pin
contract: `differential_receiver VDD VSS DP DM RXD`, no enable.

The mechanism the source fixed in its issue #97 (an NMOS-input OTA cannot
pull its output below its tail node, so at 2.5 V common mode a mid-rail
buffer never reads a K state) is a property of the topology, not of gf180.
On sky130's thick-oxide devices the 0.8 V floor (tail plus input-pair V_GS)
and the 2.5 V ceiling were both at risk; both were measured in #111 (schematic
level, no mismatch) and the ported topology passes with the P-heavy buffer
(see `design/README.md`).

### Single-ended receivers (#110)

Same OTA/buffer core comparing each line to a ratiometric `VREF` (1.4 V at
3.3 V by a 1900/1400 ohm divider). Pin contracts:
`se_receiver_dp VDD VSS DP RXDP`, `se_receiver_dm VDD VSS DM RXDM`. The two
cells differ only in pin names, so they share one issue. The 0.6 V margin each
side of `VREF` is eaten by comparator offset, which a DC sweep does not
model.

Integration note: `rtl/usb_utmi_top.v` takes `dp`/`dm` as 1.8 V digital
inputs and derives `LineState` from them. The receiver outputs are on the
3.3 V domain, and the RTL has no input for the differential receiver's
`RXD` today. Both are integration items.

### D+ pull-up and termination (#113)

Source: 1.5 kohm nominal trim ladder (1000 ohm base + 5-bit binary,
`ppolyf_u`), PMOS bypass switches, enable switch, fail-safe all-zero default
(maximum resistance). Pin contract:
`dplus_pullup DP VPU_REG VSS PU_EN TRIM0..TRIM4`. Its PASS is "some trim code
lands in band at every corner", i.e. trim selected at test.

Unresolved for sky130:

- **Pull-up supply.** §6 requires the pull-up to go to an internally
  regulated 3.0-3.6 V. The source takes `VPU_REG` as an input and builds no
  regulator. Options: an integrator-supplied rail; the 3.3 V I/O rail itself
  if its envelope is guaranteed inside 3.0-3.6 V (DR-0001 Decision 5 states
  I/O 3.0-3.6 V, the same window); or a regulator from `sky130-ldo`. The
  last is recorded as `in_tree` `status: evaluate` in `reuse.lock.json`.
  **The question:** can a sky130 sibling supply a regulated 3.0-3.6 V pull-up
  rail? `sky130-ldo`'s ratified product (at `7907775`) is a 3.3 V-in /
  1.8 V-out regulator (`design/ldo_3v3in_1v8out.sch`), so it is not a drop-in;
  adopting it would need a different output or a higher input such as VBUS.
  No edge is added until this is decided.
- **Trim-code source.** No OTP/fuse/scan exists here and the UTMI interface
  has no trim port.
- **Enable source.** `PU_EN` is the analog end of §6's pull-up enable row.
  `rtl/usb_utmi_top.v` synchronizes `TermSelect` and has no consumer for it.
- **15 kohm pull-downs.** §6 lists "Downstream port pull-downs 15 kohm +/-5 %
  on each of D+/D-". Those are host / downstream-port resistors; this repo is
  a single-role FS device (§3). The source models the host's 15 kohm as a
  testbench load. #113 does the same and builds no on-die pull-downs; whether
  the row applies to this block is an open spec question recorded in DR-0003.

### PLL (pinned reference, not ported)

`sky130-pll` at `a0af4e4` was read for interface agreement only:

- Output band 10-200 MHz is **DRAFT** there ("carried from gf180-pll and NOT
  assumed to hold"); this repo needs 144 MHz.
- Reference input 1-25 MHz is **DRAFT**; this repo needs 12 MHz.
- Its ratified jitter row is **period jitter <= 1.0 % of the output period,
  RMS**. This repo's requirement (DR-0001 Decision 1) is **accumulated
  12-UI peak-to-peak jitter < 4.17 ns** at 144 MHz. The metrics differ, so
  neither repo's row can yet be checked against the other's measurement.
- Its LVS closure is
  [sky130-pll#18](https://github.com/2AMLogic/sky130-pll/issues/18), still
  open.
- `sky130-pll`'s spec names no consumer. Per REUSE.md ("its consumers are its
  spec"), this repo's requirement rows should be filed on `sky130-pll` when
  integration starts; this plan does not file them.

### Squelch / envelope detector

No source block exists: the gf180 spec explicitly excludes squelch as an HS
feature. This repo's §6 still lists two squelch rows. The FS/HS rationale and
the proposed removal (pending ratification; the ratified rows are unchanged)
are in
[DR-0003](../spec/decision-records/0003-analog-port-scope-and-squelch-disposition.md).

## Blockers: planning versus integration

| Item | Blocks planning (this document)? | Blocks block-level port issues? | Blocks integration? |
|---|---|---|---|
| #109 analog sim harness | no | **yes** (all four) | yes |
| Digital P&R (#105), synthesis follow-ups (#104) | no | no | yes |
| sky130-pll LVS (sky130-pll#18), band and jitter-metric agreement | no | no | yes |
| Pull-up supply source (`sky130-ldo` evaluate) | no | no (#113 keeps VPU an input) | yes |
| Trim-code source for the pull-up | no | no | yes |
| 3.3 V <-> 1.8 V level shifting at the analog/digital boundary | no | no | yes |
| Squelch and 15 kohm row disposition (DR-0003 ratification) | no | no | yes (spec closure) |

## Follow-up issues filed from this plan

All filed as children of #106 with `loom:triage`; each needs its own Curator
pass.

| Issue | Block | Depends on |
|---|---|---|
| [#109](https://github.com/2AMLogic/sky130-usb2-phy/issues/109) | analog sim harness and 45-corner sky130 PVT matrix | none |
| [#110](https://github.com/2AMLogic/sky130-usb2-phy/issues/110) | single-ended receivers (D+, D-) | #109 |
| [#111](https://github.com/2AMLogic/sky130-usb2-phy/issues/111) | differential receiver | #109 |
| [#112](https://github.com/2AMLogic/sky130-usb2-phy/issues/112) | FS line driver (four inherited failing rows) | #109 |
| [#113](https://github.com/2AMLogic/sky130-usb2-phy/issues/113) | D+ pull-up and termination | #109 |

Not filed, and why: layout/DRC/LVS per block (needs the schematics first);
assembly and level shifting (needs all four blocks); PLL integration (needs
sky130-pll#18 and the metric agreement above); squelch (proposed removal,
DR-0003).

This plan does not complete any T1 analog item. T1 items 1, 2, 5 and 7
(analog) stay `unmet` until the port issues land evidence.
