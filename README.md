# sky130-usb2-phy

[![CI](https://github.com/2AMLogic/sky130-usb2-phy/actions/workflows/ci.yml/badge.svg)](https://github.com/2AMLogic/sky130-usb2-phy/actions/workflows/ci.yml)

A USB 2.0 PHY on the [sky130](https://github.com/google/skywater-pdk) open
PDK, designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source flow — cocotb + Icarus and Yosys/OpenROAD on the digital side,
xschem + ngspice on the analog side.

**The digital UTMI-side RTL is implemented and cocotb-verified. All five
analog leaves have committed layout, parasitic extraction and post-layout
simulation records. The PHY remains unassembled.**
The full-speed receive and transmit paths (bit sync, NRZI encode/decode,
(de)stuffing, framing, UTMI CDC) are implemented and verified under cocotb. A
design-anchored synthesis experiment and gate-level netlist now exist for the
real `usb_utmi_top`, with the disclosed combinational-loop and gate-level-test
limitations recorded in the characterization report; real-UTMI place-and-route
remains pending. The FS line driver, differential and single-ended receivers,
and trimmed D+ pull-up have schematic-level sky130 simulation evidence, and
each of those five leaves now has committed GDS with a clean `klt drc` record,
a matching PDK-runset LVS record and a `clean_partial` `klt erc` record.
The [post-layout records](#post-layout-records) cover individual leaf benches.
The [committed T1 report](signoff/signoff-report.json) grades 11 of 22 rows
`met`. For the analog partition, DRC and curated LVS (items 3 and 4) are
`met`, and supply ERC (item 11) is `unmet`. Post-layout verification (analog
item 7) remains `unmet` with reason `no_evidence` because the manifest has
no partition-level post-layout citation.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation in this repo is produced by AI agents working from a
ratified spec and an append-only evidence trail — not human-authored work
that agents merely assisted with. Verification is the product: every claim
traces to a recorded result. Where the agents hit friction with the
open-source tooling — most often
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — that friction
gets filed as a public issue against the tool itself, so the fix benefits
everyone using sky130, not just this repo.

## Scope, stated up front

A USB 2.0 PHY is an **assembly** — a PLL-based clock/data recovery path,
line drivers, differential and single-ended receivers, a switchable D+
pull-up, and a digital UTMI layer.

- **Digital UTMI side** (RTL, verification, synthesis) — designed here; the
  first slice, and the one with evidence today.
- **Analog front end** (FS line driver, receivers, D+ pull-up and
  termination) — **ported into this repo from
  [`gf180-usb2-phy`](https://github.com/2AMLogic/gf180-usb2-phy)**, one block
  per issue, per the operator ruling of 2026-10-08 (#40). The plan, with the
  pinned source commit and the four driver rows that fail in the source, is
  [`docs/porting-plan.md`](docs/porting-plan.md). All four block ports are
  merged, with schematic-level evidence over the 45-corner MOS PVT grid;
  differential sensitivity covers three common-mode points (135 combinations).
  Driver signal-quality and static results pass all 45 corners. All five
  leaves now have committed layout: the GDS streams and their generators are
  pinned by hash (T1 item 2.analog reads `pass`), and each leaf's latest
  frozen record reads DRC `clean`, PDK-runset LVS `match` and supply-ERC `clean_partial`.
  Of those three checks, DRC is signed off: the pinned grader (klt 0.9.2)
  carries
  [klayout-tools#5044](https://github.com/2AMLogic/klayout-tools/issues/5044)
  (fixed upstream 2026-11-06), so the five leaves' clean reports grade as a
  per-cell set and T1 item 3 (analog) reads `met` in the committed report.
  Curated LVS is signed off too: the #406 repair sizes the shared xhigh
  serpentine's first bottom U-turn so the bias resistors draw their exact
  netlist lengths (30.00 µm XRB, 140.00 µm XRBIAS), and T1 item 4 (analog)
  reads `met` with all five leaves matching (the D+ pull-up control 20/20,
  unchanged). Item 11 (analog) pairs each supply-ERC report with the same
  curated LVS and remains `unmet / substrate_isolation_undecidable` — the
  grader's substrate-isolation rule wants an ERC request naming the deck/PDK
  family or `ties[].isolation_boxes` asserted, which the committed ERC specs
  do not declare. The reports
  also disclose their own gaps: LVS `power_connectivity` is `unchecked`, ERC
  antenna levels are `pass_partial`, and each DRC report lists layers present
  in the stream with no rules. The D+ pull-up
  additionally passes 225 MOS/resistor/capacitor corner combinations, selecting
  a trim code per point. The receivers also pass the supplemental 225-point
  global resistor/capacitor-set sweep (675 point/common-mode combinations for
  differential sensitivity). Two supplemental 225-point driver sweeps are
  **complete runs that fail** — recorded failures, not missing coverage: the
  static sweep violates the unchanged 28–44 ohm output-resistance bound at 27
  of 225 points (198/225 pass, 68 problems, both sides of the bound), and the
  signal-quality sweep passes 223 of 225 points with 4 problems at the
  remaining 2 — crossover voltage above the unchanged 2.0 V maximum at `fs_ll`
  and `fs_hl`, 100 C, 3.6 V (record `20261016-184100-59ec9c0`, run as 8 batch
  jobs). Disabled-pad behaviour above the I/O supply is recorded engineering
  data against no ratified limit; an envelope and a 10 uA in-rail budget are
  *proposed* in
  [`spec/decision-records/0006-disabled-pad-leakage-envelope.md`](spec/decision-records/0006-disabled-pad-leakage-envelope.md)
  (status: proposed, awaiting operator ratification) over the case table in
  [`docs/disabled-pad-envelope-study.md`](docs/disabled-pad-envelope-study.md).

  *Mismatch:* committed Monte Carlo records exist for the
  differential receiver, both single-ended receivers and the D+ pull-up trim,
  and `sim/driver-matching-mismatch/` has all four of its declared corners
  recorded as stored evidence (not yet cited by the manifest) — leaving spec
  rows 6-06 and 6-14 formally uncovered (#331). *Integrated PHY behaviour:*
  genuinely unverified; `usb_utmi_top`
  place-and-route has not run. See [`design/README.md`](design/README.md) for
  the per-block results and limitations.
- **PLL** — not designed here: consumed by pinned reference to
  [`sky130-pll`](https://github.com/2AMLogic/sky130-pll)
  (see [`reuse.lock.json`](reuse.lock.json)).

Full-speed (12 Mbps) is the first functional target; high-speed (480 Mbps) is
a stretch goal, not a commitment.

### Post-layout records

All five analog leaves have committed `klt pex` records. The 45- and
225-point sweeps above used schematic netlists. The benches below used
extracted netlists at selected corners. Nominal is `tt_27c_3.30v`.

| Leaf and bench record | Corners tested | Post-layout result |
| --- | --- | --- |
| [Differential receiver sensitivity](sim/diff-receiver-pex/records/20261115-051001-f76df63.md) | Nominal and binding `sf_100c_3.00v` | `PASS` |
| [D+ single-ended receiver thresholds](sim/se-receiver-dp-pex/records/20261121-001320-3190eab.md) | Nominal and binding `ff_lh_100c_3.00v` | `PASS` |
| [D− single-ended receiver thresholds](sim/se-receiver-dm-pex/records/20261121-001624-3190eab.md) | Nominal and binding `ff_lh_100c_3.00v` | `PASS` |
| [DRC-repaired D+ pull-up](sim/dplus-pullup-pex/records/20261124-011843-274376a.md) | Nominal and binding `fs_hl_100c_3.00v` | `PASS` (52/52 measurement comparisons across both corners) |
| [Driver static](sim/diff-driver-pex/records/20261121-013701-e0b9d95-static.md) | 3 (nominal, `fs_-40c_3.60v`, `sf_-40c_3.60v`) | `FAIL` |
| [Driver signal quality](sim/diff-driver-pex/records/20261121-015751-e0b9d95-sq.md) | 4 (nominal, `fs_100c_3.60v`, `sf_-40c_3.60v`, `fs_100c_3.00v`) | `ERROR` |

## Why this block

The specification has been frozen since 2000, which makes it an unusually
stable target for a multi-month agent-driven design. HS PHYs have been
fabricated and verified at 0.25 µm and 0.35 µm — nodes *coarser* than sky130
— so feasibility at this node is not the open question. And the only
open-source sky130 attempt we are aware of
([Vlsir/Usb2Phy](https://github.com/Vlsir/Usb2Phy)) built the analog half and
went dormant in February 2023.

It is also the hardest workout in the program for the tools themselves, which
is the canary's actual job: a block that spans digital synthesis, analog
design, and the seam between them exercises paths no single-domain block
reaches.

## Target specification

**Ratified 2026-08-05** — see [`spec/usb2-phy.md`](spec/usb2-phy.md) for the
full specification: signaling/speed target, UTMI interface, reference clock
and PLL jitter budget, supply architecture, analog sub-block interface
requirements, verification scope, and the decision log behind each of those.
[`spec/architecture.md`](spec/architecture.md) has the block diagram and
partition table (what is designed here, ported here, or consumed by pinned
reference).

Maturity ladder: spec ratified → UTMI RTL verified → analog blocks available
→ assembly → DRC/LVS-clean → shuttle seat → measured silicon. **Current
position: spec ratified, FS receive/transmit RTL implemented and
cocotb-verified, and the real `usb_utmi_top` has a design-anchored
synthesis-only record and committed gate-level netlist. On the digital side,
P&R/STA/LVS/DRC have still been run only for the toolchain-plumbing stub, not
the real UTMI RTL. All five analog leaves are DRC-clean, LVS-matching and
ERC-`clean_partial`, with committed [post-layout records](#post-layout-records).
The PHY remains at the pre-assembly stage.**

## Characterization

[`docs/characterization.md`](docs/characterization.md) is the authoritative
characterization summary: every row of `spec/usb2-phy.md` §6 indexed against
the evidence records that exist, per PVT corner, with the record id behind
each entry. The real datapath now has one design-anchored, nominal-corner
synthesis record, but it does not establish a spec-row result; the complete
physical-flow records remain the `smoke-utmi_stub` toolchain experiment
(`design.anchors_design_claim: false`).

## Repo layout

```
spec/          ratified spec + decision records
rtl/           UTMI-side Verilog sources
verification/  cocotb testbenches
flow/          synthesis + P&R recipes (Yosys, OpenROAD), driven through klt
design/        analog schematics + derived netlists (five ported leaves:
               FS driver, differential receiver, two SE receivers, D+ pull-up)
sim/           analog simulation harness, testbenches + PVT corner results
layout/        GDS + DRC/LVS/ERC reports (klayout-tools driven); analog/ holds
               the five leaf layouts and their generators
signoff/       machine-graded T1 verdict of record (klt signoff --manifest)
measurements/  silicon characterization (empty until tape-out)
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs `npm run
check:ci` on every pull request and push to `main`, bootstrapping Icarus
Verilog, `klt`, and cocotb so both the pytest and cocotb/RTL layers of the
verification suite actually run — see
[`verification/README.md`](verification/README.md#ci-coverage-githubworkflowsciyml)
for exactly what is (and, on purpose, is not) exercised in CI.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
