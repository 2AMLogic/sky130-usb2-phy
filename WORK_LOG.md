# Work Log

Chronological record of merged PRs and closed issues, maintained automatically
by the Guide triage agent. Newest entries first.

### 2026-10-09

- **PR #125**: feat: sky130 trimmed D+ pull-up schematic and 45-corner tolerance record (#113)
- **Issue #113** (closed): analog port: trimmed D+ pull-up and termination to sky130 - schematic and 45-corner tolerance testbench
- **PR #124**: analog port: single-ended D+/D- receivers to sky130 with 45-corner threshold evidence (#110)
- **Issue #110** (closed): analog port: single-ended receivers (D+ and D-) to sky130 - schematics and 45-corner threshold testbenches
- **PR #122**: analog port: differential receiver to sky130 with 45-corner x 3 CM evidence (#111)
- **Issue #111** (closed): analog port: differential receiver to sky130 - schematic and 45-corner sensitivity testbench at three common-mode points
- **PR #120**: feat: sky130 analog sim harness and 45-corner PVT matrix (#109)
- **Issue #109** (closed): analog port: bootstrap the sky130 analog sim harness and 45-corner PVT matrix (prerequisite for the #106 block ports)
- **PR #114**: docs: plan the gf180-usb2-phy analog port; lift the no-analog scope rule (#106)
- **Issue #106** (closed): scope: port the analog blocks from gf180-usb2-phy into this repo (operator ruling 2026-10-08); lift the no-analog rule and write the porting plan

### 2026-10-08

- **Issue #104** (closed): Digital T1 item 1: synthesize the real UTMI datapath (usb_utmi_top) and commit its gate-level netlist
- **PR #107**: Digital T1 item 1: synthesize usb_utmi_top and commit its gate-level netlist

### 2026-10-03

- **Issue #89** (closed): Guard telemetry: bare rm -rf / (filesystem-root wipe) DENY confirmed correct
- **Issue #90** (closed): Guard telemetry: rm -rf on unresolvable variable target fails closed correctly (rm-scope-unresolved-var)
- **Issue #99** (closed): Guard friction: worktree-write-confinement denies /tmp scratch writes (4+ hits)
- **Issue #85** (closed): Guard trigger review: stash-scope:create-redirect DENY on worktree git stash (keep flagged)
- **Issue #77** (closed): Guard trigger review: gh-api-rawfield-body-literal-at DENY on -f body=@file (keep flagged)

### 2026-09-29

- **Issue #94** (closed): Auditor Capability Request: cocotb unavailable in klt's tool venv on loom-worker fleet host (Python 3.14.6, recurrence of #42)
- **PR #101**: docs: record unpinned cocotb working on a Python 3.14 klt env
- **Issue #95** (closed): Remove unused Fraction import: verification/test_usb_rx.py:71
- **PR #98**: Remove unused Fraction import in test_usb_rx.py
- **PR #97**: docs: stop implying cocotb must be exactly 2.0.1 in environment-setup
- **Issue #91** (closed): Remove 3 dead imports in flow/run_flow.py and verification/test_usb_rx.py
- **PR #93**: Remove 3 dead imports in flow/run_flow.py and verification/test_usb_rx.py

### 2026-09-26

- **Issue #87** (closed): Guard trigger review: loom:installed-file-write false-denies a same-command cd-then-relative-write into a scratch dir
- **PR #88**: test: add regression test + resync pin for the #87 installed-file-write false DENY

### 2026-09-22

- **Issue #81** (closed): docs: rtl/README.md cites DR-0001 'Decision 6 (bit-rate timing)' which does not exist
- **PR #83**: docs: re-point usb_tx_serializer DR-0001 citation from nonexistent Decision 6 to Decision 1

### 2026-09-21

- **Issue #79** (closed): 2am: reuse rule 9 — reconcile the shared USB protocol RTL with gf180-usb2-phy — this repo is master by lineage; the twin vendors with stamps
- **PR #80**: docs: record DR-0002 shared-RTL classification and canonical interfaces
- **Issue #76** (closed): Guard trigger review: worktree-write-confinement DENY on /tmp scratch output for klt erc comparisons
- **PR #78**: docs: establish .loom/tmp/ in-worktree scratch convention for agent sessions
- **Issue #73** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **PR #75**: feat(signoff): grade this block's T1 state via a klt signoff block manifest
- **Issue #72** (closed): T1 item 11 (power delivery, structural): no klt erc supply spec or report in this repo
- **PR #74**: feat: add T1 item 11 erc supply spec and report for utmi_stub

### 2026-09-19

- **Issue #64** (closed): Regenerate docs/characterization.md against the post-PDN records (#59 superseded the six it indexes)
- **PR #71**: docs(characterization): regenerate against post-PDN and functional-verification records
- **Issue #67** (closed): flow/check_records.py: the power-connectivity gate keys on a record field that is not required, so omitting the P&R power echo silently skips it
- **PR #70**: fix(flow): close the silent-skip path in check_records.py's power-connectivity gate
- **Issue #66** (closed): flow: regenerated LVS evidence still corresponds VGND to TXREADY — disclose it and file the tool gap upstream
- **PR #69**: docs(flow): disclose the live VGND→TXREADY LVS correspondence artifact (#66)
- **Issue #63** (closed): postlayout_verify_utmi_stub.py mints no record, so #59's PDN re-run left the current nominal record with no functional_verification stage
- **PR #68**: feat(flow): mint the post-layout functional-verification record from run_flow

### 2026-09-18

