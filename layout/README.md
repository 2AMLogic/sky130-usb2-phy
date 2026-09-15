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

Naming is `<hdl_toplevel>.<role>.<ext>`, with the routed DEF/GDS taking the
bare `<hdl_toplevel>.<ext>` form. One top-level design per name — there is no
per-corner or per-run suffix here, because only one corner's artifacts are
ever committed.

The other five committed corners each get a full, independent rebuild, but
their DEF/GDS stay in gitignored scratch under `flow/build/<corner>/`. Their
content hashes are recorded in their evidence records, so a run is
reproducible and auditable; the files themselves are regenerated on demand
rather than stored six times over.

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
