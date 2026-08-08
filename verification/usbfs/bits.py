"""LSB-first bit/byte conversion helpers shared across this package.

USB 2.0 transmits every field **LSB-first** (least-significant bit first).
Every function elsewhere in this package that takes or returns a `bits`
argument uses that same convention: `bits[0]` is the first bit transmitted
on the wire.
"""


def bits_of_int(value, width):
    """`value` (an unsigned int) -> a `width`-long LSB-first bit list."""
    return [(value >> i) & 1 for i in range(width)]


def bits_of_byte(byte):
    return bits_of_int(byte, 8)


def bytes_to_bits(data):
    """`data` (bytes-like, i.e. MSB-first *within* each byte per Python's
    own convention) -> the LSB-first bit stream USB transmits it as."""
    out = []
    for b in data:
        out.extend(bits_of_byte(b))
    return out


def value_of_bits(bits):
    """The reverse of `bits_of_int`: an LSB-first bit list -> its unsigned
    integer value."""
    value = 0
    for i, bit in enumerate(bits):
        value |= (bit & 1) << i
    return value


def bits_to_bytes(bits):
    """The reverse of `bytes_to_bits`. Raises `ValueError` if `bits` is not
    a whole number of bytes long."""
    if len(bits) % 8 != 0:
        raise ValueError(f"bit count {len(bits)} is not a whole number of bytes")
    return bytes(value_of_bits(bits[i : i + 8]) for i in range(0, len(bits), 8))
