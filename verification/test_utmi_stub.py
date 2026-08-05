"""cocotb testbench for `utmi_stub.v` -- proves the digital verification
harness (cocotb + Icarus, driven through `klt functional-verification`)
works end-to-end in this repo. See issue #3.

`utmi_stub` is deliberately trivial: a one-cycle registered pass-through
using UTMI-shaped signal names (`TxValid`/`TxReady`/`DataOut`/`DataIn`/
`RxValid`), not real UTMI protocol logic (no NRZI, no bit stuffing, no line
state). This file is *input* to `klt functional-verification` (the
testbench module named by `request.testbench.module`), not a pytest module
-- pytest never collects it, since it takes a cocotb-injected `dut` argument
and only runs inside a simulator process.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


async def reset(dut):
    dut.rst_n.value = 0
    dut.TxValid.value = 0
    dut.DataOut.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_reset_clears_outputs(dut):
    """Out of reset, all registered outputs are 0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)

    assert dut.TxReady.value == 0
    assert dut.RxValid.value == 0
    assert int(dut.DataIn.value) == 0


@cocotb.test()
async def test_registered_pass_through(dut):
    """DataOut -> DataIn and TxValid -> TxReady/RxValid, one cycle later.

    Randomized, fixed seed for reproducibility -- a bit-exact cross-check
    of the trivial pass-through, not a protocol test. Outputs are checked
    against the *previous* cycle's stimulus, since `utmi_stub` registers
    them (the value driven this cycle is not visible on the outputs until
    after the following clock edge).
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset(dut)

    rng = random.Random(0)
    prev_data, prev_valid = 0, 0
    for _ in range(40):
        data = rng.randint(0, 255)
        valid = rng.randint(0, 1)

        dut.DataOut.value = data
        dut.TxValid.value = valid
        await RisingEdge(dut.clk)

        # Registered outputs reflect the *previous* cycle's inputs.
        assert int(dut.DataIn.value) == prev_data, (
            f"DataIn: got {int(dut.DataIn.value)}, want {prev_data}"
        )
        assert dut.TxReady.value == prev_valid, (
            f"TxReady: got {dut.TxReady.value}, want {prev_valid}"
        )
        assert dut.RxValid.value == prev_valid, (
            f"RxValid: got {dut.RxValid.value}, want {prev_valid}"
        )

        prev_data, prev_valid = data, valid
