"""J/K/SE0/SE1 line-state encoding for USB 2.0 full-speed (FS) signaling.

FS uses D+ pull-up signaling: differential '1' (D+ high, D- low) is the J
state, and is also the bus idle state; differential '0' (D+ low, D- high)
is K. Single-ended zero (SE0, both lines low) marks EOP and bus reset;
SE1 (both lines high) is not a valid state on an FS bus and appears here
only as a mutation tool for negative-control tests (`usbfs.scenarios`).
"""

from enum import Enum


class LineState(Enum):
    J = "J"
    K = "K"
    SE0 = "SE0"
    SE1 = "SE1"


IDLE_STATE = LineState.J

_STATE_TO_DPDM = {
    LineState.J: (1, 0),
    LineState.K: (0, 1),
    LineState.SE0: (0, 0),
    LineState.SE1: (1, 1),
}
_DPDM_TO_STATE = {v: k for k, v in _STATE_TO_DPDM.items()}


def to_dpdm(state):
    """`LineState` -> `(dp, dm)`, each 0/1."""
    return _STATE_TO_DPDM[state]


def from_dpdm(dp, dm):
    """`(dp, dm)` -> `LineState`. Accepts anything `int()`-convertible
    (e.g. a cocotb signal value) for `dp`/`dm`."""
    return _DPDM_TO_STATE[(int(dp) & 1, int(dm) & 1)]


def level_to_state(level):
    """Map an NRZI line `level` (`nrzi.py`'s 1/0 convention) to J/K.
    `1 == J` matches `nrzi.IDLE_LEVEL`."""
    return LineState.J if level else LineState.K


def state_to_level(state):
    if state not in (LineState.J, LineState.K):
        raise ValueError(f"{state} is not a J/K data level")
    return 1 if state is LineState.J else 0
