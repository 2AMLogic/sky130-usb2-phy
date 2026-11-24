# Work Plan

Prioritized roadmap generated automatically by the Guide triage agent from
current GitHub label state. Everything between the markers below is
machine-generated and is overwritten wholesale on each update; nothing
outside the markers is touched by automation.

<!-- guide:plan-body:start -->
_Generated: 2026-11-23T12:54:01Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#132**: Worker klt tool venv still lacks cocotb_tools: pre-PR gate cannot pass on fleet hosts (recurrence of #94) *(held)*

## Important

`loom:important`; taken before unlabelled work.

- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(held)*

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#413**: Parse ngspice library sections once per simulation preflight
- **#414**: dplus_pullup layout iteration: enabled-path parasitic resistance (contacted poly heads) pushes every trim code above the ratified 1.5 kohm +/-5% window

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#418**: refactor(sim): parse the ngspice library once per PVT preflight

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)* *(held)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)* *(held)*
- **#331**: T1 item 6 (analog): cite the driver-matching and D+ pull-up klt yield reports in the manifest (6-06, 6-14) *(curated)* *(held)*
- **#394**: Merge queue: add the merge_group trigger and adapt the PR-metadata gates *(curated)*
- **#404**: T1 item 7 (analog): klt pex report for the differential_driver leaf, then cite all five leaf reports as 7.analog *(curated)* *(held)*

## Proposed (Architect / Hermit)

- **#413**: Parse ngspice library sections once per simulation preflight *(hermit)*
- **#460**: Scope dplus-pullup and resistor-sets test sandboxes to testbench plus the single record under test *(hermit)* *(held)*

## Epics

- **#23**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers) *(held)*
- **#105**: Digital T1 items 3, 4, 11 (and 5): place and route the real UTMI datapath and commit DRC, LVS, ERC and timing evidence

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 1 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 5 |
| Architect / Hermit proposals | 2 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
