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
