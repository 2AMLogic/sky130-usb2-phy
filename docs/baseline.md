# Toolchain baseline: `utmi_stub.v`

**Status: measured, 2026-08-05.** This is the first evidence record in this
repo's digital flow, produced while bootstrapping the harness itself (issue
#3). Unlike `2AMLogic/sky130-modexp`'s `docs/baseline.md` (a real design's
area/optimization baseline), this document exists to prove the harness
works end-to-end, not to anchor a future optimization program — `utmi_stub.v`
is a deliberately trivial registered pass-through, not real UTMI logic. When
the actual UTMI digital layer lands (a separate, future issue), it gets its
own baseline record; this one stays as the toolchain-plumbing proof.

## The measurement

`klt functional-verification` (Icarus Verilog 12.0, cocotb 2.0.1) and `klt
synthesize` (Yosys 0.67, via [`yowasp-yosys`](https://pypi.org/project/yowasp-yosys/) —
see [`docs/environment-setup.md`](environment-setup.md) §4 for why the
distro-packaged Yosys does not work) against `sky130_fd_sc_hd` /
`tt_025C_1v80`, with `sky130A` fetched via `volare`
(open_pdks commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`).

| Design | Functional verification | sky130 cells | Cell breakdown |
| --- | --- | --- | --- |
| `utmi_stub.v` — trivial registered pass-through (TxValid/DataOut -> TxReady/RxValid/DataIn, one cycle later) | 2/2 tests pass | **9** | 9× `sky130_fd_sc_hd__dfrtp_1` (flip-flops only) |

9 flip-flops for a design with a 1-bit `TxValid` input registered onto two
outputs (`TxReady`, `RxValid`) plus an 8-bit `DataOut` registered onto
`DataIn` (8 + 1 + 1 = 10 source registers) is expected to collapse to 9: with
no logic between `TxValid` and either `TxReady` or `RxValid`, and both driven
by the identical D input, Yosys's synthesis merges the two into a single
flip-flop fanned out to both output ports. `area_um2` for the whole design
is `225.216` (all sequential — `sequential_area_um2` equals `area_um2`,
confirming there is no combinational logic, as expected for a pure register
stage).

## Reproducing it

```bash
# functional verification (2/2 pass)
klt functional-verification verification/request-utmi_stub.json --format json

# synthesis (9 cells) -- run from a directory outside /tmp, see
# docs/environment-setup.md §4's yowasp-yosys filesystem note
mkdir -p ~/scratch/utmi_stub_synth && cd ~/scratch/utmi_stub_synth
cp /path/to/sky130-usb2-phy/rtl/utmi_stub.v .
cat > req.json <<'JSON'
{ "schema": "klt.synthesize.request/1", "engine": "yosys",
  "sources": ["utmi_stub.v"], "hdl_toplevel": "utmi_stub",
  "pdk": { "cell_library": "sky130_fd_sc_hd", "corner": "tt_025C_1v80" },
  "constraints": { "clock_period_ns": null } }
JSON
PDK=sky130A klt synthesize req.json --format json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["instance_count"])'
```

## What this does and does not prove

This proves the digital verification + synthesis harness (cocotb + Icarus,
Yosys against `sky130_fd_sc_hd`, both driven through `klt`) works
end-to-end in this repo, copied from `2AMLogic/sky130-modexp`'s working
pattern rather than invented fresh — the acceptance criterion issue #3 set
out to satisfy. It says nothing about the real UTMI digital layer's
eventual area, timing, or correctness; that RTL does not exist yet (see
`spec/architecture.md`'s partition table and "first buildable slice") and is
out of scope for this issue per `CLAUDE.md`'s scope-discipline rule.

## Known friction filed

`klt synthesize` (0.2.0) crashes against Yosys builds that don't report a
`sequential_area` field in `stat -json` output (e.g. Ubuntu noble's
`apt install yosys`, at 0.33) — worked around here with `yowasp-yosys`
(0.67). Filed generically against the tool:
[2AMLogic/klayout-tools#560](https://github.com/2AMLogic/klayout-tools/issues/560).
See `docs/environment-setup.md` §4 for the full writeup.

---

# Synthesis record: FS transmit path (issue #12)

**Status: measured, 2026-08-08.** The first synthesis record for real PHY
digital-layer RTL in this repo (everything above is the toolchain-plumbing
stub). `rtl/usb_tx_serializer.v` (which instantiates `rtl/usb_tx_framer.v`,
`rtl/usb_bit_stuffer.v`, and `rtl/usb_nrzi_encoder.v` — see `rtl/README.md`)
is the FS transmit datapath: UTMI TX handshake, SYNC/EOP packet framing, bit
stuffing (bypassable), and NRZI encoding.

**Convention note:** issue #12's Deliverables section asks for this record
"in the convention the physical-flow issue (#11) establishes." As of this
measurement #11 is still open and has not landed a convention — per that
issue's own Affected Files guidance, this section reuses the interim
`klt synthesize` recipe below (the same one `utmi_stub.v`'s baseline above
uses) rather than blocking on #11.

## The measurement

Same toolchain versions as `utmi_stub.v`'s baseline above (Icarus Verilog
12.0, cocotb 2.0.1, Yosys 0.67 via `yowasp-yosys`, `sky130_fd_sc_hd` /
`tt_025C_1v80`, `sky130A` via `volare`, open_pdks commit
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`).

