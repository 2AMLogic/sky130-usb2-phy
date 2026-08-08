"""Packet construction and parsing: SYNC + PID + fields + CRC + EOP,
layered on top of `nrzi.py` / `stuffing.py` / `crc.py` / `pid.py` /
`linestate.py`. This is Layer 3's foundation -- `scenarios.py` builds the
named stimulus scenarios and negative-control mutations on top of it.
"""

from . import crc, nrzi, pid, stuffing
from .bits import bits_of_byte, bits_to_bytes, bytes_to_bits, value_of_bits
from .linestate import LineState, level_to_state, state_to_level

# USB 2.0 Spec Rev 2.0 section 7.1.9: EOP is two bit times of SE0 followed
# by one bit time of J.
EOP_STATES = (LineState.SE0, LineState.SE0, LineState.J)


class PacketError(ValueError):
    """A structural packet failure: bad SYNC, missing/misplaced EOP, a
    field-length mismatch, or (via `stuffing.StuffingError`, a subclass of
    `ValueError` too) a bit-stuffing violation. Distinct from a
    *well-formed* packet whose CRC doesn't check out, which `parse()`
    reports as `crc_ok=False` rather than raising -- that's the case the
    'corrupted CRC' scenario exercises."""


def raw_field_bits(pid_name, *, addr=None, endp=None, frame_number=None, payload=None):
    """The unstuffed bit stream for one packet: PID + type-specific
    fields + CRC. Does not include SYNC (never stuffed) or EOP (not part
    of the bit-stuffed/NRZI-encoded field at all). Public so
    `scenarios.py`'s negative-control mutations can construct a corrupted
    variant at the raw-field level, before re-stuffing/re-wrapping."""
    pid_bits = pid.encode_bits(pid_name)
    if pid_name in pid.TOKEN_PIDS:
        if pid_name == "SOF":
            if frame_number is None or not (0 <= frame_number < 2**11):
                raise PacketError("SOF requires an 11-bit frame_number")
            field_bits = [(frame_number >> i) & 1 for i in range(11)]
        else:
            if addr is None or not (0 <= addr < 2**7):
                raise PacketError(f"{pid_name} requires a 7-bit addr")
            if endp is None or not (0 <= endp < 2**4):
                raise PacketError(f"{pid_name} requires a 4-bit endp")
            field_bits = [(addr >> i) & 1 for i in range(7)] + [
                (endp >> i) & 1 for i in range(4)
            ]
        return pid_bits + field_bits + crc.crc5_bits(field_bits)
    if pid_name in pid.DATA_PIDS:
        if payload is None:
            raise PacketError(f"{pid_name} requires payload bytes")
        payload_bits = bytes_to_bits(payload)
        return pid_bits + payload_bits + crc.crc16_bits(payload_bits)
    if pid_name in pid.HANDSHAKE_PIDS:
        return pid_bits
    raise PacketError(f"unknown PID {pid_name!r}")


def wrap_stuffed(stuffed_bits):
    """SYNC + (already bit-stuffed) field bits -> NRZI-encode -> append
    EOP -> the full `LineState` sequence a real FS bus would carry.
    Public so `scenarios.py` can drive a *deliberately unstuffed* field
    through this step for the `missing_stuff_bit` negative control."""
    full_bits = bits_of_byte(pid.SYNC_BYTE) + list(stuffed_bits)
    levels = nrzi.encode(full_bits, start_level=1)
    return [level_to_state(level) for level in levels] + list(EOP_STATES)


def build(pid_name, *, addr=None, endp=None, frame_number=None, payload=None):
    """Build the full `LineState` sequence for one packet: SYNC +
    (bit-stuffed PID+fields+CRC) + EOP."""
    raw = raw_field_bits(
        pid_name, addr=addr, endp=endp, frame_number=frame_number, payload=payload
    )
    return wrap_stuffed(stuffing.stuff(raw))


def parse(states):
    """Parse a full `LineState` sequence (SYNC..EOP) back into fields.

    Returns `{"pid": name, "crc_ok": bool, ...type-specific fields}`.
    Raises `PacketError` (or `stuffing.StuffingError`) on structural
    failures; see `PacketError`'s docstring for the crc_ok-vs-raise split.
    """
    states = list(states)
    if len(states) < 8 + 3:
        raise PacketError("too short to contain SYNC + EOP")
    if tuple(states[-3:]) != EOP_STATES:
        raise PacketError(f"missing/incorrect EOP, got {states[-3:]}")
    body = states[:-3]
    sync_states, data_states = body[:8], body[8:]

    sync_levels = [state_to_level(s) for s in sync_states]
    sync_bits = nrzi.decode(sync_levels, start_level=1)
    if sync_bits != bits_of_byte(pid.SYNC_BYTE):
        raise PacketError(f"bad SYNC pattern, decoded bits {sync_bits}")

    data_levels = [state_to_level(s) for s in data_states]
    stuffed_bits = nrzi.decode(data_levels, start_level=sync_levels[-1])
    raw = stuffing.destuff(stuffed_bits)

    if len(raw) < 8:
        raise PacketError("packet too short to contain a PID")
    pid_name = pid.decode_bits(raw[:8])
    rest = raw[8:]

    result = {"pid": pid_name}
    if pid_name in pid.TOKEN_PIDS:
        if pid_name == "SOF":
            if len(rest) != 16:
                raise PacketError(f"SOF field length {len(rest)} != 16")
            frame_bits, crc_bits = rest[:11], rest[11:]
            result["frame_number"] = value_of_bits(frame_bits)
            result["crc_ok"] = (
                crc.crc5_residue(frame_bits + crc_bits) == crc.CRC5_RESIDUE
            )
        else:
            if len(rest) != 16:
                raise PacketError(f"token field length {len(rest)} != 16")
            field_bits, crc_bits = rest[:11], rest[11:]
            result["addr"] = value_of_bits(field_bits[:7])
            result["endp"] = value_of_bits(field_bits[7:])
            result["crc_ok"] = (
                crc.crc5_residue(field_bits + crc_bits) == crc.CRC5_RESIDUE
            )
    elif pid_name in pid.DATA_PIDS:
        if len(rest) < 16:
            raise PacketError("data packet shorter than its own CRC16")
        payload_bits, crc_bits = rest[:-16], rest[-16:]
        if len(payload_bits) % 8 != 0:
            raise PacketError(
                f"payload bit count {len(payload_bits)} is not a whole byte count"
            )
        result["payload"] = bits_to_bytes(payload_bits)
        result["crc_ok"] = (
            crc.crc16_residue(payload_bits + crc_bits) == crc.CRC16_RESIDUE
        )
    elif pid_name in pid.HANDSHAKE_PIDS:
        if rest:
            raise PacketError(f"handshake {pid_name} has unexpected trailing bits")
        result["crc_ok"] = True
    return result
