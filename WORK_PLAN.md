# Work Plan

Prioritized roadmap generated automatically by the Guide triage agent from
current GitHub label state. Everything between the markers below is
machine-generated and is overwritten wholesale on each update; nothing
outside the markers is touched by automation.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#132**: Worker klt tool venv still lacks cocotb_tools: pre-PR gate cannot pass on fleet hosts (recurrence of #94)
- **#220**: T1 items 2-4, 11 (analog layout): lay out the differential_driver leaf with DRC, LVS and ERC supply evidence

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#220**: T1 items 2-4, 11 (analog layout): lay out the differential_driver leaf with DRC, LVS and ERC supply evidence

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#243**: sim: record D+ pull-up mismatch Monte Carlo; declare driver matching/crossover campaign

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)*
- **#220**: T1 items 2-4, 11 (analog layout): lay out the differential_driver leaf with DRC, LVS and ERC supply evidence *(curated)*
- **#223**: T1 item 6 (Monte Carlo, analog): mismatch campaigns for the driver rise/fall matching and D+ pull-up ±5% rows *(curated)*

## Proposed (Architect / Hermit)

- **#233**: Consolidate four near-identical analog run_checks.py into one shared runner *(hermit)*

## Epics

- **#23**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#105**: Digital T1 items 3, 4, 11 (and 5): place and route the real UTMI datapath and commit DRC, LVS, ERC and timing evidence

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 4 |
| Architect / Hermit proposals | 1 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
