# USB 2.0 PHY — target specification

**Status: Ratified 2026-08-05.** This document is the authoritative spec for
this repo. `README.md` points here instead of duplicating values; where
[`spec/architecture.md`](architecture.md) (issue #2) stated a number as
DRAFT pending this ratification, this document is the resolved source of
truth — architecture.md has been updated to point back here instead of
re-stating the numbers.

Source of truth for every hard number below is the USB Implementers Forum's
*Universal Serial Bus Specification, Revision 2.0* (frozen since April 2000).
Section/table references are to that document's Chapter 7 ("Electrical").

## 1. Scope

This spec covers the **digital UTMI-side PHY** built in this repo and the
**interface requirements** it hands to the analog sibling canary blocks
(PLL, current-mode drivers, differential receivers, squelch/envelope
detector, pull-up/pull-down). It does not specify how any sibling block is
built internally — see CLAUDE.md's scope-discipline rule and
`spec/architecture.md`'s partition table for the build-here / sibling-canary
boundary.

## 2. Signaling and speed target

| Parameter | Target | Stretch (not a commitment) |
|---|---|---|
| Signaling | USB 2.0 full-speed (FS), 12 Mbps | high-speed (HS), 480 Mbps |
| Bit period | 83.33 ns (1 / 12 Mbps) | 2.083 ns (1 / 480 Mbps) |

**Decision: FS-only architecture now; HS is an explicit non-commitment.**
FS is designed and verified cleanly on its own merits. HS requirements do
**not** constrain any FS architectural choice in this repo — per CLAUDE.md's
"Full-speed first" rule, a later HS effort accepts rework rather than the FS
core carrying speculative HS accommodations today. See Decision Log §8.1.

## 3. Digital interface: UTMI

| Parameter | Value |
|---|---|
| Interface | **UTMI** (not UTMI+) |
| Data bus width | 8 bits, parallel |
| Interface clock | 30 MHz (FS operation) |
| Core signals | `TxValid`, `TxReady`, `DataOut[7:0]` (TX path); `RxValid`, `RxActive`, `RxError`, `DataIn[7:0]` (RX path); `LineState[1:0]`; `OpMode[1:0]`; `TermSelect`; `XcvrSelect`; `SuspendM`; `Reset` |

**Decision: UTMI, not UTMI+, at 8-bit width, 30 MHz.** UTMI+'s additions
over UTMI (OTG session-request signaling, Serial-Mode/carkit interfaces,
enhanced low-power link states) exist to support dual-role/OTG operation and
HS-specific link power states. This block is a single-role FS-only device
today, so none of that is load-bearing. The 60 MHz HS interface clock a
UTMI+ or HS-capable UTMI implementation would need is intentionally **not**
reserved in silicon — see Decision Log §8.2. `spec/architecture.md`'s block
diagram already assumed this 8-bit width; this section ratifies it as the
binding interface rather than a draft assumption.

## 4. Reference clock and PLL interface requirement

| Parameter | Value | Basis |
|---|---|---|
| Reference input | 12 MHz crystal/resonator | On-chip PLL reference |
| Reference frequency tolerance | ±0.25% (2500 ppm), unsynchronized to host SOF | USB 2.0 §7.1.11, FS data rate tolerance |
| PLL output | Oversampling clock for bit/edge synchronization logic | Feeds the digital half of clock/data recovery (`spec/architecture.md`) |
| Oversampling ratio | 12× minimum (144 MHz internal clock) | Typical FS implementation; owed *to* this repo by the PLL, not the reverse |
| **PLL output jitter budget** | **Cycle-to-cycle jitter < 5% of one FS bit period, i.e. < 4.17 ns at 144 MHz (12× oversampling of 12 Mbps)** | Engineering derivation (see note below), **not** a literal USB 2.0-stated PLL jitter number |

**Jitter budget derivation, stated honestly:** USB 2.0 does not specify a
PLL jitter number directly — FS has no eye-diagram/jitter-template
requirement in the way HS does. The 12 Mbps ± 0.25% tolerance in §7.1.11
bounds the *transmitted bit rate*, not the *recovery clock's* jitter. The
< 5%-of-bit-period figure above is this repo's own derived margin: the
bit/edge synchronization logic must reliably locate NRZI transitions within
each 12×-oversampled clock period, and 5% headroom leaves sampling margin
against reference-clock tolerance, oversampling-clock duty-cycle
imperfections, and cable-induced signal transitions without eating the full
sampling window. This derived number — **< 4.17 ns cycle-to-cycle jitter at
144 MHz** — is the hard requirement handed to whichever sibling canary repo
builds the PLL. If that repo's PLL cannot meet it, the oversampling ratio
(currently 12×) is the parameter to renegotiate, not this budget.

**Decision: 12 MHz input + on-chip PLL, confirmed.** See Decision Log §8.3.

## 5. Supply architecture

| Rail | Voltage | Basis |
|---|---|---|
| Core (digital UTMI logic) | 1.8 V | sky130 core-device / standard-cell library nominal (`sky130_fd_sc_hd` and peers characterize at 1.8 V) |
| I/O (pad ring, analog-facing) | 3.3 V | sky130 3.3 V-class I/O devices; matches USB FS driver/receiver voltage range with margin |

**Decision: 3.3 V I/O + 1.8 V core, confirmed against USB FS electrical
requirements.** FS driver static output high (VOH) ranges 2.8–3.6 V with a
1.5 kΩ pull-up regulated to 3.0–3.6 V (USB 2.0 Table 7-2, §7.1.5), and
receiver common-mode input range is 0.8–2.5 V (§7.1.4) — both sit
comfortably inside a 3.3 V nominal I/O rail with headroom to the 3.6 V
ceiling. 1.8 V core logic matches sky130's standard digital cell library
without requiring level-shifted core devices for the UTMI-side logic. The
exact 3.3 V-tolerant sky130 device flavor used for the analog pad ring
(native 3.3 V vs. 5 V-tolerant thick-oxide devices operated at 3.3 V) is an
implementation decision for whichever sibling canary block owns the pad
ring, not this repo — only the supply *split* is ratified here. See
Decision Log §8.4.

## 6. Analog sub-block interface requirements

These are **interface requirements**, not designs — what this block needs
from each sibling canary block, stated as numbers with units. How each is
built is out of scope here (CLAUDE.md scope-discipline rule). This table is
the ratified, authoritative version of the same table drafted in
`spec/architecture.md` (issue #2); the two are now cross-checked and agree.

| Sibling block | Interface requirement | Target value | USB 2.0 basis |
|---|---|---|---|
| PLL | Reference input | 12 MHz ±0.25% (2500 ppm) crystal/resonator | §7.1.11, FS clock tolerance, unsynchronized |
| PLL | Output jitter (cycle-to-cycle, feeding oversampling clock) | < 5% of one bit period (< 4.17 ns at 144 MHz, 12× oversampling of 12 Mbps) | Derived — see §4 |
| PLL | Oversampling ratio delivered to bit/edge sync logic | 12× minimum | Typical FS implementation; owed to this repo by the PLL |
| Current-mode drivers | Output voltage swing, static | VOH 2.8–3.6 V (1.5 kΩ pull-up to 3.6 V), VOL 0.0–0.3 V | Table 7-2, FS driver |
| Current-mode drivers | Driver output resistance | 28–44 Ω | Sets differential line impedance with cable |
| Current-mode drivers | Rise/fall time | 4–20 ns (10%–90%), matched to within 10% rise vs. fall | §7.1.2, FS driver characteristics |
| Current-mode drivers | Output signal crossover voltage | 1.3–2.0 V | §7.1.2 |
| Current-mode drivers | Control interface from UTMI layer | Differential drive enable, output enable (OE), TxD+/TxD− data lines | Digital-to-analog handoff at the scope boundary |
| Differential receivers | Differential input sensitivity | \|(D+) − (D−)\| > 200 mV | §7.1.4 |
| Differential receivers | Common-mode input range | 0.8–2.5 V | §7.1.4 |
| Differential receivers | Single-ended receiver thresholds | VIH > 2.0 V, VIL < 0.8 V | §7.1.4, used for SE0/EOP detection |
| Squelch / envelope detector | Squelch detection threshold (differential envelope) | 100–200 mV | Table 7-2 |
| Squelch / envelope detector | Output interface to UTMI layer | Single-bit `SQUELCH`/`LineState` status, sampled at the oversampling clock rate | Feeds RxActive generation in the UTMI layer |
| Pull-up/pull-down and termination | FS device D+ pull-up | 1.5 kΩ ±5% to internally regulated 3.0–3.6 V | §7.1.5, speed signaling |
| Pull-up/pull-down and termination | Downstream port pull-downs | 15 kΩ ±5% on each of D+/D− | §7.1.5 |
| Pull-up/pull-down and termination | Control interface from UTMI layer | Single-bit pull-up enable/disable, driven during reset/attach/suspend sequencing | Digital-side ownership of an analog-side element |

## 7. Verification scope

**Decision: the floor for this repo's current milestone is a bit-exact
UTMI-level cocotb suite.** It exercises the digital UTMI-side logic (NRZI
encode/decode, bit stuffing/destuffing, SOP/EOP/RESET/suspend sequencing,
`LineState` reporting) against a behavioral ideal-transceiver stub that
reproduces DP/DM-level signaling without electrical simulation — this is
`spec/architecture.md`'s "first buildable slice," and it is sufficient to
reach "UTMI RTL verified" on the README's maturity ladder independent of
when the analog sibling blocks land.

**Link-level USB-IF compliance testing (electrical signal quality,
protocol-analyzer captures, host interoperability) is explicitly deferred
out of scope for this repo.** Trigger to revisit: once the analog assembly
(PLL + drivers + receivers + squelch detector) is integrated and the block
reaches "DRC/LVS-clean" or "shuttle seat" on the README's maturity ladder —
compliance testing needs either real silicon or an analog-inclusive
simulation testbench, neither of which exists pre-assembly. See Decision
Log §8.5.

## 8. Decision log

Every decision below was either resolved with a stated value (§§2–7) or
explicitly deferred with a trigger condition. This log records the
resolution and rationale; the binding values live in the sections above.

### 8.1 FS-only, or FS with an HS path designed in?

**Resolved: FS-only architecture now.** HS requirements do not constrain
any FS architectural decision. **Trigger to revisit:** if/when HS (480
Mbps) becomes a funded or prioritized project goal — e.g. a sibling HS
driver/receiver/squelch canary block is commissioned, or a roadmap decision
explicitly funds HS work. Until that trigger fires, HS accommodation is not
a factor in any FS design choice made in this repo.

### 8.2 UTMI vs UTMI+, and data-bus width

**Resolved: UTMI (not UTMI+), 8-bit data bus, 30 MHz FS interface clock.**
UTMI+'s incremental signaling (OTG session request, enhanced low-power link
states) serves dual-role/OTG and HS link-power scenarios this single-role
FS-only block does not need. No trigger — revisit only if the block's role
changes (e.g. OTG support becomes a goal), which is a distinct decision from
the HS trigger in §8.1.

### 8.3 Reference clock and PLL jitter budget

**Resolved: 12 MHz input, on-chip PLL, confirmed.** Jitter budget of
< 4.17 ns cycle-to-cycle at the 144 MHz (12×) oversampling clock is
**derived** (not a literal USB 2.0 PLL spec value — USB 2.0 does not specify
FS PLL jitter directly) from the bit/edge synchronization logic's sampling
margin requirement; see §4 for the full derivation and honesty note. This
number is levied on the sibling PLL canary repo as a hard interface
requirement. No trigger to revisit unless the oversampling ratio (12×)
changes, in which case the jitter budget is recomputed from the same
< 5%-of-bit-period rule.

### 8.4 Supply split

**Resolved: 3.3 V I/O, 1.8 V core, confirmed** against sky130's device
flavors and USB FS driver/receiver voltage ranges (§5). No trigger — fully
resolved, not deferred.

### 8.5 What "verified" means at the block boundary

**Resolved: bit-exact UTMI-level cocotb suite is the floor for this repo's
current milestone; link-level USB-IF compliance testing is deferred.**
**Trigger to revisit:** once the analog assembly is integrated and the
block reaches "DRC/LVS-clean" / "shuttle seat" maturity — see §7.

### 8.6 Cross-check against `spec/architecture.md` (issue #2)

Issue #2 landed first (`spec/architecture.md`, merged before this issue's
ratification) with the analog sub-block interface numbers marked DRAFT,
explicitly pending this cross-check. The numbers in §6 above were carried
forward from that draft **unchanged** — independent re-derivation from the
USB 2.0 spec (Chapter 7, as cited per-row) confirmed them, so this counts as
a completed cross-check rather than a reconciliation of a conflict.
`spec/architecture.md` has been updated (same PR) to drop its "DRAFT" /
cross-check-pending language and point to this document as authoritative,
per that document's own forward-reference.

## 9. References

- USB Implementers Forum, *Universal Serial Bus Specification, Revision
  2.0*, April 2000 — Chapter 7 ("Electrical"), specifically §7.1.2 (driver
  characteristics), §7.1.4 (receiver characteristics), §7.1.5
  (pull-up/pull-down resistors), §7.1.11 (frequency/timing tolerances), and
  Table 7-2 (driver/receiver DC electrical characteristics).
- [`spec/architecture.md`](architecture.md) — block diagram and
  build-here/sibling-canary partition table (issue #2).
- [Vlsir/Usb2Phy](https://github.com/Vlsir/Usb2Phy) — prior open-source
  sky130 USB 2.0 PHY attempt (analog half only, dormant since February
  2023); referenced for partitioning sanity-check, not copied from.
