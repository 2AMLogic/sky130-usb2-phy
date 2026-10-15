# Disabled-pad voltage envelope and current budget (study for #130)

Desk analysis. No simulation was run and no artifact was regenerated. Every
number from the simulator is read from the committed record
`sim/driver-static/records/20261009-185058-e232b2f.md` and its
`sim/driver-static/corners/20261009-185058-e232b2f/evidence.json`
(driver-static, 45-point PVT grid, schematic level). The -259 uA figure is
**engineering data**: no limit for disabled-pad behaviour is ratified in
`spec/usb2-phy.md` section 6, so it is neither a pass nor a fail, and nothing
here is a signoff or compliance claim. The accompanying
[DR-0006](../spec/decision-records/0006-disabled-pad-leakage-envelope.md) is
**proposed**, not ratified.

## 1. The observation, restated from the record

With the driver disabled (`OE` = 0, or `DRVEN` = 0) the output PMOS is off but
its drain-bulk junction is not: its bulk is `VDD`, so a pad above `VDD` plus a
diode drop conducts into the pad's forcing source (current reported negative,
out of the forcing source into the cell). Read from `evidence.json`
(`leak_dp_3p6v_na`, pad forced to 3.6 V, D+ instance disabled by `OE` = 0):

| Rail (`VDD`) | Pad over rail | `tt` -40 C | `tt` 27 C | `tt` 100 C | worst of 5 process corners at 100 C |
|---|---|---|---|---|---|
| 3.0 V | +0.6 V | -0.90 uA | -15.8 uA | -124 uA | -258.8 uA (`fs`) |
| 3.3 V | +0.3 V | -0.07 nA | -3.1 nA | -234 nA | -1.21 uA (`fs`) |
| 3.6 V | 0.0 V | -0.05 nA | -0.23 nA | -11.9 nA | -27.3 nA (`sf`) |

Counts over the 45 points: 13 have a 3.6 V pad current below -1 uA and 8 below
-10 uA, **all 8 at the 3.0 V rail**. The 0 / 1.5 / 3.0 V pad points stay within
-22.7 nA to +6.3 nA at every one of the 45 points. Two things the record does
**not** contain: a measurement at a pad voltage between 3.0 V and 3.6 V (the
sweep ran at 50 mV steps but only 0 / 1.5 / 3.0 / 3.6 V were measured), and any
case with `VDD` below 3.0 V or off. The cause above (PMOS drain-bulk junction)
is the record's own reading of the mechanism; it has not been independently
confirmed (no device-level current partition was run).

The leakage is a steep function of how far the pad sits above `VDD`, and of
temperature, not a fixed offset. That is why the envelope question, not the
number, is the first-order issue.

## 2. Case table

"Reachable?" is a statement about the integrated PHY. Where the spec or the
repo does not say, the cell says **unknown**; nothing is assumed. `VDD` is the
I/O rail (3.0-3.6 V, `spec/usb2-phy.md` section 5, DR-0001 Decision 5).
`VPU` is the D+ pull-up supply.

