"""usbfs -- behavioral ideal-transceiver model and USB 2.0 FS protocol
reference for this repo's verification (issue #10).

This package is independent of any RTL: it exists so RTL testbenches (the
TX-path and RX-path issues, #12/#13) have one shared, independently
verified reference to check against, instead of each writing its own
throwaway NRZI/stuffing helper. See `verification/README.md` for what it
does and deliberately does not model.

Layering (see each module's own docstring for detail):

- Layer 1 (pure functions, no cocotb, no simulator): `nrzi`, `stuffing`,
  `crc`, `pid`, `linestate`, `timing`.
- Layer 2 (cocotb bus-functional model): `transceiver`. **Not** imported
  here -- it imports `cocotb`, which is not installed in every environment
  that needs Layer 1/3 (see `verification/test_usbfs_model.py`, which must
  run with no simulator installed). Import `usbfs.transceiver` explicitly
  from a cocotb testbench.
- Layer 3 (packet/traffic builders on top of 1): `packets`, `scenarios`.
"""

from . import crc, linestate, nrzi, packets, pid, scenarios, stuffing, timing

__all__ = [
    "crc",
    "linestate",
    "nrzi",
    "packets",
    "pid",
    "scenarios",
    "stuffing",
    "timing",
]
