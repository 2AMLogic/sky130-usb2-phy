# sim/ -- analog simulation harness and append-only evidence

Analog testbenches, the 45-point sky130 PVT matrix, and the evidence records
produced from them (ngspice, run through `klt sim`). Results are **append-only
evidence**: a record is never edited or deleted; a re-run, even one that
corrects a mistake, mints a new record id and leaves the old one byte-identical.

This directory is the harness plus one experiment directory per block port (see
[`docs/porting-plan.md`](../docs/porting-plan.md)): `smoke-inverter` (harness
acceptance only), `diff-receiver-sensitivity` (#111, first block) and
`se-receiver-dp-thresholds` / `se-receiver-dm-thresholds` (#110) and
`dplus-pullup-tolerance` (#113) and `driver-signal-quality` / `driver-static` (#112).

## Provenance and master

- **Master: `2AMLogic/gf180-usb2-phy` @ `0aab24943aa1379026ccebb8e5746580f1eb7947`**
  (`sim/run_corners.py`, `sim/harness/`, `sim/README.md`, `sim/check_records.py`).
  Under REUSE.md "Which repo is master", rule 1 (lineage): this repo's analog
  blocks are ported from `gf180-usb2-phy`, so it is the immediate master.
  Its harness is itself a port of `2AMLogic/gf180-bandgap`'s `sim/harness/`
  (the ancestor `CLAUDE.md` "Harness bootstrap" names); that ancestry is
  documented there and not re-derived here.
- **Nothing is vendored byte-for-byte, and that is deliberate.** The upstream
  modules (`corners.py`, `pdk.py`, `klt_backend.py`, `runner.py`, `report.py`,
  `testbench.py`, `cli.py`, `evidence_lint.py`) embed gf180 constants (the
  `sm141064.ngspice` library, the nine-section gf180 bundles, 125 C and +-10 %
  defaults) and import one another and `verification/check_records.py`, so no
  file is PDK-neutral enough to carry unchanged into a `sim/harness/common/`
  directory. Putting a gf180 file under a "byte-identical" stamp, or editing it
  and calling it vendored, would both misstate provenance. Instead the
  mechanics were re-implemented compactly for sky130 and every upstream file
  read is stamped with its SHA-256 in [`reuse.lock.json`](../reuse.lock.json)
  (`mode: fetched`, full commit). Extracting a PDK-neutral core that both repos
  can vendor needs an upstream refactor and is tracked as a follow-up, not done
  here.
- Carried **mechanics**: experiment/record layout, `<record-id>` and
  `<corner-id>` grammars, one `klt sim` corners request per grid, per-corner log
  retention, append-only rule. **Replaced by sky130 configuration**: model
  library, process sections, PVT axes ([`corners.json`](corners.json)).
  **Not carried**: the local ngspice grid runner (`-j`), passive-skew corner
  bundles, the `typical` alias, `klt_measure` plumbing.

## The corner matrix

[`corners.json`](corners.json) is the single source for request generation,
`--list`, the lint and the tests; there is no second grid.

| Axis | Values | Source |
|---|---|---|
| Process | `tt ff ss fs sf` | `.lib` sections of open_pdks `sky130A` `libs.tech/ngspice/sky130.lib.spice` (confirmed present on this host by `--check-env`) |
| Temperature | -40, 27, 100 C | `spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md` Decision 5 (-40...100 C; no 125 C) |
| I/O supply | 3.0, 3.3, 3.6 V | same record: I/O supply 3.0-3.6 V, `spec/usb2-phy.md` section 5 |

5 x 3 x 3 = **45** unique tuples, swept via the supply source `vsup`
(`klt sim` re-targets it per corner with `alter`). Decision 5's STA corner
matrix covers the 1.8 V core cells only and says the 3.3 V I/O PVT signoff
belongs to the analog blocks; this matrix is that I/O-rail envelope. No
envelope change was made. Corner ids: `<process>_<temp>c_<supply>v`, e.g.
`ss_-40c_3.00v`, `tt_27c_3.30v`, `ff_100c_3.60v`.

PDK identity pinned in `corners.json`: open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (from the ciel-installed tree's `SOURCES` file; records made under the previous pin are listed in `sim/pdk-pins.json`),
model library SHA-256 `17c208a6...e075f64`. The runner refuses to run if the
submitting host's PDK differs from the pin, and a PASS record must show the
klt envelope reporting the same library hash and open_pdks version.

## Layout

```
sim/
  corners.json                 the 45-point matrix + PDK identity (id pvt45-mos)
  corners-resistor-sets.json   the supplemental 225-point resistor-set matrix (id pvt225-mos-rc)
  run_corners.py               runner (stdlib only): --list, --check-env, <experiment>
  check_records.py             toolchain-free record lint (also run by `npm run lint`)
  harness/                     matrix.py results.py runner.py evidence_lint.py
  tests/                       toolchain-free tests (pytest)
  <experiment-slug>/           e.g. smoke-inverter
    testbench/                 tb.json (analysis, measurements, harness bounds) + netlist body
    netlist-snapshots/<record-id>.spice   frozen netlist as submitted
    corners/<record-id>/       evidence directory for one run:
        evidence.json            manifest: status, job id, versions, PDK identity, SHA-256 of every file
        request.json             the resolved `klt sim` request
        report.json              the raw klt result envelope
        tb.json corners.json     testbench and matrix as of the run
        klt-stderr.txt
        <corner-id>.log          raw ngspice log, one per corner
    records/<record-id>.md     append-only summary record
```

`<record-id>` = `<YYYYMMDD>-<HHMMSS>-<short-git-sha>`. A record has the fields
`Record ID, Status (PASS|FAIL), Claim, Netlist provenance, Corner matrix run,
Statistical convention, Result, Links (cites the evidence.json SHA-256),
Timestamp / author, Supersedes`. A `FAIL` record (backend error, missing or
failed corners) is valid evidence and is kept; it never counts as coverage.

## Running

```bash
python3 sim/run_corners.py --check-env          # PDK, library, the five sections
python3 sim/run_corners.py --list               # the 45 points

# Debug one corner locally (never recorded):
python3 sim/run_corners.py smoke-inverter --backend local \
    --corner ss --temp -40 --supply 3.6 --no-write

# The full grid: one `klt sim` request, submitted explicitly to the batch fleet.
python3 sim/run_corners.py smoke-inverter --klt-runner-version-check warn
```

Rules the runner enforces: the 45-point grid is a single `klt sim --backend
batch` request (`KLT_SIM_BACKEND=batch` on dispatch hosts) and is **never** run
as a local ngspice grid; a batch error fails the run (a `FAIL` record keeps the
attempt) and does not fall back to local; a subset can only be a local
single-corner `--no-write` probe.

Reproduce a record: re-run the command above on a host with the pinned PDK; it
mints a new record id. Compare corner values with the old record's
`report.json`. Never edit the old one. To supersede, pass
`--supersedes <record-id>`.

## Stored evidence (fleet artifact store)

New recorded runs do not commit their raw outputs. `run_corners.py` stages the request, frozen
testbench/matrix, klt report and stderr, every per-corner `.log` and `evidence.json` under
`sim/.work/.stage/<bench>/<record-id>/` (git-ignored), puts each object with
`klt artifact put --manifest manifests/artifacts/<bench>-<record-id>.manifest.json`, and commits only:

- `manifests/artifacts/<bench>-<record-id>.manifest.json` (every `uri` is `artifact:<key>`),
- `sim/<bench>/records/<record-id>.md` with a **Stored evidence** table (name, size, sha256),
- the netlist snapshot `netlist-snapshots/<record-id>.spice` (small, source-like; stays in git).

`python3 sim/run_store_evidence.py <bench> <staged-dir>` does the same for a staged campaign
directory (e.g. Monte Carlo output under `sim/.work/`), writing `sim/<bench>/campaigns/<run-id>.md`.

**No fallback.** Needs `$KLT_ARTIFACT_BROKER` (never written to the repo or argv), a klt with
`artifact put` (klayout-tools `7e3561f` or later) and a reachable broker; all three are checked
before anything is simulated. Otherwise the run exits 4 with nothing committed, and no flag commits
bytes instead. If a put fails after the grid, the staged files stay under `sim/.work/.stage/`.
Zero-byte files cannot be stored (a manifest entry needs size >= 1); they are listed in the table
with size 0.

Fetch with `klt artifact get`; check with `klt artifact verify manifests/artifacts/<name>.manifest.json`
(needs the broker, so CI does not run it). CI (`scripts/check_artifact_manifests.py`, in `lint.sh`)
validates schema, `artifact:` URIs only, and that no stored object's bytes are also committed. The
record lint checks a stored record's manifest citation and table; it cannot re-derive the PASS verdict
from raw bytes it does not have. Re-derive from `klt artifact get` output when auditing. Historical
committed `corners/<record-id>/` evidence is unchanged and still linted in full; the `.gitignore` log
exception was dropped so new logs cannot be re-admitted.

## Append-only rule and lint

`python3 sim/check_records.py --base-ref <ref>` (wired into
`.github/scripts/lint.sh`, hence `npm run lint` and the `flow-records` CI job,
which already fetches full history and exports `FLOW_LINT_BASE_REF`) needs only
python3 and git. It fails on:

- any file under `sim/*/records/`, `netlist-snapshots/`, `corners/`, `campaigns/` that is
  modified, deleted or renamed relative to the merge base with the base ref
  (new files are fine); an unresolvable base ref also **fails**;
- missing record fields, an id/filename mismatch, a snapshot or evidence
  directory no record cites, a missing or hash-mismatched referenced file;
- a `PASS` record whose raw envelope does not re-derive as a complete grid:
  exactly the 45 matrix tuples once each, every simulation `pass`, every
  expected measurement finite and inside the `tb.json` bounds, a request that
  is the sky130 matrix (no gf180 library, `typical`, 125 C or +-10 % supply),
  a batch job id, and a snapshot hash equal to the envelope's netlist hash;
- for the Monte Carlo experiments (`testbench/mc.json`, see "diff-receiver-mismatch,
  se-receiver-mismatch" below): a record whose requests are not the batch, mismatch-only,
  staged-pinned-model requests `mc.json` generates, whose control deck is not the nominal deck
  plus the declared skew, whose reports do not show the pinned models executed on every shard,
  whose sample sets do not pin the committed reports by hash, or whose `klt yield` reports do
  not re-grade as a PASS (yield claim, sample size, detected negative control, non-zero spread).

Self-tests: `python3 -m pytest sim/tests` (matrix, request, mocked batch
success/failure, git-fixture append-only cases). CI never submits a job.

## smoke-inverter

Harness acceptance only: one thick-oxide (`sky130_fd_pr__nfet_g5v0d10v5` /
`pfet_g5v0d10v5`, W 1/2 um, L 0.5 um) CMOS inverter at the I/O rail in three
static states (output high, output low, self-biased switching threshold).
Measurements: `voh_v`, `vol_v`, `vm_v`, `isup_ua`. The bounds in `tb.json`
(for example VOH within 5 % of the rail, VM between 0.3 and 0.7 of the rail,
a 3 % VM spread across the grid so that corner sections and temperature are
shown to take effect) are harness plausibility bounds, **not** USB electrical
claims. Measurements are `.meas dc` cards over a two-point dummy sweep because
the fleet runner image is older than the client (below).

Records: see `sim/smoke-inverter/records/`. The first attempt
(`20261009-092814-47b5f79`) is kept as failed evidence: the fleet runner
(klt 0.5.0) refused a 0.7.0 client request, so all 45 corners errored.

## diff-receiver-sensitivity

The sky130 differential receiver (`design/differential_receiver.sch`) at
common-mode 0.8 / 1.65 / 2.5 V, one receiver instance per common-mode point in
one deck, so the single 45-corner `klt sim` request yields 135 individually
named PVT x common-mode results (`*_cm0p80_*`, `*_cm1p65_*`, `*_cm2p50_*`).
The method, thresholds and output bounds are declared in
`testbench/tb.json` (`record.method`, `checks`) and repeated in every record.
`tb.json` extensions used here (all optional; smoke omits them):

- `include`: design netlists appended to the deck body, so the immutable
  snapshot contains the exact circuit simulated.
- `record`: prose for the record (`netlist_provenance`,
  `statistical_convention`, `bounds`, `footer`, `method`, `detailed`).
  Defaults are the smoke wording, so smoke records render exactly as before;
  `detailed` adds per-measurement ranges and lists every failure with its
  corner id.

Records: `diff-receiver-sensitivity/records/`. No Monte Carlo is run; each
record says so. Record `20261009-121939-0555da1` ran on fleet runner klt 0.5.0
against client 0.7.0 (its provenance line shows the client; `report.json` has
`runner_compatibility: mismatch`, version check `warn`); all 45 corners
returned finite `.meas` values in the raw logs, and a re-run is due once the
runner image is updated (klayout-tools #2851, #2948, #2917, under Known limits).

## se-receiver-dp-thresholds, se-receiver-dm-thresholds

The sky130 single-ended D+ / D- receivers (`design/se_receiver_dp.sch`,
`design/se_receiver_dm.sch`), one experiment per line: the line input swept
0-3.0 V in 1 mV steps at each of the 45 PVT corners. Measured: the first
rising crossing of the output through VDD/2 (`vth_v`) and the last crossing
in either direction (`vth_last_v`), the output maximum over 0-0.8 V and
minimum over 2.0-3.0 V, the 0.8 V / 2.0 V boundary probes, the internal
`VREF` and the supply current. Two check keys were added to `tb.json`
`checks` for this row (both optional, used nowhere else):

- `gt` / `lt`: exclusive bounds. The ratified row needs the threshold
  *strictly* inside (0.8, 2.0) V, and `min` / `max` are inclusive, so an
  endpoint value would otherwise pass.
- `same_as: {"measure": <name>, "tol": <abs>}`: the measurement must equal
  another measurement of the same corner within `tol`. Used to require
  `vth_last_v == vth_v` within one sweep step, so a response that crosses
  more than once (non-monotonic) fails, as does an inverted one (no rising
  crossing at all).

Records: `se-receiver-dp-thresholds/records/`, `se-receiver-dm-thresholds/records/`.
No Monte Carlo is run; each record says so. Both ran on fleet runner klt
0.5.0 against client 0.7.0 with the version check in `warn` mode, as above.

## diff-receiver-mismatch, se-receiver-mismatch (Monte Carlo, T1 item 6)

The statistical evidence for the two receiver rows that mismatch limits by construction
(#166): `spec/usb2-phy.md` section 6 "Differential input sensitivity" (|(D+) - (D-)| > 200 mV)
and "Single-ended receiver thresholds" (VIH > 2.0 V, VIL < 0.8 V, read as in the
deterministic records: threshold strictly inside (0.8 V, 2.0 V) and valid output levels
beyond). The deterministic 45- and 225-point records above are corner evidence and say so;
these experiments add the local-mismatch Monte Carlo that item 6 asks for. They are separate
experiment directories (`testbench/mc.json`, not `tb.json`), so the PVT lint above does not
apply to them; `harness/mismatch_lint.py` does, and `sim/check_records.py` runs both.

Per receiver (the differential receiver; the D+ and the D- single-ended receivers) and per
corner there is one `klt sim` Monte Carlo request (`vary: mismatch`, seed 166, n = 400
samples; the `*_mm` library sections, which set `mc_mm_switch = 1`) and one **negative-control**
request (n = 50, same deck and seeds, one fixed skew declared in `mc.json`: a 0.25 V
differential input offset for the receiver; R2 length 14 -> 60, a divider-ratio skew, for the
single-ended receivers). `klt yield-samples` pairs each control with its nominal campaign and
`klt yield` grades the pair against the row limits (exclusive bounds, VDD-relative output
levels at the corner supply) with `target_yield` 0.99 at 95 % confidence. Each (receiver,
corner) is its own population; nothing is pooled across corners or across D+/D-.

Corners: `tt_mm` at 27 C / 3.3 V, and the binding corner read from the 45-point records
(`mc.json` `corners[].basis`): differential receiver `sf_mm` / 100 C / 3.0 V (largest
|threshold| at common-mode 2.5 V), single-ended receivers `ff_mm` / 100 C / 3.0 V (lowest
threshold, closest to VIL). Global process spread stays on the corner axis; the mismatch
campaign runs at those two corners, not across the 45-point grid.

Sample size: with zero failures the exact lower bound reaches 0.99 only from n = 368
(`required_n_for_target`); n = 400 is the smallest round count that can support the claim, and
the precision target (+/-0.01) needs 183. A failing row is recorded as failing; a larger n
does not rescue it.

Reproduce (the campaigns are submitted to the batch fleet, never run locally):

```bash
# klt yield needs the klt_yield_native extension, which is not on PyPI (klayout-tools#2900).
# Build it into a throwaway venv, never into the host tools (see the worker rules):
#   maturin build --release -j 2 -o <wheel-dir>      # in klayout-tools native/yield
#   uv venv --python 3.12 <venv> && uv pip install --python <venv>/bin/python <klayout-tools checkout> <wheel>
python3 sim/run_mismatch.py --list
python3 sim/run_mismatch.py diff-receiver-mismatch --klt <venv>/bin/klt --max-in-flight 3 --capacity-retries 3
python3 sim/run_mismatch.py se-receiver-mismatch  --klt <venv>/bin/klt --max-in-flight 3 --capacity-retries 3
```

Choices worth knowing:

- `options.stage_model_inputs` is set on every request. The fleet image's PDK stamp can lag the
  submitter's pin (after the #151 re-pin it still reports open_pdks `c6d73a3`), so without staging
  the image's tree would execute. With staging the executed models are the submitter's (pinned
  `f6eeac7`) files; `mismatch.pdk_problems` fails a record whose report does not show
  `models_staged` on every shard, the pinned `provenance.pdk.version` and the pinned library hash.
- The 400-sample requests are sharded (`remote.hosts: 4`, `batch.max_concurrent_jobs: 2`) because the
  fleet kills a job at its whole-job ceiling (3600 s) and loses every unit of it.
- Mismatch reaches the devices used here (g5v0d10v5 MOS and res_xhigh_po_1p41): each yield report's
  `distribution.stddev` of the threshold is non-zero, and `mismatch.grade` fails a record whose
  `spread_measures` have zero spread.
- `--from-work <dir>` grades and records a batch-set that already finished (for example when the
  harness stopped after the fleet did its work) without resubmitting; it byte-compares the requests and
  decks with what `mc.json` generates and the record says it was collected that way.

The D+ and D- receivers are identical netlists and both campaigns use seed 166, so their sample sets are
numerically identical: one population counted for two receivers, not two independent draws (the record says so).

Result at the time of writing (see the records for the numbers): every receiver/corner population has 400/400
samples inside the row limits (empirical yield 1, exact 95 % lower bound 0.9908 >= 0.99), the declared negative
control is `detected` for every measurement it is expected to degrade, and the threshold spread from mismatch is
7 - 11 mV (1-sigma) against a margin of 120 - 200 mV: the worst case is the differential receiver at common-mode 2.5 V
at the binding corner, threshold -75.6 mV (sigma 10.8 mV), 11.6 sigma from the 200 mV limit. This is local mismatch only, at
two corners per receiver; it does not replace the corner records and says nothing about layout.

Records: `diff-receiver-mismatch/records/`, `se-receiver-mismatch/records/`. The two committed records keep
their raw evidence in `<experiment>/campaigns/<record-id>/`, hashed by `evidence.json`. A new recorded run uses
the artifact store like the corner runner (see "Stored evidence" above): `run_mismatch.py` checks the store
before submitting anything and exits 4, writing nothing, if `$KLT_ARTIFACT_BROKER` is unset, `klt artifact put`
is missing or the broker is unreachable (`--no-write` does not need it). The requests, decks, klt reports,
sample sets, limits files, `klt yield` reports and `evidence.json` are staged under `sim/.work/.stage/`
(git-ignored) and stored; git keeps `manifests/artifacts/<experiment>-<record-id>.manifest.json` and the record
with its **Stored evidence** table. `mismatch_lint` checks such a record's manifest citation and table and that
no `campaigns/<record-id>/` copy is committed; the verdict is re-derived from the fetched files
(`klt artifact get`), not by the toolchain-free lint.

## dplus-pullup-tolerance

The sky130 trimmed D+ pull-up (`design/dplus_pullup.sch`) with the host's 15 kohm
on D+, at every one of its 16 trim codes, across the 45 PVT corners; plus the
disabled state. One deck holds 16 enabled instances (one hard-wired trim code
each) and four disabled ones, so a single `klt sim` request returns all raw
`V(DP)` values (`vdp_cNN_v`) and the disabled-state voltages and currents per
corner (`.meas dc` over the two-point dummy sweep, as in the other experiments).

Reproduce (the grid is submitted to the batch fleet, never run locally):

```bash
python3 sim/run_corners.py dplus-pullup-tolerance --klt-runner-version-check warn
# single-corner local debug, never recorded:
python3 sim/run_corners.py dplus-pullup-tolerance --backend local \
    --corner ss --temp 100 --supply 3.0 --no-write
```

Existential best-trim evaluation: `tb.json` gained one optional block, `trim`
(`codes`, `measure_prefix`, `load_ohm`, `target_ohm`, `lo_ohm`, `hi_ohm`), handled
by `harness/trim.py` and called from `results.evaluate`, so the runner and the
record lint apply the same rule. Per corner: `R_eff = (VPU - V(DP)) /
(V(DP)/R_load)` for every code; a code with a non-finite, non-positive-current
or `V(DP) >= VPU` measurement has no resistance and fails the corner; the corner
passes only if all 16 codes are valid **and at least one** lies in the inclusive
`[lo_ohm, hi_ohm]` window (the bound is not applied to every code). The best
code minimises `|R_eff - target_ohm|` with ties to the lowest code. Derived data
(`r_cNN_ohm`, `best_code`, `best_r_ohm`, `best_err_ohm`, `n_in_window`,
`step_cNN_ohm`, `step_min_ohm`, `step_max_ohm`, `range_ohm`, `n_nonmonotonic`) are
stored in `evidence.json` next to the preserved raw measurements in `report.json`.
Another optional `record` key, `corner_table`, prints a per-corner table of chosen
derived columns in the record.

Records: `dplus-pullup-tolerance/records/`. The first two attempts
(`20261009-172121-d85f0dc`, `20261009-172711-d85f0dc`) are FAIL records: the batch
fleet refused the job (`batch_no_capacity`, no capacity in any of the 30 pools)
before any simulation; they are kept and are not coverage. The third
(`20261009-172948-d85f0dc`) is the PASS 45/45 record. No Monte Carlo is run, and
**the pinned PDK's five bare process sections all use the typical resistor parameter set**
(`res_typical__cap_typical`), so the 45-point grid covers MOS corners and the resistor
temperature coefficient but not the resistor sheet-resistance spread; see
`design/README.md` for the separate, unrecorded design-basis check and "Resistor-set
coverage" below for the supplemental 225-point matrix. Provenance:
`reuse.lock.json` stamps the gf180 source files read (schematic, netlist, design
notes, testbench, record); the sky130 deck and evaluator are new code, not
byte-copies, and the existential selection is this port's own addition.

## driver-signal-quality, driver-static

The sky130 FS line driver (`design/differential_driver.sch`, pins `VDD VSS TXDP
TXDM DRVEN OE DP DM`, inputs in the `VDD` domain). Two experiments, one deck each,
one `klt sim` request per 45-corner grid; no new harness code (`gt`/`lt`/`same_as`
and `per_supply` checks from earlier experiments are reused).

- `driver-signal-quality` (transient, 300 ns): 50 pF per line, no resistor.
  Rise/fall time per line and direction, four matching pairings, rising and
  falling crossover, single-crossing, masked-slope monotonicity; plus
  enable/disable transitions into a pad forced to VDD/2 (engineering data).
- `driver-static` (one DC sweep of the leakage-forcing source): VOH (15 kohm to
  ground and, as the literal reading of the ratified row, 1.5 kohm to 3.6 V), VOL
  (1.5 kohm to 3.6 V), total output resistance high and low, the 16-combination
  enable truth table (both lines), disabled-pad leakage over 0-3.6 V forcing.
  VOH/VOL load readings: `spec/decision-records/0004-fs-driver-voh-vol-load-conditions.md`
  (proposed).

```bash
python3 sim/run_corners.py driver-signal-quality --klt-runner-version-check warn
python3 sim/run_corners.py driver-static --klt-runner-version-check warn
# single-corner local debug, never recorded:
python3 sim/run_corners.py driver-static --backend local \
    --corner tt --temp 27 --supply 3.3 --no-write
```

Records: `driver-signal-quality/records/` (`20261009-182102-e232b2f` PASS 45/45, batch
job `klt-sim-cfe0e1417464`; `20261009-181037-e232b2f` and `20261009-181100-e232b2f`
are FAIL attempts the fleet refused: `BATCH_MAX_CONCURRENT_INSTANCES` then
`batch_no_capacity`) and `driver-static/records/` (`20261009-185058-e232b2f` PASS
45/45, job `klt-sim-d7588a09de82`; `20261009-181043-e232b2f` FAIL, fleet at its
instance limit). FAIL attempts are kept and are not coverage; no local grid was run.
No Monte Carlo; resistor and MIM-capacitor process spread is not in the 45-point grid
(typical parameter set in all five sections; see "Resistor-set coverage"). Provenance: `reuse.lock.json` stamps
the gf180 driver schematic, netlist, testbench and record that were read; the sky130
decks are new except for the carried 50 pF load, stimulus and measurement
definitions named in `driver_tb.spice`. Results and device reasons:
`design/README.md`.

## Known limits

- **Fleet runner skew.** The batch fleet ran klt 0.5.0 against a 0.7.0 client.
  The default `enforce` check fails every corner; `--klt-runner-version-check
  warn` is needed and the request therefore avoids newer features (`expr`
  measurements). The skew is already tracked at `2AMLogic/klayout-tools`
  (#2851, #2948, #2917).
- **Execution-host PDK identity is client-reported.** The envelope's
  `models_lib_sha256` and `provenance.pdk` come from the submitting host; they
  are checked against the pin but do not independently prove the fleet's PDK.
  What does show the fleet resolved the sky130 sections is that all 45 corners
  simulated with corner- and temperature-dependent results (ngspice 46 on the
  fleet vs 42 locally, recorded per record).
- `git.dirty` in `evidence.json` is true for records minted before commit; the
  frozen netlist, request, tb and matrix copies and their hashes are the
  reproducibility anchor.

## Resistor-set coverage (#126, `spec/decision-records/0005-resistor-sheet-resistance-corner-coverage.md`, proposed)

`corners.json` (45 points) uses `tt ff ss fs sf`, all of which load
`r+c/res_typical__cap_typical.spice`; it does not cover resistor sheet resistance. The
pinned library's `ll`, `hh`, `hl`, `lh` (bare, `tt` MOS) and `<mos>_ll|hh|hl|lh` sections
select the low/high resistor sets; they also change the capacitor set and the `tol_*` drawn-width
tolerances, so they are not resistor-only, and they are the PDK's global corners (not per-device
spread or mismatch). `corners-resistor-sets.json` crosses all 25 sections (5 MOS x {typical, ll,
hh, hl, lh}) with the same 3 temperatures and 3 supplies: **225** points. Only the two approved
configurations in `harness/matrix.py` (`APPROVED_MATRICES`) load, whether from the repo or from the
corners file frozen in a historical record; the runner refuses a library whose section includes
differ from the approved mapping, and `evidence.json` stores the mapping and includes.

    python3 sim/run_corners.py --list --matrix pvt225-mos-rc
    python3 sim/run_corners.py --check-env --matrix pvt225-mos-rc
    python3 sim/run_corners.py dplus-pullup-tolerance --variant resistor-sets   # batch only, recorded
    python3 sim/run_corners.py diff-receiver-sensitivity --variant resistor-sets   # 225 points x 3 common modes = 675
    python3 sim/run_corners.py se-receiver-dp-thresholds --variant resistor-sets
    python3 sim/run_corners.py se-receiver-dm-thresholds --variant resistor-sets

An experiment opts in with a `variants` entry in its `tb.json` (it may override only `matrix_id`,
`claim` and `record` prose). `dplus-pullup-tolerance`, `diff-receiver-sensitivity`, `se-receiver-dp-thresholds` and `se-receiver-dm-thresholds` have one. Pull-up: record `20261010-014615-8ebfb55` is PASS 225/225 on the
batch backend (job `klt-sim-10dfd5d87262`; fleet runner klt 0.5.0 vs client 0.7.0, run with
`--klt-runner-version-check warn`; the default `enforce` attempt `20261010-014506-8adcaaf` was
refused for the skew with all 225 corners `error`). The earlier records
`20261010-011518-cf49e32`, `-011907-cb1d9ce`, `-012518-9f1c2dd`, `-013051-9f1c2dd` and
`-013733-8adcaaf` are FAIL attempts the fleet refused for capacity (batch_no_capacity); they are kept
and are not coverage.

Receivers (#136), all with `--klt-runner-version-check warn` (same fleet-runner klt 0.5.0 vs client 0.7.0 skew; the default `enforce`
attempts `20261010-073830-0d51889` (D+) errored all 225 corners for it). Checks, stimulus, analysis and netlist are the
base experiment's; only matrix, claim and record prose differ, and every bound is unchanged. Each record is
the complete 225 unique PVT/section points (differential: 3 common modes each = 675 combinations), PASS, batch:

| experiment | record | job | measured worst case over the 225 points |
|---|---|---|---|
| `diff-receiver-sensitivity` | `20261010-094000-0d51889` | `klt-sim-457636169781` | vth -76.5 mV (sf_hh 3.0 V 100 C, cm 2.5 V) to -12.5 mV; limit (-200, +200) mV; supply current 9.5-81.7 uA |
| `se-receiver-dp-thresholds` | `20261010-074010-0d51889` | `klt-sim-4640313c847e` | vth 1.250 V (ff_lh 3.0 V 100 C) to 1.514 V (ss_hl 3.6 V -40 C); limit exclusive (0.8, 2.0) V; single crossing at all points; supply current 76-159 uA |
| `se-receiver-dm-thresholds` | `20261010-090217-0d51889` | `klt-sim-b6118d9c04c7` | identical to D+ (same corners, same values) |

Output levels met the unchanged 0.1/0.9 x VDD bounds everywhere. Failed attempts (`batch_no_capacity`, fleet concurrency cap, and the
version-skew runs above) are kept as FAIL records and are not coverage. This is deterministic schematic evidence over the PDK's
global resistor/capacitor corner sets plus drawn-width tolerances (they are not resistor-only sections); per-device resistor
mismatch (including independent R1/R2 divider mismatch), Monte Carlo, layout parasitics and signoff are not covered.
The legacy 45-point receiver records are unchanged.

`driver-static` and `driver-signal-quality` (#135) now declare a `resistor-sets` variant (bounds and
checks unchanged). `driver-static`: record `20261010-070333-23e660b` is a complete 225-point FAIL
(198/225 points pass, 68 problems at 27 failing points, batch job `klt-sim-32c9b2c0c856`). The
inclusive 28-44 ohm output-resistance row is violated on both sides: 46 low-side violations
(26.33-27.94 ohm, 17 points, all at -40 C on `ll`/`lh` sections) and 22 high-side violations
(44.38-46.55 ohm, 10 points, on `hh`/`hl` sections with ss/fs/sf MOS at 100 C, mostly 3.0 V). `driver-signal-quality`: record `20261016-184100-59ec9c0` is a complete 225-point FAIL
(223/225 points pass; 4 problems at 2 failing points: crossover voltage above the unchanged 2.0 V
maximum at `fs_ll` and `fs_hl`, 100 C, 3.6 V, rising and falling; see the record for values). The grid
exceeds one fleet job's 3600 s whole-job ceiling, so it ran as 8 independent shard jobs
(`--hosts 8`; the record's job id lists all eight) with the per-corner timeout raised from 1500 s to
2400 s in `tb.json` (a corner at -40 C needed more than 1500 s; no bound or check changed). The
earlier attempts `20261010-084706-23e660b` (`batch_no_capacity`), `20261010-090542-23e660b`
(`batch_job_timeout`), `20261016-175635-59ec9c0` (refused pre-submit, job over the ceiling),
`20261016-175832-59ec9c0` (3 corners hit the 1500 s timeout; two fleet jobs failed; the submitting host
read an unpinned PDK install), and `20261016-183930-59ec9c0` (all shards failed on the fleet because a
PDK path was shipped in the request) are infrastructure failures, kept and not coverage. The runner
now pins the submitting host's klt to the checked install through `PDK_ROOT` in its own environment.
