# 0007: Extend the retired open_pdks pin's `records_through` to 20261016

- **Status**: ratified
- **Date**: 2026-10-21
- **Decided by**: operator (rjwalters), ruling on issue #173, option (a)
- **Related**: #173, #151 (open_pdks volare -> ciel 2.6.1 pin move),
  `sim/pdk-pins.json`, `sim/harness/matrix.py` (`check_pdk_identity`)

## Context

`sim/pdk-pins.json` retires open_pdks `c6d73a35` with `records_through`
`20261014`. Four `driver-signal-quality` records dated 20261016
(`20261016-175635-59ec9c0`, `20261016-175832-59ec9c0`,
`20261016-183930-59ec9c0`, `20261016-184100-59ec9c0`) were made under that
pin, so the analog evidence lint fails and main is red. The retired pin's
`lib_sha256` is byte-identical to the current `f6eeac7` pin's, so the library
the records ran against is unchanged.

## Decision

Move the retired `c6d73a35` entry's `records_through` in
`sim/pdk-pins.json` from `20261014` to `20261016`, exactly two days, and cite
this record from that entry (`decision_record`). Nothing else changes: the
four 20261016 records are untouched (append-only), and the evidence lint's pin
check is not modified. This is a pin-bookkeeping decision; it extends no
section of `spec/usb2-phy.md` or `spec/architecture.md`.

## Alternatives considered

- **Change the evidence lint's pin check to compare `lib_sha256` only
  (option b)** - not chosen by the operator; it would weaken the check for
  every future record.
- **Re-run the four records on `f6eeac7` and replace them** - records are
  append-only, and main should not wait on a re-run.

## Consequences

- `npm run lint` passes on main again.
- The re-run on `f6eeac7` is queued as forward evidence; main does not wait on
  it. That run is not a verified result of this record.
- Records after 20261016 must still carry the current pin.
