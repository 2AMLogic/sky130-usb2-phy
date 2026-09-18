# Characterization report — per-spec-row evidence index

**Generated 2026-09-15 against `main` at `ee9611b`.** This is the
authoritative characterization summary for this repo: one place that indexes
every row of the ratified spec's interface-requirement table
([`spec/usb2-phy.md`](../spec/usb2-phy.md) §6) against the evidence records
that exist, per PVT corner, with the record id behind every entry. It
supersedes [`docs/baseline.md`](baseline.md) as the authoritative summary;
that document is kept as the original point-in-time synthesis record it
always was, not deleted.

> **Partially stale as of issue #59.** That issue added a power grid to the
> P&R request and re-ran the flow across all six corners, so six records
> stamped `20260918-214755-fb60e2c-*` now supersede the six indexed in §1
> below. The **result this report exists to state is unchanged**: the new
> records also carry `design.anchors_design_claim: false`, so zero §6 rows
> have design-anchored evidence and every §6 row below still reads
> `NO EVIDENCE`. What *is* stale is the detail — §1's record index, §3's
> per-corner utilisation/wirelength numbers, and §3's per-run DRC coverage
> counts. Regenerating the report against the newest records is tracked in
> issue #64; until then, check any number below against the newest record
> for that corner before quoting it as current.

## Headline

> **Zero of the 16 rows of `spec/usb2-phy.md` §6 currently have
> design-anchored evidence, at any corner.**

This is not a formatting caveat, it is the result. Seven evidence records are
committed under `flow/smoke-utmi_stub/records/` and all seven carry
`design.anchors_design_claim: false`. They are the
[`smoke-utmi_stub`](../flow/README.md) experiment: `rtl/utmi_stub.v`, nine
flip-flops with no combinational logic and no USB protocol behaviour, run
through the physical flow so that any failure is unambiguously a *tool*
failure. They are real evidence — about the **toolchain**, that
synthesis → P&R → STA → extract → LVS → DRC → post-layout functional
verification runs, reports, and can be linted across six corners. They are
evidence about **nothing in `spec/usb2-phy.md`**.

Consequently this report assigns **no `PASS` and no `FAIL` to any spec row**.
Every §6 row below reads `NO EVIDENCE`, and the per-corner numbers in
§3 are presented as toolchain-smoke results, labelled as such, not as
characterization of the USB 2.0 PHY.

The real UTMI digital datapath (`rtl/usb_utmi_top.v` and the modules it
instantiates) has **not** been through the physical flow. No committed record
names any of those files in its `provenance.inputs` — see §4.

## 1. Evidence records this report indexes

| Record id | Corner | Landed in | Issue / PR | Stages | Supersedes |
|---|---|---|---|---|---|
| [`20260915-113028-7d56be5-ff_100C_1v95`](../flow/smoke-utmi_stub/records/20260915-113028-7d56be5-ff_100C_1v95.md) | `ff_100C_1v95` | `9281bc4` | #11 / PR #55 | synth, P&R, STA, extract, LVS, DRC | — |
| [`20260915-113028-7d56be5-ff_n40C_1v95`](../flow/smoke-utmi_stub/records/20260915-113028-7d56be5-ff_n40C_1v95.md) | `ff_n40C_1v95` | `9281bc4` | #11 / PR #55 | synth, P&R, STA, extract, LVS, DRC | — |
| [`20260915-113028-7d56be5-ss_100C_1v60`](../flow/smoke-utmi_stub/records/20260915-113028-7d56be5-ss_100C_1v60.md) | `ss_100C_1v60` | `9281bc4` | #11 / PR #55 | synth, P&R, STA, extract, LVS, DRC | — |
| [`20260915-113028-7d56be5-ss_n40C_1v60`](../flow/smoke-utmi_stub/records/20260915-113028-7d56be5-ss_n40C_1v60.md) | `ss_n40C_1v60` | `9281bc4` | #11 / PR #55 | synth, P&R, STA, extract, LVS, DRC | — |
| [`20260915-113028-7d56be5-tt_025C_1v80`](../flow/smoke-utmi_stub/records/20260915-113028-7d56be5-tt_025C_1v80.md) | `tt_025C_1v80` | `9281bc4` | #11 / PR #55 | synth, P&R, STA, extract, LVS, DRC | — (superseded, see below) |
| [`20260915-113028-7d56be5-tt_100C_1v80`](../flow/smoke-utmi_stub/records/20260915-113028-7d56be5-tt_100C_1v80.md) | `tt_100C_1v80` | `9281bc4` | #11 / PR #55 | synth, P&R, STA, extract, LVS, DRC | — |
| [`20260915-132956-9281bc4-tt_025C_1v80`](../flow/smoke-utmi_stub/records/20260915-132956-9281bc4-tt_025C_1v80.md) | `tt_025C_1v80` | `6cb5cc6` | #37 / PR #57 | the six above **+ functional_verification** | `20260915-113028-7d56be5-tt_025C_1v80` |

