# `flow/` — the digital physical flow and its evidence-record convention

**`rtl/utmi_stub.v` is toolchain plumbing only, and the records in this
directory anchor no design claim.** It is nine flip-flops with no
combinational logic — a registered pass-through that borrows UTMI signal
*names* from `spec/usb2-phy.md` §3 and implements none of UTMI's behaviour.
It is here because a design that trivial makes every failure in the physical
flow unambiguously a *tool* failure: there is no circuit complex enough to
blame. Nothing recorded under `flow/smoke-utmi_stub/` says anything about the
USB 2.0 PHY's eventual area, timing, or correctness, and no record here may
be cited as evidence for a `spec/` claim. The real UTMI digital layer, when it
exists, gets its own records in this same format.

**This file is the authoritative convention.** `flow/check_records.py` is its
enforcement. Where the two disagree, this file wins and the script is the
thing that gets fixed.

**For what the records in this directory add up to, read
[`docs/characterization.md`](../docs/characterization.md)** — the
authoritative characterization summary, which indexes every row of
`spec/usb2-phy.md` §6 against the evidence that exists, per corner, and
states the resulting headline: zero spec rows have design-anchored evidence
today.

---

## What the flow does

Six stages, all driven through `klt` — never a raw `openroad` or `klayout`
subprocess (`CLAUDE.md`):

