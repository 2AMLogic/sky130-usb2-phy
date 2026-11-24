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
| [`tests/`](tests/) | Negative controls for the above, and the per-leaf exact-equality pin on `find_row_x`'s chosen PMOS-row offset (issue #434) (`python3 -m pytest signoff/tests`; the pin needs `klayout.db`, so it runs in the signoff CI job and skips elsewhere). |
| [`check.py`](check.py) | **The gate.** What CI runs on every PR and push: it re-grades the manifest and fails on any drift between what is committed and what the current tree actually grades to (see "What the grader cannot check" below). |
| [`spec/`](spec/) | `digital-rows.json`: the ratified digital-partition rows of `spec/usb2-phy.md`, machine-readable, with the markdown's content hash (item 6 digital). `analog-statistical-rows.json`: the four statistical analog rows (`6-06`, `6-09`, `6-11`, `6-14`, numbered by position in the section 6 table), same hash binding (item 6 analog). `analog-rows.json`: all sixteen analog-partition rows of section 6, same hash binding (item 5 analog). |
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
  the five leaf GDS with their generators. `measurements/` holds only its
  README until tape-out. What does **not** exist yet is a placed-and-routed
  `usb_utmi_top`, post-layout verification of four of the five leaves (#281
  covered the differential receiver only), and an item 5 citation whose
  envelopes carry `limits` (#280's cited records grade `no_limits_checked`)
  — see the item 5 and item 7 rows below.

`klt 0.9.2` (whose bundled checklist carries all 11 items, so no vendored copy is needed) renders **both columns for every T1 item** for a `mixed-signal`
manifest (even the kind-independent ones render twice, once per partition):
`t1_item_count` is 22, not 11.

## The current verdict: 11 of 22 rows met, 1 `not_applicable`

**11 `met`, 1 `not_applicable`, 22 rows, `tier: null`** — read on 2026-11-22
from [`signoff-report.json`](signoff-report.json)'s own `t1_met_count`,
`t1_not_applicable_count`, `t1_item_count` and `tier`, as graded by the
pinned klt 0.9.2 released wheel ([`toolchain.json`](toolchain.json)). Those
are a snapshot of one grader run, not a standing fact: re-read them from the
report rather than from this sentence, and treat a grader re-pin (#278, #399)
as invalidating the date stamp above rather than trusting the numbers.

Every per-item verdict below is likewise read from the report, not
hand-derived. A mostly-`unmet` mechanical reading is the desired outcome, not
a disappointment — but the reason has moved on. This block's own
characterization ([`docs/characterization.md`](../docs/characterization.md),
headline as read 2026-11-16) states that **nine of the 16 spec rows of
`spec/usb2-phy.md` §6 have a committed PASS record at schematic level
(§6-04…§6-11 and §6-14), and none has post-layout evidence**; seven rows
read `NO EVIDENCE`. So the rows that stay grey below stay grey because the
evidence is schematic-level, uncited, or of a kind the item does not accept —
not because the analog partition is empty. A grader that painted the physical
items green off schematic-level records would be lying.

| Item (partition) | Verdict | Why — and what would change it |
|---|---|---|
| 1 — Design sources (analog) | **`met`** | Cites [`evidence/item-1-analog-sources.json`](evidence/item-1-analog-sources.json) under `"1.analog"`: an artifact-anchored envelope produced by `klt signoff --attest 1` (klt 0.8.0) over [`inventory/item-1-analog-sources.json`](inventory/item-1-analog-sources.json) — the five leaf schematics `design/{differential_driver,differential_receiver,dplus_pullup,se_receiver_dm,se_receiver_dp}.sch` and their five derived `design/netlist/*.spice`, each netlist with a freshness check, [`design/check_netlist.py`](../design/check_netlist.py) (15/15 checks passed). **Disclosed, not omitted:** it asserts the sources exist and the netlists match a fresh `klt netlist --block` export; it does **not** assert any analog spec row is met. `klt netlist --check` alone reports all five netlists drifted (the committed files carry `design/export_netlist.sh`'s header, real `.subckt` wrapper, repo-relative `sch_path`, and different `+` line wrapping), so the checker normalises exactly those and compares everything else; a one-character edit to a netlist fails it (tested). Like the digital check it is `local_only` (needs xschem and the pinned PDK) and `check.py` re-hashes the envelope's files instead. **Not in the partition's in-tree sources:** the PLL (pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) — if the grader's analog partition later requires either, this row is the one that changes. Refresh after a schematic change: `design/export_netlist.sh <cell>` where xschem is permitted, then `uvx --from "klayout-tools==0.8.0" klt signoff --attest 1 --inventory signoff/inventory/item-1-analog-sources.json -o signoff/evidence/item-1-analog-sources.json`, update the manifest pin, `python3 signoff/check.py --regen` — run that `--regen` only with the pinned grader on `PATH` (the wrapper-dir-on-`PATH` form from [How to re-run the grading](#how-to-re-run-the-grading); a bare `--regen` under the shared `klt` commits the wrong grader's report, and `uvx` alone does not cover it). |
| 1 — Design sources (digital) | **`met`** | Cites [`evidence/item-1-digital-sources.json`](evidence/item-1-digital-sources.json) under the partition-qualified key `"1.digital"`: an artifact-anchored envelope produced by `klt signoff --attest 1` (klt 0.8.0) over [`inventory/item-1-digital-sources.json`](inventory/item-1-digital-sources.json) — the 12 `rtl/usb_*.v` files and the synthesis request (each recorded by content hash in the envelope), plus the derived `design/netlist/usb_utmi_top.v` with its declared freshness check, `klt synthesize flow/request-synth-usb_utmi_top.json --pdk sky130A --check <newest synthesize-report.json>`. **Disclosed, not omitted:** this asserts the sources exist, are current, and that the netlist's freshness check passed. It does **not** assert any spec row is met or that synthesis is timing-clean. Cheap-mode `--check` re-hashes the request's RTL and the liberty against the report's recorded provenance; per its help text it does not open the netlist file itself, so a hand-edited netlist would not fail it (not tested); `--rerun` (full mode, re-runs Yosys) is the stronger check and was not run. The freshness command is `local_only` (needs the PDK), so `check.py` (grader 0.7.0, which lacks `--attest`) re-hashes the envelope's recorded files instead and does not re-run it. Refresh after any RTL change: `uvx --from "klayout-tools==0.8.0" klt signoff --attest 1 --inventory signoff/inventory/item-1-digital-sources.json -o signoff/evidence/item-1-digital-sources.json`, then `python3 signoff/check.py --regen` — run that `--regen` only with the pinned grader on `PATH` (the wrapper-dir-on-`PATH` form from [How to re-run the grading](#how-to-re-run-the-grading); a bare `--regen` under the shared `klt` commits the wrong grader's report, and `uvx` alone does not cover it). |
| 2 — Layout (analog) | **`met`** | Cites [`evidence/item-2-analog-layout.json`](evidence/item-2-analog-layout.json) under `"2.analog"`: an artifact-anchored generic envelope (`t1_item: 2`) pinning [`inventory/item-2-analog-layout.json`](inventory/item-2-analog-layout.json), which lists the committed GDS of each leaf (`differential_driver`, `differential_receiver`, `dplus_pullup`, `se_receiver_dm`, `se_receiver_dp`) and its generator `layout/analog/<leaf>/gen.py`, each with its sha256. This is the form used for a set of layouts because, as observed under klt 0.8.0, item 2 takes one citation and a list of native envelopes was `invalid_evidence`; that "only form" claim was not re-probed under 0.9.1 or the pinned 0.9.2 (which take per-cell lists for item 4 — 0.9.2 for item 3 too), so it is a dated 0.8.0 observation, not a standing fact. **Disclosed, not omitted:** it asserts the streams and generators are committed and current; the *reproducibly generated* half rests on each leaf's `flow/analog-layout-<leaf>/records/` entry (`reproducibility.regenerated_identical: true`), which the grader does not re-run (the envelope carries no regeneration claim); the `signoff` job of `.github/workflows/ci.yml` does re-run the check, globbing `layout/analog/*/gen.py --check` under the same pinned grader (issue #363). **Not in the partition's in-tree layout:** the PLL (a pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) have no layout here, and neither is cited. Items 3, 4 and 11 below cover the five leaves only, not a placed-and-routed PHY top. `check.py` re-hashes every listed file, so a one-byte GDS change fails the gate. |
| 2 — Layout (digital) | `unmet` / `no_evidence` | `layout/utmi_stub.gds` is the stub's output, not the block's; nothing to cite for the real datapath until it is routed. |
| 3 — DRC clean (analog) | **`met`** | The manifest cites, under `"3.analog"`, the `drc-report.json` of the latest frozen record of each leaf (`flow/analog-layout-<leaf>/artifacts/<record>/`): all five read `status: clean`, `violation_count: 0`, deck `sky130`. **As graded by klt 0.9.2 (the pinned grader) the item is `met`:** the wheel carries upstream klayout-tools#5044 (per-cell envelope sets for items 2-4, closed 2026-11-06), so the five-citation list grades member-by-member — `members_covered: 5/5`, every citation `met`, `input_verified: true` — where 0.9.1 and earlier accepted one native envelope for item 3 and rendered the same list `invalid_evidence` for its shape (probe then: citing a single leaf's report alone graded `met`, but one leaf is not the partition, so that was deliberately not committed). The 0.9.2 re-pin first passed the previous five reports. The five DRC reports frozen alongside the curated LVS comparisons also pass. **Coverage gaps are the envelopes' own and are not hidden by `met`:** each report's `coverage` block lists layers in the stream without rules (e.g. `66/13`, `68/5`, `70/5` for `se_receiver_dm`), skipped rules and unmodeled deck rules; read them in the cited reports — `met` means five clean runs against the sky130 deck, not that the deck covers every layer drawn. **Not in the partition's in-tree layout:** the PLL (a pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) have no layout here, and neither is cited. Items 3, 4 and 11 below cover the five leaves only, not a placed-and-routed PHY top. `check.py` re-hashes each cited leaf GDS against the envelope's recorded `content_hash`. |
| 3 — DRC clean (digital) | `unmet` / `no_evidence` | The only committed `klt drc` envelopes for the digital side are the smoke-utmi_stub sweep's six (`flow/smoke-utmi_stub/artifacts/*/drc-report.json`) — real evidence about the *toolchain*, explicitly **not** about the block, so they are deliberately uncited. What changes this: a DRC report against the real UTMI layout when it exists. |
| 4 — LVS clean (analog) | **`met`** | The five cited `lvs-curated-report.json` files compare the latest leaf GDS against the original design SPICE, with 5 V MOS flavour, parallel fingers and passive geometry checked. All five leaves match with complete device counts (driver 80/80, differential receiver 11/11, both single-ended receivers 13/13, D+ pull-up 20/20). The #406 repair moved one grid-aligned U-turn in the shared `gen_common.xhigh_resistor` serpentine, so the driver's XRB draws exactly 30.00 µm and each receiver XRBIAS exactly 140.00 µm at the 1.41 µm width (the pre-repair streams extracted 30.01/139.98 µm). The matching PDK runset reports remain frozen alongside the curated reports. [Per-leaf counts and parameter coverage](../layout/analog/README.md#curated-lvs-by-leaf) · [Chip #406](https://github.com/2AMLogic/sky130-usb2-phy/issues/406) |
| 4 — LVS clean (digital) | `unmet` / `no_evidence` | Same shape as the digital half of item 3: six stub LVS reports exist (`…/lvs-report.json`), none of which anchor a design claim. (They also carry the disclosed VGND↔TXREADY correspondence artifact, #66/#69 — one more reason not to paint the block's row green with them.) |
| 5 — Full corner verification (analog) | `unmet` / `no_limits_checked` | **A row-coverage answer, no longer `no_evidence`:** the manifest declares `spec_rows."5.analog"` = all sixteen rows of the spec's section 6 analog table (from [`spec/analog-rows.json`](spec/analog-rows.json), which `check.py` re-hashes against the spec markdown) and cites, per covered row, the newest passing 45-point `klt sim` envelope of each analog testbench: `driver-static` (`6-04`, `6-05`, `6-08`), `driver-signal-quality` (`6-06`, `6-07`), `diff-receiver-sensitivity` (`6-09`, `6-10`), `se-receiver-dp-thresholds` and `se-receiver-dm-thresholds` (`6-11`), `dplus-pullup-tolerance` (`6-14`) — nine rows cited, all **schematic-level** records (each names a `design/netlist/*.spice` netlist; no layout, no parasitics). **Still `unmet` as graded:** every cited request declared its measurements with no `limits` bound (this repo's harness applied the spec bounds afterward, in its own evidence records), and the grader returns `no_limits_checked` for such an envelope — a per-corner `pass` only proves a value was produced, never that a bound was checked — so all nine cited rows sit in `failed_rows`, `uncovered_rows` is empty, and `t1_met_count` is unchanged. **The limit-carrying re-runs have begun (#401 Part A):** `sim/harness/spec_limits.py` now generates `measurements[].limits` in the `klt sim` request from the ratified row table ([`spec/analog-rows.json`](spec/analog-rows.json)); `driver-static` has a new stored 45-point PASS envelope (`sim/driver-static/records/20261120-231636-18ee366.md`, batch job `klt-sim-eaeda7477b78`) whose request carried 20 bounds over rows 6-04 (VOH/VOL) and 6-05 (output resistance), and `driver-signal-quality` has one too (`sim/driver-signal-quality/records/20261122-153200-e260498.md`, batch job `klt-sim-f70d86ecaf42`) whose request carried 20 bounds over rows 6-06 (rise/fall time, rise/fall matching) and 6-07 (crossover voltage), and `diff-receiver-sensitivity` a third (`sim/diff-receiver-sensitivity/records/20261123-010210-c05f5e3.md`, batch job `klt-sim-3f4e30bcb82e`) whose request carried 6 bounds over row 6-09 (the input-referred differential threshold at each of 6-10's three common-mode test conditions, 0.8/1.65/2.5 V; row 6-10 itself carries no number, so it is evidenced by those limits holding at every condition) — with the envelope's per-corner limit verdicts agreeing with the harness cross-check 45/0 per measurement on all three — and the last three benches complete Part A: `se-receiver-dp-thresholds` (`sim/se-receiver-dp-thresholds/records/20261123-021027-1a917d6.md`, batch job `klt-sim-1bee6dd7a9db`) and `se-receiver-dm-thresholds` (`sim/se-receiver-dm-thresholds/records/20261123-021301-1a917d6.md`, batch job `klt-sim-75ddf3c7d56c`) each carry 2 bounds over row 6-11 (the switching threshold inside 0.8-2.0 V, the tb.json strict-endpoint check's own numbers), and `dplus-pullup-tolerance` (`sim/dplus-pullup-tolerance/records/20261123-021530-1a917d6.md`, batch job `klt-sim-7cccd29d10bb`) carries row 6-14's window as two one-sided reachability bounds on the extreme trim codes (`r_c00_ohm` >= 1425 ohm, `r_c15_ohm` <= 1575 ohm, derived as request `expr` measurements so the envelope itself grades them; the bounds say the ladder spans the window — the in-window existential stays the harness trim analysis's, and the record states both) — envelope and harness verdicts agree 45/0 on every mapped measurement of all six, so every section 6 row the manifest covers now has a limit-carrying stored envelope, and Part A is complete. **That evidence exists but is not yet cited, so the verdict does not move:** the new envelopes are store-resident (post-[#194](https://github.com/2AMLogic/sky130-usb2-phy/issues/194) runs commit only their store manifests), and no released klt grades a store-resolved citation — the same blocker as item 6, filed as klayout-tools#5963; the cited file-backed 2026-10-20 envelopes above stay, and flipping the citations is #401 Part B once a released klt takes the store-resolved shape. **Declared gaps (reasons in the manifest):** 6-01/6-02/6-03 — PLL rows, consumed by pinned reference to `sky130-pll`, never designed here (DR-0003 Decision 1); 6-12/6-13 — squelch, no source block exists (DR-0003 Decision 2 pending ratification); 6-15 — downstream port pull-downs, a host-side load (DR-0003 Decision 3 pending ratification); 6-16 — pull-up control interface, a digital-side element (only the analog side of 6-08 is claimed here; the digital side is `signoff/spec/digital-rows.json`'s). The supplemental 225-point resistor-set records are deliberately uncited (DR-0005 unratified, and they carry the same zero-limits shape). |
| 5 — Full corner verification (digital) | `unmet` / `no_evidence` | The cocotb suites (`verification/test_usb_*.py`) are bit-exact **pre-layout functional** verification, run at a single nominal zero-delay model — no multi-corner STA has ever run on the real RTL; the only six-corner `klt sta` reports in the tree are the stub's. Item 5 asks for the corner matrix against a ratified spec; when the real datapath is synthesized and timed across the six committed corners (`spec/decision-records/0001-…`, mirrored in `flow/corners.json`), cite the `klt sta` and `klt functional-verification` envelopes here. What exists today is honestly *less* than the row requires, so the row stays grey. |
| 6 — Monte Carlo evidence (analog) | `unmet` / `partial_coverage` | **The analog partition has statistical spec rows**, named in `spec/usb2-phy.md` section 6: *Differential input sensitivity* (\|(D+) − (D−)\| > 200 mV; offset-limited) and *Single-ended receiver thresholds* (VIH > 2.0 V, VIL < 0.8 V; `docs/porting-plan.md` states it as a threshold window under mismatch). Their Monte Carlo evidence is committed: local-mismatch campaigns with a recorded seed (166) and sample count (n = 400 per corner), a deterministic negative control, at `tt` and at the binding corner of the 45-point records, graded by `klt yield` (the record lint rejects an `insufficient` `sample_size.verdict` only on a PASS record; a FAIL record records it as one of its stated problems). See [`sim/diff-receiver-mismatch/`](../sim/diff-receiver-mismatch/records/) and [`sim/se-receiver-mismatch/`](../sim/se-receiver-mismatch/records/) and the "diff-receiver-mismatch, se-receiver-mismatch" section of [`sim/README.md`](../sim/README.md). **Still `unmet` as graded — `partial_coverage`, no longer refused evidence (moved by #402, 2026-11-20):** the manifest declares `spec_rows."6.analog"` = `6-06`, `6-09`, `6-11`, `6-14` (from `spec/analog-statistical-rows.json`, which `check.py` re-hashes against the spec) and cites six `*.yield.json` reports, the diff-receiver ones against `6-09` and the single-ended ones against `6-11`. Since #402 the citations name the **re-derived** reports of [`evidence/20261120-190153-4bdccc4-item6-rx-not-applicable/`](evidence/20261120-190153-4bdccc4-item6-rx-not-applicable/) (its README is the derivation record): the October campaigns' committed samples, unchanged, with the per-measurement `{"not_applicable": true, "reason": …}` negative-control declaration that [klayout-tools#4523](https://github.com/2AMLogic/klayout-tools/issues/4523) shipped and the pinned 0.9.2 reads — ten measurement instances declare a one-sided defect (the differential `rxd_p200_*`, three per report, where the control's +0.25 V `skew_v` offset adds to the +200 mV stimulus and only raises RXD at VDIFF = +200 mV; and the single-ended `rxd_low_max_v`, where the control's R2 14→60 divider skew raises VREF past VIH and only keeps RXD low over 0–0.8 V), each reason quoting its campaign record's Method section. Every other control is `detected`, and the nominal statistics (n = 400, errored 0, limits, empirical yields and CIs, `sufficient` sample-size verdicts) are the October numbers unchanged; the only moved fields are 0.9.1's renderings of degenerate zero-variance populations. The grader's answer moved accordingly: `failed_rows` is empty — `6-09` and `6-11` no longer fail on `negative_control_not_detected` — and `uncovered_rows` = `6-06`, `6-14`, which no cited report covers (#331 — and, as of 2026-11-16, cannot until the store-citation blocker below clears; the blocker's upstream fix merged 2026-11-20 as [klayout-tools#6550](https://github.com/2AMLogic/klayout-tools/pull/6550) and awaits a release the pin can move to). The October campaign directories and records are append-only, untouched and now uncited; the item reads `met` only once every declared row is covered by a passing citation. The D+ pull-up trim now has its own Monte Carlo record (record `20261029-123112-2573ff3`, PASS, at [`sim/dplus-pullup-mismatch/`](../sim/dplus-pullup-mismatch/records/); MOS mismatch from the PDK plus an assumed ladder-resistor spread, since the pinned PDK has no mismatch model for `res_generic_po`) and is **still uncited** — `block-manifest.json`'s `evidence."6.analog"` lists the six receiver reports above and nothing else (verified 2026-11-20). It measures the `1.5 kohm ±5 %` pull-up, i.e. row `6-14`, one of the two uncovered rows; the item-6 completion work is now tracked under **#331** (cite the driver-matching and D+ pull-up `klt yield` reports against `6-06` / `6-14`; blocked on the grader, see the store-citation blocker below); #223 was closed 2026-11-16 after decomposition into #268 and one issue per corner (#269, #271, #272, #273), all of which have landed — the corners ran, the citation did not. Not #224: that issue declared the row set and landed the six October receiver citations that #402's re-derivation supersedes, and closed 2026-10-28, one day before this record was committed. **All four campaign corners recorded, still nothing claimed:** the driver's rise/fall matching and crossover mismatch campaign has all four corners recorded ([`records/20261115-040553-f76df63.md`](../sim/driver-matching-mismatch/records/20261115-040553-f76df63.md): `tt` PASS — all six graded measurements within their 0.9-1.1 / 1.3-2.0 V limits, controls `detected`, n = 400, seed 166; stored evidence, not yet cited by the manifest; [`records/20261115-064022-f76df63.md`](../sim/driver-matching-mismatch/records/20261115-064022-f76df63.md): `sf40v36` FAIL — mismatch puts 11-13 % of samples' rise/fall ratios above the 1.1 bound, far short of the 0.99 yield target, and the 180 ohm crossover control is `not_detected` at this corner; [`records/20261115-172039-45b6298.md`](../sim/driver-matching-mismatch/records/20261115-172039-45b6298.md): `fs100v36` — match PASS (all four ratios yield 1, control `detected`) and xover FAIL (empirical yield 0.6675 / 0.655 against target 0.99 with the 180 ohm crossover control `not_detected` at 3.6 V; recorded as evidence of failure, per the campaign spec's own footer; n = 400, seed 166; stored evidence); [`records/20261115-141134-38bdad2.md`](../sim/driver-matching-mismatch/records/20261115-141134-38bdad2.md): `fs100v30` FAIL — the mismatch tail of all four rise/fall matching ratios crosses the 0.9 lower bound (3-4 of 400 samples per ratio, worst 0.8755) while both crossover measurements PASS with empirical yield 1; controls `detected`, n = 400, seed 166; stored evidence, not yet cited by the manifest — the deterministic record's thinnest low-side margin 0.9278 does not survive mismatch at this corner), and any corner x mismatch combination beyond the corners each record names. **Why the manifest still cannot cite any of it (verified 2026-11-16):** the store bytes are all intact — `klt artifact verify` is clean under the then-pinned 0.9.1 wheel for the pull-up manifest and all four cited-corner driver manifests — but no released klt grades a store-resolved citation. 0.9.1 and 0.9.2 (both checked directly) take an evidence member either **file-backed** (bytes in git — committing them is rejected by [`manifests/artifacts/README.md`](../manifests/artifacts/README.md)'s store convention) or **command-backed** (executed at grade time, needing a live artifact broker: `klt artifact get MANIFEST#NAME --output -` even documents that use). Command-backed is unusable in a gate whose committed report must be byte-reproducible: CI's ubuntu-latest runner cannot reach the fleet broker, so the same committed manifest would grade `met` on a store-configured host and `check_errored` in CI — the freshness gate would fail whichever report was committed. A member in a shape the grader does not know is worse still: one malformed member flips the whole partition to `invalid_evidence` (observed in the 0.9.1 source: `_parse_multi_members` fails the item on the first unrecognised member), so the citations must wait on the tool, not be forced. The gap is filed upstream as **klayout-tools#5963** (a store-resolved citation shape — committed store manifest + member name, pinned by the manifest's recorded `sha256` of the paired samples entry, verifiable offline). `check.py` already carries that shape (added under #331: `store_yield_samples_pin`, an offline-structural pin through the committed store manifest, with negative controls; committed-report citations behave exactly as before), so once the grader learns it the flip is a follow-up citation + re-pin. The citations to land then, newest manifest per corner as the records name them: driver `match-*`/`xover-*` from `…20261115-040553-f76df63` (tt), `…20261115-064022-f76df63` (sf40v36), `…20261115-141134-38bdad2` (fs100v30) and `…20261115-172039-45b6298` (fs100v36; supersedes `…150101-45b6298`, whose match report is byte-identical, while `…123039-38bdad2` lists no yield reports at all) against `6-06`, and `pu-tt`/`pu-binding` from `dplus-pullup-mismatch-20261029-123112-2573ff3` against `6-14` — recording whatever the grader then reports as-is, including `failed_rows` for the FAIL corners, relaxing nothing. |
| 6 — Monte Carlo evidence (digital) | `not_applicable` | The ratified spec's digital-partition rows are bit-exact protocol rows, structural declarations or corner-bounded timing rows; none is statistical. [`spec/digital-rows.json`](spec/digital-rows.json) lists the 10 rows (spec sections 2 to 6) with the hash of `spec/usb2-phy.md` they were read from, and [`evidence/item-6-digital-not-applicable.json`](evidence/item-6-digital-not-applicable.json) gives each row's class and reason. Both are cited as `"6.digital"` `not_applicable` evidence (klayout-tools#2865), never `met`, and `check.py` re-hashes the markdown, so editing the spec fails the gate until the rows are re-accounted. **Excluded, with reasons in the rows file:** every row owned by the analog partition or the PLL, including the PLL output jitter (a random-process bound, so it is *not* a digital row and sits with the analog partition under #40), the 3.3 V I/O rail, and all driver, receiver, squelch, pull-up and pull-down electrical rows. |
| 7 — Post-layout verification (analog) | `unmet` / `no_evidence` | The first `klt pex` report on a leaf now exists: [`sim/diff-receiver-pex/records/20261115-051001-f76df63.md`](../sim/diff-receiver-pex/records/20261115-051001-f76df63.md) re-runs the committed differential-receiver sensitivity bench on the extracted netlist of the committed leaf layout at `tt` and at `sf_100c_3.00v` (the binding corner of the 45-point schematic record `20261020-172719-ca4a45a` it gates on), with the schematic leg verified to reproduce the committed record's values (36/36 rows, exact equality), every device body biased (`body_bias.status: "biased"` — the drawn guard rings tie every body; the comparison is not invalidated), one device-representation divergence disclosed (`model_mismatch`: the bias resistor re-expressed as generic `sky130_fd_pr__res_xhigh_po` with measured `l=139.98` where the schematic writes `res_xhigh_po_1p41 L=140`), and all 36 delta rows passing — `vth_cm2p50_v` shifts −19.4 % at the binding corner (−75.97 mV → −90.72 mV), keeping 109 mV of the ±200 mV bound. **Deliberately uncited, so the row stays `unmet` / `no_evidence`:** the partition is five leaves and the citation must cover all five; citing a subset would claim post-layout verification leaves that do not have it. Three more leaves now carry committed `klt pex` two-corner records (#403, same method): [`se-receiver-dp-pex/records/20261121-001320-3190eab.md`](../sim/se-receiver-dp-pex/records/20261121-001320-3190eab.md) and [`se-receiver-dm-pex/records/20261121-001624-3190eab.md`](../sim/se-receiver-dm-pex/records/20261121-001624-3190eab.md) (both PASS: schematic legs reproduce their 225-point resistor-set records exactly, 14/14 rows each; the crossing moves −1.1 mV at tt and +0.1 mV at the binding `ff_lh_100c_3.00v` corner, `body_bias.status: "biased"`, the `res_xhigh_po_1p41` → generic re-expression disclosed on all three resistors per leaf, and the one non-portable measurement — the internal-node `vref_v` sanity probe — dropped with the gap filed as 2AMLogic/klayout-tools#6990), and the pull-up's [`dplus-pullup-pex/records/20261121-001916-3190eab.md`](../sim/dplus-pullup-pex/records/20261121-001916-3190eab.md) — a **FAIL** record (schematic leg 52/52, but the committed layout's contacted poly heads added ~1.6–2.1 kΩ per ladder-node stub, so no trim code reached the ratified [1425, 1575] Ω window post-layout; best code 15 at 3720.78 Ω at tt, 4006.35 Ω at `fs_hl_100c_3.00v`) — **superseded 2026-11-21 by the PASS record [`dplus-pullup-pex/records/20261121-055239-432e375.md`](../sim/dplus-pullup-pex/records/20261121-055239-432e375.md)** from the #414 layout iteration: the reworked leaf (vertical ladder spine through the switch row, interleaved switch groups, two-row square li1 contacts) measures 0.2–4.3 Ω per ladder-node head stub in the extracted netlist, so tt's best code 8 lands at 1492.74 Ω and fs_hl's best code 14 at 1477.96 Ω (that GDS then failed Magic DRC review on PR #417 — `diff/tap.19`, `poly.9`, `licon.7` — so it is itself **superseded by [`dplus-pullup-pex/records/20261124-011843-274376a.md`](../sim/dplus-pullup-pex/records/20261124-011843-274376a.md)**, the same two-corner bench re-run on the DRC-repaired layout: tt best code 8 at 1492.80 Ω, fs_hl best code 14 at 1478.02 Ω, 52/52 rows passing; the 0.2–4.3 Ω stub figures above belong to the earlier extraction and were not re-tabulated) — inside the window at both corners, schematic leg 52/52, D+ off-voltage ≤ 0.8 V; spec and bench unchanged. What changes this row: the `differential_driver` leaf (#404), then one honest citation covering all five leaves with passing post-layout evidence. |
| 7 — Post-layout verification (digital) | `unmet` / `no_evidence` | The only post-layout functional record in the tree (`20260919-001148-0f7636d-…`) re-verifies the *stub* against its post-PDN netlist — `design.anchors_design_claim: false`. Item 7 for the real datapath needs an SDF-annotated `klt functional-verification` run over its (not-yet-existing) post-route netlist, or a `klt pex` report — and a citable `pex` envelope, per item 7's own kind restriction. |
| 8 — Characterization report (both) | **`met`** | Cites [`evidence/characterization-report.json`](evidence/characterization-report.json) — a hand-rolled `kind: generic` envelope (the one item this wrapper shape is allowed to satisfy) wrapping the committed, current [`docs/characterization.md`](../docs/characterization.md), with the envelope's `provenance.input.content_hash` pinning that file (sha256 `55242b39…`) and the manifest citing the same pin. Both partition rows read from the one bare `"8"` key (the doc's mixed-signal guidance: one citation, both partitions' rows). **Disclosed, not omitted:** the characterization report's own headline (as read 2026-11-16) is that nine of the 16 spec rows hold a committed PASS record at schematic level, none holds post-layout evidence, and the remaining seven read `NO EVIDENCE` — its per-row content is schematic-level or absent evidence, not measured performance. The envelope asserts the item 8 *artifact* exists, is committed and current — it does **not** assert that any spec row is characterized, measured, or passing. |
| 9 — Testbenches shipped (both) | **`met`** | Cites [`evidence/item-9-testbenches.json`](evidence/item-9-testbenches.json), an artifact-anchored generic envelope (`t1_item: 9`) pinning [`inventory/item-9-testbenches.json`](inventory/item-9-testbenches.json): every suite in `verification/` (6 cocotb suites with their `klt functional-verification` requests, plus the pytest protocol model) and every analog testbench under `sim/*/testbench/` (9), each with the cold-start invocation from [`verification/README.md`](../verification/README.md) or [`sim/README.md`](../sim/README.md) and the pinned PDK revision (`docs/baseline.md`). **Disclosed, not omitted:** this asserts the testbenches are committed, inventoried and current — it does **not** assert that any of them passes; the pass/fail record is the CI `check-ci` job and the `sim/` records. The grader re-hashes the inventory only; `check.py` re-hashes every listed file and fails if a `verification/test_*.py`, `verification/request-*.json` or `sim/*/testbench/` file is not listed. |
| 10 — Repo hygiene (both) | **`met`** | Cites [`evidence/item-10-hygiene.json`](evidence/item-10-hygiene.json), an artifact-anchored generic envelope (`t1_item: 10`) pinning [`inventory/item-10-hygiene.json`](inventory/item-10-hygiene.json): `README.md` (block statement, spec table, reproduction), the Apache-2.0 `LICENSE`, `.github/workflows/ci.yml`, and the CI commands that keep the harness and evidence formats valid (`npm run check:ci`, `npm run lint`, `python3 signoff/check.py`). The same disclosure as item 9 applies: it attests the artifacts exist and are current, not that CI is green. Because the README and the workflow are inventoried, editing either needs `python3 signoff/check.py --regen`. |
| 11 — Power delivery, structural (analog) | `unmet` / `substrate_isolation_undecidable` | Each leaf cites its latest ERC report and the same curated LVS report as item 4. All five ERC reports give one island each for VDD and VSS and zero findings, and — after the #406 repair — all five curated LVS reports match, so the former `lvs_did_not_pass` refusal is gone. The pinned grader's remaining refusal is its substrate-isolation rule (klayout-tools#5346, bundled with the 0.9.2 notes): it wants either an ERC run whose request names the deck/PDK family so the isolation layers can be measured, or `ties[].isolation_boxes` asserted in the ERC spec — neither is declared by the committed `erc-supply-spec.json`, which grades the substrate tie by the `well_complement_of: [nwell]` region assertion instead. Lifting it needs an ERC-spec/`klt erc` capability change, not a layout change. The SPICE supplies participate in the ordinary LVS comparison. [Chip #406](https://github.com/2AMLogic/sky130-usb2-phy/issues/406) |
| 11 — Power delivery, structural (digital) | `unmet` / `no_evidence` | Same row, digital partition: needs the `place-and-route` + `erc` + `lvs` citation chain over a genuinely-routed real datapath (`power.pdn: true`, `power_connectivity.status: "match"`), none of which exists for the block. |

**What is uncited, read off the manifest and not off this prose.** `jq -r
'.evidence | keys[]' signoff/block-manifest.json` (2026-11-16) returns
`1.analog`, `1.digital`, `2.analog`, `3.analog`, `4.analog`, `5.analog`,
`6.analog`, `6.digital`, `8`, `9`, `10`, `11.analog` — so 7 of the 22 rows
carry no citation at all, in two groups:

- **The digital halves of items 2, 3, 4, 5 and 11** — uncited by deliberate
  choice for 2, 3, 4 and 11: the only envelopes that exist for them describe
  the `smoke-utmi_stub` experiment, which by its own convention
  (`design.anchors_design_claim: false`) anchors no design claim, so citing
  them would paint the block's rows with the toolchain's result. Item
  5 (digital) has no citable envelope at all — no multi-corner STA has ever
  run on the real RTL (its row above). What changes all of them is a
  genuinely placed-and-routed, timed `usb_utmi_top`.
- **Both halves of item 7** — the one design-anchored record each side has
  is not citable for the partition: on the analog side the
  differential-receiver `klt pex` report covers one leaf of five, and one
  leaf is not the partition; on the digital side the only post-layout record
  is the stub's (see the rows above).

An uncited row is the honest machine-readable statement — *no check backs
this claim* — which is what `klt signoff` renders, with a `reason`, instead
of guessing. **Uncited is not the only route to `unmet`:** items 5 and
11 (analog) are *cited and still `unmet`* — on zero-`limits` envelopes
(item 5), and on the substrate-isolation grading requirement (item 11, whose
curated LVS now matches after #406). Read each row's `reason` rather than
inferring one from this list.

**11 of 22 is a different number from the #29 hand-read's "1/10 pass (1 N/A)", and
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
  on PATH is the pinned *released registry wheel* (`git_tag v0.9.2`,
  `is_release: true`), because same-version git snapshots have been
  observed to grade differently (klayout-tools#2216). This is why the CI
  job `pip install`s the pin instead of trusting whatever `klt` a runner
  has.

## How to re-run the grading

`klt signoff --manifest` is PDK-free — it grades committed JSON envelopes,
it does not run the gates — so grading runs anywhere. Provision the pinned
wheel in a **throwaway venv**, not host-wide: shared/fleet workers forbid
host-wide installs, and `uv venv` ships no `pip`, so `python -m pip` fails
inside it — install via `uv pip --python`. Read the version from
`signoff/toolchain.json` so this recipe survives every future re-pin. Two
rules make the *same* `PATH` serve both the grading gate and every leg of
`npm run check:all` (issue #338), and a third covers the hosts those two
cannot (issue #349):

- **Put only a `klt` symlink on `PATH` — never the venv's `bin/`.**
  `check.py` resolves the grader through `shutil.which("klt")`, so the
  pinned grader must resolve first on `PATH` — skipping the venv
  entirely fails leg 2's grader-identity check. But the pytest legs of
  `check:all` (`signoff/tests`, the lint self-tests, and leg 4's model
  test at `scripts/check-ci.sh:12`) also run under the
  `python3` that the *same* `PATH` selects, and prepending the venv's
  `bin/` puts the venv's `python3` first. A venv provisioned for grading
  alone would carry no pytest and fail at the first pytest leg, leg 1's
  lint self-tests, reporting `pytest is not installed -- the lint's own
  self-tests cannot run.` (leg 1 probes with `python3 -c "import pytest"`
  and discards its stderr, so the interpreter's own `No module named
  pytest` is not what surfaces there; that text is leg 3's form) — but
  the `[functional-verification]` extra this recipe installs pulls pytest
  in transitively (cocotb depends on it), so the venv-bin form happens to
  run those legs today. The wrapper directory is still the form to use,
  on grounds that survive measurement: it does not rest on a transitive
  *test* dependency of cocotb, which the grader makes no promise to
  keep, and it leaves `python3` as the host interpreter the rest of the
  repo's tooling assumes — whose pytest is already a hard requirement of
  every pytest leg: leg 1 (`.github/scripts/lint.sh` fails closed without
  it), leg 3 (`python3 -m pytest signoff/tests`) and leg 4's first layer
  (`scripts/check-ci.sh:12`). That hard
  requirement is also this form's boundary: on a host whose `python3`
  carries no pytest, the wrapper form cannot complete those three
  pytest legs, and extending the wrapper directory with a symlink to
  the venv's `python3` does **not** rescue it — CPython resolves the
  symlink chain down to the base interpreter before searching for
  `pyvenv.cfg`, so the venv never activates (`sys.prefix` resolves to
  the base install and `import pytest` fails even with pytest installed
  in the venv; measured 2026-11-16, issue #349). On such a host use the
  venv-bin form below.
- **Install the `[functional-verification]` extra into that venv.** Leg 4
  (`scripts/check-ci.sh`) drives the cocotb testbenches through the same
  `klt` the `PATH` selects, and `klt functional-verification` imports
  cocotb **inside `klt`'s own environment**
  (`docs/environment-setup.md` §3 — the same environment CI's `check-ci`
  job provisions, installing plain `cocotb` into klt's tool venv
  directly; see the *Install cocotb into klt's own tool venv* step of
  `.github/workflows/ci.yml`). The extra does not disturb the grading
  identity: same registry wheel, same `git_tag`, `is_release` still true.
- **No pytest in the host `python3`? Run `check:all` with the venv's
  `bin/` first.** Legs 1, 3 and leg 4's first layer (`scripts/check-ci.sh:12`)
  of `check:all` need pytest in whichever
  interpreter `PATH` selects — under the wrapper form that is the host
  `python3`, which a shared worker may not carry (fleet workers have
  drifted apart: some have pytest 9.1.1 in the user site, some have
  none at all, and worker rules forbid installing into either; issue
  #349). The measured form for such a host: install pytest into the
  same grader venv — `uv pip install --python <venv>/bin/python pytest`,
  **explicitly**, so the legs do not rest on the extra's
  transitive cocotb dependency, which the grader makes no promise to
  keep — then prepend the venv's `bin/` for the `check:all` run. The
  venv's own `python3` activates its venv normally (a real venv
  interpreter finds the `pyvenv.cfg` beside it, unlike the wrapper
  symlink measured above), so pytest resolves; being a venv interpreter
  it also ignores user site-packages (`site.ENABLE_USER_SITE` is
  `False`), so the run cannot be silently rescued by whatever the host
  happens to carry. Leg 2's grader-identity check is untouched: the
  `klt` that `PATH` selects is the same pinned wheel from the same
  venv. This is the one documented exception to the first rule — and
  neither form modifies the shared tool: `~/.local/bin/klt` (deliberately
  a git snapshot, `is_release` false) is only ever *shadowed* for the
  duration of a run, never overwritten.

```bash
VER=$(python3 -c 'import json;print(json.load(open("signoff/toolchain.json"))["klt"]["package_version"])')
uv venv /tmp/signoff-grader
uv pip install --python /tmp/signoff-grader/bin/python "klayout-tools[functional-verification]==$VER"
uv pip install --python /tmp/signoff-grader/bin/python pytest    # explicit: pytest legs (1, 3, 4's layer 1) must not rest on cocotb's transitive dep
mkdir -p /tmp/signoff-grader-bin && ln -sfn /tmp/signoff-grader/bin/klt /tmp/signoff-grader-bin/klt
PATH="/tmp/signoff-grader-bin:$PATH" python3 signoff/check.py            # the gate: re-grade + drift check
PATH="/tmp/signoff-grader-bin:$PATH" python3 signoff/check.py --regen    # refresh pins + rewrite the report
# exactly one of the next two lines — the PATHs are alternatives, not sequential:
PATH="/tmp/signoff-grader-bin:$PATH" npm run check:all                   # host python3 has pytest
PATH="/tmp/signoff-grader/bin:$PATH" npm run check:all                   # host python3 has NO pytest: venv-bin form (issue #349)
```

So `npm run check:all` needs exactly this from `PATH`: the pinned grader
`klt` resolving first, a `python3` **with pytest** resolving for
`python3`, and `iverilog` for the cocotb leg — then all four legs run
and the chain exits 0 on a clean tree, with no host-wide install anywhere
(verified on a fleet worker, 2026-11-16, main @ `80e896f`). Under the
wrapper form the `python3` is the host's, so pytest must already be
there; on a host whose `python3` has no pytest, the venv-bin form above
is the supported alternative — the venv interpreter carries the explicit
pytest install and ignores user site-packages, so it works precisely
where the wrapper form cannot (measured end to end on a fleet worker,
2026-11-16, issue #349).

**Recognise a *wrong* grader before believing any output.** There are three
ways to get a confidently-wrong result here, and the checker's own FAIL text
warns about none of them:

- **The false-drift trap — the one that manufactures a defect report.** With a
  non-pinned `klt` on `PATH`, `python3 signoff/check.py` emits *two* FAILs:
  the expected `the klt on PATH is not the pinned grading build`, **and**
  `signoff/signoff-report.json no longer matches what the current tree grades
  to`, itemised to the row level. That second FAIL reads exactly like evidence
  rot in this repository, and it is not: `main()` runs `check_toolchain_pin()`
  and still falls through to the drift check on the wrong grader's output, and
  a same-version git snapshot is known to grade differently from the registry
  wheel ([klayout-tools#2216](https://github.com/2AMLogic/klayout-tools/issues/2216)).
  Re-run inside the venv before believing any drift — and **never
  `python3 signoff/check.py --regen` from a failed identity check**:
  `--regen` writes `signoff-report.json` regardless of the pin verdict, so
  running it under the wrong grader commits that grader's verdict as the
  report of record.
- **`uvx --from "klayout-tools==$VER" klt …` alone does not satisfy the
  gate.** The checker resolves the grader through `PATH` only —
  `shutil.which("klt")` and the `klt version --format json` subprocess inside
  `check_toolchain_pin()` — so a one-shot `uvx` wrapper satisfies only the
  single command it wraps, while `check.py` still sees whatever `klt` is on
  `PATH`. What is load-bearing versus `uvx` is the pinned `klt` resolving
  first on `PATH` for every command the chain runs; the wrapper dir is
  simply the form this recipe uses to arrange that.
- **Never install over the shared fleet tool.** On a shared worker,
  `~/.local/bin/klt` is deliberately a git snapshot (`is_release false`) that
  other fleet sweeps depend on; host-wide installs are forbidden by worker
  policy. The `pip install klayout-tools==…` line that the gate's own FAIL
  message prints (`check_toolchain_pin()` and the `klt`-not-on-`PATH` branch
  of `main()`) is **not** the instruction to follow on a shared worker —
  provision the throwaway venv above instead.

**Where the pin lives: three files that move together.** A re-pin updates
`signoff/toolchain.json`, the `GRADER_PACKAGE_VERSION`/`GRADER_GIT_TAG`
constants in `signoff/check.py`, and the `pip install` in
`.github/workflows/ci.yml`'s `signoff` job as one change —
`check_toolchain_pin()` fails if the first two disagree, so half a re-pin is
worse than none.

The re-hash half of the gate needs no grader at all: `--pins-only` runs the
eight stdlib re-hash checks with no `klt` on PATH — the cheap
"did I just stale a pin?" check to run before opening a PR (this is the
pre-PR instruction in `CLAUDE.md`). It cannot be combined with `--regen` —
the checker rejects that pair outright, because one runs without the pinned
grader and the other rewrites the report with it. On failure it names the
stale member and prints the refresh recipe above; only the `--regen` refresh
itself needs the pinned wheel:

```bash
python3 signoff/check.py --pins-only   # re-hash checks only, grader-free
```

CI (`signoff` job in `.github/workflows/ci.yml`) runs the gate on every PR
and push and requires the committed `signoff-report.json` to match what the
current tree grades to — so a citation whose underlying artifact has since
changed (today: `docs/characterization.md`) fails CI instead of silently
rotting. The fix is always the same one-liner — `python3 signoff/check.py
--regen` — **after** re-reading what changed and updating the envelope's
summary and this README's disclosed verdict if the content moved; the prose
and the report are one artifact, not two. The one exception is the
wrong-grader case above: a drift FAIL that arrives *together with* the
grader-identity FAIL is not drift at all, and `--regen` is forbidden until
the pinned venv is on `PATH` and the identity check passes.