| Design | Functional verification | sky130 cells | Area (µm²) | Sequential area (µm²) |
| --- | --- | --- | --- | --- |
| `usb_tx_serializer.v` — FS transmit datapath (UTMI handshake -> SYNC/EOP framing -> bit stuffing -> NRZI encoding -> line-state driver interface) | 10/10 tests pass | **142** | 1518.9568 | 778.2464 |

**Reading the cell count**: `klt synthesize`'s top-level `instance_count`
(13) and `instance_counts_by_type` report only the **top module's own**
scope — 10 standard cells plus 3 un-flattened submodule instance
references (`usb_bit_stuffer`, `usb_nrzi_encoder`, `usb_tx_framer` each
counted once, as opaque cells, not their own contents). Yosys' `stat
-liberty` **does** recursively fold every submodule's own area into the
top module's `area` figure (`1518.9568` above already **is** the whole
design's area, matching `area_um2` in `klt synthesize`'s own JSON output —
no correction needed there), but not its `num_cells`/`num_cells_by_type`
breakdown. The **142** cell count above is this record's own aggregate:
every module's `num_cells_by_type` entry, from the same `stat -json`
sidecar file (`.klt/synthesize/usb_tx_serializer_stats.json`), summed
while skipping any entry that names a user module (`usb_bit_stuffer`,
`usb_nrzi_encoder`, `usb_tx_framer`) rather than a `sky130_fd_sc_hd__*`
leaf cell — see "Reproducing it" below for the exact computation. Of the
142 cells, 31 are flip-flops (29× `sky130_fd_sc_hd__dfrtp_1` +
2× `sky130_fd_sc_hd__dfstp_2`, the latter from `usb_nrzi_encoder.v`'s
`level_out` register, which resets to `1` — a set-type flop, not a
reset-type one) and 111 are combinational.

**No inferred latches, no combinational loops** (issue #12 acceptance
criterion): confirmed two ways — (1) the aggregated cell-type breakdown
above contains no latch primitive (no `sky130_fd_sc_hd__dlx*`/`sky130_fd_sc_hd__dlrtp*`
entry); (2) a standalone `hierarchy` + `proc` + `opt_clean` + `check
-noinit` pass (no `synth`/`dfflibmap`/`abc` mapping, so it reports on the
RTL's own structure directly) prints `Found and reported 0 problems.` for
every one of the four modules.

## Reproducing it

```bash
# functional verification (10/10 pass)
klt functional-verification verification/request-usb-tx.json --format json

# synthesis -- run from a directory outside /tmp, see
# docs/environment-setup.md §4's yowasp-yosys filesystem note
mkdir -p ~/scratch/usb_tx_synth && cd ~/scratch/usb_tx_synth
cp /path/to/sky130-usb2-phy/rtl/usb_tx_serializer.v .
cp /path/to/sky130-usb2-phy/rtl/usb_tx_framer.v .
cp /path/to/sky130-usb2-phy/rtl/usb_bit_stuffer.v .
cp /path/to/sky130-usb2-phy/rtl/usb_nrzi_encoder.v .
cat > req.json <<'JSON'
{ "schema": "klt.synthesize.request/1", "engine": "yosys",
  "sources": ["usb_tx_serializer.v", "usb_tx_framer.v", "usb_bit_stuffer.v", "usb_nrzi_encoder.v"],
  "hdl_toplevel": "usb_tx_serializer",
  "pdk": { "cell_library": "sky130_fd_sc_hd", "corner": "tt_025C_1v80" },
  "constraints": { "clock_period_ns": null } }
JSON
PDK=sky130A klt synthesize req.json --format json
# aggregate the TRUE flat cell count across every module (top-level
# instance_count/instance_counts_by_type only reflects the top module's
# own scope, per the "Reading the cell count" note above):
python3 -c '
import json
d = json.load(open(".klt/synthesize/usb_tx_serializer_stats.json"))
total = 0
for mod in d["modules"].values():
    for ctype, cnt in mod["num_cells_by_type"].items():
        if ctype.startswith("sky130_fd_sc_hd__"):
            total += cnt
print(total)
'
```

## What this does and does not prove

This is a synthesizability and (aggregate) area/cell-count measurement
against `sky130_fd_sc_hd` at the nominal (`tt_025C_1v80`) corner — a
comparison point for the RX path (a future issue) and the eventual top
level, per issue #12's Deliverables section. It is **not** a timing-closed
result: `klt synthesize`'s own `--help` documents its `timing` response
field as always `null` (deferred to a future OpenROAD/OpenSTA step outside
`klt synthesize`'s own contract), and this record makes no claim about
which of `spec/decision-records/0001` Decision 5's six committed PVT
corners this design would close timing against — that is explicitly out of
scope for this issue and this record.
