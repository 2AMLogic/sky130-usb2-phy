"""cocotb testbench for the RX async FIFO in `rtl/usb_rx_cdc.v` (issue #164).

Directed FIFO-full checks for the registered `full_q` flag that replaced the
combinational `wr_en -> wptr_*_next -> full -> wr_en` loop. The DUT is
`usb_rx_cdc` itself, so the write side can be driven back-to-back and the read
side stalled by stopping `clk_utmi` -- the full receive path never presents
that stimulus. Input to `klt functional-verification` (see
`request-usb-rx-cdc.json`), not a pytest module.

FIFO capacity is 8 entries (`FIFO_DEPTH_LOG2 = 3`, DR-0001 Decision 3). The
write side has no backpressure port, so bytes offered while full are dropped
by design; the property checked is that bytes already accepted are never
overwritten and that nothing past capacity is accepted.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

DEPTH = 8
CLK144_PS = 6944
CLK_UTMI_PS = 33333

_clk = {}


def start_clock(name, sig, period_ps):
    stop_clock(name)
    _clk[name] = cocotb.start_soon(
        Clock(sig, period_ps, unit="ps", period_high=period_ps // 2).start()
    )


def stop_clock(name):
    task = _clk.pop(name, None)
    if task is not None:
        task.cancel()


async def reset_dut(dut):
    start_clock("144", dut.clk_144, CLK144_PS)
    start_clock("utmi", dut.clk_utmi, CLK_UTMI_PS)
    dut.rx_byte_valid.value = 0
    dut.rx_byte.value = 0
    dut.rx_active_144.value = 0
    dut.rx_error_144.value = 0
    dut.line_state_144.value = 0
    dut.bus_reset_144.value = 0
    dut.suspend_144.value = 0
    dut.reset_async.value = 1
    await ClockCycles(dut.clk_144, 8)
    dut.reset_async.value = 0
    await ClockCycles(dut.clk_utmi, 8)


async def write_burst(dut, data):
    """One byte per clk_144 cycle, back to back, then deassert valid."""
    for b in data:
        dut.rx_byte.value = b
        dut.rx_byte_valid.value = 1
        await RisingEdge(dut.clk_144)
    dut.rx_byte_valid.value = 0
    await ClockCycles(dut.clk_144, 4)


async def drain(dut, cycles=40):
    """Run clk_utmi and collect every RxValid byte."""
    start_clock("utmi", dut.clk_utmi, CLK_UTMI_PS)
    got = []
    for _ in range(cycles):
        await RisingEdge(dut.clk_utmi)
        await Timer(1, unit="ns")
        if int(dut.RxValid.value):
            got.append(int(dut.DataIn.value))
    return got


@cocotb.test()
async def test_fill_to_capacity_no_overwrite(dut):
    """Back-to-back writes with the reader stalled: exactly the first DEPTH
    bytes survive, in order; later offers are dropped, not overwritten."""
    await reset_dut(dut)
    stop_clock("utmi")
    data = [0xA0 + i for i in range(DEPTH + 4)]
    await write_burst(dut, data)
    got = await drain(dut)
    assert got == data[:DEPTH], f"got {[hex(g) for g in got]}"


@cocotb.test()
async def test_reset_mid_fill_clears_full(dut):
    """Reset while full: full_q clears and a fresh burst is accepted."""
    await reset_dut(dut)
    stop_clock("utmi")
    await write_burst(dut, [0x11 + i for i in range(DEPTH + 2)])
    await reset_dut(dut)  # restarts both clocks, pulses reset_async
    stop_clock("utmi")
    fresh = [0xC0 + i for i in range(3)]
    await write_burst(dut, fresh)
    got = await drain(dut)
    assert got == fresh, f"got {[hex(g) for g in got]}"


@cocotb.test()
async def test_write_after_pop_from_full(dut):
    """After a full FIFO is drained, the write side accepts new bytes again
    (full_q clears one clk_144 cycle late, conservatively)."""
    await reset_dut(dut)
    stop_clock("utmi")
    await write_burst(dut, [0x20 + i for i in range(DEPTH + 1)])
    first = await drain(dut)
    assert first == [0x20 + i for i in range(DEPTH)]
    second_in = [0x80 + i for i in range(DEPTH)]
    stop_clock("utmi")
    await write_burst(dut, second_in)
    second = await drain(dut)
    assert second == second_in, f"got {[hex(g) for g in second]}"
