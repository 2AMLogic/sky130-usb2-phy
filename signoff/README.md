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
| [`evidence/`](evidence/) | Hand-rolled **generic evidence envelopes** — the opt-in wrapper for a record no `klt` verb produces. Only T1 item 8 accepts one. |
| [`check.py`](check.py) | **The gate.** What CI runs on every PR and push: it re-grades the manifest and fails on any drift between what is committed and what the current tree actually grades to (see "What the grader cannot check" below). |
| [`toolchain.json`](toolchain.json) | The `klt` build that grades this block, pinned — and why that pin is the *released registry wheel*. |
| [`design-evidence-tiers.md`](design-evidence-tiers.md) | Vendored copy of the upstream checklist, pinned at klayout-tools commit `31a3e3c4` (file sha256 `c7a1e7e10627fae396007e0ff951734f37d95028b8f49f2e21e802e9f552f318`), supplied to the grader via `--tiers-doc` so the 11-item checklist renders all its rows. See [`toolchain.json`](toolchain.json) for the known gap it exists to close. |

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
- **Analog partition** — the PLL, current-mode drivers, differential
  receivers, squelch/envelope detector, and pad-ring pull-up/down. These are
  **explicitly out of scope to design here** (`CLAUDE.md` scope discipline):
  they come from sibling canary repos that have not landed, and this repo
  carries no committed analog content for them
  ([#40](https://github.com/2AMLogic/sky130-usb2-phy/issues/40)) —
  `design/`, `sim/`, `layout/`, and `measurements/` are placeholder-only by
  design.

`klt 0.5.0` renders **both columns for every T1 item** for a `mixed-signal`
manifest (even the kind-independent ones render twice, once per partition):
`t1_item_count` is 22, not 11.

## The current verdict: 2 of 22 rows met

`tier: null`. Every per-item verdict below is read from
[`signoff-report.json`](signoff-report.json) — not hand-derived. An
honest near-all-`unmet` mechanical reading is the desired outcome, not a
disappointment: this block's own characterization
([`docs/characterization.md`](../docs/characterization.md)) already states
that **zero of the 16 spec rows have design-anchored evidence today**, and a
grader that said otherwise would be lying.

| Item (partition) | Verdict | Why — and what would change it |
|---|---|---|
| 1 — Design sources (analog) | `unmet` / `no_evidence` | No analog content exists in this repo (#40); when the sibling canaries land schematics/netlists here, cite them. |
| 1 — Design sources (digital) | `unmet` / `no_evidence` | The real UTMI RTL is committed (`rtl/usb_*.v`) but has **never been through the physical flow** — no synthesized gate-level netlist for it exists anywhere in the tree. The only committed synthesis output belongs to the `flow/smoke-utmi_stub` toolchain experiment (`rtl/utmi_stub.v`, nine flip-flops, no USB behaviour), whose records all carry `design.anchors_design_claim: false` ([`flow/README.md`](../flow/README.md)) — citing it for this row would make it green for a design it explicitly does not describe. What changes this: run `klt synthesize` on the real RTL and commit the netlist (the flow's stage-1 request, retargeted). |
| 2 — Layout (analog) | `unmet` / `no_evidence` | No analog layout exists (#40). |
| 2 — Layout (digital) | `unmet` / `no_evidence` | `layout/utmi_stub.gds` is the stub's output, not the block's; nothing to cite for the real datapath until it is routed. |
| 3 — DRC clean (both) | `unmet` / `no_evidence` | The only committed `klt drc` envelopes are the smoke-utmi_stub sweep's six (`flow/smoke-utmi_stub/artifacts/*/drc-report.json`) — real evidence about the *toolchain*, explicitly **not** about the block, so they are deliberately uncited. What changes this: a DRC report against the real UTMI layout when it exists, cited with a `content_hash` pin. |
| 4 — LVS clean (both) | `unmet` / `no_evidence` | Same shape as item 3: six stub LVS reports exist (`…/lvs-report.json`), none of which anchor a design claim. (They also carry the disclosed VGND↔TXREADY correspondence artifact, #66/#69 — one more reason not to paint the block's row green with them.) |
| 5 — Full corner verification (analog) | `unmet` / `no_evidence` | No analog design exists to simulate (#40). |
| 5 — Full corner verification (digital) | `unmet` / `no_evidence` | The cocotb suites (`verification/test_usb_*.py`) are bit-exact **pre-layout functional** verification, run at a single nominal zero-delay model — no multi-corner STA has ever run on the real RTL; the only six-corner `klt sta` reports in the tree are the stub's. Item 5 asks for the corner matrix against a ratified spec; when the real datapath is synthesized and timed across the six committed corners (`spec/decision-records/0001-…`, mirrored in `flow/corners.json`), cite the `klt sta` and `klt functional-verification` envelopes here. What exists today is honestly *less* than the row requires, so the row stays grey. |
| 6 — Monte Carlo evidence (both) | `unmet` / `no_evidence` | **Stated explicitly, as the checklist demands:** this block's ratified spec has **no statistical spec row** — the frequency-tolerance/jitter requirements of `spec/usb2-phy.md` and decision record 0001 are deterministic PVT-corner bounds, not accuracy/offset/matching rows, so no Monte-Carlo (`klt yield`) evidence applies today. There is equally no `klt yield` report to cite. |
| 7 — Post-layout verification (analog) | `unmet` / `no_evidence` | No analog layout exists to post-layout-verify (#40). |
| 7 — Post-layout verification (digital) | `unmet` / `no_evidence` | The only post-layout functional record in the tree (`20260919-001148-0f7636d-…`) re-verifies the *stub* against its post-PDN netlist — `design.anchors_design_claim: false`. Item 7 for the real datapath needs an SDF-annotated `klt functional-verification` run over its (not-yet-existing) post-route netlist, or a `klt pex` report — and a citable `pex` envelope, per item 7's own kind restriction. |
| 8 — Characterization report (both) | **`met`** | Cites [`evidence/characterization-report.json`](evidence/characterization-report.json) — a hand-rolled `kind: generic` envelope (the one item this wrapper shape is allowed to satisfy) wrapping the committed, current [`docs/characterization.md`](../docs/characterization.md), with the envelope's `provenance.input.content_hash` pinning that file (sha256 `9ef3d0ed…`) and the manifest citing the same pin. Both partition rows read from the one bare `"8"` key (the doc's mixed-signal guidance: one citation, both partitions' rows). **Disclosed, not omitted:** the characterization report's own headline is that zero spec rows have design-anchored evidence — its per-row content is an honest `NO EVIDENCE` verdict, not measured performance. The envelope asserts the item 8 *artifact* exists, is committed and current — it does **not** assert that any spec row is characterized, measured, or passing. |
| 9 — Testbenches shipped (both) | `unmet` / `no_evidence` | **Uncited on purpose.** The committed cocotb suites (`verification/`, cold-start documented in [`verification/README.md`](../verification/README.md) and `docs/environment-setup.md`; PDK revision pinned in `docs/baseline.md`) are human-auditable evidence this row's *content* is satisfied — but item 9 has no `klt` verb behind it, the grader cannot check topical relevance of *any* passing envelope cited here, and minting a hand-rolled wrapper to turn the row green is exactly the failure mode this manifest exists to prevent. If a future `klt` release adds a testbench-shipping evidence kind, cite it then. |
| 10 — Repo hygiene (both) | `unmet` / `no_evidence` | **Uncited on purpose, same reason as item 9.** Human-audited: README states the block and its spec table and how to reproduce results; Apache-2.0 LICENSE; CI (`.github/workflows/ci.yml`) runs the verification suite and the flow evidence lint on every PR and push — and, from this PR, the `signoff` freshness job that re-grades this very directory. |
| 11 — Power delivery, structural (analog) | `unmet` / `no_evidence` | New upstream item (klayout-tools#2025); it renders a row here because the vendored checklist supplies the 11-item skeleton (see [`toolchain.json`](toolchain.json)). This repo has **no `klt erc` supply spec or report for the block** — companion issue [#72](https://github.com/2AMLogic/sky130-usb2-phy/issues/72) lands the stub's artifact pair, which anchors no design claim and would not make *this* row citable anyway; the real UTMI/PHY layout does not exist yet. What changes this: an `erc`+`lvs` citation chain per the analog column, against a real layout. |
| 11 — Power delivery, structural (digital) | `unmet` / `no_evidence` | Same row, digital partition: needs the `place-and-route` + `erc` + `lvs` citation chain over a genuinely-routed real datapath (`power.pdn: true`, `power_connectivity.status: "match"`), none of which exists for the block. |

Items 1, 2, 9 and 10 are uncited by deliberate choice, and items 3, 4, 5, 7
and 11 are uncited because the only envelopes that exist for them describe
the smoke-utmi_stub experiment — which by its own convention anchors no
design claim. In both cases the uncited row is the honest machine-readable
statement: *no check backs this claim*, which is what `klt signoff` renders,
with a `reason`, instead of guessing.

**2 of 22 is a lower number than the #29 hand-read's "1/10 pass (1 N/A)", and
both are honest reads of different questions.** The hand-read asked "does
this repo contain the artifact the item describes?" — and for item 9 it
largely does. The manifest asks "is there a passing, fresh, machine-readable
envelope of the kind this item accepts?" — and the second question is the one
a downstream consumer (or the fleet roll-up) can actually verify without
taking this repo's word for it. Where this README and `signoff-report.json`
disagree, the report wins and this prose is the thing that is wrong.

## What the grader cannot check

`klt signoff` compares a citation's manifest pin against *the envelope's own
recorded hash*; it never re-opens the underlying artifact, so two
hand-written hashes agreeing with each other proves nothing. For the generic
wrapper that is the only citation today, `check.py` closes that hole itself:
it re-hashes `docs/characterization.md` on every run and fails if the
envelope's pin has drifted (verified by negative control — a one-line
mutation of the report fails the gate with the re-pin instructions). Two more
gaps are deliberate disclosures rather than silent assumptions:

- **Native-citation re-hashing.** When a future citation names a `klt
  drc`/`lvs`/`pex` envelope, `check.py` must grow a repo-side re-hash of
  the cited *input artifact* (the GDS/netlist) the way it re-hashes the
  characterization report today — `klt` through 0.5.0 does not do this
  itself (upstream: klayout-tools#2196).
- **The grading build's identity.** `check.py` hard-fails unless the `klt`
  on PATH is the pinned *released registry wheel* (`git_tag v0.5.0`,
  `is_release: true`), because same-version git snapshots have been
  observed to grade differently (klayout-tools#2216). This is why the CI
  job `pip install`s the pin instead of trusting whatever `klt` a runner
  has.

## How to re-run the grading

`klt signoff --manifest` is PDK-free — it grades committed JSON envelopes,
it does not run the gates — so grading runs anywhere:

```bash
pip install klayout-tools==0.5.0          # the pinned released wheel
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
