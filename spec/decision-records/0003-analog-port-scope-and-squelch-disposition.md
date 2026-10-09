# 0003: Analog partition ported in-tree; squelch and 15 kohm row disposition

- **Status**: Decision 1 **ratified** (operator ruling, 2026-10-08, on #40).
  Decisions 2 and 3 **proposed**, pending ratification. They change no
  ratified target in this record or in the PR that adds it.
- **Date**: 2026-10-09
- **Decided by**: Decision 1: operator (rjwalters), recorded by the Builder
  agent for issue #106. Decisions 2 and 3: proposed by the Builder agent,
  issue #106.
- **Related**: #40 (analog partition, where the ruling was made), #106 (this
  record and the porting plan), #23 (T1 tracker),
  [`docs/porting-plan.md`](../../docs/porting-plan.md),
  `0001-clocking-cdc-jitter-metric-and-pvt-envelope.md` (PVT envelope and
  PLL jitter metric this record leaves unchanged).

## Context

`spec/usb2-phy.md` (ratified 2026-08-05) and `spec/architecture.md` assign
every analog block to "sibling canary" repositories, and `CLAUDE.md` told
agents not to design a driver or receiver here. For two months no such
sky130 repository appeared (#40's dependency re-checks, 2026-09-26 to
2026-10-08). On 2026-10-08 the operator ruled on #40
([comment](https://github.com/2AMLogic/sky130-usb2-phy/issues/40#issuecomment-6066642841)):
the analog blocks are **ported from `gf180-usb2-phy` into this
repository**, no new sibling repositories are created, and the PLL remains
a pinned reference to `sky130-pll`.

Porting the analog partition exposed two §6 rows that no source block
covers and that need a decision rather than a silent drop:

- **Squelch / envelope detector** (two rows: detection threshold 100-200 mV;
  output interface to the UTMI layer). `gf180-usb2-phy` has no such block:
  its spec
  ([`spec/usb2-device-phy.md` §4 at `0aab249`](https://github.com/2AMLogic/gf180-usb2-phy/blob/0aab24943aa1379026ccebb8e5746580f1eb7947/spec/usb2-device-phy.md))
  excludes it as a high-speed feature.
- **Downstream port pull-downs, 15 kohm +/-5 % on each of D+/D-.** These are
  host-side resistors; this block is a single-role FS device (§3).

## Decision 1 (ratified): analog partition is ported in-tree; PLL by pinned reference

Ownership changes; no numeric target changes.

| Block | Before | After |
|---|---|---|
| FS line driver ("current-mode drivers" in §6) | sibling canary, not yet designed | ported from `gf180-usb2-phy` into this repo (#112) |
| Differential receiver | sibling canary | ported in-tree (#111) |
| Single-ended receivers (D+, D-) | part of "differential receivers", sibling canary | ported in-tree (#110) |
| D+ pull-up and termination | sibling canary (pad ring) | ported in-tree (#113) |
| PLL / oversampling clock source | sibling canary, not yet designed | pinned reference to `2AMLogic/sky130-pll`; never designed here |
| Squelch / envelope detector | sibling canary | no source block; see Decision 2 |

This **supersedes** the ownership statements (not the values) in:

- `CLAUDE.md` "Scope discipline" bullet (edited in the same PR).
- `spec/architecture.md`: "Why this document exists", the block diagram's
  analog labels, the scope-boundary paragraph, the partition table, the
  "Interface requirements" heading and prose, and "First buildable slice"
  (edited in the same PR; the standalone digital slice is kept).
- `spec/usb2-phy.md` §1 scope paragraph and §6 introduction and first-column
  heading (edited in the same PR; every Target-value cell is byte-identical).
- `spec/usb2-phy.md` §5 last paragraph ("an implementation decision for
  whichever sibling canary block owns the pad ring"), §7 ("when the analog
  sibling blocks land") and §8.3 ("levied on the sibling PLL canary repo"):
  **not edited**. Read them as: the 3.3 V device flavour is owed by the port
  issues in this repo (#110 to #113); §7's trigger is the port issues'
  evidence landing; §8.3's PLL sibling is `sky130-pll`.

Reuse is recorded per the workspace convention
([2am `REUSE.md`](https://github.com/2AMLogic/2am/blob/main/REUSE.md)): the
fleet manifest already carries `ported_from: [gf180-usb2-phy]` and
`consumes: [sky130-pll]`; `reuse.lock.json` pins the upstream files read
(`mode: fetched`) at full commits.

## Decision 2 (proposed): squelch rows are high-speed scope, not FS requirements

**Proposal.** Move both §6 squelch / envelope detector rows out of the FS
commitment and into the high-speed stretch scope governed by §8.1's trigger,
and re-home the `LineState` half of the output-interface row to the
single-ended receivers' output interface. Until this proposal is ratified,
both rows stay in §6 exactly as ratified, and
`docs/characterization.md` keeps reporting them.

**Rationale (FS versus HS).**

- In USB 2.0 Chapter 7 the squelch threshold is a high-speed receiver
  parameter (V_HSSQ). An HS receiver needs it because HS idle is SE0 with
  both lines terminated near 0 V, so "is a packet present" can only be
  answered by a differential-envelope detector.
- At full speed, every line condition the PHY must recognise is a static
  logic level read by the receivers this repo is porting: idle is the J
  state held by the device's 1.5 kohm D+ pull-up; start of packet is the
  J-to-K transition; EOP and bus reset are SE0, detected by the two
  single-ended receivers; resume is a K state; suspend is idle J held for
  3 ms, a timer on `LineState`. None of these needs an envelope detector.
- This repo's digital side already generates `RxActive` from SYNC
  detection (`rtl/usb_rx_framer.v`), not from a squelch input, and
  `LineState` from the digitised D+/D- levels (`rtl/usb_linestate.v`);
  `rtl/usb_bit_sync.v` documents that it deliberately consumes no squelch
  input. The squelch row's stated purpose, "Feeds RxActive generation in the UTMI
  layer", is an HS-PHY arrangement.
- The source being ported reached the same conclusion independently and
  excludes squelch.
- `CLAUDE.md` "Full-speed first": an HS requirement must not drive FS
  architecture before FS works. Building an envelope detector now would be
  exactly that.

**Not verified by this record.** The ratified row cites "Table 7-2" for the
100-200 mV value. This record does not re-check that citation or that value
against the USB 2.0 text; a ratifier should, since it bears on whether the
row was ever an FS number.

## Decision 3 (proposed): the 15 kohm pull-down row is a verification load, not a device element

**Proposal.** Read §6 "Downstream port pull-downs, 15 kohm +/-5 % on each of
D+/D-" as the host-side load against which this device's pull-up, driver
and receivers are verified, not as resistors this block instantiates. A
single-role FS device does not have downstream-port pull-downs; the host
does. The source being ported treats them the same way (its pull-up
testbench loads D+ with 15 kohm to ground). #113 models them as a
testbench load and builds no on-die pull-downs. The ratified row is
unchanged until this is ratified.

## Alternatives considered

- **Justify the squelch rows for FS and build an envelope detector.** Not
  chosen: no FS line condition needs one (Decision 2), no source block
  exists, and it would be an HS-driven addition to the FS architecture.
- **Drop the squelch rows in this PR.** Not chosen: `CLAUDE.md` forbids
  relaxing the ratified spec without a decision record and ratification.
  The rows stay; only a proposal is made.
- **Keep the analog partition in sibling repositories.** Overruled by the
  operator on 2026-10-08: no sky130 repository builds a USB driver or
  receivers, and creating repositories is an operator decision.
- **Build on-die 15 kohm pull-downs to satisfy the row literally.** Not
  chosen: they would load D+ of a device that is never a downstream port,
  and the source design does not have them.

## Consequences

- The port issues (#109 harness, #110 single-ended receivers, #111
  differential receiver, #112 driver, #113 pull-up and termination) can be
  curated and built here. The four gf180 driver failures (rise/fall time,
  crossover voltage, rise/fall matching, aggregate FS signal quality) are
  inherited as open risks; the gf180 differential-receiver failure is not,
  because the source fixed it at the pinned commit.
- This repo now owns analog device choices on sky130 that §5 had assigned to
  a pad-ring sibling: the 3.3 V MOS flavour and every resistor flavour.
  The porting plan records the candidates without deciding them.
- Integration work appears that no sibling would have absorbed: 3.3 V to
  1.8 V level shifting at the analog/digital boundary, a pull-up supply
  source, and a trim-code source. Each is listed in the porting plan as an
  integration blocker, not a planning blocker.
- If Decision 2 is ratified: a follow-up edits §6 to move the squelch rows
  to HS stretch scope, edits `spec/architecture.md`'s partition row, and
  re-grades `docs/characterization.md` (which is content-hashed by
  `signoff/check.py`, so it is not edited in this PR). If it is rejected, a
  squelch block must be specified and a port issue filed, because no source
  block exists.
- If Decision 3 is ratified: §6's 15 kohm row is reworded as a load
  condition and `docs/characterization.md` row §6-15 is re-classified.
- No value in this record is a verified result. The rationale in Decision 2
  is a reading of the USB 2.0 FS signalling rules and of this repo's RTL, not
  a testbench result; per `CLAUDE.md`, no claim without a testbench.
