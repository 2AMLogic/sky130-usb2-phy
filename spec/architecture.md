# Architecture and partitioning

Status: drafted 2026-08-05, tracks issue #2. Interface requirement values
are recorded once, in the now-ratified
[`spec/usb2-phy.md`](usb2-phy.md) §6 (issue #1, ratified 2026-08-05); this
document shows *where* each requirement applies (block diagram, partition
table) and should be read alongside, not instead of, the ratified spec.

**Partition revised 2026-10-09 (issue #106)** to the operator ruling of
2026-10-08 on #40: the analog blocks are ported from `gf180-usb2-phy` into
this repo, and the PLL stays a pinned reference to `sky130-pll`. The ruling
and the ownership changes it makes are recorded in
[`decision-records/0003-analog-port-scope-and-squelch-disposition.md`](decision-records/0003-analog-port-scope-and-squelch-disposition.md);
the per-block port plan is [`docs/porting-plan.md`](../docs/porting-plan.md).
No interface value changed.

## Why this document exists

A USB 2.0 PHY is an assembly. This document draws the line between what
this repo builds (the digital UTMI side, and the analog front end ported
from `gf180-usb2-phy`) and what it consumes from elsewhere (the PLL, from
`sky130-pll`), so that line is visible at review time instead of being an
agent's private judgment call. See CLAUDE.md's "Scope discipline" note —
this is the document that makes it enforceable.

## Block diagram

```
                                   sky130-usb2-phy (this repo)
                                  ┌──────────────────────────────────────────┐
                                  │                                          │
  UTMI ─────────────────────────▶│  ┌────────────┐                          │
  (parallel, 8-bit @ 30/60 MHz)  │  │ UTMI digital│                          │
  ◀─────────────────────────────│  │   layer     │                          │
                                  │  └──────┬─────┘                          │
                                  │         │ NRZI byte stream +             │
                                  │         │ TxValid/RxValid/RxActive       │
                                  │         ▼                                │
                                  │  ┌────────────────┐                      │
                                  │  │ Serializer /   │                      │
                                  │  │ deserializer   │                      │
                                  │  │ (bit stuff /   │                      │
                                  │  │  destuff, S/P) │                      │
                                  │  └───────┬────────┘                      │
                                  │          │ serial NRZI bit stream        │
                                  │          ▼                               │
                                  │  ┌────────────────────┐                  │
                                  │  │ Bit / edge          │                 │
                                  │  │ synchronization      │◀── oversampling│
                                  │  │ logic (clock/data    │    clock (N×)  │
                                  │  │ recovery, digital     │                │
                                  │  │ half)                │               │
                                  │  └───────┬───────┬──────┘                │
                                  │          │       │  1.8 V core domain    │
                                  │ - - - - -│- - - -│- - - - - - - - - - - -│◀ analog/digital
                                  │          │       │  3.3 V I/O domain     │  boundary
                                  │          │       │  (interface reqs,     │
                                  │          ▼       ▼   spec §6)            │
                                  │  ┌──────────────┐  ┌──────────────────┐  │
                                  │  │ FS line      │  │ Differential rx  │  │
                                  │  │ driver + OE  │  │ + single-ended   │  │
                                  │  │ (ported,     │  │ rx D+/D−         │  │
                                  │  │  #112)       │  │ (ported, #110/   │  │
                                  │  │              │  │  #111)           │  │
                                  │  └──────┬───────┘  └────────┬─────────┘  │
                                  │         │                   │            │
                                  │         ▼                   │            │
                                  │  ┌──────────────────────┐   │            │
                                  │  │ D+ pull-up (trimmed, │◀──┘            │
                                  │  │ enable from UTMI     │                │
                                  │  │ layer; ported, #113) │                │
                                  │  └──────────┬───────────┘                │
                                  └─────────────┼────────────────────────────┘
                                                ▼
                                           D+ / D− (USB cable)

   ┌───────────────────────────┐
   │ PLL: 144 MHz oversampling │── oversampling clock (N×) into the bit/edge
   │ clock from 12 MHz ref     │   synchronization logic above
   │ (2AMLogic/sky130-pll,     │
   │  pinned reference; never  │   No squelch/envelope detector block:
   │  designed here)           │   disposition proposed in DR-0003.
   └───────────────────────────┘
```

The outer box is this repo. The dashed line inside it is the analog/digital
boundary: above it, the UTMI-side digital logic on the 1.8 V core; below
it, the analog front end on the 3.3 V I/O rail, ported block by block from
`gf180-usb2-phy` (issues #110 to #113, after the harness in #109). The two
halves meet only through the interface requirements recorded in
`spec/usb2-phy.md` §6; translating between the 3.3 V and 1.8 V domains
(level shifting) is an integration item that no port issue owns yet. The
PLL sits outside the box: it is consumed from `sky130-pll` by a pinned
reference recorded in `reuse.lock.json`.

## Partition table

| Piece | Built here? | Source | Status of that source |
|---|---|---|---|
| UTMI digital layer | yes | designed here | RTL implemented and cocotb-verified |
| Serializer / deserializer (bit stuffing/destuffing, NRZI encode/decode, parallel↔serial) | yes | designed here | RTL implemented and cocotb-verified |
| Oversampling clock source | no | pinned reference: `2AMLogic/sky130-pll` (the PLL row below) | see PLL row |
| Bit / edge synchronization logic (digital half of clock/data recovery) | yes | designed here | RTL implemented and cocotb-verified |
| PLL | no | pinned reference: `2AMLogic/sky130-pll` at a full commit in `reuse.lock.json`; never designed here | exists; output band and reference input still DRAFT there, jitter metric differs from DR-0001, LVS open (sky130-pll#18) — see `docs/porting-plan.md` |
| FS line driver ("current-mode drivers" in §6) | yes | ported from `gf180-usb2-phy` `design/differential_driver.sch` at `0aab249`; port issue #112 | source has schematic and 45-corner gf180 sweep; **4 driver rows fail in the source**; no OE in the source |
| Differential receiver | yes | ported from `gf180-usb2-phy` `design/differential_receiver.sch`; port issue #111 | source passes its sensitivity row 45/45 (gf180, not sky130) |
| Single-ended receivers (D+, D−) | yes | ported from `gf180-usb2-phy` `design/se_receiver_{dp,dm}.sch`; port issue #110 | source passes both threshold rows 45/45 (gf180, not sky130) |
| Squelch / envelope detector | no block planned | none: no source block exists; HS-only function | proposed for removal from FS scope in DR-0003, pending ratification; §6 rows unchanged |
| Pull-up and termination | yes (D+ pull-up) | ported from `gf180-usb2-phy` `design/dplus_pullup.sch`; port issue #113 | source passes 45/45 with trim; pull-up supply and trim-code source undecided; 15 kΩ pull-downs are host-side (DR-0003, proposed) |

No ported block has sky130 evidence yet. A gf180 result in the last column
is source evidence about the design being ported, not a claim about this
repo; every row is re-measured on sky130 by its port issue.

### Resolving the two open rows from the original issue

**Clock recovery** does not land cleanly on one side of the boundary. It
splits into two rows above:

- The **oversampling clock source** (an N× clock the recovery logic samples
  against) comes from the PLL, which is consumed from `sky130-pll` by
  pinned reference — "no" per the table, unchanged by the 2026-10-08 ruling.
- **Bit/edge synchronization logic** — detecting NRZI transitions in the
  oversampled stream, aligning to bit boundaries, and driving the
  UTMI-facing byte stream — is ordinary digital logic with no analog
  content. It is built here ("yes"), alongside the serializer/deserializer
  it feeds.

The interface requirement between these two rows (oversampling ratio,
edge-alignment tolerance) is the same number the PLL needs for its own
jitter budget — see `spec/usb2-phy.md` §6, issue #1's jitter-budget
acceptance criterion, and DR-0001 Decision 1 (the metric that binds).

**Pull-up and termination** is analog pad-level circuitry co-located with
the transceiver. Under the 2026-10-08 ruling it is ported here as its own
block (#113), separate from the receivers, matching the source's partition
(`dplus_pullup` is its own cell in `gf180-usb2-phy`). The FS device-side D+
pull-up is under UTMI-layer *control* even though it is analog silicon: the
digital side must be able to enable/disable it (used for speed signaling
during reset/attach and for suspend). That control signal is recorded as an
interface requirement in `spec/usb2-phy.md` §6. The 15 kΩ pull-downs in §6
are host-side; whether that row applies to this device is proposed in
DR-0003.

## Interface requirements (analog/digital boundary and PLL)

Each analog row above meets the digital side at the boundary drawn in the
block diagram, and the PLL row is a dependency on `sky130-pll`. These are
the interface requirements across those boundaries — numbers with units,
not qualitative descriptions, per issue #2's acceptance criteria. The
ported blocks owe them to this repo's digital side; the PLL owes its rows
to this repo from `sky130-pll`.

`spec/usb2-phy.md` §6 is the single authoritative source for these
requirements — the full table of target values (PLL reference and jitter,
driver output characteristics, receiver thresholds, squelch levels,
pull-up/pull-down values) lives there, not here, to avoid maintaining two
hand-synced copies. The block diagram above shows *where* each requirement
applies (the dashed analog/digital boundary labeled "interface reqs", and
the PLL's clock into the bit/edge synchronization logic);
`spec/usb2-phy.md` §6 is where the *values* are recorded.

## First buildable slice

The first buildable slice was, and remains, the **FS-only digital UTMI
core**: UTMI interface, serializer/deserializer (bit stuffing/destuffing,
NRZI encode/decode), and bit/edge synchronization logic. It was chosen when
no analog pieces were available; the 2026-10-08 ruling does not change it.
This slice has no analog content and does not block on the analog port or
on `sky130-pll`.

It is verified standalone with a bit-exact cocotb testbench that replaces
the analog front end with a behavioral/ideal transceiver model — a
digital stub that reproduces DP/DM-level NRZI signaling (including bit
stuffing edge cases and EOP/SE0 sequences) without any electrical
simulation. This lets the digital half reach "UTMI RTL verified" on the
repo's maturity ladder (see README) entirely independent of when the analog
blocks land, and it is the concrete interpretation of "Full-speed first" in
CLAUDE.md: FS digital verification does not wait on HS, and it does not wait
on analog.

The analog front end now proceeds in parallel as its own slices, one per
ported block, each verified standalone at schematic level over sky130 PVT
corners before any assembly: the analog sim harness (#109) first, then the
single-ended receivers (#110), differential receiver (#111), FS line driver
(#112) and D+ pull-up (#113), in any order once #109 lands. See
[`docs/porting-plan.md`](../docs/porting-plan.md) for the per-block source,
device choices still open, and inherited risks.

Once those blocks and the `sky130-pll` reference reach a usable state, the
digital slice becomes the digital half of the full assembly integration —
its interface requirements to those blocks are already fixed by
`spec/usb2-phy.md` §6, so integration is a matter of connecting recorded
interfaces (plus the level shifting, pull-up supply and trim-code items
listed in the porting plan) rather than renegotiating them.

## Related work

- Issue #1 (target spec ratification) landed after this issue, as planned —
  the two were drafted in parallel with neither blocking the other. The
  interface requirement values referenced above are recorded once in
  `spec/usb2-phy.md` §6; see that document for the ratified, authoritative
  table plus the decision log behind the FS/HS, UTMI, clock, supply, and
  verification-scope calls this partition table assumes.
- [Vlsir/Usb2Phy](https://github.com/Vlsir/Usb2Phy) built the analog half on
  sky130 and went dormant in February 2023; its partitioning is worth
  comparing against once it is legible from that repo's own state, as a
  sanity check on the analog rows above.
- [`2AMLogic/gf180-usb2-phy`](https://github.com/2AMLogic/gf180-usb2-phy/tree/0aab24943aa1379026ccebb8e5746580f1eb7947)
  at `0aab24943aa1379026ccebb8e5746580f1eb7947` is the source of every
  ported analog block (`ported_from` in the fleet manifest).
