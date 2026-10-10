# 0005: Resistor sheet-resistance corner coverage for recorded analog evidence

- **Status**: proposed. It changes no ratified target; `spec/usb2-phy.md` is
  not edited and the section 6 D+ pull-up row (1.5 kohm +/-5 %, i.e. 1.425 to
  1.575 kohm) is unchanged. Decision 0001 Decision 5 (temperature -40 to
  100 C, I/O supply 3.0 to 3.6 V) is unchanged and is the envelope used here.
- **Date**: 2026-10-10
- **Decided by**: proposed by the Builder agent, issue #126. Needs operator
  ratification.
- **Related**: #126 (this gap), #113 / PR #125 (D+ pull-up, which disclosed
  it), #109 (owner of `sim/corners.json`), #110, #111 (receivers), #112
  (driver), #119 (harness-core extraction: this change touches
  `sim/harness/` and must be rebased onto it, not the reverse), #127
  (malformed trim configuration, a separate failure), #23 (evidence epic),
  `0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`.

## Context

Every committed 45-point result in `sim/` uses the five bare sections `tt`,
`ff`, `ss`, `fs`, `sf` of the pinned library (`sky130A`, open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, `libs.tech/ngspice/sky130.lib.spice`
sha256 `17c208a6...5f64`). Read from that file, each of the five includes
`corners/<mos>.spice` and `r+c/res_typical__cap_typical.spice`: MOS corners and
the resistor temperature coefficient move, the resistor sheet resistance does
not. The library ships separate sections for it. Read from the same file:

| Section | MOS file | r+c set (resistor / capacitor) |
|---|---|---|
| `ll`, `hh`, `hl`, `lh` | `corners/tt.spice` | low/low, high/high, high/low, low/high |
| `<mos>_ll`, `_hh`, `_hl`, `_lh` for `<mos>` in `sf ff ss fs` | `corners/<mos>.spice` | same four sets |

So the suffixed sections keep a MOS corner (the bare `ll`/`hh`/`hl`/`lh` carry
`tt`), but they are **not resistor-only**: each r+c file also changes the
capacitor set and the drawn-width tolerances (`tol_poly`, `tol_nw`, `tol_m*`,
...). The sets are the PDK's global corners (every resistor moves together);
they are not per-device spread or mismatch. For `res_generic_po` (D+ pull-up
ladder, driver series resistor) `rp1` is 42.2 / 44 (low), 48.2 (typical),
53.52 / 55.8 (high) ohm/sq and `tol_poly` moves by +/-0.0287 um; the
`res_xhigh_po_1p41` devices (receiver dividers and bias, driver bias) respond
through their own `var_mult` terms in the same files.

## Decision

1. **A supplemental approved matrix, `pvt225-mos-rc`, in
   `sim/corners-resistor-sets.json`** (schema `.../corners/2`): the 25 sections
   {5 MOS corners} x {typical, `ll`, `hh`, `hl`, `lh`} x temperature
   {-40, 27, 100} C x supply {3.0, 3.3, 3.6} V = 225 points. The MOS axis is
   retained and fully crossed; typical is included so the record is
   self-contained. It is a full cross, not a reduced matrix, so nothing needs
   a reduction argument.
2. **`sim/corners.json` (the 45-point matrix, id `pvt45-mos`) is not changed.**
   Existing records keep their meaning and are never reinterpreted: they are
   45-point, typical-resistor evidence. The 225-point matrix is a supplement.
3. **Validation uses a closed list of approved configurations.** The loader
   (`sim/harness/matrix.py`) accepts a corners file, including the copy frozen
   inside a historical record, only if it equals an entry of
   `APPROVED_MATRICES` exactly (sections, axes, point count, PDK name and
   library, supply source); schema `/1` is by definition `pvt45-mos`. A
   self-declared matrix, an unknown section, an omitted section or a duplicate
   tuple is rejected. The runner, request check and evidence lint all go
   through the same loader. A testbench selects its matrix through a named
   `variants` entry in its `tb.json`; a variant may override only
   `matrix_id`, `claim` and `record` prose, so it cannot relax a bound, the
   trim window or a measurement. The record manifest stores the variant, the
   matrix id and, for the 225-point matrix, the section -> (MOS, resistor set,
   capacitor set) mapping with the resolved library includes; the runner
   refuses to run if the installed library's includes differ from the approved
   mapping, and the lint re-checks the stored mapping and PDK identity.
