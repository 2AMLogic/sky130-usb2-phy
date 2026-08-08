# 0000: <short title>

<!--
Copy this file to spec/decision-records/NNNN-<slug>.md and fill it in.
Use the next unused NNNN (zero-padded 4 digits). One decision per record
(a record may cover a tightly-related cluster of decisions if they were
forced by the same gap — e.g. clocking + CDC + PVT together — but keep it
to one coherent topic). A decision record is required for every spec
change (see CLAUDE.md: "Spec changes go through spec/ with a decision
record; agents do not relax the ratified spec to make results pass."). Do
not edit `spec/usb2-phy.md` or `spec/architecture.md` directly to make a
result pass or to fill a gap — extend or supersede named rows from here,
citing them by section number.

Numbering rule: before picking NNNN, check every filename already in this
directory on `main` (including superseded records) and use one greater
than the highest number found — never guess or reuse a number, and
re-check if another record may have landed concurrently, to avoid a
collision.
-->

- **Status**: proposed | ratified | superseded by NNNN
- **Date**: YYYY-MM-DD
- **Decided by**: <name / role>

## Context

What forced this decision? One short paragraph: the constraint, the
measurement, or the conflict that made the current spec inadequate. Link to
the issue, the simulation/synthesis evidence, or the prior record it
revises.

## Decision

The decision, stated as a change to the spec — the parameter and its new
value, or the approach now ratified. State explicitly which
`spec/usb2-phy.md` / `spec/architecture.md` section(s) this **extends** or
**supersedes**, by number. Be specific enough that design work can lock to
it without further interpretation.

## Alternatives considered

- **<alternative>** — why it was not chosen.
- **<alternative>** — why it was not chosen.

## Consequences

What follows from this: what becomes possible, what becomes harder, which
testbenches or corner sets change, what work is invalidated or must be
re-run. Include the bad consequences, not just the good ones.

Every numeric value introduced by a decision record is a **design target**
until a testbench (cocotb, STA, or PVT sim) verifies it — per CLAUDE.md,
"Verification is the product: no claim without a testbench." Say so
explicitly rather than letting a design target read as a verified result.
