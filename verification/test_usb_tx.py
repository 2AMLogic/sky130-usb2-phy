"""cocotb testbench for the FS transmit datapath (issue #12):
`rtl/usb_tx_serializer.v`, which instantiates `rtl/usb_tx_framer.v`,
`rtl/usb_bit_stuffer.v`, and `rtl/usb_nrzi_encoder.v`.

Drives the UTMI TX handshake (`TxValid`/`TxReady`/`DataOut`) and checks the
line-state driver interface (`tx_dp`/`tx_dn`/`tx_oe`) **bit-identically**
against `verification/usbfs`'s reference model (`usbfs.packets`,
`usbfs.scenarios`) -- never against a bespoke comparison helper written in
this file, per issue #12's explicit instruction. Same "input to `klt
functional-verification`, not a pytest module" convention as
`test_usbfs_loopback.py` / `test_utmi_stub.py` -- pytest never collects
this file (these coroutines take a cocotb-injected `dut` argument and only
run inside a simulator process).

Clock: 144 MHz (`1000/144` ns period, matching
spec/decision-records/0001's oversampling-clock domain). The RTL's own
bit-time strobe divides this by 12 (144 MHz / 12 = 12 MHz FS bit rate,
issue #12 scope item 6), which is exactly `usbfs.timing.FS_BIT_PERIOD_NS`
(1e9 / 12e6 = 83.33... ns) -- no separate timing source is introduced on
either side of the comparison.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import NextTimeStep, ReadOnly, RisingEdge

from usbfs import packets, scenarios
from usbfs.bits import bits_of_byte, bits_to_bytes, bytes_to_bits
from usbfs.linestate import from_dpdm, level_to_state
from usbfs.nrzi import encode as nrzi_encode
from usbfs.packets import EOP_STATES
from usbfs.pid import SYNC_BYTE

BIT_STB_PERIOD_CYCLES = 12  # 144 MHz / 12 = 12 MHz FS bit rate (issue scope item 6)

# 144 MHz, expressed in whole picoseconds -- cocotb's `Clock` cannot
# represent 1000/144 ns (6.944444... ns) exactly at the simulator's 1 ps
# precision; picoseconds is the same convention
# verification/usbfs/transceiver.py's `_ns_to_timer()` uses for the same
# reason (non-integer-ns FS bit periods).
CLK_PERIOD_PS = round(1_000_000_000_000 / 144_000_000)


def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_PS, unit="ps").start())


# ---------------------------------------------------------------------------
# Shared plumbing: reset, UTMI-side driver, line-side monitor.
# ---------------------------------------------------------------------------


async def reset(dut):
    dut.rst_n.value = 0
    dut.TxValid.value = 0
    dut.DataOut.value = 0
    dut.OpMode.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _tick(dut):
    """Advance one clock, then let signals settle so this coroutine's
    *subsequent reads* see this edge's post-update combinational values.
    Signal writes must happen *before* calling this, never after (cocotb
    forbids writes during the ReadOnly phase this leaves the coroutine
    parked in) -- see `send_bytes`/`collect_line_states` for the two
    write-then-tick / tick-then-read usages this splits cleanly between.
    """
    await RisingEdge(dut.clk)
    await ReadOnly()


async def send_bytes(dut, data_bytes, capture_times=None):
    """Drive the UTMI TX handshake: present `data_bytes[idx]` on `DataOut`
    with `TxValid` held, advancing to the next byte exactly when `TxReady`
    (a level, asserted for the whole bit-time leading up to acceptance --
    see rtl/usb_tx_framer.v's header comment) falls back to 0, which marks
    the clock edge that just captured the current byte. Optionally records
    the cocotb simulation-time cycle count of each capture, for the
    back-pressure timing test.

    Writes `TxValid`/`DataOut` *before* `_tick()` (the Normal phase, where
    writes are legal), reads `TxReady` *after* `_tick()` (the ReadOnly
    phase, where settled values are guaranteed), then `NextTimeStep()`
    hands the coroutine back a writable phase before the next loop
    iteration's write -- writing while still parked in `_tick()`'s
    ReadOnly phase raises `RuntimeError` in cocotb.
    """
    idx = 0
    prev_ready = 0
    cycle = 0
    dut.TxValid.value = 0
    while idx < len(data_bytes):
        dut.TxValid.value = 1
        dut.DataOut.value = data_bytes[idx]
        await _tick(dut)
        cycle += 1
        ready = int(dut.TxReady.value)
        if prev_ready and not ready:
            if capture_times is not None:
                capture_times.append(cycle)
            idx += 1
        prev_ready = ready
        await NextTimeStep()
    await RisingEdge(dut.clk)
    dut.TxValid.value = 0


async def collect_line_states(dut):
    """Sample `tx_dp`/`tx_dn` once per bit-time, from the bit-time `tx_oe`
    first asserts (SYNC bit 0) through the bit-time before it releases
    (the EOP J bit-time) -- exactly the `SYNC + body + EOP` sequence
    `usbfs.packets.build()` returns. Read-only: never writes a signal, so
    it is always safe to leave this coroutine parked in `_tick()`'s
    ReadOnly phase between samples."""
    while not int(dut.tx_oe.value):
        await _tick(dut)
    states = []
    while int(dut.tx_oe.value):
        states.append(from_dpdm(dut.tx_dp.value, dut.tx_dn.value))
        for _ in range(BIT_STB_PERIOD_CYCLES):
            await _tick(dut)
    return states


def _byte_stream_for_scenario(scenario):
    """The UTMI DataOut byte stream for a `usbfs.scenarios.Scenario`:
    PID + type-specific fields + CRC, not yet bit-stuffed or NRZI-encoded
    -- `spec/decision-records/0001`'s port table is explicit that this is
    what `DataOut` carries. Reconstructed generically from
    `scenario.fields` (== `packets.parse(scenario.states)`) so this works
    for token, data, and handshake scenarios alike."""
    fields = scenario.fields
    raw = packets.raw_field_bits(
        fields["pid"],
        addr=fields.get("addr"),
        endp=fields.get("endp"),
        frame_number=fields.get("frame_number"),
        payload=scenario.payload,
    )
    return bits_to_bytes(raw)


async def _run_scenario(dut, scenario):
    _start_clock(dut)
    await reset(dut)

    data_bytes = _byte_stream_for_scenario(scenario)
    send_task = cocotb.start_soon(send_bytes(dut, data_bytes))
    observed = await collect_line_states(dut)
    await send_task
    return observed


# ---------------------------------------------------------------------------
# Bit-exact vs. the reference model, for every scenario in usbfs.scenarios.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_max_length_bulk_payload(dut):
    """Max-length FS payload (64 bytes, FS bulk max, USB 2.0 Table 5-5)
    transmits with no under-run/dropped byte: a bit-exact match across the
    whole stream is only possible if every byte was captured and shifted
    out in order with nothing lost."""
    scenario = scenarios.max_length_bulk_payload()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states


@cocotb.test()
async def test_max_length_isochronous_payload(dut):
    """Max-length FS isochronous payload (1023 bytes, USB 2.0 FS
    isochronous max, `usbfs.scenarios.FS_MAX_ISOCHRONOUS_PACKET_SIZE`) --
    added to the shared `usbfs.scenarios` library by issue #13 for the
    RX-side drift-accumulation worst case, but it is still a scenario in
    the library this issue's own acceptance criterion covers ("for every
    scenario in the reference model's library..."), and it independently
    re-confirms the no-under-run/no-dropped-byte property (this issue's
    own criterion) over a stream 16x longer than the 64-byte bulk-max
    case above."""
    scenario = scenarios.max_length_isochronous_payload()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states


@cocotb.test()
async def test_all_ones_payload_max_stuffing(dut):
    """All-ones payload: maximum bit-stuffing density (a stuff bit every 6
    payload bits throughout)."""
    scenario = scenarios.all_ones_payload()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states


@cocotb.test()
async def test_all_zeros_payload_max_transitions(dut):
    """All-zeros payload: no bit-stuffing, maximum NRZI transition
    density (every bit toggles the line)."""
    scenario = scenarios.all_zeros_payload()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states


@cocotb.test()
async def test_corrupted_crc_token_base_case(dut):
    scenario = scenarios.corrupted_crc_token()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states


@cocotb.test()
async def test_truncated_packet_base_case(dut):
    scenario = scenarios.truncated_packet()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states


@cocotb.test()
async def test_stuff_bit_immediately_before_eop(dut):
    """Explicit, dedicated case (not just incidentally covered by another
    scenario): the last 6 bits of `STUFF_BEFORE_EOP_PAYLOAD`'s CRC16 field
    are 1, forcing a bit-stuff 0 as the very last bit transmitted before
    EOP -- the edge case spec/architecture.md names by hand."""
    scenario = scenarios.stuff_before_eop_payload()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states

    # Confirm the RTL actually exercised the edge case, not merely that
    # the bit-exact compare above happened to pass: the bit immediately
    # before EOP_STATES must be the *inserted* stuff bit, i.e. one more
    # line-state than the payload's own raw (pre-stuff) field would need.
    fields = scenario.fields
    raw = packets.raw_field_bits(fields["pid"], payload=scenario.payload)
    from usbfs import stuffing

    stuffed = stuffing.stuff(raw)
    assert len(stuffed) == len(raw) + 1
    assert stuffed[-1] == 0 and raw[-1] == 1
    assert len(observed) == 8 + len(stuffed) + 3  # SYNC(8) + stuffed field + EOP(3)


# ---------------------------------------------------------------------------
# TxReady back-pressure: byte interval stretches by exactly one bit time
# when a stuff bit falls within that byte.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_txready_backpressure_stretches_by_one_bit_time_on_stuff(dut):
    """Drives a payload built (via `usbfs.packets.raw_field_bits`, the
    reference model -- not a bespoke helper) to contain exactly one
    isolated, *unambiguously mid-byte* stuff bit -- payload byte 1
    (`0x7E` = `0b0111_1110`, LSB-first bits `0,1,1,1,1,1,1,0`) has a run
    of six consecutive 1s entirely within bit indices 1-6, well clear of
    the byte's own bit 7/bit 0 edges -- and measures the clock-cycle
    interval between successive byte captures (`TxReady` falling edges).
    Each interval must equal `12 * n` cycles, where `n` is the number of
    *stuffed-domain* bits the RTL's bit stuffer emits for that byte's 8
    raw bits -- 8 (96 cycles) normally, 9 (108 cycles, exactly one extra
    bit time) for the byte carrying the stuff. Computed generically from
    `usbfs.stuffing.stuff()` (the reference model), not hardcoded.

    Deliberately avoids `usbfs.scenarios.all_ones_payload()` here: its
    dense stuffing forces *two* stuff bits into some bytes, one of which
    always lands exactly on a byte's own last raw bit (`stuffing.stuff()`
    then counts it as that byte's, per its raw-8-bit-chunk convention) --
    but the RTL's `byte_idx` counter has, by that same bit-time, already
    advanced to the *next* byte's byte_idx == 0 (see rtl/usb_tx_framer.v's
    `ST_DATA` case: `byte_idx <= 0` fires in the same cycle the stuffer's
    `run` register reaches its stuff-triggering value of 6), so the RTL
    attributes that specific bit-time's stretch to the *following* byte
    instead. Both attributions are internally consistent and the
    transmitted content is unaffected either way -- `usbfs.scenarios.
    all_ones_payload()`'s bit-exact correctness (including this exact
    double-stuff-per-byte pattern) is already fully verified by
    `test_all_ones_payload_max_stuffing` and the negative control below --
    but the two conventions disagree about *which* byte a
    boundary-straddling stuff belongs to, which is exactly the ambiguity
    this test's per-byte comparison cannot express. Choosing a stimulus
    with a single, strictly-interior stuff bit sidesteps that ambiguity
    entirely while still exercising precisely what this issue's
    acceptance criterion asks for: "a stimulus that stuffs a bit
    mid-byte"."""
    from usbfs import stuffing

    payload = bytes([0x00, 0x7E, 0x00])
    raw = packets.raw_field_bits("DATA0", payload=payload)
    n_bytes = len(raw) // 8
    assert len(raw) % 8 == 0

    cumulative = [0] * (n_bytes + 1)
    for i in range(1, n_bytes + 1):
        cumulative[i] = len(stuffing.stuff(raw[: 8 * i]))
    expected_bits_per_byte = [
        cumulative[i] - cumulative[i - 1] for i in range(1, n_bytes + 1)
    ]

    assert any(n == 9 for n in expected_bits_per_byte), (
        "test setup error: all_ones_payload should force at least one "
        "9-bit-time (stuffed) byte interval"
    )
    assert any(n == 8 for n in expected_bits_per_byte), (
        "test setup error: expected at least one nominal 8-bit-time byte too"
    )

    _start_clock(dut)
    await reset(dut)

    data_bytes = bits_to_bytes(raw)
    capture_times = []
    send_task = cocotb.start_soon(
        send_bytes(dut, data_bytes, capture_times=capture_times)
    )
    await collect_line_states(dut)
    await send_task

    assert len(capture_times) == n_bytes
    measured_bits_per_byte = []
    prev = capture_times[0]
    # capture_times[0] marks *leaving IDLE* (the start of SYNC), not the
    # start of byte 0's own bits, so the first measured interval also
    # includes the SYNC field -- interval[k] otherwise equals exactly the
    # bit-time count byte k itself took (there is no measurable interval
    # for the final byte, which is followed by EOP rather than another
    # capture). SYNC's own contribution to that first interval is 7
    # bit-times, not 8: the RTL's IDLE->SYNC transition edge (the very
    # edge `capture_times[0]` is recorded at) *also* encodes SYNC's bit 0
    # combinationally on that same edge (see rtl/usb_tx_framer.v's
    # `entering_sync`), so only SYNC's remaining 7 bits (bits 1-7) cost a
    # *subsequent* bit_stb pulse each.
    for t in capture_times[1:]:
        measured_bits_per_byte.append((t - prev) / BIT_STB_PERIOD_CYCLES)
        prev = t
    measured_bits_per_byte[0] -= 7  # subtract SYNC's post-entering-edge bits back out

    assert measured_bits_per_byte == expected_bits_per_byte[:-1], (
        f"measured={measured_bits_per_byte} expected={expected_bits_per_byte[:-1]}"
    )
    assert 9 in measured_bits_per_byte, "back-pressure stretch was never observed"


