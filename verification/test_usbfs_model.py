"""Self-tests for `usbfs`'s Layer 1 (protocol reference) and Layer 3
(packet/traffic builders) -- pure Python, **no cocotb, no simulator**. Run
with plain `pytest` from a cold shell:

    cd verification
    python3 -m pytest test_usbfs_model.py -v

(Or `pytest verification/test_usbfs_model.py -v` from the repo root.) This
file deliberately does not import `usbfs.transceiver` (Layer 2, cocotb-only)
-- that layer is exercised by `test_usbfs_loopback.py` through
`klt functional-verification verification/request-usbfs-model.json`, which
requires a simulator. See `verification/README.md`.

Known-answer vectors live in `golden/vectors.json`, each with its own
provenance field. `RANDOM_SEED` (imported from `usbfs.scenarios`) is the
single recorded seed for every randomized test in this file.
"""

import json
import random
from pathlib import Path

import pytest

from usbfs import crc, nrzi, packets, pid, scenarios, stuffing
from usbfs.timing import FS_BIT_PERIOD_NS, MAX_FREQ_OFFSET_PPM, TimingConfig

GOLDEN = json.loads((Path(__file__).parent / "golden" / "vectors.json").read_text())

RANDOM_SEED = scenarios.RANDOM_SEED
ROUND_TRIP_SAMPLE_COUNT = 500


# ---------------------------------------------------------------------------
# Layer 1: NRZI
# ---------------------------------------------------------------------------


def test_nrzi_sync_known_vector():
    vec = GOLDEN["nrzi_sync"]
    levels = nrzi.encode(vec["input_bits_lsb_first"], start_level=1)
    got = ["J" if level else "K" for level in levels]
    assert got == vec["expected_levels"]


def test_nrzi_round_trip_random():
    """Encode -> decode round-trips over ROUND_TRIP_SAMPLE_COUNT randomized
    bit sequences, recorded seed RANDOM_SEED."""
    rng = random.Random(RANDOM_SEED)
    for _ in range(ROUND_TRIP_SAMPLE_COUNT):
        n = rng.randrange(1, 200)
        bits = [rng.randrange(2) for _ in range(n)]
        start = rng.randrange(2)
        levels = nrzi.encode(bits, start_level=start)
        assert nrzi.decode(levels, start_level=start) == bits


def test_nrzi_all_ones_never_transitions():
    levels = nrzi.encode([1] * 10, start_level=1)
    assert levels == [1] * 10


def test_nrzi_all_zeros_transitions_every_bit():
    levels = nrzi.encode([0] * 6, start_level=1)
    assert levels == [0, 1, 0, 1, 0, 1]


# ---------------------------------------------------------------------------
# Layer 1: bit stuffing
# ---------------------------------------------------------------------------


def test_stuffing_round_trip_random():
    rng = random.Random(RANDOM_SEED)
    for _ in range(ROUND_TRIP_SAMPLE_COUNT):
        n = rng.randrange(1, 300)
        bits = [rng.randrange(2) for _ in range(n)]
        assert stuffing.destuff(stuffing.stuff(bits)) == bits


def test_stuffing_inserts_zero_after_six_ones_known_vector():
    vec = GOLDEN["bit_stuffing_six_ones"]
    stuffed = stuffing.stuff(vec["input_bits_lsb_first"])
    assert stuffed == vec["expected_stuffed_bits"]
    assert stuffing.destuff(stuffed) == vec["input_bits_lsb_first"]


def test_stuffing_does_not_stuff_runs_shorter_than_six():
    bits = [1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1]
    assert stuffing.stuff(bits) == bits  # no run reaches 6


def test_stuffing_stuff_bit_immediately_before_end_of_stream():
    """The exact edge case spec/architecture.md names by hand: a run of
    six 1s that reaches the very end of the protected field (i.e., right
    before EOP in a real packet) still gets a stuff bit -- the algorithm
    doesn't special-case "nothing follows"."""
    bits = [0, 1, 1, 1, 1, 1, 1]  # transition, then six 1s, then nothing
    stuffed = stuffing.stuff(bits)
    assert stuffed == [0, 1, 1, 1, 1, 1, 1, 0]
    assert stuffed[-1] == 0
    assert stuffing.destuff(stuffed) == bits


def test_stuffing_destuff_raises_on_violation():
    # Six 1s followed by a 1 instead of the mandatory stuffed 0.
    with pytest.raises(stuffing.StuffingError):
        stuffing.destuff([1, 1, 1, 1, 1, 1, 1])


# ---------------------------------------------------------------------------
# Layer 1: CRC5 / CRC16
# ---------------------------------------------------------------------------


def _ascii_bits(s):
    return [(b >> i) & 1 for b in s.encode("ascii") for i in range(8)]


def test_crc5_known_vector():
    vec = GOLDEN["crc5_usb_check"]
    assert crc.crc5(_ascii_bits(vec["input_ascii"])) == vec["expected_check"]


