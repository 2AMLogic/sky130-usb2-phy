# 0008: Re-derive the `driver-matching-mismatch` xover negative-control load (180 ohm does not trip at two of four corners)

- **Status**: proposed. It changes no ratified target in this record or in the
  PR that adds it; `spec/usb2-phy.md` is not edited and the section 6
  "Output signal crossover voltage" row (1.3-2.0 V) is unchanged. A deeper
  negative control makes the verification stricter, not looser: re-sizing the
  control does not relax the spec.
- **Date**: 2026-11-16
- **Decided by**: proposed by the Builder agent, issue #307. Needs operator
  ratification.
- **Related**: #307 (this gap), #223 (item 6 owner, rows `6-06` / `6-14`),
  #269 (tt record), #271 / PR #314 (fs100v36 record, merged),
  #272 (sf40v36 record), #273 / PR #309 (fs100v30 record, **open, not
  landed**), `sim/driver-matching-mismatch/testbench/mc.json`,
  `sim/driver-matching-mismatch/testbench/driver_mc_tb.spice`, and the
  precedent records 0004, 0005, 0006 (proposed-by-Builder, operator-ratified).

## Context

The `xover` receiver of the `driver-matching-mismatch` Monte Carlo campaign is
graded against the ratified 1.3-2.0 V crossover window
(`spec/usb2-phy.md` section 6, unchanged here). Its negative control is a
single, corner-independent 180 ohm load from each line to ground, applied by
text substitution in `mc.json` (`receivers[xover].control.replace[0]`, one
global `find`/`with` pair — the `control` block has no corner dimension).
Its design intent, frozen in `mc.json` and restated in every record, is that
"the high level collapses and both crossings fall to about 1.26 V, below
1.3 V". A negative control that fails to degrade the measurement makes a
nominal PASS meaningless on that row: the measurement has no demonstrated
sensitivity.

**Measured control behaviour at 180 ohm** — the Monte Carlo control campaigns
(n = 50, mismatch) of the four declared corners. The first three rows are
re-derived from the committed, digest-pinned stored artifacts of the landed
records (fetched with `klt artifact get`, sha256 in the source record's
Stored-evidence table); the fourth is on an open PR and is cited as such.

| corner | nominal crossing mean, rise / fall (V) | controlled `vcross_rise_v` min-max (mean) | controlled `vcross_fall_v` min-max (mean) | control samples in window | verdict | source |
|---|---|---|---|---|---|---|
| `tt` (tt_mm / 27 C / 3.3 V) | 1.7266 / 1.7265 | 1.2394-1.2836 (1.2622) | 1.2398-1.2808 (1.2629) | 0 / 50 | `detected` — trips | record `20261115-040553-f76df63`, report sha256 `a0b54d11…` |
| `sf40v36` (sf_mm / -40 C / 3.6 V) | 1.7612 / 1.7612 | 1.3045-1.3598 (1.3317) | 1.3035-1.3559 (1.3325) | 50 / 50 | `not_detected` — does not trip | record `20261115-064022-f76df63`, report sha256 `33380725…` |
| `fs100v36` (fs_mm / 100 C / 3.6 V) | 1.9942 / 1.9942 | 1.4333-1.4727 (1.4551) | 1.4338-1.4707 (1.4559) | 50 / 50 | `not_detected` — does not trip | record `20261115-172039-45b6298`, report sha256 `1ec51efc…` |
| `fs100v30` (fs_mm / 100 C / 3.0 V) | not cited here | not measured in this record | not measured in this record | — | `detected` per PR #309 (**open, not-yet-landed**; re-read from `origin/main` before citing as settled) | PR #309, record `20261115-141134-38bdad2` |

The control's pull-down is corner-dependent. Against the nominal means, one
180 ohm load pulls the crossover down by about 465 mV at `tt`, 431 mV at
`sf40v36` and 540 mV at `fs100v36`; the distance from the nominal mean to the
1.3 V floor is 427 mV, 461 mV and 694 mV respectively. So the control trips at
`tt` with about 38 mV of deterministic margin, misses `sf40v36` by about
30 mV, and misses `fs100v36` by about 154 mV: the value was effectively sized
against the `tt` nominal crossover and carries no corner margin. The suspected
cause in issue #307 — sized at `tt`, no corner margin — is **confirmed by
measurement**, not refuted: no alternative mechanism (measurement-window
effect, `.meas` trigger, resistor temperature behaviour) is needed to explain
the misses, and the deterministic sweep below reproduces each corner's
controlled crossing within about 10 mV of the Monte Carlo control mean.

