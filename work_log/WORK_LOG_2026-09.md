# Work Log Archive — 2026-09

Sections moved byte-for-byte from [WORK_LOG.md](../WORK_LOG.md) by `loom-daemon work-docs archive`.

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

