# spec

Ratified specification and decision records.

```
spec/
  README.md               this file
  usb2-phy.md              ratified target specification
  architecture.md          block diagram and partition table
  decision-records/
    TEMPLATE.md             copy this to start a new record
    NNNN-<slug>.md           one record per topic, numbered sequentially
```

- [`usb2-phy.md`](usb2-phy.md) — **ratified target specification** (2026-08-05,
  issue #1). Signaling/speed target, UTMI interface, reference clock and PLL
  jitter budget, supply architecture, analog sub-block interface
  requirements, verification scope, and the decision log for each of those.
  This is the authoritative document — start here.
- [`architecture.md`](architecture.md) — block diagram and
  build-here/sibling-canary partition table (issue #2). Its analog interface
  numbers are cross-checked against `usb2-phy.md` §6 and agree with it.
- [`decision-records/`](decision-records/) — where **post-ratification**
  decisions land. Per CLAUDE.md, "Spec changes go through `spec/` with a
  decision record; agents do not relax the ratified spec to make results
  pass" — `usb2-phy.md` and `architecture.md` are not edited to fill a gap
  or make a result pass; instead a decision record here extends or, where it
  must, supersedes named sections of those documents, citing them by number.
  See [`decision-records/TEMPLATE.md`](decision-records/TEMPLATE.md) for the
  format and the numbering rule.

## Decision records

| Record | Title | Status |
|---|---|---|
| [0001](decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md) | Clocking, CDC discipline, jitter metric, and PVT envelope | Proposed |

A record is never deleted or rewritten once ratified — a later change
supersedes it with a new record rather than editing history in place.