**Deterministic `rload_ohm` sweep** — controlled `vcross_rise_v` /
`vcross_fall_v` (V) per load, deterministic (typical sections, no mismatch),
single transient per point, deck = `driver_mc_tb.spice` verbatim with only the
`.param rload_ohm=1e12` card replaced (the knob the deck already exposes,
line 19) and the design netlist appended as `sim/harness/mismatch.py`
`build_body` does; requests carried no `monte_carlo` block, models
`sky130A` / `sky130.lib.spice` under the current pin of `sim/pdk-pins.json`
(open_pdks `f6eeac7d…`), analysis `tran 20p 300n`, batch fleet. This is
design exploration feeding this record: **no** campaign record is minted for
it, and no file under `sim/` is changed.

| load (ohm) | `tt` rise / fall | `sf40v36` rise / fall | `fs100v36` rise / fall | `fs100v30` rise / fall |
|---|---|---|---|---|
| 180 | 1.2612 / 1.2611 | 1.3303 / 1.3302 | 1.4544 / 1.4543 | 1.1668 / 1.1667 |
| 150 | 1.1939 / 1.1938 | 1.2662 / 1.2661 | 1.3785 / 1.3784 | 1.0974 / 1.0973 |
| 120 | 1.1040 / 1.1039 | 1.1797 / 1.1796 | 1.2780 / 1.2780 | 1.0061 / 1.0060 |
| 100 | 1.0254 / 1.0253 | 1.1032 / 1.1032 | 1.1909 / 1.1909 | 0.9276 / 0.9276 |
| 91 | 0.9834 / 0.9833 | 1.0619 / 1.0619 | 1.1445 / 1.1445 | 0.8863 / 0.8863 |
| 82 | 0.9362 / 0.9362 | 1.0151 / 1.0151 | 1.0925 / 1.0924 | 0.8404 / 0.8404 |
| 75 | 0.8952 / 0.8952 | 0.9658 / 0.9658 | 1.0474 / 1.0474 | 0.8011 / 0.8011 |
| 68 | 0.8478 / 0.8478 | 0.9152 / 0.9152 | 0.9978 / 0.9977 | 0.7583 / 0.7583 |
| 62 | 0.8044 / 0.8044 | 0.8697 / 0.8697 | 0.9509 / 0.9509 | 0.7186 / 0.7186 |
| 56 | 0.7583 / 0.7583 | 0.8213 / 0.8213 | 0.8994 / 0.8994 | 0.6756 / 0.6756 |

All four corners are **measured** in this table (each cell is a deterministic
run made for this record); `fs100v30` is included for completeness and is
independent of PR #309, whose unlanded row covers the 180 ohm *Monte Carlo*
control campaign, not this sweep. The largest measured resistance that puts
both crossings below 1.3 V at every measured corner is **120 ohm** (deterministic
margin 22 mV at `fs100v36`, the binding corner), but 22 mV is inside the
observed mismatch spread of the control campaigns at 180 ohm (min-max span
39-55 mV, i.e. about 20-28 mV one-sided), so a 120 ohm control would likely
leave individual Monte Carlo control samples inside the window and could read
`not_detected` again. Issue #307's original prediction obligation for
`fs100v36` ("state a falsifiable prediction so #271's record tests it") was
discharged by PR #314 landing first: the measured row above replaces the
prediction.

## Decision (proposed)

1. **Replace the `xover` control load with a 100 ohm resistor** from each line
   to ground (`mc.json` `receivers[xover].control.replace[0].with` becomes
   `".param rload_ohm=100\n"`). 100 ohm is an E12 preferred value and the
   largest one that clears the sizing criterion at every measured corner:
   deterministic margin below the 1.3 V floor of **109 mV** at `fs100v36`
   (binding), 197 mV at `sf40v36`, 275 mV at `tt` and 372 mV at `fs100v30` —
   each exceeding the observed one-sided mismatch spread (~20-28 mV at 180
   ohm), so every Monte Carlo control sample is expected to trip. The
   `match` receiver's 330 ohm control and both nominal campaigns
   (`rload_ohm=1e12`) are untouched, and the ratified 1.3-2.0 V window is
   unchanged.
