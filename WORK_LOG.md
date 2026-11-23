# Work Log

Chronological record of merged PRs and closed issues, maintained automatically
by the Guide triage agent. Newest entries first.

## Archives

- [2026-09](work_log/WORK_LOG_2026-09.md)
- [2026-08](work_log/WORK_LOG_2026-08.md)

### 2026-11-23

- **PR #450**: test(usb_rx): bound RxActive EOP deassertion by an independent window, not the trace's own shape
- **PR #449**: test(sim): route receiver 225-point variant reports through synthetic_report
- **PR #448**: test: share the synthetic campaign builder in mismatch-store tests
- **PR #446**: feat(sim): map diff-receiver-sensitivity row 6-09 limits; 45-point re-run with envelope-graded bounds
- **PR #445**: feat: warn on forked supersede chains and duplicate same-sha record tips
- **Issue #444** (closed): Share the synthetic campaign builder in mismatch-store tests
- **PR #443**: fix: keep spec-limit unit metadata consistent with the numbers it describes
- **Issue #442** (closed): check_records.py should flag forked supersede chains and duplicate same-sha tips
- **Issue #441** (closed): Replace the circular RxActive end-of-packet assertion in the receive test
- **PR #440**: docs: point analog LVS citations at the manifest-cited 6beff8e records
- **Issue #439** (closed): Build 225-point synthetic reports in receiver tests through conftest.synthetic_report
- **Issue #438** (closed): Analog-layout evidence lineage: README cites an uncited record set, stale 10-of-22 count, and a forked supersede chain from a double mint
- **PR #437**: test: pin find_row_x's chosen PMOS-row offset per leaf to exact equality
- **Issue #435** (closed): diff-driver-pex static record: the "97%" attribution figure understates its own table (98.9%)
- **Issue #434** (closed): find_row_x: the receivers' chosen PMOS-row offset rests on 1.09e-12 um of `start += GRID` float drift
- **Issue #426** (closed): Fold sim/diff-driver-pex/run.py onto the shared leaf pex runner and exact-pair gate once #416 lands
- **Issue #424** (closed): spec_limits: emitted `unit` describes raw-unit `limits` with the display unit (record table reads "4e-09 … 2e-08 ns")
- **PR #421**: fix: absorb the xhigh serpentine snap residual in one U-turn so bias resistors draw exact netlist lengths
- **PR #416**: sim: add diff-driver-pex post-layout bench for the differential_driver leaf
- **Issue #406** (closed): Reconcile xhigh poly bias resistor lengths in the driver and three receivers

### 2026-11-22

- **PR #433**: perf(layout): draw-free find_row_x() replaces throwaway Canvas churn in the PMOS row search
- **Issue #432** (closed): Stop constructing throwaway Canvas layouts inside the analog PMOS row placement search
- **PR #430**: perf(sim): scope committed_duplicates to run_dir before statting or hashing
- **PR #427**: refactor(sim): share one leaf pex runner and its exact-pair gate
- **PR #423**: feat(sim): map driver-signal-quality rows 6-06/6-07 limits; 45-point re-run with envelope-graded bounds
- **PR #422**: fix: fail spec_limits cross_check closed on unrecognised envelope statuses
- **PR #420**: refactor: share the D+ and D− single-ended receiver PEX runner
- **PR #411**: feat(sim): generate spec-row limits in the klt sim request; driver-static limit-carrying 45-point re-run (rows 6-04, 6-05)
- **Issue #428** (closed): Scope artifact_manifest.committed_duplicates to run_dir before statting and hashing tracked files
- **Issue #425** (closed): Consolidate the remaining klt pex leaf runners onto one shared harness and retire diff-receiver-pex's inline count-only equivalence gate
- **Issue #419** (closed): Share the D+ and D− single-ended receiver PEX runner
- **Issue #412** (closed): spec_limits.cross_check: an envelope limit status that is neither pass nor fail is silently uncounted

### 2026-11-21

- **PR #415**: feat: klt pex post-layout records for the single-ended receivers (PASS) and the D+ pull-up (FAIL, layout follow-up #414)
- **PR #407**: feat: grade analog leaves with curated LVS and passive geometry checks
- **Issue #400** (closed): T1 items 4 and 11 (analog): probe the curated klt lvs engine on the five leaves and record, per leaf, which LVS route can be graded met
- **Issue #403** (closed): T1 item 7 (analog): klt pex reports for the se_receiver_dp, se_receiver_dm and dplus_pullup leaves
- **Issue #414** (open): dplus_pullup layout iteration: poly-head parasitics push every trim code above the ratified window (the FAIL post-layout record's follow-up)
- 2AMLogic/klayout-tools#6990 (open, upstream): klt pex errors the whole envelope on a DUT-internal-node measurement (no portable-subset option)

