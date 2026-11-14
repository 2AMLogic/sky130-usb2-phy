# `signoff/` — the machine-graded T1 verdict of record

This directory is this block's **verdict of record** for its gap to T1
("sim-validated", the
[klayout-tools design-evidence ladder](https://github.com/2AMLogic/klayout-tools/blob/main/docs/design-evidence-tiers.md))
— the state the [#23 tracker](https://github.com/2AMLogic/sky130-usb2-phy/issues/23)
used to hand-carry as a checkbox list. That hand-read (last taken 2026-08-15,
issue #29) was written against the **ten-item checklist that no longer
exists**: the checklist grew an eleventh item on 2026-09-17
([klayout-tools#2025](https://github.com/2AMLogic/klayout-tools/issues/2025)),
which invalidated every prior hand-read in the fleet at a stroke. A manifest
cannot rot that way: "what is this block's T1 state" is now answered by
re-running a grader, not by re-reading prose.

| File | What it is |
|---|---|
| [`block-manifest.json`](block-manifest.json) | **The claim.** This block's declared `kind` and, per T1 item, the evidence envelope cited behind it, each pinned to a `content_hash`. This is the file the fleet roll-up (2AMLogic/2am#956) consumes. |
| [`signoff-report.json`](signoff-report.json) | **The verdict.** The committed `klt signoff --manifest block-manifest.json --format json` output — byte-for-byte what the grader emitted. Regenerate with `python3 signoff/check.py --regen`. |
| [`evidence/`](evidence/) | Hand-rolled **generic evidence envelopes** — the opt-in wrapper for a record no `klt` verb produces. Item 8's wraps `docs/characterization.md`; items 9 and 10's are **artifact-anchored** (klayout-tools#2718): each declares `"t1_item"` and pins its inventory by path and content hash. |
| [`inventory/`](inventory/) | Plain, versioned **inventories** the anchored envelopes bind: `item-9-testbenches.json`, `item-10-hygiene.json`, `item-2-analog-layout.json`, `item-1-digital-sources.json` and `item-1-analog-sources.json` (the `--attest` schema, cited as `1.digital` / `1.analog` — see item 1 below). Items 9 and 10 list each file with its sha256 and `check.py` re-hashes them all; item 1's hashes live in its `--attest` envelope, which `check.py` re-hashes against. Items 9/10 are hand-rolled over their inventories until a later re-pin can run `--attest` over them. |
| [`tests/`](tests/) | Negative controls for the above (`python3 -m pytest signoff/tests`). |
| [`check.py`](check.py) | **The gate.** What CI runs on every PR and push: it re-grades the manifest and fails on any drift between what is committed and what the current tree actually grades to (see "What the grader cannot check" below). |
| [`spec/`](spec/) | `digital-rows.json`: the ratified digital-partition rows of `spec/usb2-phy.md`, machine-readable, with the markdown's content hash (item 6 digital). `analog-statistical-rows.json`: the four statistical analog rows (`6-06`, `6-09`, `6-11`, `6-14`, numbered by position in the section 6 table), same hash binding (item 6 analog). |
| [`toolchain.json`](toolchain.json) | The `klt` build that grades this block, pinned — and why that pin is the *released registry wheel*. |

Checklist: `klayout-tools/docs/design-evidence-tiers.md`.
Grader contract: `klayout-tools/docs/cli/signoff.md`.

## Block kind: `mixed-signal`

Confirmed against the block, not assumed from the filing issue: this repo is
a USB 2.0 PHY — a **digital UTMI-layer datapath plus an analog front end**
(`CLAUDE.md`, `spec/architecture.md`). A `mixed-signal` manifest renders the
checklist per partition, so the partition boundary is stated explicitly:

- **Digital partition** — everything in `rtl/`: the UTMI-layer receive and
  transmit paths (oversampled bit/edge synchronization, NRZI encode/decode,
  bit (de)stuffing, framing, and the CDC crossing into the UTMI clock
  domain), i.e. `rtl/usb_rx_path.v`, `rtl/usb_tx_serializer.v`,
  `rtl/usb_utmi_top.v` and their submodules, verified by the cocotb suites
  in [`verification/`](../verification/README.md).
- **Analog partition** — the FS line driver, differential and single-ended
  receivers, and D+ pull-up/termination, which are **ported into this repo
  from `gf180-usb2-phy`** (operator ruling 2026-10-08 on
  [#40](https://github.com/2AMLogic/sky130-usb2-phy/issues/40); plan in
  [`docs/porting-plan.md`](../docs/porting-plan.md), port issues #109 to
  #113), plus the PLL, which is consumed by pinned reference to
  `sky130-pll` and never designed here. All four block ports are merged, so
  the partition has committed content: [`design/`](../design/README.md) holds
  the five leaf schematics and their derived netlists,
  [`sim/`](../sim/README.md) holds the deterministic PVT-corner and Monte
  Carlo records behind them, and [`layout/analog/`](../layout/analog/) holds
  the five leaf GDS with their generators. `measurements/` is still empty and
  stays that way until tape-out. What does **not** exist yet is a
  placed-and-routed `usb_utmi_top`, any parasitic extraction on any leaf
  (#281), and an item 5 corner-envelope citation (#280) — see the item 5 and
  item 7 rows below.

`klt 0.8.0` (whose bundled checklist carries all 11 items, so no vendored copy is needed) renders **both columns for every T1 item** for a `mixed-signal`
manifest (even the kind-independent ones render twice, once per partition):
`t1_item_count` is 22, not 11.

## The current verdict: 9 of 22 rows met, 1 `not_applicable`

**9 `met`, 1 `not_applicable`, 22 rows, `tier: null`** — read on 2026-11-14
from [`signoff-report.json`](signoff-report.json)'s own `t1_met_count`,
`t1_not_applicable_count`, `t1_item_count` and `tier`, as graded by the
pinned klt 0.8.0 released wheel ([`toolchain.json`](toolchain.json)). Those
are a snapshot of one grader run, not a standing fact: re-read them from the
report rather than from this sentence, and treat a grader re-pin (#278) as
invalidating the date stamp above rather than trusting the numbers.

Every per-item verdict below is likewise read from the report, not
hand-derived. A mostly-`unmet` mechanical reading is the desired outcome, not
a disappointment — but the reason has moved on. This block's own
characterization ([`docs/characterization.md`](../docs/characterization.md),
headline as read 2026-11-14) states that **nine of the 16 spec rows of
`spec/usb2-phy.md` §6 have a committed PASS record at schematic level
(§6-04…§6-11 and §6-14), and none has post-layout evidence**; seven rows
read `NO EVIDENCE`. So the rows that stay grey below stay grey because the
evidence is schematic-level, uncited, or of a kind the item does not accept —
not because the analog partition is empty. A grader that painted the physical
items green off schematic-level records would be lying.

| Item (partition) | Verdict | Why — and what would change it |
|---|---|---|
| 1 — Design sources (analog) | **`met`** | Cites [`evidence/item-1-analog-sources.json`](evidence/item-1-analog-sources.json) under `"1.analog"`: an artifact-anchored envelope produced by `klt signoff --attest 1` (klt 0.8.0) over [`inventory/item-1-analog-sources.json`](inventory/item-1-analog-sources.json) — the five leaf schematics `design/{differential_driver,differential_receiver,dplus_pullup,se_receiver_dm,se_receiver_dp}.sch` and their five derived `design/netlist/*.spice`, each netlist with a freshness check, [`design/check_netlist.py`](../design/check_netlist.py) (15/15 checks passed). **Disclosed, not omitted:** it asserts the sources exist and the netlists match a fresh `klt netlist --block` export; it does **not** assert any analog spec row is met. `klt netlist --check` alone reports all five netlists drifted (the committed files carry `design/export_netlist.sh`'s header, real `.subckt` wrapper, repo-relative `sch_path`, and different `+` line wrapping), so the checker normalises exactly those and compares everything else; a one-character edit to a netlist fails it (tested). Like the digital check it is `local_only` (needs xschem and the pinned PDK) and `check.py` re-hashes the envelope's files instead. **Not in the partition's in-tree sources:** the PLL (pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) — if the grader's analog partition later requires either, this row is the one that changes. Refresh after a schematic change: `design/export_netlist.sh <cell>` where xschem is permitted, then `uvx --from "klayout-tools==0.8.0" klt signoff --attest 1 --inventory signoff/inventory/item-1-analog-sources.json -o signoff/evidence/item-1-analog-sources.json`, update the manifest pin, `python3 signoff/check.py --regen`. |
| 1 — Design sources (digital) | **`met`** | Cites [`evidence/item-1-digital-sources.json`](evidence/item-1-digital-sources.json) under the partition-qualified key `"1.digital"`: an artifact-anchored envelope produced by `klt signoff --attest 1` (klt 0.8.0) over [`inventory/item-1-digital-sources.json`](inventory/item-1-digital-sources.json) — the 12 `rtl/usb_*.v` files and the synthesis request (each recorded by content hash in the envelope), plus the derived `design/netlist/usb_utmi_top.v` with its declared freshness check, `klt synthesize flow/request-synth-usb_utmi_top.json --pdk sky130A --check <newest synthesize-report.json>`. **Disclosed, not omitted:** this asserts the sources exist, are current, and that the netlist's freshness check passed. It does **not** assert any spec row is met or that synthesis is timing-clean. Cheap-mode `--check` re-hashes the request's RTL and the liberty against the report's recorded provenance; per its help text it does not open the netlist file itself, so a hand-edited netlist would not fail it (not tested); `--rerun` (full mode, re-runs Yosys) is the stronger check and was not run. The freshness command is `local_only` (needs the PDK), so `check.py` (grader 0.7.0, which lacks `--attest`) re-hashes the envelope's recorded files instead and does not re-run it. Refresh after any RTL change: `uvx --from "klayout-tools==0.8.0" klt signoff --attest 1 --inventory signoff/inventory/item-1-digital-sources.json -o signoff/evidence/item-1-digital-sources.json`, then `python3 signoff/check.py --regen`. |
| 2 — Layout (analog) | **`met`** | Cites [`evidence/item-2-analog-layout.json`](evidence/item-2-analog-layout.json) under `"2.analog"`: an artifact-anchored generic envelope (`t1_item: 2`) pinning [`inventory/item-2-analog-layout.json`](inventory/item-2-analog-layout.json), which lists the committed GDS of each leaf (`differential_driver`, `differential_receiver`, `dplus_pullup`, `se_receiver_dm`, `se_receiver_dp`) and its generator `layout/analog/<leaf>/gen.py`, each with its sha256. This is the only form klt 0.8.0 accepts for a set of layouts: item 2 takes one citation, and a list of native envelopes is `invalid_evidence`. **Disclosed, not omitted:** it asserts the streams and generators are committed and current; the *reproducibly generated* half rests on each leaf's `flow/analog-layout-<leaf>/records/` entry (`reproducibility.regenerated_identical: true`), which the tool does not re-run (the envelope carries no regeneration claim). **Not in the partition's in-tree layout:** the PLL (a pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) have no layout here, and neither is cited. Items 3, 4 and 11 below cover the five leaves only, not a placed-and-routed PHY top. `check.py` re-hashes every listed file, so a one-byte GDS change fails the gate. |
| 2 — Layout (digital) | `unmet` / `no_evidence` | `layout/utmi_stub.gds` is the stub's output, not the block's; nothing to cite for the real datapath until it is routed. |
| 3 — DRC clean (analog) | `unmet` / `invalid_evidence` | The manifest cites, under `"3.analog"`, the `drc-report.json` of the latest frozen record of each leaf (`flow/analog-layout-<leaf>/artifacts/<record>/`): all five read `status: clean`, `violation_count: 0`, deck `sky130`. **As graded by klt 0.8.0 the item is `unmet`:** the grader accepts one native envelope for item 3 and renders a list of five `invalid_evidence` (probe: citing a single leaf's report alone grades `met`, but one leaf is not the partition, so that is deliberately not committed). The reason is the grader's shape, not a DRC finding; the gap is filed upstream as klayout-tools#5044. **Coverage gaps are the envelopes' own and are not hidden by `clean`:** each report's `coverage` block lists layers in the stream without rules (e.g. `66/13`, `68/5`, `70/5` for `se_receiver_dm`), skipped rules and unmodeled deck rules; read them in the cited reports. **Not in the partition's in-tree layout:** the PLL (a pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) have no layout here, and neither is cited. Items 3, 4 and 11 below cover the five leaves only, not a placed-and-routed PHY top. `check.py` re-hashes each cited leaf GDS against the envelope's recorded `content_hash`. |
| 3 — DRC clean (digital) | `unmet` / `no_evidence` | The only committed `klt drc` envelopes for the digital side are the smoke-utmi_stub sweep's six (`flow/smoke-utmi_stub/artifacts/*/drc-report.json`) — real evidence about the *toolchain*, explicitly **not** about the block, so they are deliberately uncited. What changes this: a DRC report against the real UTMI layout when it exists. |
| 4 — LVS clean (analog) | `unmet` / `invalid_evidence` | The manifest cites, under `"4.analog"`, the `lvs-report.json` of the latest frozen record of each leaf: all five read `status: match` (engine `klayout-runset`, reference a SPICE netlist: `design/netlist/<leaf>.spice`, and for `differential_driver` `layout/analog/differential_driver/lvs-reference.spice`). **As graded by klt 0.8.0 the item is `unmet`:** again one native envelope per item, so a list of five is `invalid_evidence`. Probing a single leaf (`differential_driver`) shows the next blocker, `runset_unrecognised_device`: the sky130 runset declares device classes (`sky130_fd_pr__cap_var_hvt`, `…cap_var_lvt`, `sky130_fd_bs_flash__special_sonosfet_star`) that no layout device uses, which the grader refuses. **Disclosed:** every report's `power_connectivity.status` is `unchecked` (the extracted netlist carries no instance-level power pins), so LVS says nothing about power connectivity. `check.py` re-hashes each cited leaf GDS and LVS reference netlist against the hashes the envelope recorded. |
| 4 — LVS clean (digital) | `unmet` / `no_evidence` | Same shape as the digital half of item 3: six stub LVS reports exist (`…/lvs-report.json`), none of which anchor a design claim. (They also carry the disclosed VGND↔TXREADY correspondence artifact, #66/#69 — one more reason not to paint the block's row green with them.) |
| 5 — Full corner verification (analog) | `unmet` / `no_evidence` | **Not "nothing exists" — nothing is *cited*.** The five analog leaves carry committed deterministic corner records: the 45-point MOS PVT matrix (process {tt, ff, ss, fs, sf} x temperature {-40, 27, 100} C x supply {3.0, 3.3, 3.6} V) and the supplemental 225-point resistor/capacitor-set matrix, under [`sim/`](../sim/README.md) and indexed per spec row in [`docs/characterization.md`](../docs/characterization.md). The manifest cites none of them under a `"5.analog"` key (verified against `block-manifest.json`'s `evidence` keys, 2026-11-14), so `no_evidence` is the grader reading the manifest correctly, not a statement about the tree. **What would change it:** #280 — declare the analog row set for item 5 and cite the committed `klt sim` corner envelopes, the same shape item 6 already uses for its statistical rows. **A citation must not cherry-pick:** two of those sweeps are *complete failures*, not gaps — `driver-static` resistor-set record `20261010-070333-23e660b` is 198/225 (68 problems at 27 points, the 28–44 ohm output-resistance row violated both sides) and `driver-signal-quality` record `20261016-184100-59ec9c0` is 223/225 (4 problems at 2 points, crossover above the 2.0 V maximum), both per [`sim/README.md`](../sim/README.md). They are carried as failing rows or not cited at all. |
| 5 — Full corner verification (digital) | `unmet` / `no_evidence` | The cocotb suites (`verification/test_usb_*.py`) are bit-exact **pre-layout functional** verification, run at a single nominal zero-delay model — no multi-corner STA has ever run on the real RTL; the only six-corner `klt sta` reports in the tree are the stub's. Item 5 asks for the corner matrix against a ratified spec; when the real datapath is synthesized and timed across the six committed corners (`spec/decision-records/0001-…`, mirrored in `flow/corners.json`), cite the `klt sta` and `klt functional-verification` envelopes here. What exists today is honestly *less* than the row requires, so the row stays grey. |
| 6 — Monte Carlo evidence (analog) | `unmet` / `negative_control_not_detected` | **The analog partition has statistical spec rows**, named in `spec/usb2-phy.md` section 6: *Differential input sensitivity* (|(D+) − (D−)| > 200 mV; offset-limited) and *Single-ended receiver thresholds* (VIH > 2.0 V, VIL < 0.8 V; `docs/porting-plan.md` states it as a threshold window under mismatch). Their Monte Carlo evidence is committed: local-mismatch campaigns with a recorded seed (166) and sample count (n = 400 per corner), a deterministic negative control, at `tt` and at the binding corner of the 45-point records, graded by `klt yield` (`sample_size.verdict` other than `insufficient` is required by the record lint). See [`sim/diff-receiver-mismatch/`](../sim/diff-receiver-mismatch/records/) and [`sim/se-receiver-mismatch/`](../sim/se-receiver-mismatch/records/) and the "diff-receiver-mismatch, se-receiver-mismatch" section of [`sim/README.md`](../sim/README.md). **Still `unmet` as graded, now with a row-coverage answer instead of `no_evidence`:** the manifest declares `spec_rows."6.analog"` = `6-06`, `6-09`, `6-11`, `6-14` (from `spec/analog-statistical-rows.json`, which `check.py` re-hashes against the spec) and cites the six committed `*.yield.json` reports, the diff-receiver ones against `6-09` and the single-ended ones against `6-11`. klt 0.8.0 refuses all six with `negative_control_not_detected` (`failed_rows` = `6-09`, `6-11`): the reports carry a control that is not detected by construction on the `rxd_p200_*` / `rxd_low_max_v` measurements (their records say it is expected and not graded) and 0.8.0 grades every control in a cited report. `uncovered_rows` = `6-06`, `6-14`, which need their own campaigns (#223). The reports are append-only and are cited as committed; the item reads `met` only once every declared row is covered by a passing citation. The D+ pull-up trim now has its own Monte Carlo record (record `20261029-123112-2573ff3`, PASS, at [`sim/dplus-pullup-mismatch/`](../sim/dplus-pullup-mismatch/records/); MOS mismatch from the PDK plus an assumed ladder-resistor spread, since the pinned PDK has no mismatch model for `res_generic_po`) and is **still uncited** — verified 2026-11-14 against `block-manifest.json`'s `evidence."6.analog"`, which lists the six receiver reports above and nothing else. It measures the `1.5 kohm ±5 %` pull-up, i.e. row `6-14`, so the open issue that would cite it is **#223** (which owns both uncovered rows). Not #224: that issue declared the row set and landed the six citations above, and closed 2026-10-28, one day before this record was committed. **Not covered, and not claimed:** the driver's rise/fall matching and crossover mismatch campaign (`sim/driver-matching-mismatch/`, declared, not yet run), and any corner x mismatch combination beyond the two corners each record names. |
| 6 — Monte Carlo evidence (digital) | `not_applicable` | The ratified spec's digital-partition rows are bit-exact protocol rows, structural declarations or corner-bounded timing rows; none is statistical. [`spec/digital-rows.json`](spec/digital-rows.json) lists the 10 rows (spec sections 2 to 6) with the hash of `spec/usb2-phy.md` they were read from, and [`evidence/item-6-digital-not-applicable.json`](evidence/item-6-digital-not-applicable.json) gives each row's class and reason. Both are cited as `"6.digital"` `not_applicable` evidence (klayout-tools#2865), never `met`, and `check.py` re-hashes the markdown, so editing the spec fails the gate until the rows are re-accounted. **Excluded, with reasons in the rows file:** every row owned by the analog partition or the PLL, including the PLL output jitter (a random-process bound, so it is *not* a digital row and sits with the analog partition under #40), the 3.3 V I/O rail, and all driver, receiver, squelch, pull-up and pull-down electrical rows. |
| 7 — Post-layout verification (analog) | `unmet` / `no_evidence` | Analog layout **does** exist: five leaf GDS, cited under `"2.analog"`, with clean DRC (`status: clean`, 0 violations), matching LVS (`status: match`) and `clean_partial` ERC records behind items 2, 3, 4 and 11 above. What does not exist is any **post-layout** artifact — no `klt pex` report and no post-extraction re-simulation on any leaf (verified 2026-11-14: no `pex` file is tracked anywhere in the tree) — so there is nothing of the kind this item accepts to cite, and `no_evidence` is honest. Every analog *result* in the repo is schematic-level, which is also what [`docs/characterization.md`](../docs/characterization.md)'s headline says. **What would change it:** #281 — the first `klt pex` run on the `differential_receiver` leaf, then a citable `pex` envelope, per item 7's own kind restriction. |
| 7 — Post-layout verification (digital) | `unmet` / `no_evidence` | The only post-layout functional record in the tree (`20260919-001148-0f7636d-…`) re-verifies the *stub* against its post-PDN netlist — `design.anchors_design_claim: false`. Item 7 for the real datapath needs an SDF-annotated `klt functional-verification` run over its (not-yet-existing) post-route netlist, or a `klt pex` report — and a citable `pex` envelope, per item 7's own kind restriction. |
| 8 — Characterization report (both) | **`met`** | Cites [`evidence/characterization-report.json`](evidence/characterization-report.json) — a hand-rolled `kind: generic` envelope (the one item this wrapper shape is allowed to satisfy) wrapping the committed, current [`docs/characterization.md`](../docs/characterization.md), with the envelope's `provenance.input.content_hash` pinning that file (sha256 `55242b39…`) and the manifest citing the same pin. Both partition rows read from the one bare `"8"` key (the doc's mixed-signal guidance: one citation, both partitions' rows). **Disclosed, not omitted:** the characterization report's own headline (as read 2026-11-14) is that nine of the 16 spec rows have a committed PASS record **at schematic level** (§6-04…§6-11 and §6-14) and that none has post-layout evidence, with seven rows reading `NO EVIDENCE` — so its per-row content is a mix of honest schematic-level results and honest `NO EVIDENCE` verdicts, not measured silicon. The envelope asserts the item 8 *artifact* exists, is committed and current — it does **not** assert that any spec row is characterized, measured, or passing, and item 8 reading `met` says nothing about the physical items above. |
| 9 — Testbenches shipped (both) | **`met`** | Cites [`evidence/item-9-testbenches.json`](evidence/item-9-testbenches.json), an artifact-anchored generic envelope (`t1_item: 9`) pinning [`inventory/item-9-testbenches.json`](inventory/item-9-testbenches.json): every suite in `verification/` (6 cocotb suites with their `klt functional-verification` requests, plus the pytest protocol model) and every analog testbench under `sim/*/testbench/` (9), each with the cold-start invocation from [`verification/README.md`](../verification/README.md) or [`sim/README.md`](../sim/README.md) and the pinned PDK revision (`docs/baseline.md`). **Disclosed, not omitted:** this asserts the testbenches are committed, inventoried and current — it does **not** assert that any of them passes; the pass/fail record is the CI `check-ci` job and the `sim/` records. The grader re-hashes the inventory only; `check.py` re-hashes every listed file and fails if a `verification/test_*.py`, `verification/request-*.json` or `sim/*/testbench/` file is not listed. |
| 10 — Repo hygiene (both) | **`met`** | Cites [`evidence/item-10-hygiene.json`](evidence/item-10-hygiene.json), an artifact-anchored generic envelope (`t1_item: 10`) pinning [`inventory/item-10-hygiene.json`](inventory/item-10-hygiene.json): `README.md` (block statement, spec table, reproduction), the Apache-2.0 `LICENSE`, `.github/workflows/ci.yml`, and the CI commands that keep the harness and evidence formats valid (`npm run check:ci`, `npm run lint`, `python3 signoff/check.py`). The same disclosure as item 9 applies: it attests the artifacts exist and are current, not that CI is green. Because the README and the workflow are inventoried, editing either needs `python3 signoff/check.py --regen`. |
| 11 — Power delivery, structural (analog) | `unmet` / `lvs_did_not_pass` | Cites, under `"11.analog"`, each leaf's `erc-supply-report.json` plus its `lvs-report.json` (item 4's). All five ERC reports read `status: clean_partial`, `erc_status: clean` (the supply nets `VDD`/`VSS` each resolve to one island). **As graded the item is `unmet`:** it is gated on item 4 passing, and the grader reports `lvs_did_not_pass` with `power_delivery`: `supply_nets` `[VDD, VSS]`, `lvs_status: match`, `power_connectivity_status: unchecked`. It reads `met` only once item 4 does. The ERC half is partial by its own status (`clean_partial`: antenna levels are `pass_partial`); it is not a full antenna signoff. **Not in the partition's in-tree layout:** the PLL (a pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) have no layout here, and neither is cited. Items 3, 4 and 11 below cover the five leaves only, not a placed-and-routed PHY top. `check.py` re-hashes the leaf GDS and LVS reference netlist behind each cited envelope. |
| 11 — Power delivery, structural (digital) | `unmet` / `no_evidence` | Same row, digital partition: needs the `place-and-route` + `erc` + `lvs` citation chain over a genuinely-routed real datapath (`power.pdn: true`, `power_connectivity.status: "match"`), none of which exists for the block. |

**What is uncited, read off the manifest and not off this prose.** `jq -r
'.evidence | keys[]' signoff/block-manifest.json` (2026-11-14) returns
`1.analog`, `1.digital`, `2.analog`, `3.analog`, `4.analog`, `6.analog`,
`6.digital`, `8`, `9`, `10`, `11.analog` — so 8 of the 22 rows carry no
citation at all, in two groups:

- **The digital halves of items 2, 3, 4 and 11** — uncited by deliberate
  choice. The only envelopes that exist for them describe the
  `smoke-utmi_stub` experiment, which by its own convention
  (`design.anchors_design_claim: false`) anchors no design claim, so citing
  them would paint the block's rows with the toolchain's result. What changes
  them is a genuinely placed-and-routed `usb_utmi_top`.
- **Both halves of items 5 and 7** — see those rows above. On the analog side
  the artifacts exist but are either not cited (#280) or not of the kind the
  item accepts (#281); on the digital side neither the corner matrix nor a
  post-route netlist exists yet.

An uncited row is the honest machine-readable statement — *no check backs
this claim* — which is what `klt signoff` renders, with a `reason`, instead
of guessing. **Uncited is not the only route to `unmet`:** items 3, 4 and 11
(analog) are *cited and still `unmet`*, on the grader's one-envelope-per-item
shape and on item 4's gating of item 11 — not on a missing artifact. Read
each row's `reason` rather than inferring one from this list.

**9 of 22 is a different number from the #29 hand-read's "1/10 pass (1 N/A)", and
both are honest reads of different questions.** The hand-read asked "does
this repo contain the artifact the item describes?" — and for item 9 it
does. The manifest asks "is there a passing, fresh, machine-readable
envelope of the kind this item accepts?" — and the second question is the one
a downstream consumer (or the fleet roll-up) can actually verify without
taking this repo's word for it. Where this README and `signoff-report.json`
disagree, the report wins and this prose is the thing that is wrong.

## What the grader cannot check

`klt signoff` compares a citation's manifest pin against *the envelope's own
recorded hash*; it never re-opens the underlying artifact, so two
hand-written hashes agreeing with each other proves nothing. For the generic
wrappers that are the only citations today, `check.py` closes that hole
itself: it re-hashes `docs/characterization.md` (item 8) and every file the
items-9, 10 and 1 inventories list, and fails if a pin has drifted (negative
controls in [`tests/`](tests/): mutating an inventoried file fails the gate,
and moving a bound inventory without re-pinning grades `stale_evidence`).
Two more gaps are deliberate disclosures rather than silent assumptions:

- **Native-citation re-hashing (closed).** `check_native_citations` re-hashes
  the *input artifacts* behind the native `klt drc`/`lvs`/`erc` envelopes cited
  for items 3, 4 and 11 -- each leaf GDS (all three kinds) and each LVS
  reference netlist -- against the hashes the envelope recorded, and requires
  every leaf to be cited once, from its latest `records/` entry. `klt` through
  0.8.0 does not do this itself (upstream: klayout-tools#2196). Negative
  controls in [`tests/`](tests/): a one-byte GDS change or an edited reference
  netlist fails the gate.
- **The grading build's identity.** `check.py` hard-fails unless the `klt`
  on PATH is the pinned *released registry wheel* (`git_tag v0.8.0`,
  `is_release: true`), because same-version git snapshots have been
  observed to grade differently (klayout-tools#2216). This is why the CI
  job `pip install`s the pin instead of trusting whatever `klt` a runner
  has.

## How to re-run the grading

`klt signoff --manifest` is PDK-free — it grades committed JSON envelopes,
it does not run the gates — so grading runs anywhere:

```bash
pip install klayout-tools==0.8.0          # the pinned released wheel
python3 signoff/check.py                  # the gate: re-grade + drift check
python3 signoff/check.py --regen          # refresh pins + rewrite the report
```

CI (`signoff` job in `.github/workflows/ci.yml`) runs the gate on every PR
and push and requires the committed `signoff-report.json` to match what the
current tree grades to — so a citation whose underlying artifact has since
changed (today: `docs/characterization.md`) fails CI instead of silently
rotting. The fix is always the same one-liner — `python3 signoff/check.py
--regen` — **after** re-reading what changed and updating the envelope's
summary and this README's disclosed verdict if the content moved; the prose
and the report are one artifact, not two.
