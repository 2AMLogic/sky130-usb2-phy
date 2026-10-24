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

- **#193**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#198**: feat: store Monte Carlo mismatch evidence in the artifact store

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)*
- **#193**: Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact) *(curated)*

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
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 3 |
| Architect / Hermit proposals | 0 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
