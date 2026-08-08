"""Stimulus scenarios and negative-control mutations, layered on
`packets.py`.

Each scenario below builds a *correct* packet (round-trips cleanly through
`packets.build()` / `packets.parse()`) and is paired -- in
`test_usbfs_model.py` -- with one of the three canonical mutations defined
at the bottom of this module (`flip_crc_bit`, `missing_stuff_bit`,
`invert_nrzi_polarity`) or `truncate`, each demonstrated to fail when
applied and to pass when it is not. "A suite that cannot fail is not
evidence" (issue #10).

`RANDOM_SEED` is the recorded seed for every pseudo-random scenario here
and for the randomized round-trip tests in `test_usbfs_model.py`.
"""

import random
from dataclasses import dataclass

from . import pid, stuffing
from . import packets
from .linestate import LineState

RANDOM_SEED = 20260807

# USB 2.0 Spec Rev 2.0 Table 5-5: FS bulk endpoint maximum packet size.
FS_MAX_PACKET_SIZE = 64

# USB 2.0 Spec Rev 2.0: largest single FS transaction is an isochronous data
# payload of up to 1023 bytes -- the worst-case drift-accumulation window
# spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md
# Decision 3's RX-FIFO-depth derivation uses (682 us at 12 Mbps). Added here
# (rather than built ad hoc in a testbench) per issue #13's Test Plan, so the
# RX-path (#13) and TX-path (#12) RTL issues can share one canonical
# maximum-length-payload scenario instead of each rebuilding it.
FS_MAX_ISOCHRONOUS_PACKET_SIZE = 1023

# Found by `find_stuff_before_eop_payload()` below; see
# verification/golden/vectors.json's `stuff_before_eop_data_packet` entry.
STUFF_BEFORE_EOP_PAYLOAD = bytes([0xF9])


@dataclass
class Scenario:
    name: str
    states: list
    fields: dict  # the correct packets.parse() result for `states`
    payload: object  # bytes, or None for token/handshake scenarios
    provenance: str


def _build_token(pid_name, addr, endp):
    states = packets.build(pid_name, addr=addr, endp=endp)
    return states, packets.parse(states)


def _build_data(pid_name, payload):
    states = packets.build(pid_name, payload=payload)
    return states, packets.parse(states)


def max_length_bulk_payload(rng_seed=RANDOM_SEED):
    rng = random.Random(rng_seed)
    payload = bytes(rng.randrange(256) for _ in range(FS_MAX_PACKET_SIZE))
    states, fields = _build_data("DATA1", payload)
    return Scenario(
        "max_length_bulk_payload",
        states,
        fields,
        payload,
        f"{FS_MAX_PACKET_SIZE}-byte (FS bulk max, USB 2.0 Table 5-5) DATA1 "
        f"payload, pseudo-random content seeded with {rng_seed}.",
    )


def max_length_isochronous_payload(rng_seed=RANDOM_SEED):
    """The 1023-byte (FS isochronous max, USB 2.0) DATA1 payload used to
    stress drift accumulation over the longest single FS transaction --
    see `FS_MAX_ISOCHRONOUS_PACKET_SIZE`'s module-level docstring."""
    rng = random.Random(rng_seed)
    payload = bytes(rng.randrange(256) for _ in range(FS_MAX_ISOCHRONOUS_PACKET_SIZE))
    states, fields = _build_data("DATA1", payload)
    return Scenario(
        "max_length_isochronous_payload",
        states,
        fields,
        payload,
        f"{FS_MAX_ISOCHRONOUS_PACKET_SIZE}-byte (FS isochronous max) DATA1 "
        f"payload, pseudo-random content seeded with {rng_seed}. The "
        f"largest single FS transaction USB 2.0 defines -- the "
        f"drift-accumulation worst case Decision 3 of the clocking/CDC "
        f"decision record sizes the RX byte FIFO against.",
    )


def find_stuff_before_eop_payload(pid_name="DATA0"):
    """Exhaustive, deterministic search over 1-byte payloads (0x00-0xFF)
    for the first whose bit-stuffed PID+payload+CRC16 stream ends with a
    forced stuff bit immediately preceding EOP. Reproduces
    `STUFF_BEFORE_EOP_PAYLOAD` from first principles -- exercised by
    `test_usbfs_model.py` so the golden constant isn't just hand-typed."""
    for value in range(256):
        payload = bytes([value])
        raw = packets.raw_field_bits(pid_name, payload=payload)
        stuffed = stuffing.stuff(raw)
        if len(stuffed) == len(raw) + 1 and stuffed[-1] == 0 and raw[-1] == 1:
            return payload
    raise LookupError("no 1-byte payload found with a trailing forced stuff bit")


