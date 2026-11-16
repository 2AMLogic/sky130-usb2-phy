# Work Plan

Prioritized roadmap generated automatically by the Guide triage agent from
current GitHub label state. Everything between the markers below is
machine-generated and is overwritten wholesale on each update; nothing
outside the markers is touched by automation.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#330**: chore(loom): resync installed Loom to v0.19.1302

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#132**: Worker klt tool venv still lacks cocotb_tools: pre-PR gate cannot pass on fleet hosts (recurrence of #94)

## Important

`loom:important`; taken before unlabelled work.

- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates
- **#270**: signoff item-10 README pin goes stale on every automated Guide README edit (3rd recurrence of #180/#181)
- **#278**: Re-pin the signoff grader from klt 0.8.0 to the 0.9.1 release and regrade

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#274**: Deduplicate analog device geometry: differential_driver/gen.py keeps a second copy of gen_common's Ports and mos
- **#295**: Remove four dead module-level symbols that each shadow a fact the live code re-states inline
- **#313**: signoff/README.md item 6 overstates the record lint: 'sample_size.verdict other than insufficient is required' holds only for PASS records
- **#319**: Remove two dead module-level symbols in hash-pinned files: record_kind() and INVENTORY_DIR (carries the item-10 re-pin)
- **#326**: DR 0008: add sim/README.md to the 'prose that must move with the value' list (and clarify the 'two of four corners' parenthetical)
- **#329**: stored_coverage's clause check couples a landed record's lint verdict to later testbench/mc.json edits
- **#331**: T1 item 6 (analog): cite the driver-matching and D+ pull-up klt yield reports in the manifest (6-06, 6-14)
- **#335**: signoff/README.md item 8 row still paraphrases characterization's old 'zero spec rows' headline

## In Progress

Issues currently being built (`loom:building`).

- **#275**: Deduplicate the raw-mode / byte-stream reference helpers duplicated across two TX testbenches
- **#336**: Fold differential_receiver/gen.py build() into the shared receiver generator (~100 duplicated lines)
- **#338**: signoff: the throwaway-grader-venv recipe makes `npm run check:all`'s pytest leg unrunnable

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#330**: chore(loom): resync installed Loom to v0.19.1302

## Proposed

Issues carrying `loom:curated`.

- **#86**: README: embed the fleet burndown chart (one line) *(curated)*
- **#116**: Real UTMI physical flow: add stage 2–6 driver and request templates *(curated)*
- **#270**: signoff item-10 README pin goes stale on every automated Guide README edit (3rd recurrence of #180/#181) *(curated)*
- **#274**: Deduplicate analog device geometry: differential_driver/gen.py keeps a second copy of gen_common's Ports and mos *(curated)*
- **#278**: Re-pin the signoff grader from klt 0.8.0 to the 0.9.1 release and regrade *(curated)*
- **#295**: Remove four dead module-level symbols that each shadow a fact the live code re-states inline *(curated)*
- **#313**: signoff/README.md item 6 overstates the record lint: 'sample_size.verdict other than insufficient is required' holds only for PASS records *(curated)*
- **#319**: Remove two dead module-level symbols in hash-pinned files: record_kind() and INVENTORY_DIR (carries the item-10 re-pin) *(curated)*
- **#326**: DR 0008: add sim/README.md to the 'prose that must move with the value' list (and clarify the 'two of four corners' parenthetical) *(curated)*
- **#329**: stored_coverage's clause check couples a landed record's lint verdict to later testbench/mc.json edits *(curated)*
- **#331**: T1 item 6 (analog): cite the driver-matching and D+ pull-up klt yield reports in the manifest (6-06, 6-14) *(curated)*
- **#335**: signoff/README.md item 8 row still paraphrases characterization's old 'zero spec rows' headline *(curated)*
- **#338**: signoff: the throwaway-grader-venv recipe makes `npm run check:all`'s pytest leg unrunnable *(curated)*

## Proposed (Architect / Hermit)

- **#339**: Deduplicate analog layout generators: conflicts() and net-routing loop copied into three gen files *(hermit)*
- **#344**: Deduplicate the run-manifest literal in sim/tests render_record tests (four hand-written copies) *(hermit)*

## Epics

- **#23**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#105**: Digital T1 items 3, 4, 11 (and 5): place and route the real UTMI datapath and commit DRC, LVS, ERC and timing evidence

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 8 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 13 |
| Architect / Hermit proposals | 2 |
| Active epics | 2 |
<!-- guide:plan-body:end -->
