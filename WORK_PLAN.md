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

- **#132**: Worker klt tool venv still lacks cocotb_tools: pre-PR gate cannot pass on fleet hosts (recurrence of #94)

## Important

`loom:important`; taken before unlabelled work.

- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates
- **#270**: signoff item-10 README pin goes stale on every automated Guide README edit (3rd recurrence of #180/#181)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#274**: Deduplicate analog device geometry: differential_driver/gen.py keeps a second copy of gen_common's Ports and mos
- **#348**: signoff/check.py's pins-refresh hint still prints the venv-bin PATH form that signoff/README.md now forbids
- **#349**: npm run check:all cannot complete on fleet workers whose host python3 has no pytest
- **#371**: signoff/README.md item-6 analog row: unescaped | truncates most of the cell on GitHub render

## In Progress

Issues currently being built (`loom:building`).

- **#275**: Deduplicate the raw-mode / byte-stream reference helpers duplicated across two TX testbenches
- **#326**: DR 0008: add sim/README.md to the 'prose that must move with the value' list (and clarify the 'two of four corners' parenthetical)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#372**: docs(spec): list sim/README.md prose in DR 0008's value-coupled prose checklist

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)*
- **#270**: signoff item-10 README pin goes stale on every automated Guide README edit (3rd recurrence of #180/#181) *(curated)*
- **#274**: Deduplicate analog device geometry: differential_driver/gen.py keeps a second copy of gen_common's Ports and mos *(curated)*
- **#326**: DR 0008: add sim/README.md to the 'prose that must move with the value' list (and clarify the 'two of four corners' parenthetical) *(curated)*
- **#331**: T1 item 6 (analog): cite the driver-matching and D+ pull-up klt yield reports in the manifest (6-06, 6-14) *(curated)*
- **#348**: signoff/check.py's pins-refresh hint still prints the venv-bin PATH form that signoff/README.md now forbids *(curated)*
- **#349**: npm run check:all cannot complete on fleet workers whose host python3 has no pytest *(curated)*
- **#371**: signoff/README.md item-6 analog row: unescaped | truncates most of the cell on GitHub render *(curated)*

## Proposed (Architect / Hermit)

- **#339**: Deduplicate analog layout generators: conflicts() and net-routing loop copied into three gen files *(hermit)*

## Epics

- **#23**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#105**: Digital T1 items 3, 4, 11 (and 5): place and route the real UTMI datapath and commit DRC, LVS, ERC and timing evidence

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 2 |
| Ready (`loom:issue`) | 4 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 9 |
| Architect / Hermit proposals | 1 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
