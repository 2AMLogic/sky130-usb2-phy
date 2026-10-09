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
- [`architecture.md`](architecture.md) — block diagram and partition table
  (issue #2; partition revised by issue #106 / DR-0003: analog blocks are
  ported in-tree from `gf180-usb2-phy`, the PLL is a pinned reference to
  `sky130-pll`). Its analog interface numbers are cross-checked against
  `usb2-phy.md` §6 and agree with it. The per-block port plan is
  [`docs/porting-plan.md`](../docs/porting-plan.md).
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
| [0002](decision-records/0002-shared-protocol-rtl-master-and-interfaces.md) | Shared USB protocol RTL — master, classification, and canonical interfaces | Proposed |
| [0003](decision-records/0003-analog-port-scope-and-squelch-disposition.md) | Analog partition ported in-tree; squelch and 15 kΩ row disposition | Decision 1 ratified (operator ruling 2026-10-08); Decisions 2–3 proposed |

A record is never deleted or rewritten once ratified — a later change
supersedes it with a new record rather than editing history in place.
