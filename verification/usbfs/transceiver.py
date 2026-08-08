"""Ideal DP/DM bus-functional model (cocotb). Layer 2: converts between
`LineState` sequences (`linestate.py`) and simulated DP/DM signals at USB
FS bit timing.

This module `import cocotb` at module scope and is only usable inside a
running cocotb simulation -- it is deliberately **not** imported by
`usbfs/__init__.py` or by `test_usbfs_model.py`, so the Layer 1/3 pytest
suite runs with no simulator installed. Import it explicitly from a cocotb
testbench (see `verification/test_usbfs_loopback.py`).

This is a *behavioral* model per spec/usb2-phy.md section 7: it drives and
samples logic-level 0/1 on whatever cocotb signal handles it is given, at
FS bit timing. It does not model driver output resistance, rise/fall
time, crossover voltage, or squelch thresholds -- see CLAUDE.md's
scope-discipline rule. The two adjustable non-ideality knobs
(`timing.TimingConfig`'s `freq_offset_ppm` / `bit_jitter_ns`) are the only
non-idealities modeled, and both default to zero.
"""

from cocotb.triggers import ReadOnly, Timer

from .linestate import LineState, from_dpdm, to_dpdm
from .timing import TimingConfig


def _ns_to_timer(ns):
    # cocotb's Timer takes an int step count; use picoseconds so
    # non-integer-ns bit periods (83.33... ns nominal) don't get rounded
    # away to nothing.
    return Timer(round(ns * 1000), unit="ps")


class IdealTransceiver:
    """Drives and/or monitors a DP/DM pair. `drive_dp`/`drive_dm` are the
    cocotb signal handles this instance's `drive_*` methods write to;
    `sense_dp`/`sense_dm` (default: same as drive_*) are what
    `monitor_states()` reads. Separate handles let one instance drive a
    DUT's inputs while a second instance (or the same instance, for a
    pure loopback DUT) monitors the DUT's outputs -- see
    `test_usbfs_loopback.py` for both roles exercised in the same test.
    """

    def __init__(self, drive_dp, drive_dm, sense_dp=None, sense_dm=None, timing=None):
        self.drive_dp = drive_dp
        self.drive_dm = drive_dm
        self.sense_dp = sense_dp if sense_dp is not None else drive_dp
        self.sense_dm = sense_dm if sense_dm is not None else drive_dm
        self.timing = timing if timing is not None else TimingConfig()

    def _drive_state(self, state):
        dp, dm = to_dpdm(state)
        self.drive_dp.value = dp
        self.drive_dm.value = dm

    async def drive_states(self, states):
        """Drive one `LineState` per FS bit period, in order (including
        this instance's `timing` knobs)."""
        for state in states:
            self._drive_state(state)
            await _ns_to_timer(self.timing.next_bit_period_ns())

    async def drive_idle(self, bit_times=1):
        await self.drive_states([LineState.J] * bit_times)

    async def drive_reset(self, bit_times=1):
        """Hold SE0 -- USB 2.0 section 7.1.7.3 bus reset signaling. Bare
        line-driving primitive: this model does not itself assert any
        particular duration is "a reset" (that's the RX-path RTL's job to
        recognize); see `timing.RESET_DETECT_MIN_NS` for the device-side
        detection threshold this can be driven toward."""
        await self.drive_states([LineState.SE0] * bit_times)

    async def drive_suspend(self, bit_times=1):
        """Hold J (idle) -- USB 2.0 section 7.1.7.6 suspend signaling is
        continuous idle for >= `timing.SUSPEND_DETECT_MIN_NS`; see that
        constant's docstring for the same caveat as `drive_reset`."""
        await self.drive_idle(bit_times)

    async def sample_state(self):
        await ReadOnly()
        return from_dpdm(self.sense_dp.value, self.sense_dm.value)

    async def monitor_states(self, count):
        """Sample one `LineState` per *nominal* FS bit period (this
        instance's `timing.freq_offset_ppm`/`bit_jitter_ns` are not
        applied to the monitor's own sample clock -- they model the
        *driving* side's imperfection, which is what a fixed-nominal-rate
        observer, or a future RX-path RTL's recovered clock, needs to
        tolerate). The first sample lands at the bit-time midpoint, not
        on an edge."""
        await _ns_to_timer(self.timing.nominal_bit_period_ns() / 2)
        states = [await self.sample_state()]
        for _ in range(count - 1):
            await _ns_to_timer(self.timing.nominal_bit_period_ns())
            states.append(await self.sample_state())
        return states


__all__ = ["IdealTransceiver"]
