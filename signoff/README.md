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
| [`inventory/`](inventory/) | Plain, versioned **inventories** the anchored envelopes bind: `item-9-testbenches.json`, `item-10-hygiene.json`, `item-1-digital-sources.json` and `item-1-analog-sources.json` (the `--attest` schema, cited as `1.digital` / `1.analog` — see item 1 below). Items 9 and 10 list each file with its sha256 and `check.py` re-hashes them all; item 1's hashes live in its `--attest` envelope, which `check.py` re-hashes against. Items 9/10 are hand-rolled over their inventories until a later re-pin can run `--attest` over them. |
| [`tests/`](tests/) | Negative controls for the above (`python3 -m pytest signoff/tests`). |
| [`check.py`](check.py) | **The gate.** What CI runs on every PR and push: it re-grades the manifest and fails on any drift between what is committed and what the current tree actually grades to (see "What the grader cannot check" below). |
| [`spec/`](spec/) | `digital-rows.json`: the ratified digital-partition rows of `spec/usb2-phy.md`, machine-readable, with the markdown's content hash (item 6 digital). |
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
  `sky130-pll` and never designed here. No analog content is committed
  yet — `design/`, `sim/`, `layout/`, and `measurements/` are still
  placeholder-only.

`klt 0.8.0` (whose bundled checklist carries all 11 items, so no vendored copy is needed) renders **both columns for every T1 item** for a `mixed-signal`
manifest (even the kind-independent ones render twice, once per partition):
`t1_item_count` is 22, not 11.

## The current verdict: 6 of 22 rows met

`tier: null`. Every per-item verdict below is read from
[`signoff-report.json`](signoff-report.json) — not hand-derived. An
honest near-all-`unmet` mechanical reading is the desired outcome, not a
disappointment: this block's own characterization
([`docs/characterization.md`](../docs/characterization.md)) already states
that **zero of the 16 spec rows have design-anchored evidence today**, and a
grader that said otherwise would be lying.