def test_crc16_known_vector():
    vec = GOLDEN["crc16_usb_check"]
    assert crc.crc16(_ascii_bits(vec["input_ascii"])) == vec["expected_check"]


def test_crc5_residue_invariant_random():
    vec = GOLDEN["crc5_usb_residue"]
    rng = random.Random(RANDOM_SEED)
    for _ in range(ROUND_TRIP_SAMPLE_COUNT):
        n = rng.randrange(1, 64)
        data_bits = [rng.randrange(2) for _ in range(n)]
        combined = data_bits + crc.crc5_bits(data_bits)
        assert crc.crc5_residue(combined) == vec["expected_residue"]


def test_crc16_residue_invariant_random():
    vec = GOLDEN["crc16_usb_residue"]
    rng = random.Random(RANDOM_SEED)
    for _ in range(ROUND_TRIP_SAMPLE_COUNT):
        n = rng.randrange(1, 600)
        data_bits = [rng.randrange(2) for _ in range(n)]
        combined = data_bits + crc.crc16_bits(data_bits)
        assert crc.crc16_residue(combined) == vec["expected_residue"]


def test_token_crc5_worked_example():
    vec = GOLDEN["token_crc5_worked_example"]
    addr_bits = [(vec["addr"] >> i) & 1 for i in range(7)]
    endp_bits = [(vec["endp"] >> i) & 1 for i in range(4)]
    field_bits = addr_bits + endp_bits
    assert field_bits == vec["field_bits_lsb_first"]
    assert crc.crc5(field_bits) == vec["expected_crc5"]


# ---------------------------------------------------------------------------
# Layer 1: PID
# ---------------------------------------------------------------------------


def test_pid_encode_decode_round_trip_all_defined_pids():
    for name in pid.PID:
        assert pid.decode(pid.encode(name)) == name
        assert pid.decode_bits(pid.encode_bits(name)) == name


def test_pid_complement_nibble_is_the_ones_complement():
    for name, nibble in pid.PID.items():
        byte = pid.encode(name)
        assert byte & 0xF == nibble
        assert (byte >> 4) & 0xF == (~nibble & 0xF)


def test_pid_decode_rejects_bad_complement_nibble():
    good = pid.encode("SETUP")
    corrupted = good ^ 0x10  # flip one bit of the complement nibble
    with pytest.raises(pid.PidError):
        pid.decode(corrupted)


# ---------------------------------------------------------------------------
# Layer 3: packets -- positive round trips (each named scenario from #10)
# ---------------------------------------------------------------------------


def test_max_length_bulk_payload_round_trips():
    scenario = scenarios.max_length_bulk_payload()
    assert len(scenario.payload) == scenarios.FS_MAX_PACKET_SIZE
    parsed = packets.parse(scenario.states)
    assert parsed == scenario.fields
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload


def test_stuff_before_eop_payload_round_trips_and_has_exact_expected_length():
    scenario = scenarios.stuff_before_eop_payload()
    vec = GOLDEN["stuff_before_eop_data_packet"]
    assert scenario.payload == bytes(vec["payload_bytes"])

    # SYNC(8) + stuffed-field(33, per the golden vector) + EOP(3) == 44.
    expected_len = 8 + vec["raw_bit_count_after_stuffing"] + 3
    assert len(scenario.states) == expected_len

    # The line-state immediately before EOP is the forced stuff bit's
    # NRZI symbol -- not asserting a specific J/K value here (that
    # depends on the preceding polarity), just that decode is exact.
    parsed = packets.parse(scenario.states)
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload


def test_find_stuff_before_eop_payload_matches_golden_constant():
    assert (
        scenarios.find_stuff_before_eop_payload() == scenarios.STUFF_BEFORE_EOP_PAYLOAD
    )


def test_all_ones_payload_round_trips():
    scenario = scenarios.all_ones_payload()
    parsed = packets.parse(scenario.states)
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload


def test_all_zeros_payload_round_trips():
    scenario = scenarios.all_zeros_payload()
    parsed = packets.parse(scenario.states)
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload


def test_corrupted_crc_token_base_case_round_trips():
    scenario = scenarios.corrupted_crc_token()
    parsed = packets.parse(scenario.states)
    assert parsed["pid"] == "SETUP"
    assert parsed["crc_ok"] is True
    assert parsed["addr"] == 0x3A
    assert parsed["endp"] == 0xA


def test_truncated_packet_base_case_round_trips():
    scenario = scenarios.truncated_packet()
    parsed = packets.parse(scenario.states)
    assert parsed["crc_ok"] is True
    assert parsed["payload"] == scenario.payload


# ---------------------------------------------------------------------------
# Layer 3: negative controls -- each fails when mutated, passes when not.
# "A suite that cannot fail is not evidence."
# ---------------------------------------------------------------------------


