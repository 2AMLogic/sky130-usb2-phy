"""Bit-timing model for the DP/DM bus-functional model: the nominal FS bit
period plus the two adjustable non-ideality knobs (reference-frequency
offset, per-bit timing jitter).

Deliberately pure functions/state -- no cocotb dependency -- so the knob
arithmetic itself is testable without a simulator (`test_usbfs_model.py`).
`usbfs.transceiver.IdealTransceiver` (the cocotb BFM, Layer 2) uses
`TimingConfig` for its actual per-bit `Timer` durations.

Both knobs default to zero, matching spec/usb2-phy.md section 7's "ideal
transceiver" baseline -- non-ideality is opt-in, never the default.
"""

import random

FS_BIT_RATE_HZ = 12_000_000
FS_BIT_PERIOD_NS = 1_000_000_000 / FS_BIT_RATE_HZ  # 83.33... ns

# USB 2.0 Spec Rev 2.0 section 7.1.11: FS reference-clock (and hence bit
# rate) tolerance is +/-0.25% (2500 ppm), unsynchronized to host SOF.
MAX_FREQ_OFFSET_PPM = 2500.0

# USB 2.0 Spec Rev 2.0 sections 7.1.7.3 / 7.1.7.6: device-side detection
# thresholds this behavioral model can drive *toward* for reset/suspend
# sequencing -- not asserted by this module; recognizing them is the
# RX-path RTL's job (a later issue), not this reference model's.
RESET_DETECT_MIN_NS = 2_500  # 2.5 us continuous SE0
SUSPEND_DETECT_MIN_NS = 3_000_000  # 3 ms continuous idle (J)


class TimingConfig:
    """Non-ideality knobs for `IdealTransceiver`.

    `freq_offset_ppm`: a fixed offset applied to every bit period,
    bounded to the USB FS reference-clock tolerance (+/-2500 ppm).

    `bit_jitter_ns`: a *bound* (not a fixed value) -- each bit period is
    perturbed by a uniformly-distributed random offset in
    `[-bit_jitter_ns, +bit_jitter_ns]`, drawn from `rng`. Deterministic
    and reproducible given `rng`'s seed.
    """

    def __init__(self, freq_offset_ppm=0.0, bit_jitter_ns=0.0, rng=None,
                 allow_out_of_spec=False):
        """`allow_out_of_spec`: bypasses the +/-2500 ppm physical-tolerance
        check below. Exists solely for margin-exploration sweeps (e.g.
        issue #13's `test_offset_sweep_finds_first_failure`) that
        deliberately drive a receive path *beyond* any real USB FS device's
        possible clock offset to locate the design's actual failure point --
        never set this to claim a device could really run this far out of
        tolerance; that claim is exactly what the default (False) check
        exists to prevent."""
        if not allow_out_of_spec and abs(freq_offset_ppm) > MAX_FREQ_OFFSET_PPM:
            raise ValueError(
                f"freq_offset_ppm={freq_offset_ppm} exceeds the USB FS reference-clock "
                f"tolerance of +/-{MAX_FREQ_OFFSET_PPM} ppm (USB 2.0 section 7.1.11)"
            )
        if bit_jitter_ns < 0:
            raise ValueError(
                "bit_jitter_ns must be >= 0 -- it's a +/- bound, not a signed offset"
            )
        self.freq_offset_ppm = freq_offset_ppm
        self.bit_jitter_ns = bit_jitter_ns
        self.rng = rng if rng is not None else random.Random(0)

    @property
    def is_ideal(self):
        return self.freq_offset_ppm == 0.0 and self.bit_jitter_ns == 0.0

    def nominal_bit_period_ns(self):
        """The bit period implied by `freq_offset_ppm` alone (no jitter
        draw -- deterministic, doesn't touch `rng`)."""
        return FS_BIT_PERIOD_NS * (1.0 + self.freq_offset_ppm / 1_000_000.0)

    def next_bit_period_ns(self):
        """One bit period, including this call's jitter draw (a no-op,
        and `rng`-transparent, when `bit_jitter_ns == 0`)."""
        period = self.nominal_bit_period_ns()
        if self.bit_jitter_ns:
            period += self.rng.uniform(-self.bit_jitter_ns, self.bit_jitter_ns)
        return period
