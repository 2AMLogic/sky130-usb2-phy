# rtl

UTMI-side Verilog sources.

- `utmi_stub.v` — a trivial registered pass-through using UTMI-shaped signal
  names (`TxValid`/`TxReady`/`DataOut`/`DataIn`/`RxValid`, per
  `spec/usb2-phy.md` §3). **Not** the real UTMI digital layer — it exists
  solely to prove the cocotb/Icarus + Yosys toolchain works end-to-end in
  this repo (issue #3). The measured synthesis baseline for this stub is
  recorded in `docs/baseline.md`. The real UTMI digital layer is
  `usb_utmi_top.v` (below), which is the `hdl_toplevel` any flow work should
  target; this stub stays only as the toolchain-plumbing proof.

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

## FS transmit path (issue #12)

The real UTMI-side transmit datapath: UTMI TX handshake in, SYNC/EOP packet
framing, bit stuffing (bypassable), NRZI encoding, and the line-state driver
interface handed to the current-mode driver sibling canary
(`spec/usb2-phy.md` §6's "Control interface from UTMI layer" row). One
module per function, so each is independently testable and independently
synthesizable — see `verification/test_usb_tx.py` for the bit-exact cocotb
suite that checks every module together against `verification/usbfs`'s
reference model, and `docs/baseline.md` for the measured synthesis result.

| Module | What it is | Clock domain | Spec section implemented |
|---|---|---|---|
| `usb_tx_serializer.v` | Top-level TX datapath: exposes the UTMI TX handshake (`TxValid`/`TxReady`/`DataOut[7:0]`/`OpMode[1:0]`) and the line-state driver interface (`tx_drive_en`/`tx_oe`/`tx_dp`/`tx_dn`); derives the 12 Mbps bit-time strobe (`bit_stb`) from `clk` by an exact `/12` divide (144 MHz oversampling clock / 12 = 12 Mbps, `spec/decision-records/0001`); instantiates and wires `usb_tx_framer.v` -> `usb_bit_stuffer.v` -> `usb_nrzi_encoder.v` in dataflow order. | 144 MHz oversampling clock (`spec/decision-records/0001` Decisions 1/3) | `spec/usb2-phy.md` §3 (UTMI TX handshake), §6 (line-state driver control interface); `spec/decision-records/0001` Decision 6 (bit-rate timing) |
| `usb_tx_framer.v` | Packet-level state machine: SYNC (fixed 8-bit `0x80` pattern) -> DATA (byte stream, bit-stuffed) -> FLUSH/HOLD (the "stuff bit immediately before EOP" and last-body-bit-visibility edge cases) -> EOP (SE0, SE0, J) -> IDLE. Owns `TxReady` back-pressure and the `tx_dp`/`tx_dn`/`tx_oe`/`tx_drive_en` line-state mux. | 144 MHz oversampling clock | `spec/usb2-phy.md` §3 (UTMI TX handshake, back-pressure), §6 (line driver interface); USB 2.0 Spec Rev 2.0 §7.1.9 (SYNC/EOP framing) |
| `usb_bit_stuffer.v` | Inserts a `0` after every six consecutive `1`s in the pre-NRZI stream; bypassable (`OpMode == 2'b10`, raw/transparent test mode, `spec/decision-records/0001` Decision 4); exposes a same-cycle `stuff_pending_after` lookahead so the framer can detect "the next bit-time is a forced stuff" without spending an idle bit-time to find out. | 144 MHz oversampling clock, gated by `bit_stb` | USB 2.0 Spec Rev 2.0 §7.1.9 (bit stuffing) |
| `usb_nrzi_encoder.v` | NRZI line encoder: `0` -> transition, `1` -> no transition, initialized from the idle J level; bypassable in lockstep with the bit stuffer for `OpMode == 2'b10`. | 144 MHz oversampling clock, gated by `bit_stb` | USB 2.0 Spec Rev 2.0 §7.1.9 (NRZI encoding) |

Every module is verified **bit-exactly** against `verification/usbfs`'s
reference model (`usbfs.packets`, `usbfs.scenarios`) — never against a
helper written inside the RTL testbench itself — including the
maximum-stuffing (all-ones) and maximum-transition (all-zeros) payloads, the
stuff-bit-immediately-before-EOP edge case, `TxReady` back-pressure timing,
the bit-stuffing/NRZI bypass mode, and a negative control (a mutated stuff
threshold is demonstrated to make the suite fail). See
`verification/test_usb_tx.py` and `verification/README.md`.

**Clock-domain-crossing note:** `TxValid`/`TxReady`/`DataOut`/`OpMode` are
presented *at this module's own ports* as already-synchronized 144 MHz-domain
signals, per `spec/decision-records/0001` Decision 3's per-signal CDC table
(which specifies 2-flop synchronizers crossing these to/from the 30 MHz UTMI
domain). Those synchronizer instances live one level up, in
`usb_utmi_top.v` (below), which is what a link controller actually connects
to; `usb_tx_serializer.v` itself is unchanged by that integration.

## The UTMI digital top (issue #52)

`usb_utmi_top.v` is **the** HDL toplevel for this repo's digital half — the
module `verification/request-usb-utmi_top.json` drives, and the
`hdl_toplevel` a synthesis / place-and-route flow should target (it replaces
`utmi_stub.v`, which was only ever toolchain-plumbing for issue #3).

| Module | Clock domain | Implements |
|---|---|---|
| `usb_utmi_top.v` | Both (integration top) | Instantiates `usb_tx_serializer.v` and `usb_rx_path.v` **unmodified**, exposes decision record #9 Decision 4's full UTMI port table (`Clock`, `Reset`, `TxValid`/`TxReady`/`DataOut[7:0]`, `RxValid`/`RxActive`/`RxError`/`DataIn[7:0]`, `LineState[1:0]`, `OpMode[1:0]`, `TermSelect`, `XcvrSelect[1:0]`, `SuspendM`) alongside the pad-side interface owed to the sibling analog canaries (`dp`/`dm` in, `tx_drive_en`/`tx_oe`/`tx_dp`/`tx_dn` out, `spec/usb2-phy.md` §6), and adds the TX-side 30↔144 MHz crossings and per-domain reset synchronizers Decision 3's CDC table specifies. |

What the top adds on top of the two datapaths (all derived in its header
comment, which cross-references every port to Decision 4's table row):

- **30 → 144 MHz**: 2-flop synchronizers on `TxValid`, `DataOut[7:0]`,
  `OpMode[1:0]`, `TermSelect`, `XcvrSelect[1:0]`, `SuspendM`, plus one
  destination-domain skew-guard flop on `TxValid` (not a third synchronizer
  stage) so `DataOut` is settled in the 144 MHz domain before the serializer
  is told a byte is available.
- **144 → 30 MHz `TxReady`**: a toggle (pulse) synchronizer — Decision 3's
  2-flop synchronizer on a level, plus a destination-domain edge detector —
  producing a **one-`Clock`-cycle** acknowledge per byte consumed. A plain
  level synchronizer would break Decision 4's "one byte per `TxReady`"
  handshake, because the serializer's `TxReady` level spans a whole 83.33 ns
  FS bit time (2.5 periods of the 33.33 ns UTMI clock).
- **Per-domain resets**: async-assert / sync-deassert, one synchronizer per
  domain, the same pattern `usb_rx_cdc.v` uses.
- **Pad-side driver gating**: `OpMode == 2'b01` (Decision 4's "Non-driving")
  and `SuspendM == 0` (suspend) deassert `tx_drive_en`/`tx_oe`. Disabling the
  drivers is an act on the pad-side control interface, which only exists at
  this level, so `usb_tx_serializer.v` (which implements only the
  `OpMode == 2'b10` bypass) is untouched.

Verified end-to-end by `verification/test_usb_utmi_top.py`: a DP/DM loopback
(TX ports → pads → RX ports, byte-exact against `usbfs`), RX-only and TX-only
replays of `test_usb_rx.py`/`test_usb_tx.py`'s scenario lists through the
top's ports, `OpMode`/`SuspendM` behaviour at the pad-side ports, the
synchronizer depths, and a negative control on the handshake crossing.
