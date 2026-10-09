# sky130-usb2-phy — agent instructions

Open-source canary block: a USB 2.0 PHY on the sky130 PDK, designed and
verified by AI agents. This is a **mixed-signal** block — digital UTMI layer
plus an analog front end — so both flows apply.

- **PDK**: sky130 (open PDK). Digital: cocotb + Icarus for verification,
  Yosys for synthesis, OpenROAD for place-and-route. Analog: xschem +
  ngspice. Layout, DRC, and LVS go through klayout-tools (`klt`) in both
  cases.
- **Scope discipline — the thing most likely to go wrong here.** Operator
  ruling 2026-10-08 (#40, recorded in
  `spec/decision-records/0003-analog-port-scope-and-squelch-disposition.md`):
  the analog blocks (FS line driver, differential receiver, single-ended
  receivers, D+ pull-up and termination) are **ported from
  `2AMLogic/gf180-usb2-phy` into this repo**, one block per issue, following
  `docs/porting-plan.md`. No new sibling repos. The **PLL is never designed
  here**: it is consumed by pinned reference to `2AMLogic/sky130-pll`; if it
  is not ready, specify the interface and stop. A port re-derives every
  device for sky130 and re-measures every row: a gf180 result is source
  evidence, never a sky130 claim. Do not add blocks the plan does not list
  (no squelch detector, no regulator) without a ratified decision record.
  Pins to sibling repos live in `reuse.lock.json` at full commit SHAs.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue at
  `2AMLogic/klayout-tools` describing the tool gap generically — that tracker
  is scoped to the tool, so keep design-specific detail (spec values, this
  repo's content) out of it and describe the gap, not the design.
- **Verification is the product**: no claim without a testbench. PVT corners
  on every recorded analog result; recorded results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not relax
  the ratified spec to make results pass.
- **Full-speed first.** High-speed is a stretch goal. Do not let HS
  requirements drive FS architecture decisions before FS works.

## Harness bootstrap

Copy the digital verification harness pattern from `2AMLogic/sky130-modexp`
and the analog sim-harness pattern from `2AMLogic/gf180-bandgap` rather than
reinventing either — see issue #3.

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.
<!-- END LOOM ORCHESTRATION -->

<!-- BEGIN REPO-SKILLS -->
This repository has [Repo Skills](https://github.com/rjwalters/repo) v0.19.5 installed —
general repository hygiene and environment commands invoked as `/repo:<command>`. Run
`/repo:help` for the command list, or see `.claude/skills/repo/SKILL.md` for the full
guide. Hygiene commands apply safe, reversible fixes by default and report each
change; run with `--ask` to review first, and `--prune` to allow irreversible
removals. Managed by `install.sh` — edit outside the markers only.
<!-- END REPO-SKILLS -->
