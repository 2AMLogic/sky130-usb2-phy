# sky130-usb2-phy

[![CI](https://github.com/2AMLogic/sky130-usb2-phy/actions/workflows/ci.yml/badge.svg)](https://github.com/2AMLogic/sky130-usb2-phy/actions/workflows/ci.yml)

A USB 2.0 PHY on the [sky130](https://github.com/google/skywater-pdk) open
PDK, designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source flow — cocotb + Icarus and Yosys/OpenROAD on the digital side,
xschem + ngspice on the analog side.

**Status: digital UTMI-side RTL implemented and cocotb-verified; the five
analog leaves are drawn and DRC/LVS/ERC-recorded; no post-layout evidence
anywhere, and no PHY-level assembly.**
The full-speed receive and transmit paths (bit sync, NRZI encode/decode,
(de)stuffing, framing, UTMI CDC) are implemented and verified under cocotb. A
design-anchored synthesis experiment and gate-level netlist now exist for the
real `usb_utmi_top`, with the disclosed combinational-loop and gate-level-test
limitations recorded in the characterization report; real-UTMI place-and-route
remains pending. The FS line driver, differential and single-ended receivers,
and trimmed D+ pull-up have schematic-level sky130 simulation evidence, and
each of those five leaves now has committed GDS with a clean `klt drc` record,
a matching `klt lvs` record and a `clean_partial` `klt erc` record. No leaf has
parasitic extraction or post-layout re-simulation, so every circuit result in
this repo is schematic-level. See the scope note below for the coverage limits,
and [`signoff/README.md`](signoff/README.md) for the machine-graded T1 verdict
(9 of 22 rows `met` as read from `signoff/signoff-report.json` on 2026-11-14).

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
  Driver signal-quality and static results pass all 45 corners. The D+ pull-up
  additionally passes 225 MOS/resistor/capacitor corner combinations, selecting
  a trim code per point. The receivers also pass the supplemental 225-point
  global resistor/capacitor-set sweep (675 point/common-mode combinations for
  differential sensitivity). Two supplemental 225-point driver sweeps are
  **complete runs that fail** — recorded failures, not missing coverage: the
  static sweep violates the unchanged 28–44 ohm output-resistance bound at 27
  of 225 points (198/225 pass, 68 problems, both sides of the bound), and the
  signal-quality sweep passes 223 of 225 points with 4 problems at the
  remaining 2 — crossover voltage above the unchanged 2.0 V maximum at `fs_ll`
  and `fs_hl`, 100 C, 3.6 V (record `20261016-184100-59ec9c0`, run as 8 shard
  jobs). Disabled-pad behaviour above the I/O supply is recorded engineering
  data against no ratified limit; an envelope and a 10 uA in-rail budget are
  *proposed* in
  [`spec/decision-records/0006-disabled-pad-leakage-envelope.md`](spec/decision-records/0006-disabled-pad-leakage-envelope.md)
  (status: proposed, awaiting operator ratification) over the case table in
  [`docs/disabled-pad-envelope-study.md`](docs/disabled-pad-envelope-study.md).

  **Layout, mismatch and integrated PHY behaviour — the partial state, not one
  word.** *Layout:* each of the five leaves has committed GDS with a clean
  `klt drc` record (0 violations), a matching `klt lvs` record and a
  `clean_partial` `klt erc` record; **no** leaf has parasitic extraction or
  post-layout re-simulation (#281), so every result above stays
  schematic-level. *Mismatch:* committed Monte Carlo records exist for the
  differential receiver, both single-ended receivers and the D+ pull-up trim,
  while `sim/driver-matching-mismatch/` is **declared but not run** — a
  testbench and no `records/` — leaving spec rows 6-06 and 6-14 uncovered
  (#223). *Integrated PHY behaviour:* genuinely unverified; `usb_utmi_top`
  place-and-route has not run. See [`design/README.md`](design/README.md) for
  the per-block results and limitations.
- **PLL** — not designed here: consumed by pinned reference to
  [`sky130-pll`](https://github.com/2AMLogic/sky130-pll)
  (see [`reuse.lock.json`](reuse.lock.json)).

Full-speed (12 Mbps) is the first functional target; high-speed (480 Mbps) is
a stretch goal, not a commitment.

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
the real UTMI RTL. On the analog side the five ported leaves are DRC-clean,
LVS-matching and ERC-`clean_partial`, but no leaf is parasitic-extracted and
nothing is assembled, so the "DRC/LVS-clean" rung is reached per leaf and not
for the PHY.**

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
