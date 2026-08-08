"""Bit stuffing / destuffing, USB 2.0 Spec Rev 2.0 section 7.1.9:

    "... a zero is inserted after every six consecutive ones in the data
    stream before the data is NRZI encoded. This guarantees at least one
    transition every seven bit times, thus guaranteeing that the receiver
    maintains bit and data synchronization."

Stuffing applies to every bit **after** SYNC through the end of CRC (SYNC
itself is a fixed pattern that is never stuffed -- and, being
`0000 0001`, never contains six consecutive ones anyway). This module
doesn't know or enforce that scope; it operates on whatever bit list it is
given -- `packets.py` is the layer that decides which fields to stuff.

**Stuff bit immediately before EOP:** if the *last* six bits of the
protected field happen to be `1`, `stuff()` inserts the stuff bit as the
very last bit of its output, with nothing (in-protocol) following it but
EOP. This is the edge case `spec/architecture.md` calls out by name, and
this module handles it with no special-casing at all: the algorithm below
doesn't know where the field ends relative to EOP, it just keeps counting.
See `usbfs.scenarios.stuff_before_eop_payload` for a constructed example
and `verification/golden/vectors.json`'s `stuff_before_eop_data_packet`
entry for its provenance.
"""


class StuffingError(ValueError):
    """Raised by `destuff()` on a bit-stuff violation: a 7th consecutive
    `1` appeared where a stuffed `0` was mandatory."""


def stuff(bits):
    out = []
    run = 0
    for bit in bits:
        out.append(bit)
        if bit == 1:
            run += 1
            if run == 6:
                out.append(0)
                run = 0
        else:
            run = 0
    return out


def destuff(bits):
    """The inverse of `stuff()`. Raises `StuffingError` if a run of six
    `1`s is followed by another `1` instead of the mandatory stuffed `0`."""
    out = []
    run = 0
    for bit in bits:
        if run == 6:
            if bit != 0:
                raise StuffingError(
                    "bit-stuff violation: expected a stuffed 0 after six consecutive 1s"
                )
            run = 0
            continue
        out.append(bit)
        run = run + 1 if bit == 1 else 0
    return out
