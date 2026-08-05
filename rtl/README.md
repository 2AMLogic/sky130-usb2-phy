# rtl

UTMI-side Verilog sources.

- `utmi_stub.v` — a trivial registered pass-through using UTMI-shaped signal
  names (`TxValid`/`TxReady`/`DataOut`/`DataIn`/`RxValid`, per
  `spec/usb2-phy.md` §3). **Not** the real UTMI digital layer — it exists
  solely to prove the cocotb/Icarus + Yosys toolchain works end-to-end in
  this repo (issue #3). The measured synthesis baseline for this stub is
  recorded in `docs/baseline.md`.