### 2026-11-20

- **PR #409**: chore(signoff): re-pin grader to klayout-tools 0.9.2 and regrade
- **Issue #410** (closed): signoff CI: read the grading klt pin from signoff/toolchain.json instead of a third hand-edited copy
- **Issue #399** (closed): Re-pin the signoff grader from klt 0.9.1 to the 0.9.2 release and regrade (item 3 analog grades met, 9 -> 10 of 22)
- **Issue #193** (closed): Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)

### 2026-11-18

- **PR #396**: ci: run on merge_group and fail closed on its base ref
- **Issue #322** (closed): layout/analog: res_generic_po hardcodes head=0.8 while callers keep RES_HEAD; unused import re in differential_driver/gen.py

### 2026-11-17

- **PR #392**: feat(flow): require a netlist-delta disclosure on superseding records (rule 8f)
- **Issue #387** (closed): Minting a utmi-top record under a newer klt silently rewrites the committed netlist inside an unrelated PR
- **Issue #270** (closed): signoff item-10 README pin goes stale on every automated Guide README edit (3rd recurrence of #180/#181)
- **PR #390**: refactor(layout): hoist conflicts() and the met3 trunk/via-stack loop into gen_common
- **Issue #339** (closed): Deduplicate analog layout generators: conflicts() and net-routing loop copied into three gen files
- **PR #389**: chore(loom): resync installed Loom to v0.19.1306
- **PR #388**: refactor(verification): fold test_usb_rx expected_rx_bytes into usbfs.byte_stream_for_scenario
- **Issue #386** (closed): Fold test_usb_rx.py's expected_rx_bytes into usbfs.scenarios.byte_stream_for_scenario (third copy)
- **PR #385**: layout: deduplicate differential_driver's Ports and mos into gen_common
- **Issue #274** (closed): Deduplicate analog device geometry: differential_driver/gen.py keeps a second copy of gen_common's Ports and mos
- **PR #285**: refactor(verification): move the raw-mode and byte-stream reference helpers into usbfs
- **Issue #284** (closed): Mint a new utmi-top flow record after the #275 verification-helper dedup
- **Issue #275** (closed): Deduplicate the raw-mode / byte-stream reference helpers duplicated across two TX testbenches

- **PR #383**: docs(porting-plan): fold per-block tracking links into Done cells
- **Issue #378** (closed): docs/porting-plan.md rows 132-135 have one cell more than their 7-column header: the trailing issue-link cell is silently dropped on the forge
- **PR #381**: docs: count all three pytest legs in signoff grading recipe
- **Issue #377** (closed): signoff/README.md undercounts which check:all legs need pytest (legs 1 and 3 -> also leg 4's layer 1)
- **PR #380**: test(signoff): couple the pins-refresh hint's install line to the README recipe
- **Issue #379** (closed): Nothing couples check.py's pins-refresh install line to signoff/README.md's recipe
- **PR #376**: fix(signoff): defer pins-refresh hint PATH rules to the README recipe
- **Issue #348** (closed): signoff/check.py's pins-refresh hint still prints the venv-bin PATH form that signoff/README.md now forbids
- **PR #375**: docs: escape table-cell pipes that truncate two rows on the forge
- **Issue #371** (closed): signoff/README.md item-6 analog row: unescaped | truncates most of the cell on GitHub render
- **PR #374**: docs: add a pytest-less-host form to the signoff re-run recipe
- **Issue #349** (closed): npm run check:all cannot complete on fleet workers whose host python3 has no pytest

### 2026-11-16

