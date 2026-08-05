# Architecture and partitioning

Status: drafted 2026-08-05, tracks issue #2. Interface requirement numbers
below are DRAFT — cross-check against `spec/usb2-phy.md` once #1 ratifies
the target spec; whichever of #1/#2 lands first is an input to the other,
not an independent source of truth (see both issues' curator notes).

## Why this document exists

A USB 2.0 PHY is an assembly, and most of the analog pieces it needs are
being designed as their own canary blocks in sibling repos that do not exist
in finished form yet. This document draws the line between what this repo
builds and what it depends on, so that line is visible at review time
instead of being an agent's private judgment call. See CLAUDE.md's "Scope
discipline" note — this is the document that makes it enforceable.

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
                                  │          │       │                       │
                                  └──────────┼───────┼───────────────────────┘
                                             │       │  DP/DM (digital I/O to pads)
                          interface reqs ────┤       ├──── interface reqs
                          (§ Interface        │       │    (§ Interface
                           requirements)      │       │     requirements)
                                             ▼       ▼
                     ┌──────────────┐  ┌──────────────────┐  ┌───────────────┐
                     │ PLL (osc.    │  │ Current-mode       │  │ Differential  │
                     │ clock source,│  │ drivers            │  │ receivers +   │
                     │ sibling      │  │ (sibling canary)   │  │ squelch/      │
                     │ canary)      │  │                    │  │ envelope      │
                     └──────────────┘  └────────┬───────────┘  │ detector      │
                                                 │              │ (sibling      │
                                                 │              │  canary)      │
                                                 ▼              └───────┬───────┘
                                       ┌──────────────────────┐        │
                                       │ Pull-up / pull-down   │◀───────┘
                                       │ and termination        │
                                       │ (pad ring, sibling     │
                                       │  canary — enable ctrl  │
                                       │  from UTMI layer)      │
                                       └──────────┬─────────────┘
                                                   ▼
                                              D+ / D− (USB cable)
```

The vertical line down the middle of the outer box is the scope boundary
from the repo README: everything left of it is UTMI-side digital logic
built in this repo; everything right of it is analog, sourced from sibling
canary repos, and reachable from this repo only through the interface
requirements recorded below.

## Partition table

| Piece | Built here? | Source if not | Status of that source |
|---|---|---|---|
| UTMI digital layer | yes | — | — |
| Serializer / deserializer (bit stuffing/destuffing, NRZI encode/decode, parallel↔serial) | yes | — | — |
| Oversampling clock source | no | sibling canary (PLL) | not yet designed |
| Bit / edge synchronization logic (digital half of clock/data recovery) | yes | — | — |
| PLL | no | sibling canary | not yet designed |
| Current-mode drivers | no | sibling canary | not yet designed |
| Differential receivers | no | sibling canary | not yet designed |
| Squelch / envelope detector | no | sibling canary | not yet designed |
| Pull-up/pull-down and termination | no | sibling canary (pad ring, co-located with transceiver) | not yet designed |

### Resolving the two open rows from the original issue

**Clock recovery** does not land cleanly on one side of the boundary. It
splits into two rows above:

- The **oversampling clock source** (an N× clock the recovery logic samples
  against) comes from the PLL, which is squarely a sibling canary block —
  "no" per the existing table, unchanged.
- **Bit/edge synchronization logic** — detecting NRZI transitions in the
  oversampled stream, aligning to bit boundaries, and driving the
  UTMI-facing byte stream — is ordinary digital logic with no analog
  content. It is built here ("yes"), alongside the serializer/deserializer
  it feeds.

The interface requirement between these two rows (oversampling ratio,
edge-alignment tolerance) is the same number the PLL sibling block needs for
its own jitter budget — see the interface requirements table below and
issue #1's jitter-budget acceptance criterion.

**Pull-up/pull-down and termination** is analog pad-level circuitry
co-located with the transceiver, so it is marked "no / sibling canary" here.
This still leaves the FS device-side D+ pull-up under UTMI-layer *control*
even though it is not UTMI-layer *silicon*: the digital side must be able to
enable/disable it (used for speed signaling during reset/attach and for
suspend). That control signal is recorded as an interface requirement below.
This assignment should be confirmed against whatever the differential
receiver sibling block's pad ring actually ends up owning — if pull-up/
termination is folded into that block's pad ring rather than kept separate,
this row should be merged into the receiver row instead of kept standalone.

## Interface requirements (owed to sibling canary blocks)

Every "no" row above is a dependency this repo cannot satisfy itself. These
are the interface requirements this repo hands to whichever sibling repo
builds each piece — numbers with units, not qualitative descriptions, per
issue #2's acceptance criteria. Values are drawn from the USB 2.0
specification (frozen since 2000), Chapter 7 (Electrical). **DRAFT**: cross-
check against `spec/usb2-phy.md` once #1 ratifies; treat any conflict there
as authoritative until this document is reconciled.

| Sibling block | Interface requirement | Target value | Notes |
|---|---|---|---|
| PLL | Reference input | 12 MHz ±0.25% (2500 ppm) crystal/resonator | USB 2.0 §7.1.11 FS clock tolerance, unsynchronized |
| PLL | Output jitter (cycle-to-cycle, feeding oversampling clock) | < 5% of one bit period (< ~4.2 ns at 12 Mbps, 12× oversampling) | Draft budget; tightens once the recovery logic's oversampling ratio is fixed |
| PLL | Oversampling ratio delivered to bit/edge sync logic | 12× minimum (typical FS implementation) | Interface number owed *to* this repo, not from it — recorded here so both sides agree |
| Current-mode drivers | Output voltage swing, static | VOH 2.8–3.6 V (1.5 kΩ pull-up to 3.6 V), VOL 0.0–0.3 V | USB 2.0 Table 7-2, FS driver |
| Current-mode drivers | Driver output resistance | 28–44 Ω | Sets differential line impedance with cable |
| Current-mode drivers | Rise/fall time | 4–20 ns (10%–90%), matched to within 10% rise vs. fall | USB 2.0 §7.1.2 FS driver characteristics |
| Current-mode drivers | Output signal crossover voltage | 1.3–2.0 V | USB 2.0 §7.1.2 |
| Current-mode drivers | Control interface from UTMI layer | Differential drive enable, output enable (OE), and TxD+/TxD− data lines | Digital-to-analog handoff at the scope boundary |
| Differential receivers | Differential input sensitivity | \|(D+) − (D−)\| > 200 mV | USB 2.0 §7.1.4 |
| Differential receivers | Common-mode input range | 0.8–2.5 V | USB 2.0 §7.1.4 |
| Differential receivers | Single-ended receiver thresholds | VIH > 2.0 V, VIL < 0.8 V | USB 2.0 §7.1.4, used for SE0/EOP detection |
| Squelch / envelope detector | Squelch detection threshold (differential envelope) | 100–200 mV | USB 2.0 Table 7-2 |
| Squelch / envelope detector | Output interface to UTMI layer | Single-bit `SQUELCH`/`LineState` status, sampled at the oversampling clock rate | Feeds RxActive generation in the UTMI layer |
| Pull-up/pull-down and termination | FS device D+ pull-up | 1.5 kΩ ±5% to internally regulated 3.0–3.6 V | USB 2.0 §7.1.5, speed signaling |
| Pull-up/pull-down and termination | Downstream port pull-downs | 15 kΩ ±5% on each of D+/D− | USB 2.0 §7.1.5 |
| Pull-up/pull-down and termination | Control interface from UTMI layer | Single-bit pull-up enable/disable, driven during reset/attach/suspend sequencing | Digital-side ownership of an analog-side element |

## First buildable slice

The analog pieces are unavailable, so the first buildable slice is the
**FS-only digital UTMI core**: UTMI interface, serializer/deserializer (bit
stuffing/destuffing, NRZI encode/decode), and bit/edge synchronization
logic. This slice has no analog content and does not block on any sibling
canary repo.

It is verified standalone with a bit-exact cocotb testbench that replaces
the analog front end with a behavioral/ideal transceiver model — a
digital stub that reproduces DP/DM-level NRZI signaling (including bit
stuffing edge cases and EOP/SE0 sequences) without any electrical
simulation. This lets the digital half reach "UTMI RTL verified" on the
repo's maturity ladder (see README) entirely independent of when the analog
blocks land, and it is the concrete interpretation of "Full-speed first" in
CLAUDE.md: FS digital verification does not wait on HS, and it does not wait
on analog.

Once the sibling canary blocks (PLL, drivers, receivers, squelch detector)
reach a usable state, this slice becomes the digital half of the full
assembly integration — its interface requirements to those blocks are
already fixed by the table above, so integration is a matter of connecting
recorded interfaces rather than renegotiating them.

## Related work

- Issue #1 (target spec ratification) and this issue can be drafted in
  parallel; neither blocks the other. Cross-check the interface requirement
  numbers above against `spec/usb2-phy.md` once it lands — see that issue's
  curator notes for the same cross-reference in the other direction.
- [Vlsir/Usb2Phy](https://github.com/Vlsir/Usb2Phy) built the analog half on
  sky130 and went dormant in February 2023; its partitioning is worth
  comparing against once it is legible from that repo's own state, as a
  sanity check on the "no" rows above.
