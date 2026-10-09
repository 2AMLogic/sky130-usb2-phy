# sim/ -- analog simulation harness and append-only evidence

Analog testbenches, the 45-point sky130 PVT matrix, and the evidence records
produced from them (ngspice, run through `klt sim`). Results are **append-only
evidence**: a record is never edited or deleted; a re-run, even one that
corrects a mistake, mints a new record id and leaves the old one byte-identical.

This directory is the harness plus one experiment directory per block port (see
[`docs/porting-plan.md`](../docs/porting-plan.md)): `smoke-inverter` (harness
acceptance only) and `diff-receiver-sensitivity` (#111, first block).

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
`c6d73a35f524070e85faff4a6a9eef49553ebc2b` (from the volare `SOURCES` file),
model library SHA-256 `17c208a6...e075f64`. The runner refuses to run if the
submitting host's PDK differs from the pin, and a PASS record must show the
klt envelope reporting the same library hash and open_pdks version.

## Layout

```
sim/
  corners.json                 the one 45-point matrix + PDK identity
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

## Append-only rule and lint

`python3 sim/check_records.py --base-ref <ref>` (wired into
`.github/scripts/lint.sh`, hence `npm run lint` and the `flow-records` CI job,
which already fetches full history and exports `FLOW_LINT_BASE_REF`) needs only
python3 and git. It fails on:

- any file under `sim/*/records/`, `netlist-snapshots/`, `corners/` that is
  modified, deleted or renamed relative to the merge base with the base ref
  (new files are fine); an unresolvable base ref also **fails**;
- missing record fields, an id/filename mismatch, a snapshot or evidence
  directory no record cites, a missing or hash-mismatched referenced file;
- a `PASS` record whose raw envelope does not re-derive as a complete grid:
  exactly the 45 matrix tuples once each, every simulation `pass`, every
  expected measurement finite and inside the `tb.json` bounds, a request that
  is the sky130 matrix (no gf180 library, `typical`, 125 C or +-10 % supply),
  a batch job id, and a snapshot hash equal to the envelope's netlist hash.

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