# ---------------------------------------------------------------------------
# Bit-stuffing / NRZI bypass mode (OpMode == 2'b10, raw/transparent test
# mode -- spec/decision-records/0001 Decision 4).
# ---------------------------------------------------------------------------


def _raw_mode_expected(payload_bytes):
    """SYNC is still normal NRZI (PHY-generated framing, not link-
    controller payload -- see rtl/usb_tx_framer.v's header comment); the
    body bits are placed directly onto the line (bit value == J/K level,
    no NRZI transform, no stuffing); EOP is unaffected by OpMode."""
    sync_states = [
        level_to_state(level)
        for level in nrzi_encode(bits_of_byte(SYNC_BYTE), start_level=1)
    ]
    body_states = [level_to_state(bit) for bit in bytes_to_bits(payload_bytes)]
    return sync_states + body_states + list(EOP_STATES)


@cocotb.test()
async def test_bit_stuffing_nrzi_bypass_mode(dut):
    """OpMode == 2'b10 disables bit-stuffing and NRZI encoding for the
    packet body. Drives a payload (0xFF repeated) that would force
    stuffing in normal mode, and confirms the observed line states match
    the raw/transparent expectation instead -- proving stuffing and NRZI
    both did not run."""
    _start_clock(dut)
    await reset(dut)
    dut.OpMode.value = 0b10

    payload_bytes = bytes([0xFF, 0xFF, 0xFF])
    send_task = cocotb.start_soon(send_bytes(dut, payload_bytes))
    observed = await collect_line_states(dut)
    await send_task

    assert observed == _raw_mode_expected(payload_bytes)


# ---------------------------------------------------------------------------
# Negative control: mirrors test_usbfs_model.py's convention
# (`missing_stuff_bit` paired with `all_ones_payload`) -- demonstrates the
# bit-exact comparison this suite relies on actually *can* fail, by
# comparing the RTL's (correct) output against a deliberately-corrupted
# reference sequence.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_negative_control_missing_stuff_bit_would_be_caught(dut):
    """`usbfs.scenarios.missing_stuff_bit()` reproduces the RTL bug this
    negative control stands in for (a bit stuffer that fails to insert a
    stuff bit -- e.g. a forced-wrong run-length threshold, or a mutated
    RTL constant): the same mutation `test_usbfs_model.py` uses for this
    exact scenario. The correct RTL output must equal the correct
    reference and must NOT equal the mutated (buggy) reference -- proving
    this suite's comparison methodology is sensitive to exactly the class
    of defect issue #12 asks a negative control to catch."""
    scenario = scenarios.all_ones_payload()
    observed = await _run_scenario(dut, scenario)
    assert observed == scenario.states

    mutated = scenarios.missing_stuff_bit(
        scenario.fields["pid"], payload=scenario.payload
    )
    assert observed != mutated, "negative control did not fail as expected"
