"""cocotb testbench for `usbfs_dp_dm_loopback.v` -- proves the Layer 2 BFM
(`usbfs.transceiver.IdealTransceiver`) drives and monitors DP/DM against a
live simulator, driven through `klt functional-verification` (see
`request-usbfs-model.json`). Round-trips packets built by `usbfs.packets` /
`usbfs.scenarios` through the trivial wire-loopback DUT.

Like `test_utmi_stub.py`, this file is *input* to
`klt functional-verification` (the module named by
`request.testbench.module`), not a pytest module -- pytest does not invoke
`@cocotb.test()`-decorated coroutines, since they take a cocotb-injected
`dut` argument and only run inside a simulator process. See issue #10.
"""

import random

import cocotb
from cocotb.triggers import Timer

from usbfs import packets, scenarios
from usbfs.timing import TimingConfig
from usbfs.transceiver import IdealTransceiver


async def _round_trip(dut, states, timing=None):
    tx = IdealTransceiver(dut.dp_drv, dut.dm_drv, timing=timing)
    rx = IdealTransceiver(dut.dp_sense, dut.dm_sense, timing=timing)

    drive_task = cocotb.start_soon(tx.drive_states(states))
    observed = await rx.monitor_states(len(states))
    await drive_task
    return observed


@cocotb.test()
async def test_loopback_drives_and_monitors_a_packet(dut):
    """Acceptance criterion: 'The BFM can both drive and monitor DP/DM,
    demonstrated in the same test.' Drives a full packet (the
    stuff-bit-before-EOP scenario) onto the loopback DUT's inputs while
    concurrently monitoring its outputs, then decodes what was monitored
    with `usbfs.packets.parse()` and checks it matches what was sent."""
    dut.dp_drv.value = 0
    dut.dm_drv.value = 0
    await Timer(1, unit="ns")

    scenario = scenarios.stuff_before_eop_payload()
    observed = await _round_trip(dut, scenario.states)

    assert observed == scenario.states, (
        "loopback did not reproduce the driven line states"
    )

    parsed = packets.parse(observed)
    assert parsed["pid"] == "DATA0"
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload


@cocotb.test()
async def test_loopback_with_nonzero_timing_knobs(dut):
    """The frequency-offset and bit-timing-jitter knobs (`usbfs.timing.
    TimingConfig`) exist, default to zero (see `test_usbfs_model.py`'s
    plain-pytest coverage of the knob arithmetic itself), and are
    exercised here at a non-zero setting against a live simulator: a
    +1000 ppm reference-frequency offset (within the +/-2500 ppm USB FS
    tolerance) plus +/-2 ns per-bit jitter still round-trips correctly
    over this scenario's packet length, since the cumulative drift stays
    well inside the monitor's mid-bit sampling margin."""
    dut.dp_drv.value = 0
    dut.dm_drv.value = 0
    await Timer(1, unit="ns")

    timing = TimingConfig(
        freq_offset_ppm=1000.0, bit_jitter_ns=2.0, rng=random.Random(1234)
    )
    scenario = scenarios.all_zeros_payload()
    observed = await _round_trip(dut, scenario.states, timing=timing)

    assert observed == scenario.states
    parsed = packets.parse(observed)
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload
