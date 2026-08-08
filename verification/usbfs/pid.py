"""SYNC field and PID (Packet Identifier) encoding, USB 2.0 Spec Rev 2.0
section 7.1.9 (SYNC) and section 8.3.1 / Table 8-1 (PID Types).

Every field in this package is LSB-first (`bits.py`), matching USB's
transmission bit order.
"""

from .bits import bits_of_byte, value_of_bits

# SYNC field: byte 0x80, bits (LSB-first) 0,0,0,0,0,0,0,1. NRZI-encoded
# from idle (J), this produces the "KJKJKJKK" pattern the spec names
# directly -- see verification/golden/vectors.json's `nrzi_sync` entry,
# which cross-checks this by hand.
SYNC_BYTE = 0x80

# USB 2.0 Table 8-1: PID Types. 4-bit values; the transmitted PID byte is
# this nibble in bits[3:0] with its one's complement in bits[7:4].
PID = {
    # Token
    "OUT": 0b0001,
    "IN": 0b1001,
    "SOF": 0b0101,
    "SETUP": 0b1101,
    # Data
    "DATA0": 0b0011,
    "DATA1": 0b1011,
    # Handshake
    "ACK": 0b0010,
    "NAK": 0b1010,
    "STALL": 0b1110,
}
PID_NAME_BY_VALUE = {v: k for k, v in PID.items()}

TOKEN_PIDS = frozenset({"OUT", "IN", "SOF", "SETUP"})
DATA_PIDS = frozenset({"DATA0", "DATA1"})
HANDSHAKE_PIDS = frozenset({"ACK", "NAK", "STALL"})


class PidError(ValueError):
    """Raised on a PID complement-nibble self-check failure, or an
    unrecognized PID nibble -- both are real bus errors this field exists
    to catch, not this package's own bugs."""


def encode(name):
    """`name` (e.g. "SETUP") -> the 8-bit PID byte: low nibble + its one's
    complement in the high nibble."""
    nibble = PID[name]
    return nibble | ((~nibble & 0xF) << 4)


def encode_bits(name):
    return bits_of_byte(encode(name))


def decode(byte):
    """8-bit PID byte -> name. Raises `PidError` if the complement nibble
    doesn't match, or the nibble isn't a PID this package knows."""
    low = byte & 0xF
    high = (byte >> 4) & 0xF
    if high != (~low & 0xF):
        raise PidError(
            f"PID complement check failed: byte=0x{byte:02X} low={low:04b} high={high:04b}"
        )
    name = PID_NAME_BY_VALUE.get(low)
    if name is None:
        raise PidError(f"unrecognized PID nibble 0x{low:X}")
    return name


def decode_bits(bits):
    return decode(value_of_bits(bits[:8]))