All seven: `experiment: smoke-utmi_stub`, `design.hdl_toplevel: utmi_stub`,
`design.sources: ["rtl/utmi_stub.v"]`, `design.anchors_design_claim: false`.

**Current record per corner**: the last row supersedes the `tt_025C_1v80`
record from the first sweep, so the current `tt_025C_1v80` evidence is
`20260915-132956-9281bc4-tt_025C_1v80`. The superseded record is kept (the
append-only rule in [`flow/README.md`](../flow/README.md) — records are never
edited or deleted) and is cited here for completeness, not as live evidence.

The corner set is the six committed corners of
[`spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`](../spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md)
Decision 5, mirrored in [`flow/corners.json`](../flow/corners.json):
`ss_n40C_1v60`, `ss_100C_1v60`, `tt_025C_1v80`, `tt_100C_1v80`,
`ff_n40C_1v95`, `ff_100C_1v95`. Every record's `corner_matrix.run` lists all
six, i.e. the full matrix was run — no subset.

## 2. `spec/usb2-phy.md` §6 — per-row evidence index

Rows are numbered top-to-bottom as they appear in §6's table; the spec itself
does not number them, so `§6-NN` is this report's citation handle, not spec
text. Nothing in `spec/` is modified by this report.

`Corners with evidence` counts corners at which a **design-anchored** record
supports the row. `NO EVIDENCE` means exactly that — not "fails", not
"passes".

| Row | Sibling block | Interface requirement | Target value | Evidence record(s) | Corners with evidence | Verdict |
|---|---|---|---|---|---|---|
| §6-01 | PLL | Reference input | 12 MHz ±0.25% (2500 ppm) crystal/resonator | none | 0 of 6 | NO EVIDENCE |
| §6-02 | PLL | Output jitter (cycle-to-cycle, feeding oversampling clock) | < 5% of one bit period (< 4.17 ns at 144 MHz) | none | 0 of 6 | NO EVIDENCE |
| §6-03 | PLL | Oversampling ratio delivered to bit/edge sync logic | 12× minimum | none | 0 of 6 | NO EVIDENCE |
| §6-04 | Current-mode drivers | Output voltage swing, static | VOH 2.8–3.6 V, VOL 0.0–0.3 V | none | 0 of 6 | NO EVIDENCE |
| §6-05 | Current-mode drivers | Driver output resistance | 28–44 Ω | none | 0 of 6 | NO EVIDENCE |
| §6-06 | Current-mode drivers | Rise/fall time | 4–20 ns (10%–90%), matched within 10% | none | 0 of 6 | NO EVIDENCE |
| §6-07 | Current-mode drivers | Output signal crossover voltage | 1.3–2.0 V | none | 0 of 6 | NO EVIDENCE |
| §6-08 | Current-mode drivers | Control interface from UTMI layer | drive enable, OE, TxD+/TxD− | none | 0 of 6 | NO EVIDENCE |
| §6-09 | Differential receivers | Differential input sensitivity | \|(D+) − (D−)\| > 200 mV | none | 0 of 6 | NO EVIDENCE |
| §6-10 | Differential receivers | Common-mode input range | 0.8–2.5 V | none | 0 of 6 | NO EVIDENCE |
| §6-11 | Differential receivers | Single-ended receiver thresholds | VIH > 2.0 V, VIL < 0.8 V | none | 0 of 6 | NO EVIDENCE |
| §6-12 | Squelch / envelope detector | Squelch detection threshold | 100–200 mV differential envelope | none | 0 of 6 | NO EVIDENCE |
| §6-13 | Squelch / envelope detector | Output interface to UTMI layer | 1-bit `SQUELCH`/`LineState`, at the oversampling rate | none | 0 of 6 | NO EVIDENCE |
| §6-14 | Pull-up/pull-down and termination | FS device D+ pull-up | 1.5 kΩ ±5% to regulated 3.0–3.6 V | none | 0 of 6 | NO EVIDENCE |
| §6-15 | Pull-up/pull-down and termination | Downstream port pull-downs | 15 kΩ ±5% on each of D+/D− | none | 0 of 6 | NO EVIDENCE |
| §6-16 | Pull-up/pull-down and termination | Control interface from UTMI layer | 1-bit pull-up enable/disable | none | 0 of 6 | NO EVIDENCE |

