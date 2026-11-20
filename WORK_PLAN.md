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

- **#132**: Worker klt tool venv still lacks cocotb_tools: pre-PR gate cannot pass on fleet hosts (recurrence of #94) *(held)*
- **#399**: Re-pin the signoff grader from klt 0.9.1 to the 0.9.2 release and regrade (item 3 analog grades met, 9 -> 10 of 22)

## Important

`loom:important`; taken before unlabelled work.

- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(held)*
- **#403**: T1 item 7 (analog): klt pex reports for the se_receiver_dp, se_receiver_dm and dplus_pullup leaves

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#399**: Re-pin the signoff grader from klt 0.9.1 to the 0.9.2 release and regrade (item 3 analog grades met, 9 -> 10 of 22)
- **#401**: T1 item 5 (analog): re-run the six 45-point corner benches with spec limits in the klt sim request (stored evidence; citation flip waits on klayout-tools#5963)
- **#403**: T1 item 7 (analog): klt pex reports for the se_receiver_dp, se_receiver_dm and dplus_pullup leaves

## In Progress

Issues currently being built (`loom:building`).

- **#400**: T1 items 4 and 11 (analog): probe the curated klt lvs engine on the five leaves and record, per leaf, which LVS route can be graded met
- **#402**: T1 item 6 (analog): rows 6-09 and 6-11 fail on undetected negative controls; give each measurement a detecting control or a declared not_applicable one and re-derive the yield reports
- **#404**: T1 item 7 (analog): klt pex report for the differential_driver leaf, then cite all five leaf reports as 7.analog

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#407**: feat: grade analog leaves with curated LVS and passive geometry checks

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#405**: fix: declare one-sided receiver negative controls not_applicable so item 6 rows 6-09/6-11 grade met

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)* *(held)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)* *(held)*
- **#331**: T1 item 6 (analog): cite the driver-matching and D+ pull-up klt yield reports in the manifest (6-06, 6-14) *(curated)* *(held)*
- **#394**: Merge queue: add the merge_group trigger and adapt the PR-metadata gates *(curated)* *(held)*
- **#399**: Re-pin the signoff grader from klt 0.9.1 to the 0.9.2 release and regrade (item 3 analog grades met, 9 -> 10 of 22) *(curated)*
- **#400**: T1 items 4 and 11 (analog): probe the curated klt lvs engine on the five leaves and record, per leaf, which LVS route can be graded met *(curated)*
- **#401**: T1 item 5 (analog): re-run the six 45-point corner benches with spec limits in the klt sim request (stored evidence; citation flip waits on klayout-tools#5963) *(curated)*
- **#402**: T1 item 6 (analog): rows 6-09 and 6-11 fail on undetected negative controls; give each measurement a detecting control or a declared not_applicable one and re-derive the yield reports *(curated)*
- **#403**: T1 item 7 (analog): klt pex reports for the se_receiver_dp, se_receiver_dm and dplus_pullup leaves *(curated)*
- **#404**: T1 item 7 (analog): klt pex report for the differential_driver leaf, then cite all five leaf reports as 7.analog *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#23**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers) *(held)*
- **#105**: Digital T1 items 3, 4, 11 (and 5): place and route the real UTMI datapath and commit DRC, LVS, ERC and timing evidence

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 2 |
| Important | 2 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 3 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 1 |
| Curated | 10 |
| Architect / Hermit proposals | 0 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