| Item (partition) | Verdict | Why — and what would change it |
|---|---|---|
| 1 — Design sources (analog) | **`met`** | Cites [`evidence/item-1-analog-sources.json`](evidence/item-1-analog-sources.json) under `"1.analog"`: an artifact-anchored envelope produced by `klt signoff --attest 1` (klt 0.8.0) over [`inventory/item-1-analog-sources.json`](inventory/item-1-analog-sources.json) — the five leaf schematics `design/{differential_driver,differential_receiver,dplus_pullup,se_receiver_dm,se_receiver_dp}.sch` and their five derived `design/netlist/*.spice`, each netlist with a freshness check, [`design/check_netlist.py`](../design/check_netlist.py) (15/15 checks passed). **Disclosed, not omitted:** it asserts the sources exist and the netlists match a fresh `klt netlist --block` export; it does **not** assert any analog spec row is met. `klt netlist --check` alone reports all five netlists drifted (the committed files carry `design/export_netlist.sh`'s header, real `.subckt` wrapper, repo-relative `sch_path`, and different `+` line wrapping), so the checker normalises exactly those and compares everything else; a one-character edit to a netlist fails it (tested). Like the digital check it is `local_only` (needs xschem and the pinned PDK) and `check.py` re-hashes the envelope's files instead. **Not in the partition's in-tree sources:** the PLL (pinned reference to `2AMLogic/sky130-pll`, `reuse.lock.json`) and the squelch detector (undecided, DR-0003 Decision 2 pending ratification) — if the grader's analog partition later requires either, this row is the one that changes. Refresh after a schematic change: `design/export_netlist.sh <cell>` where xschem is permitted, then `uvx --from "klayout-tools==0.8.0" klt signoff --attest 1 --inventory signoff/inventory/item-1-analog-sources.json -o signoff/evidence/item-1-analog-sources.json`, update the manifest pin, `python3 signoff/check.py --regen`. |
| 1 — Design sources (digital) | **`met`** | Cites [`evidence/item-1-digital-sources.json`](evidence/item-1-digital-sources.json) under the partition-qualified key `"1.digital"`: an artifact-anchored envelope produced by `klt signoff --attest 1` (klt 0.8.0) over [`inventory/item-1-digital-sources.json`](inventory/item-1-digital-sources.json) — the 12 `rtl/usb_*.v` files and the synthesis request (each recorded by content hash in the envelope), plus the derived `design/netlist/usb_utmi_top.v` with its declared freshness check, `klt synthesize flow/request-synth-usb_utmi_top.json --pdk sky130A --check <newest synthesize-report.json>`. **Disclosed, not omitted:** this asserts the sources exist, are current, and that the netlist's freshness check passed. It does **not** assert any spec row is met or that synthesis is timing-clean. Cheap-mode `--check` re-hashes the request's RTL and the liberty against the report's recorded provenance; per its help text it does not open the netlist file itself, so a hand-edited netlist would not fail it (not tested); `--rerun` (full mode, re-runs Yosys) is the stronger check and was not run. The freshness command is `local_only` (needs the PDK), so `check.py` (grader 0.7.0, which lacks `--attest`) re-hashes the envelope's recorded files instead and does not re-run it. Refresh after any RTL change: `uvx --from "klayout-tools==0.8.0" klt signoff --attest 1 --inventory signoff/inventory/item-1-digital-sources.json -o signoff/evidence/item-1-digital-sources.json`, then `python3 signoff/check.py --regen`. |
| 2 — Layout (analog) | `unmet` / `no_evidence` | No analog layout exists (#40). |
| 2 — Layout (digital) | `unmet` / `no_evidence` | `layout/utmi_stub.gds` is the stub's output, not the block's; nothing to cite for the real datapath until it is routed. |
| 3 — DRC clean (both) | `unmet` / `no_evidence` | The only committed `klt drc` envelopes are the smoke-utmi_stub sweep's six (`flow/smoke-utmi_stub/artifacts/*/drc-report.json`) — real evidence about the *toolchain*, explicitly **not** about the block, so they are deliberately uncited. What changes this: a DRC report against the real UTMI layout when it exists, cited with a `content_hash` pin. |
| 4 — LVS clean (both) | `unmet` / `no_evidence` | Same shape as item 3: six stub LVS reports exist (`…/lvs-report.json`), none of which anchor a design claim. (They also carry the disclosed VGND↔TXREADY correspondence artifact, #66/#69 — one more reason not to paint the block's row green with them.) |
| 5 — Full corner verification (analog) | `unmet` / `no_evidence` | No analog design exists to simulate (#40). |
| 5 — Full corner verification (digital) | `unmet` / `no_evidence` | The cocotb suites (`verification/test_usb_*.py`) are bit-exact **pre-layout functional** verification, run at a single nominal zero-delay model — no multi-corner STA has ever run on the real RTL; the only six-corner `klt sta` reports in the tree are the stub's. Item 5 asks for the corner matrix against a ratified spec; when the real datapath is synthesized and timed across the six committed corners (`spec/decision-records/0001-…`, mirrored in `flow/corners.json`), cite the `klt sta` and `klt functional-verification` envelopes here. What exists today is honestly *less* than the row requires, so the row stays grey. |
| 6 — Monte Carlo evidence (analog) | `unmet` / `no_evidence` | **The analog partition has statistical spec rows**, named in `spec/usb2-phy.md` section 6: *Differential input sensitivity* (|(D+) − (D−)| > 200 mV; offset-limited) and *Single-ended receiver thresholds* (VIH > 2.0 V, VIL < 0.8 V; `docs/porting-plan.md` states it as a threshold window under mismatch). Their Monte Carlo evidence is committed: local-mismatch campaigns with a recorded seed (166) and sample count (n = 400 per corner), a deterministic negative control, at `tt` and at the binding corner of the 45-point records, graded by `klt yield` (`sample_size.verdict` other than `insufficient` is required by the record lint). See [`sim/diff-receiver-mismatch/`](../sim/diff-receiver-mismatch/records/) and [`sim/se-receiver-mismatch/`](../sim/se-receiver-mismatch/records/) and the "diff-receiver-mismatch, se-receiver-mismatch" section of [`sim/README.md`](../sim/README.md). **Still `unmet` / `no_evidence` as graded**, deliberately: the manifest declares no `spec_rows."6"` set and cites no `klt yield` report, because the reports are not yet cited against a ratified row list (the citation pass is #118 or a later one) and a report must not be cited against an unratified limit; the item stays `unmet` until **every** declared statistical row is covered. **Not covered, and not claimed:** the other analog matching-type rows (the driver's rise/fall matching and the D+ pull-up trim), which need their own campaigns, and any corner x mismatch combination beyond the two corners each record names. |
| 6 — Monte Carlo evidence (digital) | `not_applicable` | The ratified spec's digital-partition rows are bit-exact protocol rows, structural declarations or corner-bounded timing rows; none is statistical. [`spec/digital-rows.json`](spec/digital-rows.json) lists the 10 rows (spec sections 2 to 6) with the hash of `spec/usb2-phy.md` they were read from, and [`evidence/item-6-digital-not-applicable.json`](evidence/item-6-digital-not-applicable.json) gives each row's class and reason. Both are cited as `"6.digital"` `not_applicable` evidence (klayout-tools#2865), never `met`, and `check.py` re-hashes the markdown, so editing the spec fails the gate until the rows are re-accounted. **Excluded, with reasons in the rows file:** every row owned by the analog partition or the PLL, including the PLL output jitter (a random-process bound, so it is *not* a digital row and sits with the analog partition under #40), the 3.3 V I/O rail, and all driver, receiver, squelch, pull-up and pull-down electrical rows. |
| 7 — Post-layout verification (analog) | `unmet` / `no_evidence` | No analog layout exists to post-layout-verify (#40). |
| 7 — Post-layout verification (digital) | `unmet` / `no_evidence` | The only post-layout functional record in the tree (`20260919-001148-0f7636d-…`) re-verifies the *stub* against its post-PDN netlist — `design.anchors_design_claim: false`. Item 7 for the real datapath needs an SDF-annotated `klt functional-verification` run over its (not-yet-existing) post-route netlist, or a `klt pex` report — and a citable `pex` envelope, per item 7's own kind restriction. |
| 8 — Characterization report (both) | **`met`** | Cites [`evidence/characterization-report.json`](evidence/characterization-report.json) — a hand-rolled `kind: generic` envelope (the one item this wrapper shape is allowed to satisfy) wrapping the committed, current [`docs/characterization.md`](../docs/characterization.md), with the envelope's `provenance.input.content_hash` pinning that file (sha256 `55242b39…`) and the manifest citing the same pin. Both partition rows read from the one bare `"8"` key (the doc's mixed-signal guidance: one citation, both partitions' rows). **Disclosed, not omitted:** the characterization report's own headline is that zero spec rows have design-anchored evidence — its per-row content is an honest `NO EVIDENCE` verdict, not measured performance. The envelope asserts the item 8 *artifact* exists, is committed and current — it does **not** assert that any spec row is characterized, measured, or passing. |
| 9 — Testbenches shipped (both) | **`met`** | Cites [`evidence/item-9-testbenches.json`](evidence/item-9-testbenches.json), an artifact-anchored generic envelope (`t1_item: 9`) pinning [`inventory/item-9-testbenches.json`](inventory/item-9-testbenches.json): every suite in `verification/` (6 cocotb suites with their `klt functional-verification` requests, plus the pytest protocol model) and every analog testbench under `sim/*/testbench/` (9), each with the cold-start invocation from [`verification/README.md`](../verification/README.md) or [`sim/README.md`](../sim/README.md) and the pinned PDK revision (`docs/baseline.md`). **Disclosed, not omitted:** this asserts the testbenches are committed, inventoried and current — it does **not** assert that any of them passes; the pass/fail record is the CI `check-ci` job and the `sim/` records. The grader re-hashes the inventory only; `check.py` re-hashes every listed file and fails if a `verification/test_*.py`, `verification/request-*.json` or `sim/*/testbench/` file is not listed. |
| 10 — Repo hygiene (both) | **`met`** | Cites [`evidence/item-10-hygiene.json`](evidence/item-10-hygiene.json), an artifact-anchored generic envelope (`t1_item: 10`) pinning [`inventory/item-10-hygiene.json`](inventory/item-10-hygiene.json): `README.md` (block statement, spec table, reproduction), the Apache-2.0 `LICENSE`, `.github/workflows/ci.yml`, and the CI commands that keep the harness and evidence formats valid (`npm run check:ci`, `npm run lint`, `python3 signoff/check.py`). The same disclosure as item 9 applies: it attests the artifacts exist and are current, not that CI is green. Because the README and the workflow are inventoried, editing either needs `python3 signoff/check.py --regen`. |
| 11 — Power delivery, structural (analog) | `unmet` / `no_evidence` | New upstream item (klayout-tools#2025); it renders a row here because the bundled `klt 0.8.0` checklist carries the 11-item skeleton. This repo has **no `klt erc` supply spec or report for the block** — companion issue [#72](https://github.com/2AMLogic/sky130-usb2-phy/issues/72) lands the stub's artifact pair, which anchors no design claim and would not make *this* row citable anyway; the real UTMI/PHY layout does not exist yet. What changes this: an `erc`+`lvs` citation chain per the analog column, against a real layout. |
| 11 — Power delivery, structural (digital) | `unmet` / `no_evidence` | Same row, digital partition: needs the `place-and-route` + `erc` + `lvs` citation chain over a genuinely-routed real datapath (`power.pdn: true`, `power_connectivity.status: "match"`), none of which exists for the block. |

Item 2 is uncited by deliberate choice, and items 3, 4, 5, 7 and 11
are uncited because the only envelopes that exist for them describe the
smoke-utmi_stub experiment — which by its own convention anchors no design
claim. In both cases the uncited row is the honest machine-readable
statement: *no check backs this claim*, which is what `klt signoff` renders,
with a `reason`, instead of guessing.

**6 of 22 is a different number from the #29 hand-read's "1/10 pass (1 N/A)", and
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

- **Native-citation re-hashing.** When a future citation names a `klt
  drc`/`lvs`/`pex` envelope, `check.py` must grow a repo-side re-hash of
  the cited *input artifact* (the GDS/netlist) the way it re-hashes the
  characterization report today — `klt` through 0.8.0 does not re-hash
  the input of a *native* envelope itself (upstream: klayout-tools#2196).
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