**Why every row is empty**, by group — these are two different reasons and
the difference matters:

- **§6-01…§6-07, §6-09…§6-12, §6-14, §6-15 — analog rows owed by sibling
  canary blocks.** These are electrical requirements on a PLL, drivers,
  receivers, a squelch detector, and the termination network. Per
  [`CLAUDE.md`](../CLAUDE.md)'s scope rule none of those is designed in this
  repo, `design/` and `sim/` are empty, and no analog testbench or PVT
  simulation result exists to cite. There is nothing to be measured here yet
  and that is the intended state, not a gap in this report.
- **§6-08, §6-13, §6-16 — the digital side of the analog boundary.** These
  three are obligations on *this* repo's UTMI layer: the pad-side control and
  status signals it must present. `rtl/usb_utmi_top.v` declares ports for
  §6-08 (`tx_drive_en`, `tx_oe`, `tx_dp`, `tx_dn`) and for the digitized
  pad-level inputs behind §6-13 (`dp`, `dm` → `LineState`). For §6-16 there
  is no pull-up-enable output port at all: `TermSelect` arrives as a UTMI
  input and that module's header states it has no consumer inside this repo
  — its consumer is the sibling termination block — so its synchronized net
  is an attachment point for a future consumer, not a driven control
  interface. Existing
  RTL-level simulation of those ports is *adjacent* evidence, not row
  evidence — see §4 for exactly what it is and why it does not close a row.

## 3. Per-corner results from the landed records (toolchain-smoke scope)

**Read this table with §1's scope statement attached to every cell.** It
characterizes `rtl/utmi_stub.v` — nine flip-flops — not the USB 2.0 PHY. It
is reproduced here because the report would otherwise be citing records
without saying what is in them.