- **Issue #59** (closed): utmi_stub.gds has no power grid and six LVS reports say 'match' (one maps VGND to TXREADY) — the flow template will pass this hole to the real UTMI layer
- **PR #65**: feat(flow): give utmi_stub a real power grid and gate LVS on it (#59)
- **Issue #62** (closed): Guard-decision review: quoted $(...) redirect target with an embedded pipe mis-parsed as relative path, false-positive worktree-write-confinement DENY
- **Issue #60** (closed): Same protocol logic, two incompatible implementations: usb_nrzi_encoder.v diverged across PDKs
- **PR #61**: docs(rtl): record sibling-PDK divergence and why the sky130 side is deliberate

### 2026-09-15

- **Issue #38** (closed): Add a characterization report aggregating per-spec-row PVT results (T1 item 8)
- **PR #58**: docs: add the per-spec-row characterization report (#38)
- **Issue #37** (closed): Post-layout verification: re-run functional suites against the extracted netlist (T1 item 7, digital)
- **PR #57**: feat(flow): re-verify utmi_stub against the post-layout netlist (#37)
- **Issue #56** (closed): Guard-decision review: rm-scope-unresolved-var (allowlist/refine proposal)
- **Issue #11** (closed): Bootstrap the physical flow: synthesis → P&R → GDS → DRC/LVS, multi-corner timing, evidence records and CI
- **PR #55**: feat(flow): bootstrap the digital physical flow — synth→P&R→GDS→DRC/LVS, 6-corner timing, append-only evidence records and CI
- **Issue #54** (closed): Curator dep-recheck idempotency: CONCLUSION_HASH is not stable across passes, causing heartbeat-comment spam

### 2026-09-09

- **Issue #52** (closed): RTL: the real UTMI digital top — integrate usb_tx_serializer + usb_rx_path behind DR-0001 Decision 4's full port table, add the TX-side 30↔144 MHz CDC synchronizers, and verify it end-to-end with a DP/DM loopback cocotb suite
- **PR #53**: RTL: usb_utmi_top — the UTMI digital top (TX+RX integration, TX-side 30↔144 MHz CDC, DP/DM loopback suite)

### 2026-09-04

- **Issue #47** (closed): Champion: Merge-Risk Hold Digest

### 2026-08-16

- **Issue #42** (closed): Auditor Capability Request: cocotb unavailable in klt's tool venv on this host (Python 3.14, cocotb needs <=3.13) -- Layer 2 RTL tests unvalidated
- **Issue #39** (closed): Add a CI workflow that runs the verification harness on every PR (T1 item 10)
- **PR #43**: ci: add GitHub Actions workflow running the verification suite on every PR
- **Issue #34** (closed): Decompose the T1 re-read's failing items (#29) into dispatchable issues
- **Issue #41** (closed): scratch permission probe - safe to delete
- **Issue #35** (closed): Docs: dedupe hand-maintained interface-requirements table in spec/architecture.md
- **PR #36**: docs: dedupe interface-requirements table in spec/architecture.md

### 2026-08-15

- **Issue #29** (closed): T1/bronze checklist re-read against current evidence (2026-08-15)
- **Issue #25** (closed): Wire up package.json check scripts to real verification, or remove them: they currently lie about running checks
- **PR #26**: fix: wire package.json check scripts to real verification, or remove them

### 2026-08-11

- **Issue #19** (closed): Guard: worktree-write-confinement-unresolved-var denies mktemp-rooted rm cleanup it cannot statically resolve
- **Issue #20** (closed): Guard: catastrophic rm -rf pattern matches inline markdown prose inside a create-issue.sh --body heredoc
- **Issue #22** (closed): Guard: stash-scope asks are correct-as-designed, not false positives (keep flagged)

### 2026-08-08

- **Issue #12** (closed): RTL: FS transmit path — UTMI TX handshake, framing, bit stuffing, NRZI encode
- **PR #21**: feat(rtl): FS transmit path -- UTMI TX handshake, framing, bit stuffing, NRZI encode
- **Issue #13** (closed): RTL: FS receive path — 12× oversampled bit/edge synchronizer, NRZI decode, destuffing, LineState and the UTMI crossing
- **PR #18**: feat(rtl): FS receive path — bit/edge sync, NRZI decode, destuffing, LineState, UTMI CDC
- **Issue #16** (closed): Guard false positive: worktree-write-confinement misreads Python >>/>>= as shell append-redirect inside interpreter-fed heredocs
- **PR #17**: fix: split shell vs script interpreters in guard heredoc masking
- **Issue #10** (closed): Behavioral ideal-transceiver model and DP/DM protocol reference — the testbench substrate spec §7 requires
- **PR #15**: feat: add usbfs behavioral ideal-transceiver model and FS protocol reference
- **Issue #9** (closed): Spec gaps: the PLL jitter budget binds the wrong metric, the 30 MHz UTMI clock has no source, and there is no PVT envelope
- **PR #14**: docs: add decision record for PLL jitter metric, UTMI clock, CDC, and PVT gaps

### 2026-08-05

- **Issue #7** (closed): Missing flow/ directory — needed as soon as the digital half is synthesized
- **PR #8**: docs: add flow/ directory for synthesis + P&R recipes
- **Issue #3** (closed): Harness bootstrap: digital verification flow, copied not reinvented
- **PR #6**: feat: bootstrap cocotb+Icarus+Yosys digital verification harness
- **Issue #1** (closed): Ratify the target spec
- **PR #5**: docs: ratify target spec into spec/usb2-phy.md
- **Issue #2** (closed): Architecture and partitioning: what this block is made of, and which pieces come from siblings
- **PR #4**: Add architecture and partitioning spec (spec/architecture.md)