def test_negative_control_flip_crc_bit_on_max_length_bulk():
    scenario = scenarios.max_length_bulk_payload()
    mutated = scenarios.flip_crc_bit("DATA1", payload=scenario.payload)
    parsed = packets.parse(mutated)  # structurally valid, just wrong CRC
    assert parsed["crc_ok"] is False
    # ... and the un-mutated packet still passes (the "when it is not" half).
    assert packets.parse(scenario.states)["crc_ok"] is True


def test_negative_control_flip_crc_bit_on_stuff_before_eop():
    scenario = scenarios.stuff_before_eop_payload()
    mutated = scenarios.flip_crc_bit("DATA0", payload=scenario.payload)
    assert packets.parse(mutated)["crc_ok"] is False
    assert packets.parse(scenario.states)["crc_ok"] is True


def test_negative_control_flip_crc_bit_on_corrupted_crc_token():
    scenario = scenarios.corrupted_crc_token()
    mutated = scenarios.flip_crc_bit("SETUP", addr=0x3A, endp=0xA)
    assert packets.parse(mutated)["crc_ok"] is False
    assert packets.parse(scenario.states)["crc_ok"] is True


def test_negative_control_missing_stuff_bit_on_all_ones():
    """All-ones has multiple non-terminal stuff-bit insertions throughout
    the payload (not just at the very end), so skipping stuffing entirely
    corrupts bit alignment and is reliably caught -- either as a raised
    error or as a CRC/payload mismatch. See `missing_stuff_bit`'s
    docstring for why this pairing (not stuff_before_eop) is used."""
    scenario = scenarios.all_ones_payload()
    mutated = scenarios.missing_stuff_bit("DATA1", payload=scenario.payload)

    failed = False
    try:
        parsed = packets.parse(mutated)
    except (packets.PacketError, stuffing.StuffingError):
        failed = True
    else:
        failed = parsed["crc_ok"] is False or parsed.get("payload") != scenario.payload
    assert failed, "missing_stuff_bit mutation was not detected"

    # ... and the un-mutated packet still passes.
    assert packets.parse(scenario.states)["crc_ok"] is True


def test_negative_control_invert_nrzi_polarity_on_all_zeros():
    scenario = scenarios.all_zeros_payload()
    mutated = scenarios.invert_nrzi_polarity(scenario.states)
    assert mutated != scenario.states

    with pytest.raises(packets.PacketError):
        packets.parse(mutated)  # SYNC no longer decodes correctly

    assert packets.parse(scenario.states)["crc_ok"] is True


def test_negative_control_truncate_on_truncated_packet_scenario():
    scenario = scenarios.truncated_packet()
    mutated = scenarios.truncate(scenario.states)

    with pytest.raises(packets.PacketError):
        packets.parse(mutated)

    assert packets.parse(scenario.states)["crc_ok"] is True


# ---------------------------------------------------------------------------
# Non-ideality knobs: default to zero, bounded, and exercised non-zero.
# ---------------------------------------------------------------------------


def test_timing_knobs_default_to_zero_and_ideal():
    timing = TimingConfig()
    assert timing.is_ideal
    assert timing.nominal_bit_period_ns() == FS_BIT_PERIOD_NS
    assert timing.next_bit_period_ns() == FS_BIT_PERIOD_NS


def test_timing_knob_freq_offset_nonzero():
    timing = TimingConfig(freq_offset_ppm=2500.0)
    assert not timing.is_ideal
    expected = FS_BIT_PERIOD_NS * 1.0025
    assert timing.nominal_bit_period_ns() == pytest.approx(expected)


def test_timing_knob_freq_offset_rejects_out_of_tolerance():
    with pytest.raises(ValueError):
        TimingConfig(freq_offset_ppm=MAX_FREQ_OFFSET_PPM + 1)
    with pytest.raises(ValueError):
        TimingConfig(freq_offset_ppm=-(MAX_FREQ_OFFSET_PPM + 1))


def test_timing_knob_bit_jitter_nonzero_is_bounded_and_seeded():
    timing = TimingConfig(bit_jitter_ns=5.0, rng=random.Random(RANDOM_SEED))
    nominal = timing.nominal_bit_period_ns()
    samples = [timing.next_bit_period_ns() for _ in range(200)]
    assert not timing.is_ideal
    assert all(abs(sample - nominal) <= 5.0 + 1e-9 for sample in samples)
    assert len(set(samples)) > 1  # not degenerately constant

    # Deterministic given the same seed.
    replay = TimingConfig(bit_jitter_ns=5.0, rng=random.Random(RANDOM_SEED))
    replay_samples = [replay.next_bit_period_ns() for _ in range(200)]
    assert replay_samples == samples


def test_timing_knob_bit_jitter_rejects_negative():
    with pytest.raises(ValueError):
        TimingConfig(bit_jitter_ns=-1.0)