- **PR #372**: docs(spec): list sim/README.md prose in DR 0008's value-coupled prose checklist
- **Issue #326** (closed): DR 0008: add sim/README.md to the 'prose that must move with the value' list (and clarify the 'two of four corners' parenthetical)
- **PR #330**: chore(loom): resync installed Loom to v0.19.1302
- **PR #369**: docs: scope signoff item-6 record-lint sample-size rule to PASS records
- **Issue #313** (closed): signoff/README.md item 6 overstates the record lint: 'sample_size.verdict other than insufficient is required' holds only for PASS records
- **PR #368**: docs: distinguish grader from CI in signoff item-2 regeneration disclosure
- **Issue #366** (closed): signoff/README.md item 2 still discloses analog regeneration as not re-run; PR #365 made it CI-enforced
- **PR #365**: ci: enforce analog GDS reproducibility in the signoff job
- **PR #364**: lint: check stored records' degraded-mode coverage clause for internal consistency only
- **PR #360**: docs: drop stale restated headline from flow/README.md characterization pointer
- **PR #359**: refactor: delete unread MANIFEST_GLOB and IDLE_STATE constants
- **PR #357**: refactor: remove dead record_kind() and INVENTORY_DIR, re-pin item 10
- **PR #340**: refactor: draw differential_receiver through the shared receiver generator
- **Issue #363** (closed): CI never regenerates the analog leaf GDS: gen.py --check is the only reproducibility oracle and runs by hand
- **Issue #358** (closed): flow/README.md still restates the retired 'zero spec rows have design-anchored evidence' characterization headline
- **Issue #336** (closed): Fold differential_receiver/gen.py build() into the shared receiver generator (~100 duplicated lines)
- **Issue #329** (closed): stored_coverage's clause check couples a landed record's lint verdict to later testbench/mc.json edits
- **Issue #319** (closed): Remove two dead module-level symbols in hash-pinned files: record_kind() and INVENTORY_DIR (carries the item-10 re-pin)
- **Issue #295** (closed): Remove four dead module-level symbols that each shadow a fact the live code re-states inline
- **PR #356**: docs: restate signoff item 8 disclosure to match characterization headline
- **PR #355**: signoff: accept artifact-store-resolved item-6 yield citations in check.py
- **Issue #335** (closed): signoff/README.md item 8 row still paraphrases characterization's old 'zero spec rows' headline
- **PR #351**: docs(signoff): attribute current item 3/6 grades to klt 0.9.1
- **PR #350**: test: share one run-manifest builder for record-render tests
- **PR #346**: signoff: re-pin grading klt from 0.8.0 to the 0.9.1 release and regrade
- **PR #342**: docs(signoff): run every check:all leg via a klt-only wrapper dir on PATH
- **Issue #325** (closed): main's strict required-status-checks policy stalls every approved PR (all 6 are MERGEABLE/BEHIND)
- **Issue #347** (closed): signoff/README.md still attributes current rows to klt 0.8.0 after the 0.9.1 re-pin
- **Issue #344** (closed): Deduplicate the run-manifest literal in sim/tests render_record tests (four hand-written copies)
- **Issue #338** (closed): signoff: the throwaway-grader-venv recipe makes `npm run check:all`'s pytest leg unrunnable
- **Issue #278** (closed): Re-pin the signoff grader from klt 0.8.0 to the 0.9.1 release and regrade
- **PR #341**: docs: repoint disabled-pad above-VDD tracker from closed #130 to DR-0006
- **Issue #334** (closed): design/README.md cites closed #130 as the tracker for the disabled-pad above-VDD current
- **PR #333**: test: pin rule 8e superseded-netlist exemption via superseded-record selector
- **PR #332**: fix: pass --no-provenance-header to klt netlist in checker and exporter
- **PR #328**: runner: share one snapshot-body format; pex bench writes its own snapshot
- **PR #327**: docs(sim): point the klt yield recipe at the PyPI klayout-tools[yield] extra
- **PR #324**: docs(spec): add DR 0008 proposing a 100 ohm xover negative-control load
- **Issue #323** (closed): Lock in the superseded-netlist hash exemption at check_synthesis_only's call site with a test
- **PR #321**: lint: check corner coverage on the stored-evidence mismatch record path
- **Issue #316** (closed): sim/README.md:318 is stale: klt_yield_native IS on PyPI (klt-yield-native 0.1.0, 2026-11-05)
- **Issue #315** (closed): diff-receiver-pex: the pex snapshot convention re-triggers the artifact-manifest gate on every re-run, and freezes a deck with no device cards
- **Issue #311** (closed): design/check_netlist.py reports STALE for every cell on this host (klt/xschem build drift vs the committed netlists)
- **Issue #307** (closed): sim/driver-matching-mismatch: the 180 ohm xover negative control does not trip at sf40v36 (min 1.3035 V vs the 1.3 V floor)
- **Issue #304** (closed): Consolidate the four copies of the pinned-PDK root search and open_pdks revision check
- **Issue #297** (closed): Consolidate the four divergent sha256_file helpers behind one explicit digest contract
- **PR #294**: docs: sync signoff and root README prose to the committed signoff report
- **Issue #293** (closed): Deduplicate the analog layout generators: the sky130 layer table, the GDS CLI epilogue and the poly-resistor builders are copied per block
- **Issue #292** (closed): Corner-coverage declaration is unchecked on the artifact-store record path
- **PR #291**: build: drop the stale `test` script and add the signoff gate to `check:all`
- **Issue #288** (closed): Deduplicate the se_receiver dp/dm testbench specs: the two are one token substitution apart
- **Issue #286** (closed): Deduplicate the three provenance hash-verification loops in flow/check_records.py
- **Issue #282** (closed): Remove the stale `npm test` script and widen `check:all`: both report green for a suite they do not run
- **Issue #279** (closed): signoff/README.md and README.md contradict the committed signoff report (stale analog rows, "6 of 22", #130)
- **Issue #273** (closed): sim/driver-matching-mismatch: run and record the fs100v30 corner (thinnest low-side matching margin, 0.9278)
- **Issue #223** (closed): T1 item 6 (Monte Carlo, analog): mismatch campaigns for the driver rise/fall matching and D+ pull-up ±5% rows
- **Issue #128** (closed): docs(signoff): "How to re-run the grading" never warns about the three wrong-grader traps (false drift, uvx, shared klt) — recipe itself landed in #298
- **PR #310**: refactor(flow): share one provenance hash-verification helper across the three record checks
- **PR #317**: refactor(analog): consolidate the layer table, GDS CLI and poly-resistor builders into gen_common
- **PR #312**: refactor: consolidate the four pinned-PDK root searches into sim/harness/pdk_pin.py
- **PR #309**: sim: record driver-matching-mismatch fs100v30 corner (match FAIL, xover PASS)
- **PR #320**: sim: render the se_receiver dp/dm testbench inputs from one shared source

