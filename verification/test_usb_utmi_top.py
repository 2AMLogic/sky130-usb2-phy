"""cocotb testbench for the UTMI digital top (issue #52):
`rtl/usb_utmi_top.v`, which instantiates `rtl/usb_tx_serializer.v` and
`rtl/usb_rx_path.v` unmodified and adds the TX-side 30 <-> 144 MHz CDC that
`spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`
("decision record #9") Decision 3 specifies.

Like `test_usb_rx.py` / `test_usb_tx.py` / `test_usbfs_loopback.py`, this
file is *input* to `klt functional-verification` (see
`request-usb-utmi_top.json`), not a pytest module.

Every expected value in this file comes from `verification/usbfs` -- the
independently-verified reference model (`usbfs.packets`, `usbfs.scenarios`,
`usbfs.nrzi`, `usbfs.stuffing`) -- never from a comparison helper written
here, so a passing check means "the RTL agrees with the reference," not
"the RTL agrees with its own author."

---------------------------------------------------------------------
What this suite adds over `test_usb_rx.py` + `test_usb_tx.py`
---------------------------------------------------------------------
Those two suites drive the RX path from the pads and the TX path from
already-144 MHz-domain handshake signals. Neither exercises the UTMI
clock domain, the CDC between the two domains, or both datapaths at once.
This suite drives **only the top's own ports**:

1. **DP/DM loopback** -- the packet is handed to the top's 30 MHz UTMI TX
   ports, transmitted, wired back from `tx_dp`/`tx_dn` into `dp`/`dm`, and
   the bytes are checked as they re-emerge on `RxValid`/`DataIn`. Three
   independent `usbfs` comparisons per packet: the driven line states
   equal `scenario.states`, `usbfs.packets.parse()` of those states equals
   `scenario.fields`, and the received bytes equal the byte stream
   `usbfs.packets.raw_field_bits()` says the link handed over.
2. **RX-only / TX-only** replays of the same scenario lists
   `test_usb_rx.py` and `test_usb_tx.py` use, through the top's ports.
3. **`OpMode`** `2'b10` (bit-stuffing/NRZI bypass) and `2'b01`
   (non-driving) observed at the top's own pad-side ports, plus the
   `SuspendM` driver gate.
4. **CDC structure**: the synchronizer depth of every 30 -> 144 MHz
   crossing, and the "one byte per `TxReady`" property of the 144 -> 30 MHz
   acknowledge crossing.
5. **A negative control** on the handshake crossing (below).

---------------------------------------------------------------------
The UTMI-side TX protocol this suite drives
---------------------------------------------------------------------
Per decision record #9 Decision 4: the link asserts `TxValid` with a byte
on `DataOut` and holds both stable until `TxReady` acknowledges; one
`TxReady` == one byte consumed. `rtl/usb_utmi_top.v` implements that
acknowledge as a **one-`clk_utmi`-cycle pulse** produced by a toggle
synchronizer (see that file's header for the derivation and for why a
plain level synchronizer on the serializer's own `TxReady` would not hold
the one-byte-per-acknowledge contract at 83.33 ns/33.33 ns).

`_utmi_send_bytes()` below is the link-controller model for that protocol.
Its `bytes_per_ack` knob exists solely for the negative control
(`test_negative_control_over_advancing_link_corrupts_packet`): a link that
advances more than one byte per acknowledge is exactly the failure a
mis-designed `TxReady` crossing would induce (a 2.5-UTMI-cycle-wide level
observed as 2-3 asserted cycles), and the test demonstrates the suite's
comparison actually catches it.

---------------------------------------------------------------------
The loopback wire
---------------------------------------------------------------------
`_loopback_mirror()` copies `tx_dp`/`tx_dn` onto `dp`/`dm` once per
`clk_144` edge -- one 6.94 ns cycle of delay, uniform, no jitter (the
serializer's pad outputs only ever change on a `clk_144` edge). When
`tx_oe` is deasserted it drives idle J instead, modelling the FS device's
1.5 kOhm D+ pull-up (`spec/usb2-phy.md` §6) holding the bus at J whenever
no driver is enabled -- which is what makes the `OpMode = 2'b01` /
`SuspendM = 0` cases observable as "nothing was received."
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, NextTimeStep, ReadOnly, RisingEdge, Timer

from usbfs import packets, scenarios
from usbfs.bits import bits_of_byte, bits_to_bytes, bytes_to_bits
from usbfs.linestate import from_dpdm, level_to_state
from usbfs.nrzi import encode as nrzi_encode
from usbfs.packets import EOP_STATES
from usbfs.pid import SYNC_BYTE
from usbfs.transceiver import IdealTransceiver

# 144 MHz / 30 MHz, in whole picoseconds: neither period is an integer
# number of nanoseconds (6.944... / 33.333...), the same reason
# `usbfs.transceiver._ns_to_timer()` and `test_usb_rx.py` use picoseconds.
CLK144_PERIOD_PS = round(1_000_000_000_000 / 144_000_000)
CLK_UTMI_PERIOD_PS = round(1_000_000_000_000 / 30_000_000)

# 144 MHz / 12 = 12 Mbps FS bit rate (decision record #9, Decision 6) --
# the same divide `rtl/usb_tx_serializer.v` implements.
BIT_STB_PERIOD_CYCLES = 12

# Generous per-loop caps so a broken DUT fails with a readable assertion
# instead of hanging the simulator until `klt`'s own timeout.
MAX_WAIT_144_CYCLES = 4_000_000
MAX_WAIT_UTMI_CYCLES = 1_000_000

_clock_tasks = {}


async def _start_clocks(dut):
    """(Re)start both PLL-supplied clocks, cancelling any previously
    started clock task on the same signal.

    Started per test, not once per simulation: cocotb kills every task a
    test started when that test ends, so a clock started inside the first
    test would stop with it and the simulator would run out of events. The
    same reason `test_usb_rx.py`'s `set_clocks()` restarts them per test.

    An odd total picosecond count is split explicitly with `period_high`,
    so cocotb's "evenly divisible by 2" check for an implicit 50% duty
    cycle does not trip on the 144 MHz period."""
    for name, sig, period_ps in (
        ("144", dut.clk_144, CLK144_PERIOD_PS),
        ("utmi", dut.clk_utmi, CLK_UTMI_PERIOD_PS),
    ):
        old = _clock_tasks.get(name)
        if old is not None:
            old.cancel()
        _clock_tasks[name] = cocotb.start_soon(
            Clock(sig, period_ps, unit="ps", period_high=period_ps // 2).start()
        )
    await Timer(1, unit="ns")


async def _reset_dut(dut):
    """Drive every UTMI input to its idle value and pulse the asynchronous,
    active-high `Reset` (Decision 4's port table)."""
    dut.Reset.value = 1
    dut.TxValid.value = 0
    dut.DataOut.value = 0
    dut.OpMode.value = 0b00       # normal operation
    dut.TermSelect.value = 1      # FS termination (the only mode here)
    dut.XcvrSelect.value = 0b01   # FS encoding; every other value is don't-care
    dut.SuspendM.value = 1        # active-low: 1 == not suspended
    dut.dp.value = 1              # idle J
    dut.dm.value = 0
    await ClockCycles(dut.clk_144, 8)
    dut.Reset.value = 0
    # Both per-domain reset synchronizers must deassert before anything
    # downstream (the RX FIFO pointers, the TX toggle synchronizer) leaves
    # reset -- the 30 MHz domain is the slower of the two.
    await ClockCycles(dut.clk_utmi, 8)


async def _start_test(dut):
    await _start_clocks(dut)
    await _reset_dut(dut)


async def _tick144(dut):
    """Advance one `clk_144` edge and settle. Leaves the caller parked in
    the ReadOnly phase, so a coroutine that calls this must do its writes
    *before* the call (or step to a writable phase with `NextTimeStep()`
    afterwards) -- same convention as `test_usb_tx.py`."""
    await RisingEdge(dut.clk_144)
    await ReadOnly()


# ---------------------------------------------------------------------------
# Reference-model helpers (everything expected comes from `usbfs`).
# ---------------------------------------------------------------------------


def _byte_stream_for_scenario(scenario):
    """The UTMI byte stream for a `usbfs.scenarios.Scenario`: PID +
    type-specific fields + CRC, not yet bit-stuffed or NRZI-encoded.

    This is *both* what the link controller hands to `DataOut` (decision
    record #9's port table: "byte to transmit, not yet NRZI-encoded or
    bit-stuffed") and what `DataIn` must deliver on receive (SYNC is
    consumed by SOP lock and never delivered; EOP is not part of the
    bit-stuffed stream -- see `rtl/usb_rx_framer.v`'s header). One helper
    for both ends of the loopback, built from `usbfs.packets` rather than
    re-derived here."""
    fields = scenario.fields
    raw = packets.raw_field_bits(
        fields["pid"],
        addr=fields.get("addr"),
        endp=fields.get("endp"),
        frame_number=fields.get("frame_number"),
        payload=scenario.payload,
    )
    return list(bits_to_bytes(raw))


def _raw_mode_expected(payload_bytes):
    """Expected line states under `OpMode == 2'b10` (bit-stuffing and NRZI
    both disabled for the packet body). SYNC is PHY-generated framing, not
    link-controller payload, so it stays normally NRZI-encoded -- see
    `rtl/usb_tx_framer.v`'s header. Built from `usbfs.nrzi` /
    `usbfs.linestate` / `usbfs.packets.EOP_STATES`, the same construction
    `test_usb_tx.py` uses for the serializer-level version of this check."""
    sync_states = [
        level_to_state(level)
        for level in nrzi_encode(bits_of_byte(SYNC_BYTE), start_level=1)
    ]
    body_states = [level_to_state(bit) for bit in bytes_to_bits(payload_bytes)]
    return sync_states + body_states + list(EOP_STATES)


# ---------------------------------------------------------------------------
# UTMI-side link-controller model, pad-side monitors, loopback wire.
# ---------------------------------------------------------------------------


async def _utmi_send_bytes(dut, data_bytes, bytes_per_ack=1, ack_times=None):
    """Drive the top's 30 MHz UTMI TX ports per Decision 4's handshake:
    hold `TxValid` with a stable `DataOut`, advance one byte per `TxReady`
    acknowledge, and deassert `TxValid` once the final byte is
    acknowledged (which is what tells the serializer to close the packet
    with EOP).

    `bytes_per_ack` > 1 models a *broken* link/crossing pair -- see the
    module docstring and the negative-control test.
    `ack_times` optionally records the `clk_utmi` cycle index of each
    acknowledge, for the one-byte-per-`TxReady` timing check."""
    idx = 0
    cycle = 0
    dut.TxValid.value = 1
    dut.DataOut.value = data_bytes[0]
    while True:
        await RisingEdge(dut.clk_utmi)
        await ReadOnly()
        cycle += 1
        acked = bool(dut.TxReady.value)
        await NextTimeStep()
        if acked:
            if ack_times is not None:
                ack_times.append(cycle)
            idx += bytes_per_ack
            if idx >= len(data_bytes):
                dut.TxValid.value = 0
                return
            dut.DataOut.value = data_bytes[idx]
        assert cycle < MAX_WAIT_UTMI_CYCLES, (
            f"TxReady never acknowledged byte {idx} within "
            f"{MAX_WAIT_UTMI_CYCLES} clk_utmi cycles"
        )


async def _collect_tx_line_states(dut):
    """Sample `tx_dp`/`tx_dn` once per bit time, from the bit time `tx_oe`
    first asserts (SYNC bit 0) through the bit time before it releases (the
    EOP J bit time) -- exactly the `SYNC + body + EOP` sequence
    `usbfs.packets.build()` returns. Read-only, so it is safe to leave this
    coroutine parked in `_tick144()`'s ReadOnly phase."""
    waited = 0
    while not int(dut.tx_oe.value):
        await _tick144(dut)
        waited += 1
        assert waited < MAX_WAIT_144_CYCLES, "tx_oe never asserted"
    states = []
    while int(dut.tx_oe.value):
        states.append(from_dpdm(dut.tx_dp.value, dut.tx_dn.value))
        for _ in range(BIT_STB_PERIOD_CYCLES):
            await _tick144(dut)
        assert len(states) < MAX_WAIT_144_CYCLES, "tx_oe never released"
    return states


class RxMonitor:
    """Samples `RxValid`/`DataIn`/`RxActive`/`RxError` once per `clk_utmi`
    edge -- the rate at which the UTMI-domain outputs can change. Same
    monitor shape as `test_usb_rx.py`'s."""

    def __init__(self, dut):
        self.dut = dut
        self.bytes = []
        self.saw_error = False
        self.saw_active = False
        self._task = None

    async def _run(self):
        while True:
            await RisingEdge(self.dut.clk_utmi)
            await ReadOnly()
            if self.dut.RxValid.value:
                self.bytes.append(int(self.dut.DataIn.value))
            if self.dut.RxError.value:
                self.saw_error = True
            if self.dut.RxActive.value:
                self.saw_active = True

    def start(self):
        self._task = cocotb.start_soon(self._run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None


class DriverMonitor:
    """Records whether the pad-side driver enables ever asserted, and the
    `TxReady` pulse widths observed in the UTMI domain."""

    def __init__(self, dut):
        self.dut = dut
        self.saw_oe = False
        self.saw_drive_en = False
        self._task = None

    async def _run(self):
        while True:
            await RisingEdge(self.dut.clk_144)
            await ReadOnly()
            if self.dut.tx_oe.value:
                self.saw_oe = True
            if self.dut.tx_drive_en.value:
                self.saw_drive_en = True

    def start(self):
        self._task = cocotb.start_soon(self._run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None


class LoopbackWire:
    """The DP/DM loopback: `tx_dp`/`tx_dn` -> `dp`/`dm`, resampled once per
    `clk_144` edge (see the module docstring)."""

    def __init__(self, dut):
        self.dut = dut
        self._task = None

    async def _run(self):
        while True:
            await RisingEdge(self.dut.clk_144)
            await ReadOnly()
            if int(self.dut.tx_oe.value):
                dp, dm = int(self.dut.tx_dp.value), int(self.dut.tx_dn.value)
            else:
                dp, dm = 1, 0  # FS D+ pull-up idles the un-driven bus at J
            await NextTimeStep()
            self.dut.dp.value = dp
            self.dut.dm.value = dm

    def start(self):
        self._task = cocotb.start_soon(self._run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None


# ---------------------------------------------------------------------------
# 1. DP/DM loopback: UTMI TX ports -> pads -> UTMI RX ports, end to end.
# ---------------------------------------------------------------------------

_LOOPBACK_SCENARIOS = {
    # The two edge cases issue #52 names explicitly, plus the maximum
    # NRZI-transition payload, a 64-byte (FS bulk max) payload, and a token
    # packet (a non-DATA PID, so the loopback is not only exercised on
    # `packets.parse()`'s data-packet path).
    "stuff_before_eop_payload": scenarios.stuff_before_eop_payload,
    "all_ones_payload": scenarios.all_ones_payload,
    "all_zeros_payload": scenarios.all_zeros_payload,
    "max_length_bulk_payload": scenarios.max_length_bulk_payload,
    "corrupted_crc_token": scenarios.corrupted_crc_token,
}


async def _run_loopback(dut, scenario, settle_utmi_cycles=60):
    wire = LoopbackWire(dut)
    rx = RxMonitor(dut)
    wire.start()
    rx.start()
    try:
        data_bytes = _byte_stream_for_scenario(scenario)
        send = cocotb.start_soon(_utmi_send_bytes(dut, data_bytes))
        observed = await _collect_tx_line_states(dut)
        await send
        await ClockCycles(dut.clk_utmi, settle_utmi_cycles)
    finally:
        rx.stop()
        wire.stop()
    return data_bytes, observed, rx


def _make_loopback_test(name, builder):
    async def _test(dut):
        await _start_test(dut)
        scenario = builder()
        data_bytes, observed, rx = await _run_loopback(dut, scenario)

        # (a) what left the pads is bit-exactly the reference packet
        assert observed == scenario.states, (
            f"{name}: transmitted line states differ from usbfs.scenarios"
        )
        # (b) the reference model can parse it back to the same fields
        assert packets.parse(observed) == scenario.fields, (
            f"{name}: usbfs.packets.parse() of the transmitted packet "
            f"disagrees with the scenario's own fields"
        )
        # (c) the bytes re-emerged on the UTMI RX ports, byte-exact
        assert rx.bytes == data_bytes, (
            f"{name}: loopback byte mismatch, got {rx.bytes!r}"
        )
        assert not rx.saw_error, f"{name}: unexpected RxError on a clean loopback"
        assert rx.saw_active, f"{name}: RxActive never asserted"

    _test.__name__ = f"test_loopback_{name}"
    _test.__qualname__ = _test.__name__
    _test.__doc__ = (
        f"DP/DM loopback through the top's own ports: "
        f"usbfs.scenarios.{name}() driven into the 30 MHz UTMI TX ports, "
        f"transmitted, wired back into the pads, and checked byte-exact on "
        f"RxValid/DataIn against the same usbfs byte stream."
    )
    return _test


for _name, _builder in _LOOPBACK_SCENARIOS.items():
    globals()[f"test_loopback_{_name}"] = cocotb.test()(
        _make_loopback_test(_name, _builder)
    )


# ---------------------------------------------------------------------------
# 2. TX-only and RX-only replays of the existing suites' scenario lists.
# ---------------------------------------------------------------------------

# The same list `test_usb_tx.py` and `test_usb_rx.py` cover between them --
# replayed here through the top's ports (and hence through the CDC) rather
# than against the sub-blocks directly.
_SCENARIOS = {
    "max_length_bulk_payload": scenarios.max_length_bulk_payload,
    "max_length_isochronous_payload": scenarios.max_length_isochronous_payload,
    "stuff_before_eop_payload": scenarios.stuff_before_eop_payload,
    "all_ones_payload": scenarios.all_ones_payload,
    "all_zeros_payload": scenarios.all_zeros_payload,
    "corrupted_crc_token": scenarios.corrupted_crc_token,
    "truncated_packet": scenarios.truncated_packet,
}


def _make_tx_only_test(name, builder):
    async def _test(dut):
        await _start_test(dut)
        scenario = builder()
        data_bytes = _byte_stream_for_scenario(scenario)
        send = cocotb.start_soon(_utmi_send_bytes(dut, data_bytes))
        observed = await _collect_tx_line_states(dut)
        await send
        assert observed == scenario.states, (
            f"{name}: TX line states differ from usbfs.scenarios"
        )

    _test.__name__ = f"test_tx_only_{name}"
    _test.__qualname__ = _test.__name__
    _test.__doc__ = (
        f"TX-only through the top's ports: usbfs.scenarios.{name}() driven "
        f"into the 30 MHz UTMI handshake, checked bit-exactly at "
        f"tx_dp/tx_dn."
    )
    return _test


for _name, _builder in _SCENARIOS.items():
    globals()[f"test_tx_only_{_name}"] = cocotb.test()(
        _make_tx_only_test(_name, _builder)
    )


def _make_rx_only_test(name, builder):
    async def _test(dut):
        await _start_test(dut)
        scenario = builder()
        rx = RxMonitor(dut)
        rx.start()
        try:
            tx = IdealTransceiver(dut.dp, dut.dm)
            await tx.drive_idle(4)
            await tx.drive_states(scenario.states)
            await tx.drive_idle(4)
            await ClockCycles(dut.clk_utmi, 40)
        finally:
            rx.stop()
        assert rx.bytes == _byte_stream_for_scenario(scenario), (
            f"{name}: RX byte mismatch, got {rx.bytes!r}"
        )
        assert not rx.saw_error, f"{name}: unexpected RxError"
        # The TX side must stay off the bus while the link is not
        # transmitting (`TxValid` low) -- otherwise "RX-only" would not be.
        assert not int(dut.tx_oe.value)

    _test.__name__ = f"test_rx_only_{name}"
    _test.__qualname__ = _test.__name__
    _test.__doc__ = (
        f"RX-only through the top's ports: usbfs.scenarios.{name}() driven "
        f"onto the pads by usbfs.transceiver.IdealTransceiver, checked "
        f"byte-exact on RxValid/DataIn."
    )
    return _test


for _name, _builder in _SCENARIOS.items():
    globals()[f"test_rx_only_{_name}"] = cocotb.test()(
        _make_rx_only_test(_name, _builder)
    )


# ---------------------------------------------------------------------------
# 3. OpMode / SuspendM behaviour observed at the top's own ports.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_opmode_bypass_at_top_ports(dut):
    """`OpMode == 2'b10` (decision record #9 Decision 4: "Disable
    bit-stuffing and NRZI encoding") observed at the *top's* ports -- i.e.
    with `OpMode` crossing the 30 -> 144 MHz synchronizer rather than being
    presented directly to the serializer as `test_usb_tx.py` does. A
    payload of 0xFF bytes would force dense stuffing in normal mode; under
    bypass the line must carry the raw bits instead."""
    await _start_test(dut)
    dut.OpMode.value = 0b10
    # Let the 2-flop synchronizer settle before the first byte is offered.
    await ClockCycles(dut.clk_utmi, 4)

    payload_bytes = [0xFF, 0xFF, 0xFF]
    send = cocotb.start_soon(_utmi_send_bytes(dut, payload_bytes))
    observed = await _collect_tx_line_states(dut)
    await send

    assert observed == _raw_mode_expected(bytes(payload_bytes))

    # `_collect_tx_line_states()` leaves this coroutine parked in the
    # ReadOnly phase; step to a writable one before restoring `OpMode`.
    await NextTimeStep()
    dut.OpMode.value = 0b00
    await ClockCycles(dut.clk_utmi, 4)


@cocotb.test()
async def test_opmode_non_driving_at_top_ports(dut):
    """`OpMode == 2'b01` (Decision 4: "Non-driving (TX drivers disabled)").
    `usb_tx_serializer.v` does not implement this encoding -- disabling the
    drivers is an act on the pad-side control interface, which only exists
    at the top -- so this checks the integration-level gate
    `rtl/usb_utmi_top.v` adds: across a full packet's worth of accepted
    bytes, neither `tx_oe` nor `tx_drive_en` ever asserts, the looped-back
    bus therefore stays idle, and nothing is received.

    Paired with a positive control in the same test (the identical stimulus
    at `OpMode == 2'b00` *does* drive and *is* received), so a gate stuck
    permanently off could not pass."""
    await _start_test(dut)
    scenario = scenarios.stuff_before_eop_payload()
    data_bytes = _byte_stream_for_scenario(scenario)

    dut.OpMode.value = 0b01
    await ClockCycles(dut.clk_utmi, 4)

    wire = LoopbackWire(dut)
    rx = RxMonitor(dut)
    drv = DriverMonitor(dut)
    wire.start()
    rx.start()
    drv.start()
    try:
        await _utmi_send_bytes(dut, data_bytes)
        # Let the (silently running) serializer finish the packet it framed.
        await ClockCycles(dut.clk_144, BIT_STB_PERIOD_CYCLES * 40)
    finally:
        drv.stop()
        rx.stop()
        wire.stop()

    assert not drv.saw_oe, "tx_oe asserted while OpMode == 2'b01 (non-driving)"
    assert not drv.saw_drive_en, "tx_drive_en asserted while OpMode == 2'b01"
    assert rx.bytes == [], f"bus was driven while non-driving: {rx.bytes!r}"

    # Positive control: same stimulus, normal OpMode.
    await _start_test(dut)
    dut.OpMode.value = 0b00
    await ClockCycles(dut.clk_utmi, 4)
    data_bytes, observed, rx2 = await _run_loopback(dut, scenario)
    assert observed == scenario.states
    assert rx2.bytes == data_bytes


@cocotb.test()
async def test_suspendm_disables_the_line_drivers(dut):
    """`SuspendM` is active-low (Decision 4): `SuspendM == 0` commands the
    PHY into suspend, and a suspended PHY must not drive the bus. Same
    integration-level gate as `OpMode == 2'b01`, exercised through the
    `SuspendM` 30 -> 144 MHz synchronizer, with the same
    positive-control pairing."""
    await _start_test(dut)
    scenario = scenarios.all_zeros_payload()
    data_bytes = _byte_stream_for_scenario(scenario)

    dut.SuspendM.value = 0
    await ClockCycles(dut.clk_utmi, 4)

    drv = DriverMonitor(dut)
    drv.start()
    try:
        await _utmi_send_bytes(dut, data_bytes)
        await ClockCycles(dut.clk_144, BIT_STB_PERIOD_CYCLES * 40)
    finally:
        drv.stop()

    assert not drv.saw_oe, "tx_oe asserted while SuspendM == 0 (suspended)"
    assert not drv.saw_drive_en, "tx_drive_en asserted while SuspendM == 0"

    dut.SuspendM.value = 1
    await ClockCycles(dut.clk_utmi, 4)
    await _start_test(dut)
    send = cocotb.start_soon(_utmi_send_bytes(dut, data_bytes))
    observed = await _collect_tx_line_states(dut)
    await send
    assert observed == scenario.states, "driving did not resume once suspend lifted"


# ---------------------------------------------------------------------------
# 4. CDC structure: synchronizer depth, and one byte per TxReady.
# ---------------------------------------------------------------------------


async def _measure_sync_depth(dut, port, internal, new_value):
    """Drive `port` to `new_value` immediately after a `clk_144` edge and
    return how many `clk_144` edges pass before `internal` follows.

    White-box on purpose: decision record #9 Decision 3 fixes the *depth*
    of these crossings (2 flops), and depth is not observable from the
    top's ports alone. A 1-flop mutation returns 1 here and a 3-flop
    mutation returns 3, so this doubles as the negative control on
    synchronizer depth."""
    await RisingEdge(dut.clk_144)
    await NextTimeStep()
    port.value = new_value
    edges = 0
    while True:
        await RisingEdge(dut.clk_144)
        await ReadOnly()
        edges += 1
        if int(internal.value) == new_value:
            await NextTimeStep()
            return edges
        await NextTimeStep()
        assert edges < 16, "synchronized value never followed its port"


@cocotb.test()
async def test_control_input_synchronizer_depth_is_two(dut):
    """Every 30 -> 144 MHz control crossing decision record #9 Decision 3's
    table lists is a **2-flop** synchronizer: the destination-domain value
    must not follow after one edge, and must follow after exactly two."""
    await _start_test(dut)

    for port, internal, new_value, name in (
        (dut.TermSelect, dut.term_select_144, 0, "TermSelect"),
        (dut.XcvrSelect, dut.xcvr_select_144, 0b10, "XcvrSelect"),
        (dut.SuspendM, dut.suspendm_144, 0, "SuspendM"),
        (dut.OpMode, dut.opmode_144, 0b10, "OpMode"),
    ):
        depth = await _measure_sync_depth(dut, port, internal, new_value)
        assert depth == 2, f"{name}: synchronizer depth {depth}, expected 2"

    # Restore the idle configuration for the tests that follow.
    dut.SuspendM.value = 1
    dut.TermSelect.value = 1
    dut.XcvrSelect.value = 0b01
    dut.OpMode.value = 0b00
    await ClockCycles(dut.clk_utmi, 4)


@cocotb.test()
async def test_txvalid_lags_dataout_by_the_skew_guard_flop(dut):
    """`TxValid` crosses through Decision 3's 2-flop synchronizer **plus**
    one destination-domain pipeline flop (`rtl/usb_utmi_top.v`'s skew
    guard), so `DataOut` -- which crosses through 2 flops -- is guaranteed
    settled in the 144 MHz domain before the serializer is ever told a byte
    is available. This pins that relationship: 3 edges for `TxValid`, 2 for
    `DataOut`."""
    await _start_test(dut)

    dut.DataOut.value = 0xA5
    depth_data = await _measure_sync_depth(dut, dut.TxValid, dut.txvalid_144, 1)
    assert depth_data == 3, (
        f"TxValid reached the serializer after {depth_data} edges, expected 3 "
        f"(2-flop synchronizer + 1 skew-guard flop)"
    )
    dut.TxValid.value = 0
    await ClockCycles(dut.clk_utmi, 4)

    await _start_test(dut)
    depth = await _measure_sync_depth(dut, dut.DataOut, dut.dataout_144, 0x5A)
    assert depth == 2, f"DataOut synchronizer depth {depth}, expected 2"
    dut.DataOut.value = 0
    await ClockCycles(dut.clk_utmi, 4)


@cocotb.test()
async def test_txready_is_exactly_one_utmi_cycle_per_byte(dut):
    """Decision 4's handshake semantics: one `TxReady` per byte consumed.
    A plain level synchronizer on the serializer's own `TxReady` would
    present it for 2-3 consecutive `clk_utmi` cycles (an 83.33 ns bit time
    against a 33.33 ns clock), so this checks the property that would
    break: exactly one acknowledge per byte, each exactly one cycle wide,
    and successive acknowledges no closer than the 8-bit-time byte
    interval (20 UTMI cycles)."""
    await _start_test(dut)
    scenario = scenarios.all_zeros_payload()
    data_bytes = _byte_stream_for_scenario(scenario)

    ack_times = []
    send = cocotb.start_soon(_utmi_send_bytes(dut, data_bytes, ack_times=ack_times))
    observed = await _collect_tx_line_states(dut)
    await send

    assert observed == scenario.states, "packet was not transmitted correctly"
    assert len(ack_times) == len(data_bytes), (
        f"{len(ack_times)} TxReady acknowledges for {len(data_bytes)} bytes"
    )
    # One cycle wide: no two acknowledges on adjacent cycles.
    gaps = [b - a for a, b in zip(ack_times, ack_times[1:])]
    assert all(gap > 1 for gap in gaps), (
        f"TxReady asserted on consecutive clk_utmi cycles: {ack_times!r}"
    )
    # 8 FS bit times == 666.7 ns == 20 clk_utmi cycles; allow one cycle of
    # slack for where the crossing lands relative to the UTMI clock edge.
    assert all(gap >= 19 for gap in gaps), (
        f"acknowledges closer together than one byte interval: {gaps!r}"
    )


# ---------------------------------------------------------------------------
# 5. Negative control on the handshake crossing.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_negative_control_over_advancing_link_corrupts_packet(dut):
    """Negative control for the `TxReady` crossing (issue #52's "a mutated
    synchronizer depth or handshake" -- the depth half is pinned by
    `test_control_input_synchronizer_depth_is_two`).

    A link controller that advances **three** bytes per acknowledge is
    exactly what a mis-designed 144 -> 30 MHz `TxReady` crossing would
    cause: the serializer's `TxReady` level is asserted for one 83.33 ns FS
    bit time, i.e. 2.5 periods of the 33.33 ns UTMI clock, so a plain
    2-flop *level* synchronizer would present it on 2-3 consecutive UTMI
    cycles and a conforming link would hand over 2-3 bytes for the single
    byte actually consumed.

    Driven against the correct RTL, this must produce a packet that does
    **not** match the reference -- proving the loopback/bit-exact
    comparisons above can actually fail, rather than passing by
    construction."""
    await _start_test(dut)
    scenario = scenarios.max_length_bulk_payload()
    data_bytes = _byte_stream_for_scenario(scenario)

    wire = LoopbackWire(dut)
    rx = RxMonitor(dut)
    wire.start()
    rx.start()
    try:
        send = cocotb.start_soon(_utmi_send_bytes(dut, data_bytes, bytes_per_ack=3))
        observed = await _collect_tx_line_states(dut)
        await send
        await ClockCycles(dut.clk_utmi, 60)
    finally:
        rx.stop()
        wire.stop()

    assert observed != scenario.states, (
        "negative control did not fail: an over-advancing link produced the "
        "reference packet anyway"
    )
    assert rx.bytes != data_bytes, (
        "negative control did not fail: the loopback still delivered the "
        "reference byte stream"
    )

    # Positive control on the same stimulus: the conforming link (one byte
    # per acknowledge) does reproduce it exactly.
    await _start_test(dut)
    data_bytes, observed, rx2 = await _run_loopback(dut, scenario)
    assert observed == scenario.states
    assert rx2.bytes == data_bytes
