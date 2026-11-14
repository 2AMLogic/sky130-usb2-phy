# Roadmap

A full-speed USB 2.0 PHY on sky130 (digital UTMI layer plus a ported analog
front end), built to exercise the open flow and
[klayout-tools](https://github.com/2AMLogic/klayout-tools) end to end.

Status as of 2026-11-13, `main` @ `4c3750c`.

[`WORK_PLAN.md`](../WORK_PLAN.md) is the machine-generated label snapshot;
[`signoff/signoff-report.json`](../signoff/signoff-report.json) is the verdict
of record and wins where this file disagrees with it.

## Where it stands

The ladder is the klayout-tools design-evidence checklist, graded by
`klt signoff` (pinned to the 0.8.0 release) and enforced in CI by
[`signoff/check.py`](../signoff/check.py). The block is `mixed-signal`, so each
of the 11 items is graded per partition: **9 of 22 rows `met`, 1
`not_applicable`, `tier: null`.** Tracker: #23.

| Item | Analog (five leaves) | Digital (`usb_utmi_top`) |
|---|---|---|
| 1 Design sources | met (#219) | met (#206) |
| 2 Layout | met: five leaf GDS + generators (#167, #220, #221, #222) | unmet, `no_evidence` (#207) |
| 3 DRC clean | unmet, `invalid_evidence`: five clean reports, grader takes one envelope | unmet, `no_evidence` (#117) |
| 4 LVS clean | unmet, `invalid_evidence`: five `match` reports, same shape problem | unmet, `no_evidence` (#117) |
| 5 Corner verification | unmet, `no_evidence`: nothing cited yet | unmet, `no_evidence` (#117, #118) |
| 6 Monte Carlo | unmet, `negative_control_not_detected`; rows 6-06, 6-14 uncovered (#223) | not applicable (#208) |
| 7 Post-layout | unmet, `no_evidence` | unmet, `no_evidence` (#209) |
| 8 Characterization report | met (#218) | met |
| 9 Testbenches shipped | met | met |
| 10 Repo hygiene | met | met |
| 11 Power delivery | unmet, `lvs_did_not_pass` (gated on item 4) | unmet, `no_evidence` (#117) |

What is evidenced behind those rows:

- **Spec** ratified 2026-08-05 ([`spec/usb2-phy.md`](../spec/usb2-phy.md)).
  By their own status lines, DR-0007 and DR-0003 Decision 1 are ratified;
  DR-0001, 0002, 0004, 0005, 0006 and DR-0003 Decisions 2 and 3 read proposed.
- **Digital:** FS receive/transmit RTL verified under cocotb (six suites in
  `verification/`); one design-anchored synthesis record and a committed
  gate-level netlist for `usb_utmi_top` (#164). Place-and-route, STA, DRC and
  LVS have run only on the `utmi_stub` toolchain smoke
  (`flow/smoke-utmi_stub/`), which anchors no design claim.
- **Analog:** all four block ports are merged as five leaf schematics. Nine of
  the 16 rows of spec section 6 have a schematic-level PASS record
  ([`docs/characterization.md`](characterization.md)): 45-point and 225-point
  PVT matrices, plus `klt yield` Monte Carlo for the receiver rows (#166) and
  the D+ pull-up trim (PR #243). Each leaf has a generated layout with a clean
  `klt drc`, a matching `klt lvs` and a `klt erc` supply report under
  `flow/analog-layout-<leaf>/` (cited by PR #256).
- **Not evidenced:** the three PLL rows, the two squelch rows, and rows 6-15
  and 6-16 read `NO EVIDENCE`. Nothing is post-layout, and no PHY top exists.

Stale elsewhere: the body of #23 and parts of
[`signoff/README.md`](../signoff/README.md) still describe an empty analog
partition and "6 of 22"; the report is current.

## Now (startable today; none has an issue yet)

1. **Re-pin the grader from klt 0.8.0 to the 0.9.1 release and regrade.**
   Done when `signoff/check.py`, `signoff/toolchain.json` and
   `.github/workflows/ci.yml` name one version, `signoff-report.json` is
   regenerated with it, and `python3 signoff/check.py` passes (as in #165).
2. **Bring `signoff/README.md` and the top-level README back in line with the
   report.** Done when the verdict heading matches `t1_met_count`, the item 5
   and item 7 analog rows no longer say that no analog design or layout exists,
   the README no longer calls #130 open, and `python3 signoff/check.py` passes
   (the README is in the item 10 inventory, so this needs `--regen`).
3. **Item 5 (analog): declare the analog row set and cite the committed corner
   envelopes.** Done when `signoff/block-manifest.json` carries
   `spec_rows."5.analog"`, cites the newest passing 45-point `klt sim`
   envelopes under `sim/*/corners/`, declares the rows with no evidence as
   gaps, and 5 analog no longer reads `no_evidence` (it stays `unmet`).
4. **Item 7 (analog): first `klt pex` report on one leaf.** Done when a
   committed `klt pex` report for `differential_receiver` gives the
   schematic-versus-extracted delta for its section 6 rows, with a record under
   `flow/` or `sim/`. If the tool cannot produce it, the done-criterion is the
   upstream klayout-tools issue describing the gap.

## Next

- **Items 3, 4 and 11 (analog): cite the five leaves as a set.** The grader
  gap is klayout-tools#5044, closed upstream on 2026-11-06, after the 0.9.1
  wheel; unblocked by the first klt release that carries it, then a re-pin.
  Item 4 has a second recorded blocker (`runset_unrecognised_device` on a
  single-leaf probe). Done when 3, 4 and 11 analog read `met`.
- **Item 6 (analog): finish #223.** The driver rise/fall matching campaign
  (`sim/driver-matching-mismatch/`, declared, not run) needs more compute time
  than one build session; the pull-up record needs citing under row 6-14. Also
  open: the receiver reports are refused for a control that is undetected by
  construction. Done when 6 analog reads `met`.
- **Remaining four leaves through `klt pex`**, after Now 4 settles the method.
- **Digital physical chain, in order:** #116 (stage 2 to 6 driver and request
  templates) → #117 (six-corner layout, DRC, LVS, ERC, STA) → #118, #207, #209
  (citations and the SDF-annotated re-run). Epic #105. Unblocked by #132.

## Later

- **Squelch detector and the 15 kΩ pull-down rows.** First question: are
  DR-0003 Decisions 2 and 3 ratified as proposed? Rows 6-12, 6-13 and 6-15
  stand as ratified with no source block, which keeps item 5 analog open.
- **PLL rows 6-01 to 6-03.** First question: what evidence from the pinned
  `sky130-pll` reference ([`reuse.lock.json`](../reuse.lock.json)) can this
  block cite, and against which pin?
- **PHY top assembly** (analog leaves, digital macro, pads). First question:
  what is the top-level floorplan and supply plan, as a decision record?
- **Driver output resistance** fails the 28 to 44 ohm bound at 27 of 225
  supplemental points. First question: is DR-0005's corner coverage ratified?
- **High-speed (480 Mbps).** Stretch goal; first question: is full-speed
  assembled and evidenced?

## Blocked and waiting

**Every open issue carries `loom:blocked` today, so no existing issue is
dispatchable.** The four Now items are the only startable work.

- #132: fleet workers' `klt` environment cannot import `cocotb_tools`, so the
  pre-PR gate fails there. Re-checked 2026-11-13, still unmet. It holds #116
  and through it #117, #118, #207, #209 and epic #105.
- #223: the driver campaign outlasts one build session (parked twice).
  #193: the artifact-store adoption waits on a first recorded campaign.
- Operator decisions: ratification of the decision records that read proposed.
- #23 and #40 are trackers; #51, #84, #86, #128 are tooling housekeeping.

## Not planned

- A PLL designed here (pinned reference only), or a squelch detector or
  regulator without a ratified decision record.
- Relaxing a ratified spec row, or citing the `utmi_stub` smoke as block evidence.