def stuff_before_eop_payload():
    states, fields = _build_data("DATA0", STUFF_BEFORE_EOP_PAYLOAD)
    return Scenario(
        "stuff_before_eop_payload",
        states,
        fields,
        STUFF_BEFORE_EOP_PAYLOAD,
        "DATA0, payload 0xF9: the last 6 bits of the CRC16 field are 1, "
        "forcing a bit-stuff 0 as the very last bit before EOP -- the edge "
        "case spec/architecture.md names by hand. Found by "
        "find_stuff_before_eop_payload(); see verification/golden/vectors.json.",
    )


def all_ones_payload(n_bytes=8):
    payload = bytes([0xFF] * n_bytes)
    states, fields = _build_data("DATA1", payload)
    return Scenario(
        "all_ones_payload",
        states,
        fields,
        payload,
        f"{n_bytes} bytes of 0xFF: maximum bit-stuffing density (a stuff "
        f"bit every 6 payload bits, repeatedly through the whole payload).",
    )


def all_zeros_payload(n_bytes=8):
    payload = bytes([0x00] * n_bytes)
    states, fields = _build_data("DATA0", payload)
    return Scenario(
        "all_zeros_payload",
        states,
        fields,
        payload,
        f"{n_bytes} bytes of 0x00: no bit stuffing occurs (no run of six "
        f"1s anywhere), and NRZI toggles on every single bit -- maximum "
        f"transition density.",
    )


def corrupted_crc_token(addr=0x3A, endp=0xA):
    states, fields = _build_token("SETUP", addr, endp)
    return Scenario(
        "corrupted_crc_token",
        states,
        fields,
        None,
        f"SETUP token, addr=0x{addr:02X} endp=0x{endp:X}: the *correct* "
        f"base case that flip_crc_bit() is paired with below.",
    )


def truncated_packet():
    payload = b"\x42\x43"
    states, fields = _build_data("DATA0", payload)
    return Scenario(
        "truncated_packet",
        states,
        fields,
        payload,
        "DATA0, 2-byte payload: the *correct* base case that truncate() "
        "is paired with below.",
    )


# ---- mutations (negative controls) ----
#
# Every mutation is deterministic and operates on the same construction
# inputs as the scenario it corrupts, not on an already-built LineState
# list where possible -- that keeps each mutation exactly the thing it
# claims to be (a CRC bit flip, a missing stuff bit, ...), with no
# incidental side effects from re-deriving stuffing/NRZI/CRC around it.


def flip_crc_bit(pid_name, *, addr=None, endp=None, payload=None, bit_index=0):
    """Flip one bit within the field's own CRC (before stuffing/NRZI),
    then re-stuff and re-wrap."""
    raw = list(packets.raw_field_bits(pid_name, addr=addr, endp=endp, payload=payload))
    if pid_name in pid.TOKEN_PIDS:
        crc_width = 5
    elif pid_name in pid.DATA_PIDS:
        crc_width = 16
    else:
        raise ValueError(f"{pid_name} has no CRC field to flip")
    idx = len(raw) - crc_width + (bit_index % crc_width)
    raw[idx] ^= 1
    return packets.wrap_stuffed(stuffing.stuff(raw))


def missing_stuff_bit(pid_name, *, payload=None):
    """Skip bit-stuffing entirely, as if the encoder failed to insert
    stuff bits. Only reliably *detectable on decode* when the raw field
    has a run of six 1s that is not the very last bits of the field --
    dropping a stuff bit that would have landed as the field's last bit
    (immediately before EOP) removes exactly one bit-time with nothing
    (in-protocol) after it to misinterpret, so it doesn't corrupt any
    *content* by itself. That's why this mutation is paired with
    `all_ones_payload` (stuffing in the middle of the payload) rather than
    `stuff_before_eop_payload` in `test_usbfs_model.py` -- see that file's
    comment for the length-based check used for the latter instead."""
    raw = packets.raw_field_bits(pid_name, payload=payload)
    return packets.wrap_stuffed(raw)  # stuffing.stuff() deliberately skipped


def invert_nrzi_polarity(states):
    """Swap J<->K, as if the DP/DM differential pair were physically
    swapped. SE0/SE1 are unaffected -- both lines being equal is
    polarity-independent."""
    swap = {
        LineState.J: LineState.K,
        LineState.K: LineState.J,
        LineState.SE0: LineState.SE0,
        LineState.SE1: LineState.SE1,
    }
    return [swap[s] for s in states]


def truncate(states, drop=6):
    """Drop the last `drop` line-states before EOP -- a packet that never
    reaches EOP (e.g. a dropped/corrupted transmission)."""
    if drop >= len(states):
        raise ValueError("drop must be smaller than the packet")
    return states[:-drop]
