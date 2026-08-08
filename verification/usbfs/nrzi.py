"""NRZI (Non-Return-to-Zero Inverted) line encoding, USB 2.0 Spec Rev 2.0
section 7.1.9 ("NRZI, Bit Stuffing, and the SYNC Field"):

    "USB data is NRZI encoded ... a '0' bit is represented by a transition
    in the line state, and a '1' bit is represented by no transition."

Bits are plain ints (0/1) in this package's LSB-first transmission order.
"Level" here is likewise a plain int (0/1); this module intentionally does
not know about J/K -- that mapping is `linestate.py`'s job. By convention
(matched by `linestate.level_to_state`), level `1` represents the bus idle
level (J for FS signaling).
"""

IDLE_LEVEL = 1


def encode(bits, start_level=IDLE_LEVEL):
    """NRZI-encode `bits` (LSB-first) into a same-length list of line
    levels. `start_level` is the level held immediately before the first
    bit (bus idle, by default)."""
    levels = []
    level = start_level
    for bit in bits:
        if bit == 0:
            level ^= 1
        levels.append(level)
    return levels


def decode(levels, start_level=IDLE_LEVEL):
    """The inverse of `encode`: a level sequence -> the bits that produced
    it, given the level held immediately before the first sample."""
    bits = []
    level = start_level
    for new_level in levels:
        bits.append(0 if new_level != level else 1)
        level = new_level
    return bits
