"""Shared cocotb helpers for the verification suites: background monitors
plus the bounded TX line-state capture coroutine both TX-side suites use
(issue #475).

Deliberately a sibling of the `test_*.py` files, not part of the `usbfs`
package: `usbfs/__init__.py` documents that cocotb-importing code is not
imported there, and these helpers need `cocotb`.
"""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

from usbfs.linestate import from_dpdm
from usbfs.scenarios import FS_MAX_ISOCHRONOUS_PACKET_SIZE


class Monitor:
    """Background sampler. Subclasses implement `async def _run(self)`."""

    def __init__(self, dut):
        self.dut = dut
        self._task = None

    def start(self):
        self._task = cocotb.start_soon(self._run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None


class RxMonitor(Monitor):
    """Samples RxValid/DataIn/RxActive/RxError once per clk_utmi edge (the
    rate at which the UTMI-domain outputs can change)."""

    def __init__(self, dut):
        super().__init__(dut)
        self.bytes = []
        self.saw_error = False
        self.active_trace = []  # one bool per clk_utmi edge
        # Sim time (ns) of each active_trace sample, parallel to it, so a
        # test can reason about *when* RxActive changed relative to the
        # driven stimulus rather than only about the trace's own shape
        # (issue #441: the EOP-boundary check needs an independent time
        # reference; the trace alone cannot provide one).
        self.sample_times_ns = []

    @property
    def saw_active(self):
        return any(self.active_trace)

    async def _run(self):
        while True:
            await RisingEdge(self.dut.clk_utmi)
            await ReadOnly()
            if self.dut.RxValid.value:
                self.bytes.append(int(self.dut.DataIn.value))
            if self.dut.RxError.value:
                self.saw_error = True
            self.active_trace.append(bool(self.dut.RxActive.value))
            self.sample_times_ns.append(get_sim_time(units="ns"))


# ---------------------------------------------------------------------------
# Bounded TX line-state capture (issue #475), shared by test_usb_tx.py and
# test_usb_utmi_top.py.
# ---------------------------------------------------------------------------

# 144 MHz oversampling clock / 12 = 12 Mbps FS bit rate (decision record
# #9, Decision 6) -- the divide `rtl/usb_tx_serializer.v` implements, and
# hence the bit-time length in `clock` cycles of every suite that drives
# that serializer.
FS_BIT_PERIOD_CYCLES = 12

# Worst-case length, in bit times, of the longest packet the reference
# model defines: the 1023-byte FS isochronous maximum payload
# (`usbfs.scenarios.FS_MAX_ISOCHRONOUS_PACKET_SIZE`, USB 2.0's largest
# single FS transaction). PID (8) + payload (8*N) + CRC16 (16) raw field
# bits, plus one forced stuff bit per 6 raw bits (the all-ones maximum
# stuffing density), plus SYNC (8, never stuffed) and EOP (2x SE0 + J).
_MAX_PACKET_RAW_BITS = 8 + 8 * FS_MAX_ISOCHRONOUS_PACKET_SIZE + 16
_MAX_PACKET_BIT_TIMES = (
    8 + _MAX_PACKET_RAW_BITS + _MAX_PACKET_RAW_BITS // 6 + 3
)

# Default bound for both capture waits, in clock cycles of the `clock`
# passed to `collect_tx_line_states()`: the longest packet's worst-case
# duration with 2x headroom, so a passing capture never trips it while a
# driver stuck either way fails in bounded time with a readable
# assertion instead of hanging the regression (issue #475).
DEFAULT_CAPTURE_LIMIT_CYCLES = 2 * _MAX_PACKET_BIT_TIMES * FS_BIT_PERIOD_CYCLES


async def collect_tx_line_states(
    dut,
    clock,
    bit_period_cycles=FS_BIT_PERIOD_CYCLES,
    max_assert_wait_cycles=DEFAULT_CAPTURE_LIMIT_CYCLES,
    max_release_wait_cycles=DEFAULT_CAPTURE_LIMIT_CYCLES,
):
    """Sample `tx_dp`/`tx_dn` once per bit time, from the bit time `tx_oe`
    first asserts (SYNC bit 0) through the bit time before it releases
    (the EOP J bit time) -- exactly the `SYNC + body + EOP` sequence
    `usbfs.packets.build()` returns.

    The one capture loop both TX-side suites use (issue #475): pass the
    clock of the domain the serializer runs in explicitly -- `dut.clk` in
    `test_usb_tx.py`, `dut.clk_144` in `test_usb_utmi_top.py`. Each
    sample lands one `RisingEdge` plus one `ReadOnly` after the previous
    one, so it reads post-settle values exactly where the original
    per-suite collectors did.

    Read-only: never writes a signal, so it is always safe to leave this
    coroutine parked in the ReadOnly phase between samples (and it
    returns the caller parked in one -- a caller that then needs to write
    a signal must `NextTimeStep()` first).

    Both waits are bounded in `clock` cycles (the units are in the
    parameter names) so a broken DUT reports a diagnostic naming *which*
    wait expired instead of hanging the simulator: `tx_oe` never
    asserting trips the assert-wait message, `tx_oe` never releasing
    trips the release-wait message.
    """
    waited = 0
    while not int(dut.tx_oe.value):
        await RisingEdge(clock)
        await ReadOnly()
        waited += 1
        assert waited < max_assert_wait_cycles, (
            f"tx_oe never asserted within {max_assert_wait_cycles} "
            f"clock cycles"
        )
    states = []
    driven = 0
    while int(dut.tx_oe.value):
        states.append(from_dpdm(dut.tx_dp.value, dut.tx_dn.value))
        for _ in range(bit_period_cycles):
            await RisingEdge(clock)
            await ReadOnly()
            driven += 1
        assert driven < max_release_wait_cycles, (
            f"tx_oe never released within {max_release_wait_cycles} clock "
            f"cycles ({len(states)} line states sampled)"
        )
    return states
