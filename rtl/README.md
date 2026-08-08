# rtl

UTMI-side Verilog sources.

- `utmi_stub.v` — a trivial registered pass-through using UTMI-shaped signal
  names (`TxValid`/`TxReady`/`DataOut`/`DataIn`/`RxValid`, per
  `spec/usb2-phy.md` §3). **Not** the real UTMI digital layer — it exists
  solely to prove the cocotb/Icarus + Yosys toolchain works end-to-end in
  this repo (issue #3). The measured synthesis baseline for this stub is
  recorded in `docs/baseline.md`.

## FS receive path (issue #13)

The FS receive datapath, from the DP/DM line-level inputs (delivered by the
differential-receiver/squelch sibling canary, out of scope here) up to the
UTMI byte interface. Clocking, CDC discipline, reset scheme, and the UTMI
port table are all fixed by
`spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`
("decision record #9") — none of it is invented in this RTL. Verified
against `verification/usbfs/` (the behavioral ideal-transceiver reference
model) via `verification/test_usb_rx.py`; the frequency-offset sampling
margin is derived in `docs/bit-sync-budget.md`.

| Module | Clock domain | Implements |
|---|---|---|
| `usb_bit_sync.v` | 144 MHz recovery (`clk_144`) | Pad-level input synchronization (2-flop) plus the 12x-oversampled, hard-resync-on-every-transition bit/edge synchronizer — `spec/architecture.md`'s "bit/edge synchronization logic" block; `spec/usb2-phy.md` §4/§6 (oversampling ratio, sampling margin). |
| `usb_nrzi_decoder.v` | 144 MHz recovery | NRZI decode (mirrors the TX path's encoder) — `spec/usb2-phy.md` §7.1.9-equivalent NRZI rule (USB 2.0 Spec Rev 2.0 §7.1.9). Gated so SE0/SE1 bit cells (EOP, bus reset) are never decoded as if they were NRZI data. |
| `usb_bit_destuffer.v` | 144 MHz recovery | Bit destuffing and 7th-consecutive-1 (bit-stuff violation) detection, gated to run only from SOP lock through EOP — `spec/usb2-phy.md` §6/§7 (`RxError` on a bit-stuff violation, no silent corruption). |
| `usb_rx_framer.v` | 144 MHz recovery | SOP/SYNC lock, EOP detection, byte deserialization, missing-EOP watchdog, and bus-reset (sustained SE0) / suspend (sustained idle J) detection — `spec/usb2-phy.md` §3/§6/§7 (`RxActive`, `RxError`, packet framing, reset/suspend signaling). |
| `usb_linestate.v` | 144 MHz recovery (combinational) | Raw `LineState[1:0]` formatting (`{D-, D+}`, not pre-encoded J/K) per decision record #9 Decision 4's port table — `spec/usb2-phy.md` §3/§6 (`LineState`). |
| `usb_rx_cdc.v` | Crosses 144 MHz recovery -> 30 MHz UTMI (`clk_utmi`) | The 144<->30 MHz domain crossing: async (dual-clock) elastic FIFO for `RxValid`/`DataIn[7:0]`, 2-flop synchronizers for `RxActive`/`RxError`/`LineState`/bus-reset/suspend, and the per-domain (async-assert/sync-deassert) reset synchronizers — decision record #9 Decision 3 (CDC discipline), in full. |
| `usb_rx_path.v` | Both (integration top) | Wires the above into the dataflow order `spec/architecture.md`'s block diagram describes; not itself a "one function" deliverable module, but the single HDL toplevel `verification/request-usb-rx.json`'s cocotb testbench attaches to. |