### 2026-11-15

- **PR #308**: docs(signoff): document the three wrong-grader traps in the re-grading recipe
- **PR #314**: sim: record driver-matching-mismatch fs100v36 corner (match PASS, xover FAIL); state partial driver coverage
- **PR #305**: sim: record driver-matching-mismatch sf40v36 corner (FAIL); state partial driver coverage
- **PR #303**: feat(sim): first klt pex report on the differential_receiver leaf (36/36 rows pass, bodies biased)
- **PR #302**: sim: record driver-matching-mismatch tt corner (PASS); state partial coverage
- **PR #301**: feat(sim): render a one-line note instead of empty detail tables when no corner measured
- **PR #300**: test: share one synthetic klt-report builder across the sim/tests analog modules
- **PR #299**: signoff: declare the item-5 analog row set with cited 45-point envelopes
- **PR #287**: refactor(lint): share one merge-base, fail-closed append-only check between both evidence lints
- **Issue #289** (closed): Deduplicate the synthetic klt-report builders in sim/tests: five hand-rolled copies of one corner envelope, one carrying a dead no-op loop
- **Issue #283** (closed): Simplify record rendering: skip the per-corner and measurement-range tables when no corner produced a measurement
- **Issue #281** (closed): T1 item 7 (post-layout verification, analog): first klt pex report on the differential_receiver leaf
- **Issue #280** (closed): T1 item 5 (corner verification, analog): declare the analog row set and cite the committed klt sim corner envelopes
- **Issue #276** (closed): Remove the duplicate append-only base-ref check in flow/check_records.py: it disagrees with sim/harness/evidence_lint.py and is wrong both ways
- **Issue #272** (closed): sim/driver-matching-mismatch: run and record the sf40v36 corner (thinnest high-side matching margin, 1.0772)
- **Issue #271** (closed): sim/driver-matching-mismatch: run and record the fs100v36 corner (thinnest crossover margin, ~7 mV)
- **Issue #269** (closed): sim/driver-matching-mismatch: run and record the tt corner (Monte Carlo mismatch, driver rise/fall matching + crossover)
- **PR #298**: feat(signoff): grader-free --pins-only mode makes pin staleness locally detectable

### 2026-11-14

- **PR #290**: feat(sim): scope a mismatch record to a declared subset of corners (--corner)
- **Issue #268** (closed): sim/harness: let a mismatch record cover a declared subset of corners (--corner), so a multi-corner campaign can land one corner per PR
- **PR #277**: docs: roadmap as of 2026-11-13

### 2026-11-12

- **PR #265**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-07

