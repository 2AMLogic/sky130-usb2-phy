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

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#219**: T1 item 1 (design sources, analog partition): attest the five analog leaf schematics + netlists and cite them as 1.analog
- **#221**: T1 items 2-4, 11 (analog layout): lay out the se_receiver_dp and se_receiver_dm leaves with DRC, LVS and ERC supply evidence
- **#222**: T1 items 2-4, 11 (analog layout): lay out the dplus_pullup leaf with DRC, LVS and ERC supply evidence
- **#223**: T1 item 6 (Monte Carlo, analog): mismatch campaigns for the driver rise/fall matching and D+ pull-up ±5% rows
- **#224**: T1 item 6 (Monte Carlo, analog): declare the analog statistical row set and cite the committed klt yield reports as 6.analog

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#228**: feat: add sky130 se_receiver_dp and se_receiver_dm analog layouts with check records

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#227**: feat(layout): add sky130 dplus_pullup layout with DRC/LVS/ERC evidence
- **#229**: feat: declare analog statistical rows and cite receiver yield reports under item 6
- **#230**: feat: attest analog design sources as 1.analog with klt-based netlist freshness check

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)*
- **#219**: T1 item 1 (design sources, analog partition): attest the five analog leaf schematics + netlists and cite them as 1.analog *(curated)*
- **#220**: T1 items 2-4, 11 (analog layout): lay out the differential_driver leaf with DRC, LVS and ERC supply evidence *(curated)*
- **#221**: T1 items 2-4, 11 (analog layout): lay out the se_receiver_dp and se_receiver_dm leaves with DRC, LVS and ERC supply evidence *(curated)*
- **#222**: T1 items 2-4, 11 (analog layout): lay out the dplus_pullup leaf with DRC, LVS and ERC supply evidence *(curated)*
- **#223**: T1 item 6 (Monte Carlo, analog): mismatch campaigns for the driver rise/fall matching and D+ pull-up ±5% rows *(curated)*
- **#224**: T1 item 6 (Monte Carlo, analog): declare the analog statistical row set and cite the committed klt yield reports as 6.analog *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#23**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#105**: Digital T1 items 3, 4, 11 (and 5): place and route the real UTMI datapath and commit DRC, LVS, ERC and timing evidence

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 5 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 3 |
| Curated | 8 |
| Architect / Hermit proposals | 0 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
