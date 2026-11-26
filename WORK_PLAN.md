# Work Plan

Prioritized roadmap generated automatically by the Guide triage agent from
current GitHub label state. Everything between the markers below is
machine-generated and is overwritten wholesale on each update; nothing
outside the markers is touched by automation.

<!-- guide:plan-body:start -->
_Generated: 2026-11-26T02:32:07Z (snapshot; compare against live labels)_
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

- **#473**: Share the receiver grading rules so PEX rejects invalid voltages on D+ and D−
- **#475**: Share the bounded TX line-state sampler across the serializer and UTMI-top tests

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#476**: refactor(verification): share one bounded TX line-state sampler across both TX suites

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#474**: fix(sim): grade extracted receivers with schematic bench rules

## Proposed

Issues carrying `loom:curated`.

- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)* *(held)*
- **#331**: T1 item 6 (analog): cite the driver-matching and D+ pull-up klt yield reports in the manifest (6-06, 6-14) *(curated)* *(held)*
- **#394**: Merge queue: add the merge_group trigger and adapt the PR-metadata gates *(curated)* *(held)*
- **#404**: T1 item 7 (analog): klt pex report for the differential_driver leaf, then cite all five leaf reports as 7.analog *(curated)* *(held)*

## Proposed (Architect / Hermit)

_None._

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
| Approved PRs awaiting merge | 1 |
| Curated | 4 |
| Architect / Hermit proposals | 0 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
