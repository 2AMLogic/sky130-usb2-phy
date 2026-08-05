# sky130-usb2-phy

A USB 2.0 PHY on the [sky130](https://github.com/google/skywater-pdk) open
PDK, designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source flow — cocotb + Icarus and Yosys/OpenROAD on the digital side,
xschem + ngspice on the analog side.

**Status: just opened, specification phase.** Nothing is designed yet. This
repo currently holds no RTL, no schematics, and no layout. See the scope note
below for what is deliberately *not* being built yet.

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
current-mode drivers, differential receivers, squelch envelope detection, and
a digital UTMI layer. Most of those analog pieces are being designed as their
own canary blocks in sibling repos and do not exist in finished form yet.

So this repo starts with the half that does not depend on them:

- **In scope now** — the target specification, the block-level architecture
  and partitioning, and the digital UTMI side (RTL, verification, synthesis).
- **Not in scope yet** — the analog assembly. It waits on the sibling blocks
  that supply the PLL, drivers, and receivers.

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
build-here/sibling-canary partition table.

Maturity ladder: spec ratified → UTMI RTL verified → analog blocks available
→ assembly → DRC/LVS-clean → shuttle seat → measured silicon. **Current
position: spec ratified, pre-RTL.**

## Repo layout

```
spec/          ratified spec + decision records
rtl/           UTMI-side Verilog sources
verification/  cocotb testbenches
design/        analog schematics (empty until the sibling blocks land)
sim/           analog testbenches + PVT corner results (empty for now)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
