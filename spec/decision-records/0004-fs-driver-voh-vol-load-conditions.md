# 0004: FS driver VOH/VOL load conditions (proposed reading of the section 6 static-swing row)

- **Status**: proposed. It changes no ratified target in this record or in the
  PR that adds it; `spec/usb2-phy.md` is not edited.
- **Date**: 2026-10-09
- **Decided by**: proposed by the Builder agent, issue #112. Needs operator
  ratification.
- **Related**: #112 (FS line driver port), `spec/usb2-phy.md` section 6 row
  "Output voltage swing, static", DR-0003 (which records the same kind of
  unverified-citation caveat for the 15 kohm row),
  `sim/driver-static/records/`.

## Context

The ratified section 6 row reads: "Output voltage swing, static | VOH
2.8-3.6 V (1.5 kohm pull-up to 3.6 V), VOL 0.0-0.3 V | Table 7-2, FS driver".
The parenthetical sits in the Target-value cell as a whole, so on its face it
attaches one load, 1.5 kohm to 3.6 V, to both VOH and VOL.

The USB 2.0 Chapter 7 DC characteristics bind two different loads: VOL (low,
driven) is specified into a 1.5 kohm pull-up to 3.6 V, and VOH (high, driven)
is specified into a 15 kohm load to ground. A driver driving high into a
1.5 kohm pull-up to 3.6 V is pulled toward 3.6 V, not loaded by it, so that
reading is a different (and much easier) VOH test than the one in the source.

**Not verified by this record.** The load values above are the author's
reading of the Chapter 7 text; the specification PDF was not available in the
build environment, and the section and table numbers (the ratified row cites
"Table 7-2"; the testbench comments cite section 7.1.1.1) were not re-checked.
The ratifier must confirm both against the specification text before
accepting this record.

## Decision (proposed)

Read the "Output voltage swing, static" row as two loads, one per bound:

- VOL 0.0-0.3 V measured with the driver low into 1.5 kohm to 3.6 V;
- VOH 2.8-3.6 V measured with the driver high into 15 kohm to ground.

The numeric bounds are unchanged. Until ratified, the `driver-static`
experiment reports **both** VOH loads (15 kohm to ground, and the literal
1.5 kohm to 3.6 V) against the same 2.8-3.6 V bound, each as its own
measurement, and a record states which one it treats as the row's verdict.

## Alternatives considered

- **Keep the literal single load (1.5 kohm to 3.6 V) for both bounds** -
  passes trivially for VOH on any driver that can pull up at all, and does not
  test what the source specifies. Kept as a secondary measurement only.
- **Silently re-read the row in the testbench** - rejected by the issue
  acceptance criteria and by CLAUDE.md; this record exists so the re-reading
  is a ratified decision, not an agent choice.

## Consequences

- If ratified, section 6's parenthetical is edited by a later spec PR to name
  both loads; no target value changes and no existing record is invalidated,
  because both VOH loads are already measured.
- If rejected, the literal-reading VOH measurement (`voh15_*`) is the row's
  verdict and the 15 kohm measurement becomes engineering data.
