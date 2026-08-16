# Work Log

Chronological record of merged PRs and closed issues, maintained automatically
by the Guide triage agent. Newest entries first.

### 2026-08-16

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
