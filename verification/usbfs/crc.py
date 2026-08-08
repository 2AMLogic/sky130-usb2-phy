"""CRC5 (token) and CRC16 (data) generators/checkers, USB 2.0 Spec Rev 2.0
section 8.3.5 ("Cyclic Redundancy Checks"):

    Token packets (ADDR+ENDP, or the SOF frame number) are protected by a
    5-bit CRC, generator polynomial G(x) = x^5 + x^2 + 1. Data packets are
    protected by a 16-bit CRC over the payload, generator polynomial
    G(x) = x^16 + x^15 + x^2 + 1. Both are computed **LSB-first** over the
    field's transmission bit order, with the CRC register initialized to
    all-ones and the transmitted CRC value the one's complement of the
    remainder.

These are exactly the standard "CRC-5/USB" and "CRC-16/USB" parameter sets
from the CRC RevEng catalogue
(https://reveng.sourceforge.io/crc-catalogue/, `width/poly/init/refin/
refout/xorout` -- the reflected/LSB-first bit-serial form used below is
the standard way to implement that catalogue entry). The catalogue's own
published self-test ("check") and "residue" values are this module's
primary known-answer vectors -- see `verification/golden/vectors.json`
(`crc5_usb_check`, `crc16_usb_check`) and `test_usbfs_model.py`, which
re-derives them here and checks the result matches.

`CRC5_POLY_REFLECTED` (`0x14`) and `CRC16_POLY_REFLECTED` (`0xA001`) are
the bit-reversals of the polynomials' non-leading coefficients (`0x05` and
`0x8005` respectively) -- the standard transform for a reflected-input,
LSB-first bit-serial CRC implementation. `0xA001` is also the well-known
"CRC-16/ARC"/Modbus polynomial constant, which is the same generator
polynomial USB16 uses (with different init/xorout) -- an independent
cross-check that this constant is right, not just self-consistent.
"""

CRC5_WIDTH = 5
CRC5_POLY_REFLECTED = 0x14
CRC5_INIT = 0x1F
CRC5_XOROUT = 0x1F
CRC5_RESIDUE = 0x06  # crc_reflected(field + crc(field), ..., xorout=0)

CRC16_WIDTH = 16
CRC16_POLY_REFLECTED = 0xA001
CRC16_INIT = 0xFFFF
CRC16_XOROUT = 0xFFFF
CRC16_RESIDUE = 0xB001


def _crc_reflected(bits, width, poly_reflected, init, xorout):
    reg = init
    mask = (1 << width) - 1
    for bit in bits:
        lsb = reg & 1
        reg >>= 1
        if bit ^ lsb:
            reg ^= poly_reflected
        reg &= mask
    return reg ^ xorout


def crc5(bits):
    """`bits`: LSB-first bit list of the protected field. Returns the
    5-bit CRC value (already one's-complemented, ready to transmit)."""
    return _crc_reflected(bits, CRC5_WIDTH, CRC5_POLY_REFLECTED, CRC5_INIT, CRC5_XOROUT)


def crc16(bits):
    return _crc_reflected(
        bits, CRC16_WIDTH, CRC16_POLY_REFLECTED, CRC16_INIT, CRC16_XOROUT
    )


def crc5_bits(bits):
    value = crc5(bits)
    return [(value >> i) & 1 for i in range(CRC5_WIDTH)]


def crc16_bits(bits):
    value = crc16(bits)
    return [(value >> i) & 1 for i in range(CRC16_WIDTH)]


def crc5_residue(bits_with_crc_appended):
    """`bits_with_crc_appended`: the protected field's bits followed by
    its own (correct) CRC5 bits, LSB-first. Recomputing the CRC over that
    combined stream (with `xorout=0`) always yields the fixed value
    `CRC5_RESIDUE` if -- and only if -- no bit was corrupted. This is how
    `packets.parse()` checks a received packet's CRC."""
    return _crc_reflected(
        bits_with_crc_appended, CRC5_WIDTH, CRC5_POLY_REFLECTED, CRC5_INIT, 0
    )


def crc16_residue(bits_with_crc_appended):
    return _crc_reflected(
        bits_with_crc_appended, CRC16_WIDTH, CRC16_POLY_REFLECTED, CRC16_INIT, 0
    )
