# sky130-usb2-phy — agent instructions

Open-source canary block: a USB 2.0 PHY on the sky130 PDK, designed and
verified by AI agents. This is a **mixed-signal** block — digital UTMI layer
plus an analog front end — so both flows apply.

- **PDK**: sky130 (open PDK). Digital: cocotb + Icarus for verification,
  Yosys for synthesis, OpenROAD for place-and-route. Analog: xschem +
  ngspice. Layout, DRC, and LVS go through klayout-tools (`klt`) in both
  cases.
- **Scope discipline — the thing most likely to go wrong here.** This block
  is an assembly of analog pieces that are still being designed in sibling
  canary repos. Do not design a PLL, a driver, or a receiver here. If a
  needed sibling block is not ready, the correct move is to specify the
  interface to it and stop, not to build a throwaway. Work in scope today:
  the spec, the architecture and partitioning, and the digital UTMI side.
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
This repository has [Repo Skills](https://github.com/rjwalters/repo) v0.10.0 installed —
general repository hygiene and environment commands invoked as `/repo:<command>`. Run
`/repo:help` for the command list, or see `.claude/skills/repo/SKILL.md` for the full
guide. Hygiene commands apply safe, reversible fixes by default and report each
change; run with `--ask` to review first, and `--prune` to allow irreversible
removals. Managed by `install.sh` — edit outside the markers only.
<!-- END REPO-SKILLS -->