- **PR #261**: Bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #258**: refactor: share one analog leaf check runner across the five leaves
- **Issue #233** (closed): Consolidate four near-identical analog run_checks.py into one shared runner
- **PR #256**: feat(signoff): cite analog leaf DRC/LVS/ERC evidence and re-hash native inputs
- **Issue #255** (closed): Cite the five analog leaves' DRC/LVS/ERC evidence as T1 items 2-4 and 11 (analog)

### 2026-11-02

- **PR #249**: feat: pair MIM caps in driver LVS reference and mint record
- **Issue #220** (closed): T1 items 2-4, 11 (analog layout): lay out the differential_driver leaf with DRC, LVS and ERC supply evidence

### 2026-10-31

- **PR #247**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-30

- **PR #243**: sim: record D+ pull-up mismatch Monte Carlo; declare driver matching/crossover campaign

### 2026-10-29

- **PR #241**: refactor: share se_receiver dm/dp layout generator
- **Issue #240** (closed): Consolidate se_receiver_dm/dp gen.py: 302-line near-duplicate generators
- **PR #239**: refactor: share analog leaf generator helpers in gen_common.py
- **Issue #238** (closed): Consolidate copy-pasted helpers across five analog layout gen.py files

### 2026-10-28

- **PR #237**: docs: scope netlist byte-identity claims to one host
- **Issue #236** (closed): Committed design/netlist/*.spice do not regenerate byte-identically on all hosts (xschem line wrapping)
- **PR #235**: refactor: export netlists via klt netlist --block instead of raw xschem call
- **Issue #232** (closed): Replace raw xschem call in design/export_netlist.sh with klt netlist --block
- **PR #230**: feat: attest analog design sources as 1.analog with klt-based netlist freshness check
- **Issue #219** (closed): T1 item 1 (design sources, analog partition): attest the five analog leaf schematics + netlists and cite them as 1.analog
- **PR #227**: feat(layout): add sky130 dplus_pullup layout with DRC/LVS/ERC evidence
- **Issue #222** (closed): T1 items 2-4, 11 (analog layout): lay out the dplus_pullup leaf with DRC, LVS and ERC supply evidence
- **PR #228**: feat: add sky130 se_receiver_dp and se_receiver_dm analog layouts with check records
- **Issue #221** (closed): T1 items 2-4, 11 (analog layout): lay out the se_receiver_dp and se_receiver_dm leaves with DRC, LVS and ERC supply evidence
- **PR #229**: feat: declare analog statistical rows and cite receiver yield reports under item 6
- **Issue #224** (closed): T1 item 6 (Monte Carlo, analog): declare the analog statistical row set and cite the committed klt yield reports as 6.analog
- **PR #225**: docs: rewrite characterization per-row table from committed sim records and re-pin item 8
- **Issue #218** (closed): T1 item 8 (characterization report): docs/characterization.md is stale — it reports zero evidenced §6 rows while 45/225-point analog records pass; refresh and re-pin
- **PR #226**: feat: add differential_driver analog layout generator and DRC/ERC-clean GDS

### 2026-10-27

- **PR #214**: chore: bump pinned klayout-tools to 0.8.0 in flow defaults and docs
- **Issue #213** (closed): Bump klayout-tools pin 0.7.0 → 0.8.0
- **PR #211**: feat(signoff): bind not_applicable statement for T1 item 6 digital, re-pin klt 0.8.0
- **Issue #208** (closed): T1 item 6 (Monte Carlo, digital partition): bound not_applicable statement for the UTMI digital rows
- **PR #210**: feat(signoff): cite T1 item 1 digital via klt attest envelope
- **Issue #206** (closed): T1 item 1 (design sources, digital partition): attest and cite the ready UTMI source inventory as 1.digital

### 2026-10-24

- **PR #203**: refactor: share cocotb Monitor base and RxMonitor across verification suites
- **Issue #200** (closed): Consolidate duplicated cocotb monitor classes in verification tests
- **PR #202**: refactor: share record-header, hash and JSON helpers across sim harness
- **Issue #201** (closed): Consolidate duplicated record-header lint and hash helpers in sim/harness
- **PR #198**: feat: store Monte Carlo mismatch evidence in the artifact store

### 2026-10-23

- **PR #197**: feat: store mismatch campaign evidence in the artifact store
- **Issue #195** (closed): Rewire sim/run_mismatch.py Monte Carlo campaigns to the artifact store
- **PR #194**: feat: store new sim evidence in the artifact store with manifest-based records

### 2026-10-22

