# 0006: Disabled-pad voltage envelope and leakage budget for the FS line driver (proposed)

- **Status**: proposed. It changes no ratified target in this record or in the
  PR that adds it; `spec/usb2-phy.md` is not edited. Nothing here is a
  compliance claim.
- **Date**: 2026-10-15
- **Decided by**: proposed by the Builder agent, issue #130, following the
  operator ruling of 2026-10-15 (option a: study the integration envelope and
  current budget first). Needs operator ratification.
- **Related**: #130, #112 (FS driver port), #113 (D+ pull-up), #23 (evidence
  epic), `docs/disabled-pad-envelope-study.md` (the case table behind this
  record), `0001-clocking-cdc-jitter-metric-and-pvt-envelope.md` Decision 5,
  `0003-analog-port-scope-and-squelch-disposition.md`,
  `0004-fs-driver-voh-vol-load-conditions.md`.

## Context

`spec/usb2-phy.md` section 6 has no disabled-pad leakage limit for the FS line
driver. The committed `driver-static` record `20261009-185058-e232b2f` reports
`leak_dp_3p6v_na` / `leak_dm_3p6v_na` down to -258776 nA at `fs_100c_3.00v`
(driver disabled, pad forced to 3.6 V on a 3.0 V rail, 8 of 45 points below
-10 uA, all at the 3.0 V rail). That is engineering data about the schematic,
not a pass or a fail. The study shows an over-rail disabled pad is reachable
from ranges the ratified spec itself states (VOH up to 3.6 V, pull-up supply
3.0-3.6 V, I/O rail 3.0-3.6 V), and that the sequencing and connectivity that
would exclude it are not written down anywhere in the repo.

## Decision (proposed)

1. **Envelope.** Treat a disabled pad above `VDD`, and with `VDD` off, as
   **undetermined**, not as excluded. No sizing or circuit change is approved
   by this record.
2. **Integration facts to be supplied before a limit is ratified** (each is
   listed unknown in the study, section 2): whether `VDD` and the host signal
   rail are one rail; the source of `VPU` and whether it can exceed `VDD`; the
   `PU_EN` / `TermSelect` connection; whether `VDD` stays up in suspend;
   power-up order of `VDD`, `VPU` and the bus; pad-level overshoot.
3. **In-rail budget (design target).** Disabled-pad current `|I|` <= 10 uA for
   0 V <= pad <= 3.3 V, over the existing 45-point PVT grid, both pads, both
   disable states (`OE` = 0, `DRVEN` = 0), signed and absolute. The 10 uA
   anchor is the author's unverified reading of USB 2.0 Chapter 7 hi-Z
   data-line leakage; the ratifier must confirm value and table number against
   the specification text.
4. **Over-rail budget.** No number is proposed. It depends on the chosen
   envelope (how far over `VDD`, how long, whether `VDD` off is included).
5. **Extends** `spec/usb2-phy.md` section 6 "Current-mode drivers" rows only if
   ratified, as a new row; no existing row is changed or relaxed.

The operator chooses among: require pad tolerance up to 3.6 V at a 3.0 V rail
(a driver change such as a floating-well PMOS, separately scoped); restrict
operation to pad <= `VDD` by an integration contract (needs the facts in item
2); or ratify a bounded over-rail current as a numerical budget.

## Alternatives considered

- **Require 3.6 V pad tolerance at a 3.0 V rail now** - not chosen: needs a
  ratified over-rail budget and a process-feasibility study first; costs more
  circuit work, and a floating-well solution is unverified.
- **Restrict to pad <= `VDD` now** - not chosen: not established by any
  existing document, and omitting the failing sweep would not demonstrate
  compliance.
- **Ratify a number now** - not chosen: the data cover only a pad of 0 / 1.5 /
  3.0 / 3.6 V at rails >= 3.0 V; the 3.0-3.3 V pad point on a 3.0 V rail, rails
  below 3.0 V, `VDD` off and transients are unmeasured.

## Consequences

- The -259 uA figure stays engineering data; no signoff or compliance claim is
  made against an unratified limit.
- A future driver-static revision needs pad points between 3.0 and 3.6 V,
  rails below 3.0 V and off, and signed plus worst-absolute current checks. A
  positive-MAX-only check misses the failing sign.
- Every value above is a **design target** until a testbench verifies it, and
  the 10 uA anchor is unverified against the source specification.
- If an over-rail requirement is ratified, `design/differential_driver.*` may
  need a separately approved change, and the existing driver-static record
  would be superseded by a new append-only record, not edited.
