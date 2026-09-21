# `layout/` — committed physical artifacts

**These files are toolchain plumbing and anchor no design claim.**
`utmi_stub` is nine flip-flops with no combinational logic. See
[`flow/README.md`](../flow/README.md)'s opening paragraph; nothing here may be
cited as evidence for a `spec/` claim.

## What lands here

`flow/run_flow.py` copies the **nominal corner**'s (`tt_025C_1v80`) physical
artifacts into this directory, and only that corner's:

| File | What it is | Produced by |
|---|---|---|
| `utmi_stub.gds` | Routed GDS — the DEF merged with the standard-cell GDS views via KLayout's `pya`, in-process | `klt place-and-route` (`gds_path`) |
| `utmi_stub.def` | Routed DEF | `klt place-and-route` (`def_path`) |
| `utmi_stub.asbuilt.v` | As-built gate-level netlist: CTS buffers, `repair_design`/`repair_timing` resizes and antenna diodes included. **This is the LVS reference**, not the pre-CTS synthesis netlist | `klt place-and-route` (`verilog_path`) |
| `utmi_stub.extracted.spice` | Layout-derived netlist at cell-instance granularity (every standard cell a pin-only black box). **This is the LVS layout side** | `klt extract --abstract-cells` |
| `erc-supply-spec.json` | The **T1 item 11** (power delivery, structural) `klt erc` supply spec — every field justified inline (issue #72) | committed data (not a flow stage) |
| `erc-supply-report.json` | Verbatim `klt erc --format json` run of that spec against the committed `utmi_stub.gds` — the item-11 supply read | `klt erc` (see "The ERC supply read" below) |

Naming is `<hdl_toplevel>.<role>.<ext>`, with the routed DEF/GDS taking the
bare `<hdl_toplevel>.<ext>` form. One top-level design per name — there is no
per-corner or per-run suffix here, because only one corner's artifacts are
ever committed.

The other five committed corners each get a full, independent rebuild, but
their DEF/GDS stay in gitignored scratch under `flow/build/<corner>/`. Their
content hashes are recorded in their evidence records, so a run is
reproducible and auditable; the files themselves are regenerated on demand
rather than stored six times over.

## The ERC supply read (T1 item 11, issue #72)

The two `erc-*` files are one artifact pair, the structural power-delivery
read the T1 checklist grew on 2026-09-17 (upstream
[klayout-tools#2025](https://github.com/2AMLogic/klayout-tools/issues/2025)):
the spec declares every supply (`VPWR`, `VGND` — the names the cited P&R
response's own `power.power_net`/`.ground_net` report) as a `nets[]` entry
with `"kind": "supply"`, and the report shows each resolving to **exactly one
electrical island** — `erc_finding_count: 0`, with
`erc.net_connectivity:["VPWR"]` and `["VGND"]` in its `erc_coverage.checked`
(the tool stating the checks actually ran) and zero `erc.unconnected_net` /
`erc.supply_short`. Per item 11, that supply-findings state is the graded
quantity — **not** the envelope's overall `status: "clean_partial"`, whose
`_partial` is the sky130 antenna table's met3-met5 coverage gap, a
different item's subject.

**The `erc.missing_tie` half is not computed, and the report says so
mechanically**: `erc_coverage.inapplicable` carries
`{"id": "erc.missing_tie:[]", "reason": "no_ties_declared"}`. Declaring
`ties[]` on the klt release line this repo's records cite pins collapses a
routed design into one island and reports a false `erc.supply_short`
(upstream [klayout-tools#2169](https://github.com/2AMLogic/klayout-tools/issues/2169),
reproduced four ways in `gf180-drone-fc`'s FRICTION F-034), so the spec
deliberately omits it — see the spec's own `_comment` block. What stands in
for the well-tie evidence, per the same records, is the real PDN the routed
artifact was produced with (`stages.place_and_route.power`:
`power.pdn: true`, `power.tapcell_master:
"sky130_fd_sc_hd__tapvpwrvgnd_1"`, straps on met1/met4/met5 — all covered by
the spec's stackup) and the same run's device-aware
`stages.lvs.power_connectivity.status: "match"` on power pins VGND, VPB and
VPWR. That is an absence-of-evidence disclosure, not a zero.

**Pinned tool state.** The committed report's provenance pins itself:
`provenance.input.content_hash` is `sha256:f234c14426e7…` — the committed
`utmi_stub.gds`, byte for byte — and `provenance.spec.content_hash` is the
committed spec. It was produced by klayout-tools at commit
`e8ca621a6961879cec1af60cc932c3b3d58ddcaa` (upstream main, unreleased
post-v0.5.0): the released `klt` v0.5.0 that this repo's flow records cite
predates `stackup[0].active_layer` and silently ignores it (its spec
validation accepts unknown keys), which would compute raw-poly antenna
denominators while the spec looks like it requires `poly ∩ diff`. Re-verify
either hash with `sha256sum`, and regenerate the report with the exact
invocation recorded in the spec's `_comment`.

## Where the DRC and LVS reports land

**Not here.** Reports are evidence, and evidence lives with the
evidence-record convention:

```
flow/smoke-utmi_stub/
  records/<record-id>.md                 # the human-readable verdict + provenance
  artifacts/<record-id>/drc-report.json  # `klt drc` envelope, verbatim
  artifacts/<record-id>/lvs-report.json  # `klt lvs` envelope, verbatim
  artifacts/<record-id>/extract-report.json
  artifacts/<record-id>/place-and-route-report.json
  artifacts/<record-id>/sta-report.json
  artifacts/<record-id>/synthesize-report.json
```

with `<record-id>` = `<YYYYMMDD>-<HHMMSS>-<short-git-sha>-<corner-id>`. There
is one such directory per corner per run, and DRC/LVS are run on **every**
corner's own GDS, not only the nominal one committed here.

Records are append-only: never edited, never deleted, enforced by
`flow/check_records.py` and by CI. See
[`flow/README.md`](../flow/README.md) for the full convention, the required
fields, the freshness rule, and what the current verdicts do and do not
claim.

## Regenerating

```bash
PDK=sky130A python3 flow/run_flow.py
```

Everything in this directory is a build product. Editing a file here by hand
invalidates every record whose `provenance.artifacts` cites its content hash,
and the lint will say so.