- **PR #189**: docs: remove stale harness sharing analysis
- **Issue #174** (closed): Remove sim/harness/SHARING.md: closed #119 analysis with drifted line counts and citations
- **PR #176**: sim: mismatch Monte Carlo evidence for the receiver sensitivity and threshold rows
- **Issue #166** (closed): T1 item 6 (analog): Monte Carlo mismatch evidence for the receiver sensitivity and threshold rows, and correct the "no statistical row" statement
- **PR #184**: flow: re-qualify digital flow records under open_pdks f6eeac7
- **PR #172**: feat(layout): sky130 differential_receiver layout with DRC/LVS/ERC evidence and analog record lint
- **PR #177**: test(sim): re-qualify cited analog sim records under open_pdks f6eeac7
- **Issue #152** (closed): Re-qualify cited sim and flow records under open_pdks f6eeac7 (child of #151)
- **Issue #167** (closed): T1 items 2-4 (analog): lay out the differential receiver as the first DRC/LVS-verified analog leaf

### 2026-10-21

- **PR #181**: fix(signoff): refresh item-10 ci.yml pin after comment-only change
- **PR #179**: fix: extend retired open_pdks pin records_through to 20261016
- **PR #178**: Bump Repo Skills 0.24.3 -> 0.24.7
- **Issue #180** (closed): main red: klt signoff inventory pin item-10-hygiene is stale after a ci.yml change
- **Issue #173** (closed): main red: 4 driver-signal-quality records (20261016) carry the retired open_pdks pin

### 2026-10-20

- **PR #153**: feat: re-pin open_pdks to the ciel f6eeac7 revision and verify the PDK revision at resolution
- **Issue #151** (closed): Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3

### 2026-10-17

- **PR #169**: fix(rtl): register RX FIFO full flag to remove wr_en combinational loop
- **PR #168**: build(signoff): re-pin grader to klayout-tools 0.7.0 and cite T1 items 9 and 10
- **Issue #165** (closed): Re-pin the signoff grader to klayout-tools 0.7.0 and cite T1 items 1 (digital), 9 and 10 with artifact-anchored envelopes
- **Issue #164** (closed): Fix the combinational loop in rtl/usb_rx_cdc.v (wr_en depends on itself through full) and re-synthesize usb_utmi_top

### 2026-10-16

- **PR #162**: sim: record driver-signal-quality 225-point resistor-sets run via sharded batch jobs
- **Issue #135** (closed): sim: resistor-set (sheet-resistance) sweep for the driver (series resistor, bias, MIM caps)
- **PR #157**: Bump Repo Skills 0.24.1 -> 0.24.3

### 2026-10-15

- **PR #155**: docs: add disabled-pad envelope study and proposed DR-0006
- **Issue #130** (closed): FS driver: disabled pad forced above VDD forward-biases output PMOS junction (up to -259 uA at 3.6 V pad on 3.0 V rail)
- **PR #148**: Bump Repo Skills 0.19.5 -> 0.24.1

### 2026-10-13

- **PR #146**: chore(loom): drop onIdle [auditor]; follow the fleet idle-role setting
- **PR #145**: chore(loom): disable buildGate for now (pre-PR preflight off)

### 2026-10-10

- **PR #143**: sim: resistor-set (225-point) sweep for the differential and single-ended receivers (#136)
- **Issue #136** (closed): sim: resistor-set (sheet-resistance) sweep for the differential and single-ended receivers
- **PR #142**: sim: resistor-sets variant for driver experiments (#135)

- **Issue #127** (closed): sim harness: tb.json trim block fails open when measure_prefix/codes do not match declared measurements
- **PR #139**: sim harness: fail closed on undeclared trim inputs (#127)

- **PR #137**: sim: resistor sheet-resistance corner coverage, 225-point D+ pull-up record (#126)
- **Issue #126** (closed): sim: resistor sheet-resistance spread is not in the 45-corner matrix (D+ pull-up trim coverage unrecorded)
- **PR #134**: docs(sim): harness sharing analysis and upstream issue draft (#119)
- **Issue #119** (closed): sim harness: extract a PDK-neutral core from gf180-usb2-phy so sky130-usb2-phy can vendor it byte-identically

### 2026-10-09

- **PR #131**: feat: sky130 FS line driver with OE, 45-corner signal-quality and static evidence (#112)
- **Issue #112** (closed): analog port: FS line driver to sky130 - schematic with OE and 45-corner signal-quality testbench (inherits four failing driver rows)
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