| # | Case | Max pad voltage vs `VDD` | Driver state | Reachable in the integrated PHY? | Basis |
|---|---|---|---|---|---|
| C1 | External bus drive (host or hub driving D+/D-) while this device is receiving, rail up | Host high level up to 3.6 V (section 6 VOH bound: 2.8-3.6 V). `VDD` may be 3.0 V. Pad up to **+0.6 V over rail** | Disabled (`OE` = 0 when not transmitting) | **Yes, if the I/O rail and the host's signal rail are independent.** Nothing in the repo ties them or bounds `VDD` against bus level. Undetermined for a specific integration | Spec section 6 (VOH 2.8-3.6 V); section 5 and DR-0001 Decision 5 (`VDD` 3.0-3.6 V, independently stated) |
| C2 | D+ pull-up (#113) pulling D+ to `VPU` while the driver is idle | `VPU` is 3.0-3.6 V (section 6 pull-up row); `VDD` is 3.0-3.6 V. Independent ranges give pad up to **+0.6 V over rail** | Disabled | **Undetermined.** `VPU` is an input of `dplus_pullup` and its source is open (porting-plan "Pull-up supply"): an integrator rail, the I/O rail itself (then `VPU` = `VDD`, pad never over rail by this path), or a regulator (not designed here) | `docs/porting-plan.md` section "D+ pull-up and termination (#113)"; `design/README.md` pin table (`VPU`) |
| C3 | Attach: pull-up enabled (`PU_EN`) while the driver is disabled | As C2 | Disabled (the driver is not transmitting during attach) | Same as C2. The enable path itself is **unknown**: `PU_EN` has no RTL consumer (`TermSelect` is synchronized and unused) | `docs/porting-plan.md` "Enable source"; `rtl/usb_utmi_top.v` (not changed here) |
| C4 | Suspend with `VDD` on | As C1/C2 | Disabled | Reachable by the same mechanisms as C1/C2 while `VDD` is up. Whether `VDD` stays up in suspend is **unknown**; the digital side only provides `SuspendM` | `spec/usb2-phy.md` section 3 (`SuspendM`), section 6 ("reset/attach/suspend sequencing") |
| C5 | Suspend or standby with `VDD` **off** (0 V) while the bus or `VPU` is up | Pad up to 3.6 V against a 0 V rail: **over rail by up to 3.6 V** | Disabled, with all drivers unpowered | **Undetermined and worse than the measured case.** Not simulated (the record's lowest rail is 3.0 V). The pull-up of the output PMOS bulk would be the only conduction path to a collapsed rail | Not covered by the record; no spec statement on supply sequencing |
| C6 | Attach before the rail is up (bus or `VPU` already present, `VDD` ramping) | Transient pad over a partially risen `VDD` | Disabled, controls undefined until the rail is up | **Unknown.** No power-sequencing statement exists in the spec, `design/README.md` or the porting plan. The disable state during ramp is not defined (`DRVEN`/`OE` are `VDD`-domain inputs with undefined levels at low `VDD`) | Absence of any sequencing text in `spec/` and `design/README.md` |
| C7 | Pad over rail only because of device transients (overshoot, reflections at a 3.0 V rail) | Beyond static bus levels | Disabled | **Unknown.** The record is DC; no transient pad-voltage excursion was measured | Record Method: single DC sweep only |
| C8 | Operation with the pad never above `VDD` (option c) | 0 V | n/a | **Not established.** Holds only if C1-C6 are all excluded by an integration contract, which none states today | -- |

Missing connectivity or sequencing information, listed as unknown and not
assumed: (a) whether `VDD` and the host's signal rail are the same rail;
(b) the source of `VPU` and whether it can exceed `VDD`; (c) the `PU_EN` /
`TermSelect` connection and its timing; (d) whether `VDD` is held up during
suspend; (e) power-up order of `VDD`, `VPU` and the bus; (f) pad-level
overshoot; (g) the pad ring itself (no pad or ESD structure is modelled; the
driver "is not current-limited or ESD-protected here", `design/README.md`).

## 3. Is an over-rail disabled pad reachable?

**Undetermined, leaning yes.** C1 and C2 both reach +0.6 V over a 3.0 V rail
using only ranges the ratified spec itself states (VOH up to 3.6 V; pull-up
supply 3.0-3.6 V; I/O rail 3.0-3.6 V); they are excluded only by an
integration fact that no document in this repo supplies (`VDD` and the
bus/`VPU` level tracking each other). C5 and C6 depend on sequencing the repo
does not define at all. The case supporting "no" is narrow: `VPU` = `VDD` (the
I/O rail used for the pull-up) *and* a host whose levels never exceed `VDD`.
The case table shows the set of conditions that would have to be written down
to make the answer "no"; it does not show that they hold.

## 4. Proposed current budget (design target; not ratified, not verified)

A number can be proposed for the envelope the data covers, and cannot yet be
proposed for the rest.

| Item | Proposal |
|---|---|
| Polarity | Report signed current (positive out of the pad into the forcing source) and check worst **absolute** value; a positive-MAX-only check misses the failing sign (the record's `leak_*_max_na` is positive and small while `leak_*_min_na` is the -259 uA) |
| Pad range, in-rail | 0 V up to `VDD` |
| Disable states | `OE` = 0 and `DRVEN` = 0, both pads |
| PVT scope | the existing 45-point grid (`sim/corners.json`); resistor-process spread remains out of scope per DR-0005 |
| In-rail budget | `|I|` <= **10 uA** for 0 V <= pad <= 3.3 V. This number is anchored on the full-speed hi-Z data-line leakage limit as the author reads it from USB 2.0 Chapter 7 (about +/-10 uA, 0 < V < 3.3 V); the specification PDF is not available in this environment, so the value and its table number are **unverified** and the ratifier must confirm them (the same caveat as DR-0004). Existing in-rail data (<= 22.7 nA at 0 / 1.5 / 3.0 V pad) would sit three orders below it, but a 3.0-3.3 V pad on a 3.0 V rail is **not** measured |
| Over-rail budget (pad above `VDD`) | **No number proposed.** An over-rail limit is only meaningful once the envelope is chosen (how far above `VDD`, for how long, with what source impedance, and whether it also covers `VDD` off). The data shows 1.2 uA at +0.3 V over a 3.3 V rail at worst-case 100 C and 258.8 uA at +0.6 V over a 3.0 V rail, so any limit between those is a choice between a driver change and an integration restriction, and that choice is the ratification this study does not make |
| Remaining condition for the in-rail row | The 10 uA figure applies only after the 3.0-3.3 V pad point on a 3.0 V rail is measured; as a proposal it adds a needed future testbench check, not a result |

## 5. What this study does and does not conclude

- It does **not** conclude that the driver fails or passes anything, and it
  adds no limit to `spec/usb2-phy.md`.
- It does **not** select option b (3.6 V pad tolerance) or option c
  (restrict to pad <= `VDD`); those remain operator choices once the unknowns
  in section 2 are resolved. A circuit change (floating-well PMOS or isolated
  structure) is out until a record is ratified; nothing in `design/` is
  touched.
- The next evidence step, after ratification of an envelope, is a new
  driver-static measurement set (pad points between 3.0 and 3.6 V, rails
  below 3.0 V and off, signed and absolute current), which is a separate
  issue.

## 6. Test-plan edge cases from the issue

- Pull-up supply 3.6 V with rail 3.0 V: case C2 (and the measured -259 uA row
  of section 1).
- Suspend with rail off: case C5, unmeasured.
- Attach before rail up: case C6, unmeasured and undefined sequencing.

## References

`spec/usb2-phy.md` sections 3, 5, 6; `spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`
Decision 5; `spec/decision-records/0003-analog-port-scope-and-squelch-disposition.md`;
`spec/decision-records/0004-fs-driver-voh-vol-load-conditions.md`;
`spec/decision-records/0005-resistor-sheet-resistance-corner-coverage.md`;
`design/README.md` (driver and pull-up pin tables); `docs/porting-plan.md`;
issues #112 (driver port), #113 (D+ pull-up), #23 (evidence epic), #130.