4. **`dplus-pullup-tolerance --variant resistor-sets`** is the recorded run:
   all 16 trim codes at all 225 points, batch backend only, the same
   existential rule per point (at least one code within 1425 to 1575 ohm,
   inclusive), the same deterministic best-code tie break (lowest code), and
   the same caveat that the code is chosen per point, not as one calibration
   code. A FAIL result is recorded as FAIL; no bound is relaxed.
5. **Other blocks.** The receivers and the driver are audited, not re-run in
   this change (see Consequences).

## Alternatives considered

- **Add the resistor axis to `sim/corners.json`.** Rejected: it would change
  the meaning of 45-point records the lint would then have to special-case,
  and it multiplies every experiment's cost five-fold when only resistor-
  dominated blocks need it.
- **A reduced matrix (only `ll` and `hh`, or only worst-case MOS pairing).**
  Rejected: the suffixed sections also move capacitors and `tol_*`, and the
  worst MOS/resistor/temperature pairing differs per block. DC points are
  cheap on the batch fleet, so the full cross is simpler to justify.
- **Keep the two-run design-basis check and write a decision record instead of
  a run.** Rejected: a recorded run was feasible. The two-run check remains
  unrecorded design evidence and is not relied on.
- **Let each record declare its own matrix.** Rejected: it would let a record
  narrow its own coverage and still lint clean.

## Consequences

- Coverage claimed by the new record is limited to the PDK's global
  resistor/capacitor corners at deterministic PVT, schematic level. It is not
  per-device resistor spread, mismatch, Monte Carlo, a single fixed calibration
  code across the matrix, or layout.
- Audit of the other blocks (no re-run here; each needs its own follow-up):
  the differential receiver (`RBIAS`, `res_xhigh_po_1p41`, L 140 um) and both
  single-ended receivers (`R1`, `R2` divider and `RBIAS`) set bias current and,
  for the SE receivers, the threshold reference through resistors, and the
  driver has a `res_generic_po` series resistor (W 20 / L 10.8 um, about 26 ohm
  against a 28 to 44 ohm row), an `RB` bias resistor and MIM edge-rate
  capacitors. Their 45-point records cover MOS corners and temperature only.
  The earlier statements that "resistor spread rides on the same `tt ff ss fs
  sf` sections" are wrong and are corrected in `design/README.md`. Each block
  needs the same supplemental sweep (a `resistor-sets` variant) before any
  claim that covers sheet-resistance or capacitor-set spread: the driver series
  resistor is the most direct, since its row is a +/-22 % window on a
  resistance that moves with `rp1` and `tol_poly`. Follow-up issues track
  this.
- `sim/corners-resistor-sets.json` is a new file next to `sim/corners.json`
  (owned by #109); `sim/harness/` edits overlap #119 and must be rebased
  when that extraction lands.
- Every number here is a design target or an observation from the library
  text until the recorded run verifies it; this record asserts no electrical
  PASS.

## Result of the recorded run (observation, not a ratified claim)

`sim/dplus-pullup-tolerance/records/20261010-014615-8ebfb55.md`: batch job
`klt-sim-10dfd5d87262`, PASS 225/225 (every point has at least two codes in
1425 to 1575 ohm; best code 1 to 14), independently recomputed from the raw
V(DP) in the envelope. Extremes: the highest code-15 resistance is 1443.9 ohm
(`sf_hl`, 100 C, 3.0 V) and the lowest code-0 resistance is 1531.7 ohm
(`fs_lh`, -40 C, 3.6 V), so the code range brackets the window with 19 ohm of
margin at the high-resistance end. Six earlier attempts are kept as FAIL
records (five `batch_no_capacity`, one fleet-runner/client klt version skew
refused under the default `enforce`; the PASS run used
`--klt-runner-version-check warn` as the other batch records do).
