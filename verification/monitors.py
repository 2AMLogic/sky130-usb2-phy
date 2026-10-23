"""Shared cocotb background monitors for the verification suites.

Deliberately a sibling of the `test_*.py` files, not part of the `usbfs`
package: `usbfs/__init__.py` documents that cocotb-importing code is not
imported there, and these monitors need `cocotb`.
"""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge


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
