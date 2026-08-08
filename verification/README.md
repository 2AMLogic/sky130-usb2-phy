# verification

cocotb testbenches and Icarus cross-checks. Recorded results are append-only
evidence.

## Harness plumbing

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

## `usbfs`: the behavioral ideal-transceiver model and FS protocol reference

`spec/usb2-phy.md` §7 sets the verification floor for this repo's current
milestone as a bit-exact UTMI-level cocotb suite checked **against a
behavioral ideal-transceiver stub that reproduces DP/DM-level signaling
without electrical simulation**. `usbfs/` (issue #10) is that stub, plus the
USB 2.0 full-speed (FS) protocol reference it's built on — a reusable Python
package, independent of any RTL, so the TX-path and RX-path RTL issues (#12,
#13) check against one shared reference instead of each writing their own
throwaway NRZI/stuffing helper.

**What it is:**

- **Layer 1 — protocol reference** (pure functions, no cocotb, no
  simulator): `usbfs/nrzi.py`, `usbfs/stuffing.py`, `usbfs/crc.py`,
  `usbfs/pid.py`, `usbfs/linestate.py`, `usbfs/timing.py`. NRZI encode/decode,
  bit stuffing/destuffing (including the stuff-bit-immediately-before-EOP
  edge case), CRC5/CRC16, SYNC pattern, PID encoding, J/K/SE0/SE1 line
  states, and the bit-timing model (including the non-ideality knobs)
  live here.
- **Layer 2 — DP/DM bus-functional model** (cocotb): `usbfs/transceiver.py`.
  `IdealTransceiver` drives and/or monitors a DP/DM pair at USB FS (12 Mbps)
  bit timing: SOP (SYNC), EOP, inter-packet delay, idle, reset (SE0 hold),
  and suspend (J hold) sequencing.
- **Layer 3 — packet/traffic builders**: `usbfs/packets.py` (SYNC + PID +
  fields + CRC + EOP construction/parsing for token, data, and handshake
  packets) and `usbfs/scenarios.py` (the named stimulus scenarios and
  negative-control mutations below).

**What it deliberately does *not* model** (§7's boundary, and CLAUDE.md's
scope-discipline rule): driver output resistance, rise/fall time, crossover
voltage, squelch thresholds, or any other electrical behavior. No cable, no
analog front end. The two adjustable knobs
(`usbfs.timing.TimingConfig.freq_offset_ppm` / `bit_jitter_ns`) are
*behavioral* timing perturbations, not electrical ones — a bounded per-bit
timing offset is in scope here; a slew rate is not. Both default to zero, so
the §7 "ideal transceiver" case is the default, and non-ideality is opt-in.

### Stimulus scenarios and negative controls

`usbfs/scenarios.py` builds named scenarios: a maximum-length (64-byte, FS
bulk max) payload, a maximum-length (1023-byte, FS isochronous max) payload
(added by issue #13, for the worst-case drift-accumulation window decision
record #9's RX-FIFO-depth derivation uses), a payload chosen to force a
bit-stuff immediately before EOP, an all-ones payload (maximum stuffing
density), an all-zeros payload (maximum NRZI transition density), a token
packet used as the base case for a corrupted-CRC negative control, and a
packet used as the base case for a truncated-packet negative control.

Every scenario is paired with a **negative control** — one of three
mutations (`flip_crc_bit`, `missing_stuff_bit`, `invert_nrzi_polarity`) or
`truncate` — demonstrated in `test_usbfs_model.py` to **fail** when applied
and to **pass** when it is not. A suite that cannot fail is not evidence.

### Seed convention

`usbfs.scenarios.RANDOM_SEED` (`20260807`) is the single recorded seed used
by every pseudo-random scenario in `scenarios.py` and every randomized
round-trip test in `test_usbfs_model.py` (`ROUND_TRIP_SAMPLE_COUNT = 500`
samples per property test). Re-running the suite is bit-exact reproducible;
changing the seed or sample count is a deliberate, reviewable edit, not
something that happens implicitly.

### Golden vectors

`golden/vectors.json` holds the known-answer vectors, each carrying its own
`provenance` field: either a citation into the USB 2.0 Spec Rev 2.0 (with
section number) or the CRC RevEng catalogue, or — where no published vector
was available in this environment — an explicit statement of how this repo
derived the value (e.g. `token_crc5_worked_example`, `stuff_before_eop_data_packet`,
both reproduced from first principles by helper functions the test suite
also exercises, not just hand-typed).

### Running it cold — Layer 1/3 (pytest, no simulator required)

```bash
cd verification
python3 -m pip install pytest   # if not already available
python3 -m pytest test_usbfs_model.py -v
```

This exercises Layers 1 and 3 only (`usbfs/transceiver.py`, the cocotb BFM,
is never imported by this file or by `usbfs/__init__.py`) — it runs
identically whether or not cocotb or a simulator is installed at all.

### Running it cold — Layer 2 (cocotb, through `klt`)

Requires the toolchain in `docs/environment-setup.md` (Icarus + cocotb
injected into `klt`'s own environment). Then, from the repo root:

```bash
klt functional-verification verification/request-usbfs-model.json --format json
```

This drives `test_usbfs_loopback.py` (a cocotb testbench, **not** collected
by plain pytest — same convention as `test_utmi_stub.py`) against
`usbfs_dp_dm_loopback.v`, a two-wire pass-through fixture that exists solely
so cocotb has an HDL toplevel to attach to (`klt functional-verification`
always drives cocotb against a live simulator process, never in-process
against pure Python). It contains no PID/NRZI/stuffing/CRC logic — it is
test-fixture plumbing, in the same spirit as `rtl/utmi_stub.v` (issue #3),
kept out of `rtl/` so that directory stays reserved for actual PHY
digital-layer RTL. The two tests it runs demonstrate `IdealTransceiver`
driving and monitoring DP/DM in the same test (round-tripping the
stuff-bit-before-EOP scenario through the loopback), and the timing knobs
exercised at a non-zero setting against a live simulator.

## `test_usb_rx.py`: the FS receive-path RTL suite (issue #13)

`rtl/usb_bit_sync.v` .. `rtl/usb_rx_cdc.v` (see `rtl/README.md`'s module
table), integrated as `rtl/usb_rx_path.v`, checked against `usbfs`'s
reference model with non-ideality knobs turned **on** — the point of issue
#13 is specifically the frequency-offset behavior, not just zero-offset
bit-exactness.

```bash
klt functional-verification verification/request-usb-rx.json --format json
```

What it covers (mapping to issue #13's acceptance criteria):

- **Bit-exact zero-offset reception** for every scenario in
  `usbfs.scenarios` (`test_zero_offset_*`), including the 1023-byte FS
  isochronous max-length payload (`usbfs.scenarios.max_length_isochronous_payload`,
  added by this issue).
- **Frequency-offset tolerance**: ±0.25% (2500 ppm) each endpoint alone
  (`test_offset_host_plus_quarter_percent` / `_minus_quarter_percent`), and
  ±0.5% combined with host/device offset in opposite directions, both
  pairings (`test_offset_combined_half_percent_host_fast` /
  `_host_slow`) — against the max-length isochronous payload, per the
  decision record's own FIFO-depth worst-case window.
- **Offset sweep**: `test_offset_sweep_finds_first_failure` locates the
  design's actual first-failing combined offset (measured well beyond the
  required ±0.5% bound); see `docs/bit-sync-budget.md` for the full
  derivation and the measured result.
- **SOP lock from all 12 oversampling phases**
  (`test_sop_lock_all_oversample_phases`).
- **Bit-stuff violation -> `RxError`, no silent corruption**
  (`test_bit_stuff_violation_asserts_rxerror`, paired with a negative
  control, `test_no_bit_stuff_violation_on_clean_all_ones`).
- **EOP detection / `RxActive` deassertion at the correct byte boundary**
  (`test_eop_deasserts_rxactive_at_correct_boundary`).
- **`LineState` matches the driven sequence** (`test_linestate_matches_driven_sequence`,
  using a latency-agnostic de-duplicated-subsequence comparison — see the
  test file's module docstring for why an absolute-timestamp comparison
  would be too tight given the CDC latency involved).
- **Bus reset (sustained SE0) / suspend (sustained idle J) detection**
  (`test_bus_reset_detected_on_sustained_se0`, `test_suspend_detected_on_sustained_idle_j`).

`verification/usbfs/timing.py`'s `TimingConfig` gained an
`allow_out_of_spec` escape hatch (default `False`, existing behavior
unchanged) used only by the offset sweep, which deliberately drives beyond
the physical USB FS tolerance to find where the design actually breaks —
see that parameter's docstring.