2. **Re-run disposition for the already-recorded corners — the operator
   picks; this record does not assume one.** Existing records are append-only
   and stay valid evidence of what they ran against regardless of the choice.
   - **Option A (ranked first): re-run only `sf40v36` and `fs100v36`** under
     the ratified control. Repairs exactly the two corners whose control is
     broken; `tt`'s landed record keeps a working (`detected`) 180 ohm control
     and is not re-minted; `fs100v30` is still unrecorded and would be
     recorded under the ratified control when its turn comes (#273 / PR #309
     coordinates). Trade-off: the campaign's records then span two control
     values (180 ohm at `tt`, 100 ohm elsewhere) — each record states its own
     control, so nothing is misread, but the corners are not graded against an
     identical control.
   - **Option B (ranked second): re-run all four corners** under the ratified
     control for a uniform control across the campaign. Trade-off: mints a
     second `tt` record whose only change is the control value, and if PR #309
     has not merged by then it makes that PR's `fs100v30` record obsolete on
     arrival — the fleet cost of four corners versus two buys symmetry, not
     new information.
   - **Option C (ranked third): apply the new control to unrecorded corners
     only** (i.e. `fs100v30` whenever it is recorded; any future corners).
     Cheapest, but leaves the landed evidence with a broken control at exactly
     the two corners where the nominal crossover is weakest (`sf40v36`,
     `fs100v36`) — the crossover row keeps no working sensitivity control
     there until a later re-run.

Every numeric value above is a **design/exploration figure**, not a verified
signoff result: the deterministic sweep is mismatch-free single-point
evidence, and confirming the 100 ohm control reads `detected` at all four
corners requires the Monte Carlo control re-runs themselves (post-ratification
work, per the operator's pick among the options above).

## Alternatives considered

- **Keep 180 ohm** — rejected: `not_detected` at two of the four measured
  corners (three if PR #309's unlanded `fs100v30` row is excluded); a
  crossover PASS at those corners would rest on a measurement with no
  demonstrated sensitivity.
- **Propose 120 ohm** (the largest measured value that trips everywhere) —
  rejected: its 22 mV deterministic margin at `fs100v36` is smaller than the
  observed one-sided mismatch spread, so the control could still read
  `not_detected` per sample after the Monte Carlo re-run; 100 ohm is the
  largest preferred value with margin.
- **A per-corner control load** (extend `mc.json`'s `control` schema to vary
  by corner) — rejected as speculative generality: a single value suffices at
  all four measured corners, and the schema belongs to `klt` (klayout-tools),
  not this repo. The conditional follow-up issue #307 anticipated — filing a
  generic capability gap at `2AMLogic/klayout-tools` if **no** single
  resistance trips every corner — is **not triggered** by this sweep.

## Consequences

- **Pinned members move when this is implemented.** Both
  `sim/driver-matching-mismatch/testbench/mc.json` (sha256
  `984705140b976229b805392528a3df131d2635d006044714235b36f7664a1fe0`) and
  `sim/driver-matching-mismatch/testbench/driver_mc_tb.spice` (sha256
  `3104bd80f5ddbb992e3c4bcf563c6675f27a0a715dee28490202e2bf872d3684`) are
  item-9 pinned members of `signoff/inventory/item-9-testbenches.json`, so the
  edit reds `python3 signoff/check.py --pins-only` until a `--regen` under the
  pinned grader (recipe: `signoff/README.md`).
- **Prose that must move with the value**: `mc.json` line 149 (the `xover`
  control description, "fixed 180 ohm load … below 1.3 V"), line 153 (the
  substitution value itself), and line 175 (the `record.method` bullet that
  restates the control and its "about 1.26 V" expectation);
  `driver_mc_tb.spice` lines 15-17 (the negative-control-knob comment
  describing the 180 ohm load). The stored records are untouched: each froze
  its own deck and `mc.json` by digest and remains valid evidence of what it
  ran against.
- **What ratification enables**: the implementing PR re-derives the control
  as decided, re-pins, and — per the operator's re-run choice — mints the
  follow-up records whose `xover` controls must read `detected`. Until one of
  options A-C is executed, item 6's crossover row (`6-06` / `6-14`, #223)
  still has no working control at `sf40v36` / `fs100v36` in landed evidence;
  today that costs nothing in the manifest grade because the driver records
  are not yet cited there (`signoff/README.md` item 6 still cites the
  diff-/se-receiver reports for `negative_control_not_detected`), but it
  bites the moment #223 cites them.
- **What does not change**: `spec/usb2-phy.md` (crossover window 1.3-2.0 V
  and every other row), the nominal campaigns, the `match` receiver and its
  330 ohm control, `sim/corners.json`, and the harness. The change strictly
  strengthens the negative control; it relaxes nothing.