| Corner | Current record | Fmax | Synth cells | Synth area (µm²) | Die (µm²) | Core (µm²) | Util (%) | Wirelength (µm) | STA verdict | DRC | LVS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ss_n40C_1v60` | `20260915-113028-7d56be5-ss_n40C_1v60` | not derivable | 9 | 225.216 | 768.953 | 500.48 | 50.25 | 407 | `unconstrained` | clean (0) | match |
| `ss_100C_1v60` | `20260915-113028-7d56be5-ss_100C_1v60` | not derivable | 9 | 225.216 | 768.953 | 500.48 | 50.25 | 407 | `unconstrained` | clean (0) | match |
| `tt_025C_1v80` | `20260915-132956-9281bc4-tt_025C_1v80` | not derivable | 9 | 225.216 | 768.953 | 500.48 | 50.25 | 407 | `unconstrained` | clean (0) | match |
| `tt_100C_1v80` | `20260915-113028-7d56be5-tt_100C_1v80` | not derivable | 9 | 225.216 | 768.953 | 500.48 | 50.25 | 407 | `unconstrained` | clean (0) | match |
| `ff_n40C_1v95` | `20260915-113028-7d56be5-ff_n40C_1v95` | not derivable | 9 | 225.216 | 768.953 | 500.48 | 50.25 | 407 | `unconstrained` | clean (0) | match |
| `ff_100C_1v95` | `20260915-113028-7d56be5-ff_100C_1v95` | not derivable | 9 | 225.216 | 768.953 | 500.48 | 50.25 | 407 | `unconstrained` | clean (0) | match |

Also identical across all six corners: `route_drc_violation_count: 0`,
`antenna_violation_count: 0`, `clock_skew_ns: 0`, extraction
`33 nets / 25 pins / 0 devices`, LVS `error_count: 0` with the single
warnings-only `topology.power_only_pruned` mismatch every record carries, and
the synthesized cell breakdown `9× sky130_fd_sc_hd__dfrtp_1`.

### Fmax — why the column says "not derivable"

Every record's `timing.verdict` is `unconstrained` and every timing field is
OpenSTA's unconstrained sentinel, literally `1e+39` ns, at every corner.
`utmi_stub` is nine flip-flops whose D inputs are primary input ports and
whose Q outputs are primary output ports: there is no register-to-register
path to time, and neither `klt place-and-route` nor `klt sta` exposes
`set_input_delay`/`set_output_delay` or a caller-supplied SDC
([klayout-tools#1865](https://github.com/2AMLogic/klayout-tools/issues/1865)).
`1e+39` is a positive number, so a naive `wns >= 0` gate would read it as
enormous margin; `flow/check_records.py` refuses any record that calls it a
pass, and so does this report. **No Fmax figure is available at any corner,
for the stub or for anything else.**

### Area — what the numbers are and are not

The area columns are real measurements of the stub. They are identical across
all six corners because the design is nine flip-flops of a single cell type:
synthesis was run per-corner against that corner's own liberty deck
(`sky130_fd_sc_hd__<corner>`, hashes in each record) and mapped the same nine
`dfrtp_1` instances every time, and P&R was likewise re-run per corner from
the same netlist with the same seed (`1`), producing an identical floorplan.
This is expected for a design this trivial; it is not a sign that corners
were shared or copied.

### Power — not measured anywhere

**No committed record contains a power number, at any corner.** The flow has
six stages (synthesis, P&R, STA, extraction, LVS, DRC) plus #37's
functional-verification stage, and none of them performs power analysis.
At the revision this report was generated against there was also no PDN at
all — `flow/request-par-utmi_stub.json` omitted `power`, so no power grid, no
tapcell insertion and no explicit filler placement. **Issue #59 changed
that**: the P&R request now declares a `power` block and the records minted
after it carry a real grid plus `klt lvs`'s `power_connectivity: match`
verdict (see [`flow/README.md`](../flow/README.md) → "The power-connectivity
rule"). That is a *connectivity* verdict and nothing more — it changes
nothing in this section's headline, because no stage in the flow performs
power analysis either before or after. The post-layout functional run also
compiled the cell library **without** `USE_POWER_PINS`, to match the
as-built netlist's port list. Power is unmeasured, not "measured and fine".

### Post-layout functional verification (record `…-9281bc4-tt_025C_1v80`)

- `functional_verification.status: pass`, 2 of 2 tests, 0 failed, 0 skipped,
  `random_seed: 1`, Icarus 13.0 + cocotb 2.1.0.
- Design under test: `layout/utmi_stub.asbuilt.v` — the as-built gate-level
  netlist, which that record's own LVS stage proves structurally equivalent
  to `layout/utmi_stub.extracted.spice`.
- Testbench: `verification/test_utmi_stub.py`, unmodified from the pre-layout
  run — re-targeted at a different design under test only.
- `sdf_back_annotation: false`. No post-route SDF exists for this design, so
  this is a zero-delay functional-only re-verification, **not** a
  timing-annotated one.
- Nominal corner only: this stage exists at `tt_025C_1v80` and nowhere else.
  The other five corners have no functional-verification stage.

It closes nothing in §6. It is evidence that the post-layout
re-verification *pipeline* works, on the stub.

**Superseded by issue #59's PDN re-run, and not yet re-minted (issue #63).**
That record names the pre-PDN `layout/utmi_stub.asbuilt.v` as an input, and
the re-run replaced both the netlist and the nominal-corner record, so the
current nominal record carries no `functional_verification` stage. The claim
above stands as history against the netlist it names, and as nothing about
the committed netlist today.

### Standing caveats that travel with every DRC/LVS verdict above

- The DRC deck is `klt`'s curated sky130 deck (47 rules), not the PDK-native
  signoff deck, with ten enumerated coverage gaps pinned by content hash in
  [`flow/drc-deck-coverage.json`](../flow/drc-deck-coverage.json). Each run
  additionally reports its own per-run coverage: for these records, 22 rules
  never executed (their layers are absent from the stream) and 18 layers
  present in the stream that no rule references. A `clean` verdict must be
  read together with both numbers.
- LVS is a KLayout `NetlistComparer` graph-isomorphism compare against P&R's
  own as-built netlist, not against the pre-CTS synthesis netlist.
- Upstream tool gaps filed while producing these records:
  [#1865](https://github.com/2AMLogic/klayout-tools/issues/1865),
  [#1866](https://github.com/2AMLogic/klayout-tools/issues/1866),
  [#1867](https://github.com/2AMLogic/klayout-tools/issues/1867),
  [#1868](https://github.com/2AMLogic/klayout-tools/issues/1868).

## 4. The real UTMI RTL: what exists, and what it is not evidence of

The digital UTMI layer is implemented and simulated, and that is genuinely
different from the stub. It is still not §6 row evidence, for a specific
reason: **no physical-flow record names it**.

- What exists: `rtl/usb_utmi_top.v` (the integration top, issue #52/PR #53)
  over `rtl/usb_tx_serializer.v` / `rtl/usb_rx_path.v` and their submodules,
  with cocotb testbenches under `verification/`
  (`request-usb-utmi_top.json`, `request-usb-rx.json`, `request-usb-tx.json`,
  `request-usbfs-model.json`, plus the stub's own) run in CI via
  `npm run check:ci` — see
  [`verification/README.md`](../verification/README.md).
- What that is: RTL-level functional simulation against a behavioral
  ideal-transceiver model, which is exactly the floor `spec/usb2-phy.md` §7
  sets for this milestone.
- What that is **not**: a synthesis, place-and-route, timing, LVS, DRC or
  post-layout result for the real datapath, at any corner. Grep the records
  and every `provenance.inputs` entry is `rtl/utmi_stub.v`; none is
  `rtl/usb_utmi_top.v`. And an RTL simulation against a behavioral model
  cannot, even in principle, evidence an electrical row like §6-04's voltage
  swing or §6-05's output resistance.

The gap that would move §6-08/§6-13/§6-16 off `NO EVIDENCE` is a
physical-flow experiment whose `design.hdl_toplevel` is `usb_utmi_top`,
`design.anchors_design_claim: true`, under its own experiment slug (the
`smoke-utmi_stub` slug is reserved for the plumbing experiment —
`flow/README.md`: "Real RTL gets its own slug"). No such experiment exists as
of `ee9611b`.

## 5. Provenance

This report is a derived artifact. Everything below is re-derivable with the
commands in §6.

**Generated against**: `main` @ `ee9611b` (`ee9611bdc8d14c2f1b02afaa63db4a627688cf34`).

**Cited evidence records**, hashes as listed in
[`flow/smoke-utmi_stub/records/MANIFEST.sha256`](../flow/smoke-utmi_stub/records/MANIFEST.sha256):

| Record | sha256 |
|---|---|
| `20260915-113028-7d56be5-ff_100C_1v95.md` | `0d37a87e3e89f15f9ff7f4c0b95ae0b31f80f1cd8c4253a734b3ea0e5ef22bc1` |
| `20260915-113028-7d56be5-ff_n40C_1v95.md` | `d378ab259eb3196f048dc7fbbfe30fc1990c7b462eb92ca31173b5534d811892` |
| `20260915-113028-7d56be5-ss_100C_1v60.md` | `626b79f1452f8ed8cf87e1110a237cd8aa9e531896ce69f1fe4d339b31d0c738` |
| `20260915-113028-7d56be5-ss_n40C_1v60.md` | `976c49affcf28a98996da47d1dd48a16ee85ef6539ce1e45b1824b673c4c671c` |
| `20260915-113028-7d56be5-tt_025C_1v80.md` | `a428a1b2b9b86eaf480543ae5ef8bd98540b460b215593360f569b2cfd803849` |
| `20260915-113028-7d56be5-tt_100C_1v80.md` | `417bd4c25748e73ddc911bad037cf005b185f3a201d802530e1c128be6b4aa3c` |
| `20260915-132956-9281bc4-tt_025C_1v80.md` | `99138f03129d4ff503fae4860254eb3e40f0b2518e88983f2dbe46499d0059b1` |

**Commits behind those records**: `9281bc4` (#11 / PR #55, six-corner sweep,
flow run at revision `7d56be5`) and `6cb5cc6` (#37 / PR #57, post-layout
functional verification, flow run at revision `9281bc4`). A record's
`git_revision` is the revision the flow *ran at* — necessarily the parent of
the commit that adds it.

**RTL sources on `main` @ `ee9611b`**, with the record that measures each:

| Source | sha256 | Measured by |
|---|---|---|
| `rtl/utmi_stub.v` | `b11cf0e00737eff6a01a76a37e08a0508a22827a1a438c3194d891c31750d548` | all seven records (`provenance.inputs`) |
| `rtl/usb_utmi_top.v` | `da74d9a87c09317719cff4be9a2ebf315038bddab7336c25725c811bf2a290c1` | no physical-flow record |
| `rtl/usb_tx_serializer.v` | `62f097bcb5c4feee2d1f6ce20f3744fc8d7898ac34a9424fa487a9529deceaca` | no physical-flow record |
| `rtl/usb_tx_framer.v` | `ee88fd2b593fa631a212d41fd00034422e7a8e99caaee96184d943475080952e` | no physical-flow record |
| `rtl/usb_bit_stuffer.v` | `8987568b5bf36d0bfa649c2cb8bfbe7c06a2a3c22df3491d5548820a917ce0c4` | no physical-flow record |
| `rtl/usb_nrzi_encoder.v` | `9ab1f95a877aab538d13784fa02e7c260d173cac851b4c9e9fa78d25ea01bf39` | no physical-flow record |
| `rtl/usb_rx_path.v` | `a87bf71fc3eca750ef3ec1a1f3e8997d7209a4a7ecb4467398d9d138ad696e75` | no physical-flow record |
| `rtl/usb_rx_framer.v` | `2cec795c15feae44da651c8b55063c816bed2398cdfb9760ba6884bc9d6e286b` | no physical-flow record |
| `rtl/usb_rx_cdc.v` | `215cf4620894de0fe36df0b6fe92d1a012528de19a340a2bf2d6565907407d66` | no physical-flow record |
| `rtl/usb_bit_destuffer.v` | `03fc67bcec9eaece476ed46a7cb41fab4000bcd49e18cc7c7bf60f016f1ffc51` | no physical-flow record |
| `rtl/usb_nrzi_decoder.v` | `aa7eef14d8b00c6969ff375007ce34b960a9e2bd8f337d18590d902edad426c3` | no physical-flow record |
| `rtl/usb_bit_sync.v` | `361f9c615d3ef030584384de2f04fe29f43f4b9eb9da8ab95e3e15afdbb3a145` | no physical-flow record |
| `rtl/usb_linestate.v` | `beb5a2f4c30e74d7cd883de9d241edccf5cd8631fcfd0df056d277b2234222a7` | no physical-flow record |

`rtl/utmi_stub.v`'s hash above matches the `provenance.inputs` hash recorded
in all seven records, so the freshness rule holds as of `ee9611b`: the
evidence still describes the source it names. The other twelve files appear
in no record's `provenance.inputs` at all — that is the "no design-anchored
evidence" finding, stated as a hash comparison rather than a claim.

**Spec source indexed**: `spec/usb2-phy.md` §6 as of `ee9611b`, 16 table
rows. If that table gains, loses, or reorders a row, §2's `§6-NN` handles
shift and this report must be regenerated.

## 6. Refreshing this report

This report is a manual aggregation, refreshable by the procedure below (a
lint/CI staleness check can follow later; there is none today, so re-run this
whenever `spec/usb2-phy.md` §6 or `flow/*/records/` changes).

```bash
# 1. Validate the evidence trail first. This enforces the append-only rule,
#    the MANIFEST hashes, and the freshness rule (every provenance.inputs
#    hash re-checked against the current tree). If it fails, fix that before
#    touching this report -- a stale record must be re-run, never re-hashed.
python3 flow/check_records.py

# 2. Re-derive the per-corner table in section 3.
python3 - <<'PY'
import glob, json, re
for path in sorted(glob.glob("flow/smoke-utmi_stub/records/*.md")):
    meta = json.loads(re.search(r"<!-- record-meta\n(.*?)\n-->", open(path).read(), re.S).group(1))
    st, par = meta["stages"], meta["stages"]["place_and_route"]
    print(" | ".join(str(x) for x in (
        meta["corner"], meta["record_id"], meta["design"]["anchors_design_claim"],
        st["synthesize"]["instance_count"], st["synthesize"]["area_um2"],
        par["die_area_um2"], par["core_area_um2"], par["utilization_pct"],
        par["wirelength_um"], meta["timing"]["verdict"], meta["timing"]["worst_slack_ns"],
        st["drc"]["status"], st["lvs"]["status"], meta["supersedes"])))
PY

# 3. Re-derive section 2's row list from the spec (never edit spec/ to fit).
#    Prints the 16 data rows, in order -- section 2's §6-NN handles are just
#    this list numbered from 1.
sed -n '/^## 6\./,/^## 7\./p' spec/usb2-phy.md | grep '^| ' | tail -n +2

# 4. Re-derive section 5's provenance block.
git rev-parse HEAD
cat flow/smoke-utmi_stub/records/MANIFEST.sha256
sha256sum rtl/*.v

# 5. Re-derive "which sources any record actually measures".
python3 - <<'PY'
import glob, json, re
measured = set()
for path in glob.glob("flow/smoke-utmi_stub/records/*.md"):
    meta = json.loads(re.search(r"<!-- record-meta\n(.*?)\n-->", open(path).read(), re.S).group(1))
    measured.update(i["path"] for i in meta["provenance"]["inputs"] if i["path"].startswith("rtl/"))
print("measured by at least one record:", sorted(measured))
PY
```

**Rules for a refresh**, so a later pass cannot quietly launder the scope:

1. A record may only move a §6 row off `NO EVIDENCE` if its
   `design.anchors_design_claim` is `true` **and** its `design.sources` name
   the RTL (or analog netlist) the row is actually about.
2. A `smoke-utmi_stub` record never evidences a spec row, whatever its
   verdicts say.
3. `unconstrained` timing is never an Fmax and never a pass.
4. Nothing under `spec/` is edited to make this report's verdicts look
   better. Spec changes go through `spec/` with a decision record.

## 7. Relationship to `docs/baseline.md`

[`docs/baseline.md`](baseline.md) stays as the original point-in-time
synthesis/cell-count record for `utmi_stub.v` (2026-08-05) and for
`usb_tx_serializer.v` (2026-08-08), both at the nominal corner only and both
predating `flow/`'s evidence-record convention. It is history, and useful as
the only synthesis number this repo has for real TX-path RTL — that
`usb_tx_serializer.v` figure (142 cells, 1518.9568 µm², `tt_025C_1v80`) is a
`klt synthesize` measurement, not a record under the `flow/` convention, and
carries no corner sweep, no P&R, no timing, no LVS/DRC and no content-hashed
provenance. It is therefore cited here as background, not as §6 row evidence.
This report is the authoritative characterization summary.