| # | Stage | Command | Committed request |
|---|---|---|---|
| 1 | Synthesis | `klt synthesize` (Yosys) | `request-synth-utmi_stub.json` |
| 2 | Place & route | `klt place-and-route` (OpenROAD) | `request-par-utmi_stub.json` |
| 3 | Timing | `klt sta` (OpenSTA) | `request-sta-utmi_stub.json` |
| 4 | Extraction | `klt extract` (KLayout) | `request-extract-utmi_stub.json` |
| 5 | LVS | `klt lvs` (KLayout `NetlistComparer`) | `request-lvs-utmi_stub.json` |
| 6 | DRC | `klt drc` (klt's curated sky130 deck) | `request-drc-utmi_stub.json` |

Stage 2 produces the routed DEF, the merged GDS, **and** the as-built
gate-level netlist (`write_verilog`, with CTS buffers, resizes and antenna
diodes included). Stage 5 compares the layout-derived netlist against *that*
as-built netlist — not against stage 1's pre-CTS synthesis netlist, which
describes a different design.

Every stage is committed **data**, not prose. `flow/run_flow.py` does exactly
three things to those documents: substitutes the corner, rewrites relative
paths to absolute, and chains one stage's output into the next stage's input.
It never invents a parameter that is not in a committed file.

### Two of the six requests are not `klt` schemas

`klt extract` and `klt drc` are argv-only — they have no request-document
surface, unlike the other four stages. `request-extract-utmi_stub.json` and
`request-drc-utmi_stub.json` therefore carry a repo-local
`usb2phy.flow.*-invocation/1` schema that `run_flow.py` translates into argv,
and each says so in its own `_schema_note`. Filed upstream as
[klayout-tools#1867](https://github.com/2AMLogic/klayout-tools/issues/1867);
if that lands a real `klt.extract.request/1` / `klt.drc.request/1`, these two
files should be *replaced* by real ones, not kept alongside them.

## Running it

```bash
# every committed corner (see "Corner matrix" below)
PDK=sky130A python3 flow/run_flow.py

# one corner
PDK=sky130A python3 flow/run_flow.py --corners tt_025C_1v80 \
    --subset-justification "why this run is not the full matrix"

# what would run, without running it
python3 flow/run_flow.py --dry-run
```

Prerequisites: `klt`, a `sky130A` PDK install, and an `openroad` binary on
`$PATH` — see [`docs/environment-setup.md`](../docs/environment-setup.md).
Per-corner scratch lands in `flow/build/<corner>/` (gitignored). Records and
raw `klt` envelopes land under `flow/smoke-utmi_stub/` (committed). The
nominal corner's physical artifacts are copied into `layout/` (committed) —
see [`layout/README.md`](../layout/README.md).

Exit codes: `0` every gate passed, `1` a gate failed (negative WNS without a
waiver, DRC violations, LVS mismatch), `2` a stage or the environment failed
outright.

### One caveat about the environment

If `$PDK_ROOT` is unset, `run_flow.py` resolves it via `klt pdk find` and
exports it before invoking any stage. That is a deliberate workaround for
[klayout-tools#1868](https://github.com/2AMLogic/klayout-tools/issues/1868):
`klt` can resolve a PDK through its own search order (e.g. `~/.volare`) with
`$PDK_ROOT` unset, but the documented container wrapper for `openroad` only
bind-mounts `$PDK_ROOT` — so every stage dies on an opaque `cannot read file
<liberty>` from inside the container. Delete the workaround once #1868 is
fixed.

### Post-layout functional re-verification (issue #37)

A seventh, separate stage — not one of the six above, and not driven by
`run_flow.py` — re-runs `verification/test_utmi_stub.py` against the
post-layout gate-level netlist instead of the pre-layout RTL:

```bash
PDK=sky130A python3 flow/postlayout_verify_utmi_stub.py --format json
```

This augments the *existing* nominal-corner record rather than opening a new
experiment slug: it mints a new record that `supersedes` the newest
`tt_025C_1v80` record, regenerating that record's six-stage measurements
unchanged from its own committed `klt` envelopes and adding a
`functional_verification` stage on top — see
`flow/smoke-utmi_stub/records/20260919-001148-0f7636d-tt_025C_1v80.md` for
the current result and exactly what it does and does not model (in short: a
functional-only, zero-delay check against `layout/utmi_stub.asbuilt.v` — LVS
already proved that structurally equivalent to `layout/utmi_stub.extracted.spice`,
the netlist `klt functional-verification` cannot simulate directly — no SDF
back-annotation, and no claim about the real UTMI digital datapath). Unlike
the six committed `flow/request-*.json` documents, this stage's request
cannot be a static committed file: its `sources` must name the PDK's
`sky130_fd_sc_hd` behavioral Verilog models, which live outside this repo at
a host-resolved path, so the script resolves the PDK root itself (the same
`klt pdk find` workaround as `resolve_pdk_root` above) and builds the request
in memory instead.

**The record is written by `run_flow.py`'s own machinery, not a second
writer** (issue #63). `flow/postlayout_verify_utmi_stub.py` calls
`build_record_meta`, `render_record`, `latest_record_for_corner` and
`rebuild_manifest` directly, so a record carrying this seventh stage has its
JSON block and its prose generated from the same source as every other
record here — the property "Required fields" below depends on. Before it
writes anything it re-hashes every input and artifact the superseded record
names and refuses to proceed if a physical-flow input moved: a changed
netlist means the flow was re-run, and a fresh functional-verification stage
must not be stapled onto physical measurements that no longer describe it.
Re-run `flow/run_flow.py` first in that case. `--no-record` runs the
regression and writes nothing, for a dry check.

## Corner matrix

`flow/corners.json` is the single source of truth, and it is **not
provisional**. It transcribes the six shipped `sky130_fd_sc_hd` corners that
`spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`
Decision 5 commits to:

```
ss_n40C_1v60   ss_100C_1v60   tt_025C_1v80   tt_100C_1v80   ff_n40C_1v95   ff_100C_1v95
```

`tt_025C_1v80` is nominal. Decision 5 names `ss_n40C_1v60` the presumptive
setup-binding corner (sky130's low-Vdd temperature inversion) and
`ff_n40C_1v95` the presumptive hold-binding one — both stated there as design
targets awaiting real STA, which is what this flow is for. Issue #11 proposed
an interim slow/typ/fast triple *pending* that decision record; the record
landed first, so this flow adopts the full committed six instead.

A run covering fewer than all six corners must state why, in
`--subset-justification`; the justification is written into every record the
run produces, and `check_records.py` rejects a subset record without one.

**Each corner gets its own full rebuild** — synthesis and place-and-route are
re-run against that corner's liberty, not just re-timed. That is more
expensive than one build swept across corners, and it is the point: this flow
exists to put the *tools* under load at every corner, not only OpenSTA.

Each corner is additionally re-timed by `klt sta` against its own routed DEF,
because that is the only way to get per-corner **TNS**: `klt
place-and-route`'s own `pdk.sweep_corners` breakdown reports worst slack per
corner and no TNS
([klayout-tools#1866](https://github.com/2AMLogic/klayout-tools/issues/1866)).
The native sweep's rows are recorded anyway, as a cross-check, under
`stages.place_and_route.native_corner_sweep`.

---

## Directory and naming convention

```
flow/
  corners.json                   # the committed corner matrix
  waivers.json                   # timing waivers, keyed by corner
  drc-deck-coverage.json         # the DRC deck's known gaps, pinned by content hash
  request-*.json                 # one committed request per stage
  run_flow.py                    # the driver
  check_records.py               # the lint
  tests/                         # the lint's own self-tests
  build/<corner>/                # per-corner scratch (gitignored)
  smoke-utmi_stub/               # <experiment-slug>
    records/
      <record-id>.md             # one append-only record per corner
      MANIFEST.sha256            # one line per record: <sha256>  <filename>
    artifacts/
      <record-id>/               # every klt JSON envelope, verbatim
```

- **`<experiment-slug>`** — one directory per distinct claim under test, not
  per run. `smoke-utmi_stub` is the toolchain-plumbing smoke experiment. Real
  RTL gets its own slug.
- **`<record-id>`** — `<YYYYMMDD>-<HHMMSS>-<short-git-sha>-<corner-id>`, e.g.
  `20260915-113028-7d56be5-tt_025C_1v80`. Every corner of one sweep shares the
  timestamp and sha, so the six records of a run sort together and are
  visibly one run. The `git_revision` field records the revision the flow was
  *run at* — necessarily the parent of the commit that adds the record.
- **`<corner-id>`** — the liberty corner name exactly as the PDK spells it
  (`tt_025C_1v80`), never a re-invented spelling. It must be one of
  `corners.json`'s committed names; the lint checks that the record-id's
  corner field, the record's `corner` field, and `corner_matrix.run` all
  agree.

This mirrors the analog side's convention in
[`2AMLogic/gf180-bandgap`'s `sim/README.md`](https://github.com/2AMLogic/gf180-bandgap)
(experiment slug / record id / append-only records / frozen artifacts per
record) so the two halves of this program read as one house style.

## The append-only rule

**A record, once written, is never edited and never deleted.** A re-run —
including one that corrects a mistake — mints a *new* record with a new id
and names the record it replaces in its `supersedes` field. There is no
mechanism for changing what a record said, and that is the entire point: an
evidence trail you can rewrite is not evidence.

Enforced in two layers, because either alone is insufficient:

1. **`MANIFEST.sha256`** — one line per record. The lint fails if a listed
   record is missing (deletion) or its hash has changed (edit), and if a
   record exists on disk with no manifest line (an unverifiable record).
   Works offline, with no git.
2. **A base-ref comparison** — every record blob present in `origin/main`
   must be byte-identical in the working tree, and no manifest line present
   in the base may be removed or rewritten. This closes the hole layer 1
   cannot: an edit that also re-stamps the manifest. The base ref is not
   writable from a PR, so the comparison cannot be laundered.

CI runs both. Layer 2 needs real history, which is why the `flow-records` job
checks out with `fetch-depth: 0`.

## Required fields

`check_records.py`'s `REQUIRED_FIELDS` table is normative; the list below is
its shape, grouped. Every record embeds them as JSON in a
`<!-- record-meta ... -->` block at the top of the file, with a human-readable
rendering below it. The JSON is what the lint reads; the prose is what a
human reads. They are generated together from one source, so they cannot
drift apart.

- **Identity** — `schema`, `record_id`, `experiment`, `corner`,
  `created_utc`, `git_revision`, `supersedes` (may be null).
- **Design** — `design.hdl_toplevel`, `design.sources`, and
  `design.anchors_design_claim`, which is `false` for every record in this
  experiment and is checked as such by the tests.
- **Corner matrix** — `corner_matrix.committed` (must equal
  `corners.json`), `corner_matrix.run`, `corner_matrix.subset_justification`.
- **Timing** — `timing.corner`, `timing.worst_slack_ns`,
  `timing.total_negative_slack_ns`, `timing.verdict`, `timing.waiver`,
  `timing.note`.
- **Stages** — a status for each of the six, plus the numbers each stage's
  verdict rests on: synthesis instance count, P&R `stage_reached`,
  `gds_path` and the `power` block `klt place-and-route` echoes back (what
  PDN it actually generated), LVS engine, its warnings-only mismatches and
  its separate `power_connectivity` verdict, DRC violation count, deck name,
  deck content hash, the deck's known coverage gaps, and the run's own
  per-run coverage block.
- **Provenance** — `klt` / KLayout / OpenROAD / Yosys versions, the resolved
  PDK, `provenance.inputs` (every committed file the run consumed, with its
  content hash), and `provenance.artifacts` (every committed output, with its
  content hash).
- **Tool gaps** — `tool_gaps`, the upstream filings made while producing the
  record.

## The freshness rule

Every path in `provenance.inputs` is re-hashed by the lint against the
current tree. A record whose recorded input hash no longer matches the file
it names is **stale** and fails CI: the evidence describes a source that no
longer exists. The fix is always to re-run the flow and mint new records —
never to edit the hash.

This is what makes "staleness is failure" enforceable rather than
aspirational: editing `rtl/utmi_stub.v` or any committed request document
turns every existing record red until the flow is re-run.

**One exemption, and only one: a record another record supersedes.** Records
are append-only, so a re-run never edits or deletes its predecessor — it
mints a new record naming the old one in `supersedes`. The superseded record
is then frozen evidence of what the flow reported against an *earlier*
revision of its own committed inputs, and that is exactly what it is kept
for; freshness, which is a claim about the current tree, is not asked of it.
Freshness still applies in full to every **standing** record, so a request
change with no re-run still turns the evidence red — the only thing the
exemption removes is retro-failing history that a deliberate, recorded
re-run has already replaced. `run_flow.py` fills `supersedes` in
automatically from the newest existing record for the same corner, so the
chain is machine-maintained rather than hand-asserted.

A deeper tier exists and is opt-in, because it needs a toolchain:

```bash
python3 flow/check_records.py --klt-check
```

re-verifies each committed `drc-report.json` / `lvs-report.json` through
`klt drc --check` / `klt lvs --check`, which re-hash the reports' own layout,
reference and deck inputs against the recorded provenance. CI does not run
this (it would need the full toolchain for a check the hash comparison above
already approximates); run it locally after a `klt` upgrade.

## The timing gate

`klt place-and-route` reports scalar WNS/TNS and documents that it has no
pass/fail concept of its own, so **this flow owns the gate.** Four verdicts,
and `check_records.py` enforces the consistency of each against the numbers:

| Verdict | Means | Gate |
|---|---|---|
| `pass` | WNS ≥ 0 and TNS ≥ 0, from a real measurement | run continues |
| `fail` | WNS < 0, no waiver | `run_flow.py` **exits 1**; the lint rejects the record |
| `waived` | WNS < 0, covered by an entry in `waivers.json` | allowed, and the waiver text is written into the record |
| `unconstrained` | OpenSTA reported its no-constrained-path sentinel | **not a pass**; requires a written `timing.note` |

A waiver must carry a `reason`, an `author` and a `date`. It lives in
`flow/waivers.json` — a committed, reviewable file — never on a command line.
A waiver covers a negative WNS only; **no waiver can turn `unconstrained`
into a pass**, and the lint refuses a record that tries.

### Why every corner in the committed evidence is `unconstrained`

This is the single most important thing to understand about the smoke
evidence, and it is stated here rather than buried in a record.

`utmi_stub` is nine flip-flops whose `D` inputs are primary input ports and
whose `Q` outputs are primary output ports. **There is no
register-to-register path anywhere in it.** Neither `klt place-and-route` nor
`klt sta` has any surface for `set_input_delay` / `set_output_delay` or a
caller-supplied SDC — both emit `create_clock` and nothing else — so the
ports carry no arrival or required time, OpenSTA has no startpoint or
endpoint, and every timing field comes back as its unconstrained sentinel,
literally `1e+39`.

That sentinel is a *positive number*. A naive `wns >= 0` gate reads it as an
enormous margin and reports "timing closed" with maximum confidence on zero
evidence. This flow classifies it as its own verdict precisely so that cannot
happen here, and `check_records.py` fails any record that calls it a pass.

Filed upstream as
[klayout-tools#1865](https://github.com/2AMLogic/klayout-tools/issues/1865),
with a suggested fix for the sentinel-as-measurement trap independent of the
missing constraint surface.

**Consequence, stated plainly: this flow has closed no timing, at any corner.**
The six committed records are evidence that the multi-corner plumbing runs,
reports, and is gated — not evidence that anything met a timing target. The
first design with a real register-to-register path will produce real numbers
through the identical, unchanged flow.

## The DRC coverage rule

A clean DRC verdict from a deck whose holes are undisclosed is a false claim.
So:

- `flow/drc-deck-coverage.json` enumerates the deck's known gaps — ten of
  them, with sources — pinned to the deck's **content hash**.
- Every DRC record embeds that enumeration and the deck's content hash.
- `check_records.py` fails if the record's deck hash does not equal the
  pinned hash (so a `klt` upgrade that changes the deck forces the
  enumeration to be re-derived and re-reviewed, rather than silently going
  stale), and fails if a record drops a gap the pinned coverage declares.

Read a record's DRC verdict together with its per-run `coverage` block, never
alone: `rules_skipped` names rules that never executed because their layers
are absent from the stream, and `layers_in_stream_without_rules` names drawn
geometry no rule looked at.

The deck is `klt`'s **curated** sky130 deck: 47 rules built from KLayout
`Region` primitives, not the PDK-native `sky130A.lydrc` signoff deck. It is a
real check, and it is not signoff.

## The power-connectivity rule

**An LVS `match` is a verdict about signals only. It is not evidence that the
design is powered, and this flow never lets the first stand in for the
second.**

The LVS reference here is `klt place-and-route`'s own as-built
`write_verilog` netlist, which carries no supply pins at all. A
`gate-level-verilog` compare therefore *drops* the layout's supply nets
rather than failing on them — so a layout with no power grid whatsoever can
and did report `status: "match"` at all six corners — with one supply rail
corresponded to a *signal* net in the bargain (`VGND` → `TXREADY`). That was
issue #59,
and the hole mattered because this experiment is the template the real UTMI
digital layer inherits.

Four things close it, and all four are enforced, not documented:

- **`request-par-utmi_stub.json` must declare a `power` block.**
  `check_records.py`'s `REQUEST_REQUIREMENTS` requires `power.power_net`,
  `power.ground_net` and `power.straps` on the P&R request. Without them
  `klt place-and-route` generates no PDN at all: no straps, no global
  connect, no tapcells, and every standard cell's `VPWR`/`VGND` pin left on
  a per-row island. The committed block is met1 `FOLLOWPIN` rails plus met4
  and met5 straps, with met1↔met4 and met4↔met5 connects.
- **`request-lvs-utmi_stub.json` must declare
  `options.power_connectivity.expected_nets`** (also enforced by
  `REQUEST_REQUIREMENTS`). Omitted, `klt lvs` still runs the check — but only
  as a *relative* one: every instance's same-named pin must reach the same
  net as every other instance's. A design where all of them agree on the
  *wrong* net passes that, which is exactly how the pre-#59 evidence
  corresponded `VGND` to `TXREADY` and still reported `match`. Naming the
  nets makes it absolute — verified by construction: re-running `klt lvs` on
  the committed `tt_025C_1v80` artifacts with `VPWR` declared as `TXREADY`
  returns `power_connectivity.status: "mismatch"` ("must reach net 'TXREADY'
  … but 57 instance(s) reach a different net") while the signal `status`
  stays `match`. `klt lvs` also emits no finding for a declared pin it never
  resolved, so `unchecked_expected_pins` is recorded and gated on as well
  (klayout-tools#1978) — the `klt` build behind the current records predates
  that field, so it reads `null` there and the gate is latent rather than
  exercised.
- **Every record carries `stages.lvs.power_connectivity`**, `klt lvs`'s
  separate power/ground verdict (klayout-tools#1964), reported *beside*
  `status` and never folded into it. `run_flow.py` records a klt build that
  emits no such block as its own `unreported` status with a written note —
  never as a pass.
- **`run_flow.py` and `check_records.py` both gate on it.** A `mismatch` is a
  gate failure (`run_flow.py` exits 1; the lint rejects the record); an
  `unchecked`/`unreported`/absent verdict on a record that claims a generated
  PDN is UNVERIFIED and must be written down as such. Records minted before
  the `power` block existed predate the verdict entirely and are not
  retro-failed — they are append-only evidence of exactly the state this
  section describes.

What the committed evidence now says, concretely: every record reports
`place_and_route.power.pdn: true` with a real `tapcell_master`, and
`lvs.power_connectivity.status: match` over 57 instances with zero findings,
at all six corners. Read that verdict together with the LVS `status` above
it, never instead of it.

**One caveat, in the check itself, filed as
[klayout-tools#2076](https://github.com/2AMLogic/klayout-tools/issues/2076).**
Every record's `power_connectivity.power_pins` reads
`["VGND", "VPB", "VPWR", "Y"]`. `Y` is a signal output, not a supply: `klt`
derives the power-pin universe as "declared by the library, not carried by
the gate-level-Verilog reference", and CTS's clock-load `inv_1` has its `Y`
output dangling, so no reference pin of that name exists to subtract. Here it
is harmless — one instance, so the check's "all instances of this pin reach
the same net" rule passes trivially, and the `VGND`/`VPWR`/`VPB` half of the
verdict is the real one. It will **not** stay harmless on the real UTMI
layer: CTS emits a clock load per leaf, and two of them on different leaf
nets turn that rule into a spurious `mismatch`. Expect to re-read this
verdict, not just inherit it, when the real datapath goes through.

## Upstream tool gaps found while building this flow

Per `CLAUDE.md`'s friction protocol, each is filed generically against the
tool at `2AMLogic/klayout-tools`, and each is linked from every record:

| Issue | Gap |
|---|---|
| [#1865](https://github.com/2AMLogic/klayout-tools/issues/1865) | No `set_input_delay`/`set_output_delay`/SDC surface on `place-and-route` or `sta`, and the `1e+39` unconstrained sentinel is returned as if it were slack. |
| [#1866](https://github.com/2AMLogic/klayout-tools/issues/1866) | The per-corner sweep reports WNS only — no per-corner TNS, so recovering it costs one extra `klt sta` run per corner. |
| [#1867](https://github.com/2AMLogic/klayout-tools/issues/1867) | `klt drc` and `klt extract` are the only physical-flow stages with no request-document surface. |
| [#1868](https://github.com/2AMLogic/klayout-tools/issues/1868) | `place-and-route` resolves the PDK via a search root, but the documented `openroad` container wrapper only mounts `$PDK_ROOT` — every stage dies on an opaque `cannot read file`. |
| [#2073](https://github.com/2AMLogic/klayout-tools/issues/2073) | Stage responses use two shapes for the same output-artifact path field — `synthesize` emits `{"path": …, "scope": "repo"}`, `place-and-route` a plain absolute string — with `schema_version` unchanged, so a flow chaining the stages cannot detect which it will get. `run_flow.py`'s `envelope_path()` accepts both. |
| [#2076](https://github.com/2AMLogic/klayout-tools/issues/2076) | `lvs`'s `power_connectivity` admits a dangling signal output (CTS's clock-load `inv_1.Y`) into its power-pin universe when the design has no other carrier of that pin name — harmless at one instance, a spurious `mismatch` at two. See "The power-connectivity rule". |

An earlier filing,
[#560](https://github.com/2AMLogic/klayout-tools/issues/560) (`klt synthesize`
crashes on a Yosys build with no `sequential_area` field), came out of the
synthesis baseline in [`docs/baseline.md`](../docs/baseline.md) and is
worked around by using `yowasp-yosys`.

## What this flow does *not* produce

Stated so no reader mistakes the committed GDS for a signoff artifact:

- **No timing closure.** See above.
- **A PDN, but no power signoff.** `request-par-utmi_stub.json` now declares
  a `power` block (met1 `FOLLOWPIN` rails, met4 + met5 straps, met1↔met4 and
  met4↔met5 connects), so `klt place-and-route` generates a real grid,
  inserts `sky130_fd_sc_hd__tapvpwrvgnd_1` tapcells and places fillers
  explicitly — and `klt lvs`'s `power_connectivity` verdict is `match` at
  every corner (see "The power-connectivity rule" above). What that is
  **not**: an IR-drop, electromigration or power-integrity analysis, or a
  power number of any kind. No stage in this flow performs power analysis,
  and the grid's geometry was chosen to be a working, checkable PDN on this
  PDK, not a budgeted one. (The `sky130_fd_sc_hd` tap and filler cells have
  only supply pins, which the as-built gate-level Verilog reference does not
  carry, so `klt lvs` prunes them as power-only cells before comparing —
  that is the one warnings-only mismatch every LVS record carries.)
- **No IO ring, no metal fill, no `DONT_USE_CELLS` exclusion.** Core-only
  floorplan.
- **No SDF-annotated post-layout timing simulation.** Issue #37 re-ran
  `verification/test_utmi_stub.py` against the post-layout gate-level netlist
  (`layout/utmi_stub.asbuilt.v`, LVS-proven structurally equivalent to
  `layout/utmi_stub.extracted.spice`) and it passed — see
  `flow/postlayout_verify_utmi_stub.py` and the `functional_verification`
  stage of `flow/smoke-utmi_stub/records/20260919-001148-0f7636d-tt_025C_1v80.md`,
  the standing nominal-corner record, which re-ran the regression against the
  post-PDN netlist issue #59 committed (issue #63; the earlier
  `…-9281bc4-…` record it descends from names the pre-PDN netlist and stands
  as history only). That is a **functional-only** check (zero-delay
  `FUNCTIONAL` cell models, no SDF back-annotation — no post-route SDF exists
  for this design in the first place), and only for the toolchain-smoke
  design. It is **not** a timing-annotated re-verification, and it is **not**
  a post-layout claim about the real UTMI digital datapath — see that
  record's own "Post-layout functional verification" section for the exact
  scope statement.
- **No antenna/ERC signoff.** `klt place-and-route` reports zero post-repair
  antenna violations; a real ERC pass (`klt erc`) has not been run.
