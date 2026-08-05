# verification

cocotb testbenches and Icarus cross-checks. Recorded results are append-only
evidence.

- `test_utmi_stub.py` — cocotb testbench for `rtl/utmi_stub.v`, a trivial
  registered pass-through (not real UTMI protocol logic — see issue #3).
  Proves the digital verification/synthesis harness (cocotb + Icarus,
  Yosys against `sky130_fd_sc_hd`, both through `klt`) works end-to-end in
  this repo, copied from the working pattern in `2AMLogic/sky130-modexp`
  rather than invented fresh.
- `request-utmi_stub.json` — `klt functional-verification` request driving
  `test_utmi_stub.py` against `utmi_stub.v` via Icarus.

Run it with:

```bash
klt functional-verification verification/request-utmi_stub.json --format json
```

See `docs/environment-setup.md` for the toolchain setup this requires, and
`docs/baseline.md` for the synthesis cell-count measurement.
