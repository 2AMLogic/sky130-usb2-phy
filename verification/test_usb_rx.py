"""cocotb testbench for the FS receive datapath (issue #13):
`rtl/usb_bit_sync.v` .. `rtl/usb_rx_cdc.v`, wired together in
`rtl/usb_rx_path.v`. Drives `usbfs.transceiver.IdealTransceiver` /
`usbfs.scenarios` stimulus onto the DUT's `dp`/`dm` pads and checks the
UTMI-side output (`RxValid`/`DataIn`/`RxActive`/`RxError`/`LineState`),
including the frequency-offset sweep this issue exists to exercise --
"the frequency-offset tests are the point of this issue."

Like `test_usbfs_loopback.py`/`test_utmi_stub.py`, this file is *input* to
`klt functional-verification` (see `request-usb-rx.json`), not a pytest
module.

---------------------------------------------------------------------
Expected byte stream
---------------------------------------------------------------------
`DataIn` delivers PID + type-specific fields + CRC (SYNC is consumed by
SOP lock and never delivered; EOP is not part of the bit-stuffed stream
at all -- see `rtl/usb_rx_framer.v`'s header). The expected sequence is
`usbfs.scenarios.byte_stream_for_scenario(scenario)` -- the one shared,
independently verified reference the scenario builders themselves come
from, not a local re-derivation (issue #386). `RxMonitor` collects
`list[int]` (`monitors.py`) while the helper returns `bytes`, so every
comparison converts the monitor side: `bytes(mon.bytes) == ...`.

---------------------------------------------------------------------
Combined host+device frequency offset
---------------------------------------------------------------------
`usbfs.timing.TimingConfig.freq_offset_ppm` is capped at +/-2500 ppm per
instance (the USB FS reference-clock tolerance, USB 2.0 section 7.1.11) --
it cannot itself represent the +/-0.5% *combined* host+device acceptance
criterion. This suite models the two offset sources separately, per the
issue's Test Plan guidance: a host-side offset via `TimingConfig` (how
fast/slow the driven bit stream arrives) and a *device*-side offset by
directly scaling the DUT's own `clk_144`/`clk_utmi` periods (how fast/slow
this device's own local oscillator runs) -- physically what "the device's
local crystal is off by up to +/-0.25%" means. Driving both to the same
extreme in *opposite* directions reproduces the full +/-0.5% relative
separation the acceptance criterion asks for, without exceeding
`TimingConfig`'s own per-instance bound.

---------------------------------------------------------------------
"Maximum-length FS payload" -- which one, and why
---------------------------------------------------------------------
Per the issue's Test Plan: the dedicated offset-tolerance acceptance
criteria (+/-0.25%, +/-0.5% combined) use
`usbfs.scenarios.max_length_isochronous_payload()` (1023 bytes, the FS
isochronous max -- added to `scenarios.py` by this issue, shared with
#12), matching the decision record's own FIFO-depth derivation's
worst-case drift-accumulation window, rather than the 64-byte FS bulk max.
See `docs/bit-sync-budget.md` for why this repo's hard-resync-per-NRZI-
transition CDR design predicts *no* dependence on packet length in the
first place (each transition discards all prior phase error), and how the
measured sweep result relates to that prediction.

---------------------------------------------------------------------
LineState comparison methodology
---------------------------------------------------------------------
The 144->30 MHz CDC latency for `LineState` (2 flops in each of two
domains, `rtl/usb_rx_cdc.v`) is, worst-case, ~80 ns -- close to one full
83.33 ns FS bit period. A fixed-offset, per-bit-window absolute-timestamp
comparison against the driven stimulus is therefore too tight to be
robust. Instead, `LineStateMonitor` samples `LineState` continuously (once
per `clk_utmi` edge -- `LineState` only *updates* at that rate) and the
test compares the **de-duplicated, order-preserving sequence** of distinct
values observed against the de-duplicated sequence of driven states: this
is latency-agnostic (works for any bounded, sub-bit-period-ish latency)
while still checking every value transition the driven stimulus produced
shows up, in order, exactly once each -- "matches the reference model's
line state...at every sample point across a full packet" without
depending on nailing an exact absolute-time alignment.

---------------------------------------------------------------------
RxActive end-of-packet window (issue #441)
---------------------------------------------------------------------
The EOP-boundary test bounds RxActive's deassertion with references
*independent of the monitored trace*: the lower edge is the driven EOP's
SE0->J transition (the earliest event the receive path could possibly
react to -- `usb_bit_sync.v` anchors the EOP-terminating J's bit strobe
CENTER_PHASE=6 clk_144 cycles after that dp edge, and `usb_rx_framer.v`
drops `rx_active` only on that strobe), and the upper edge is the end of
the driven EOP's J bit plus `EOP_DEASSERT_LATENCY_MAX_NS`, a budget
assembled from the documented receive-path latencies (CDR strobe
placement, framer registration, 2-flop CDC into clk_utmi, one monitor
sampling period). The trace contributes only the *observation*: RxActive
must form exactly one contiguous interval whose observed fall lands
inside the window. Issue #441 replaced an earlier last-high-sample search
plus trailing-sum check that was circular -- the sum after the last high
sample is zero by construction, so it accepted any trace shape at all.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer
from cocotb.utils import get_sim_time

from monitors import Monitor, RxMonitor
from usbfs import scenarios
from usbfs.linestate import LineState, to_dpdm
from usbfs.packets import EOP_STATES
from usbfs.timing import FS_BIT_PERIOD_NS, MAX_FREQ_OFFSET_PPM, TimingConfig
from usbfs.transceiver import IdealTransceiver

CLK144_PERIOD_NS_NOMINAL = 1000.0 / 144.0  # 6.9444... ns (144 MHz)
CLK_UTMI_PERIOD_NS_NOMINAL = 1000.0 / 30.0  # 33.333... ns (30 MHz)

_clock_tasks = {}


async def set_clocks(dut, clk144_period_ns=CLK144_PERIOD_NS_NOMINAL,
                      clk_utmi_period_ns=CLK_UTMI_PERIOD_NS_NOMINAL):
    """(Re)start both clocks at the given periods, killing any
    previously-started clock task on the same signal. `klt
    functional-verification` runs every `@cocotb.test()` in this file
    sequentially inside one live simulation (no automatic per-test reset),
    so tests that need a different (offset) clock period restart it
    explicitly rather than relying on a single session-wide Clock."""
    for name, sig, period_ns in (
        ("144", dut.clk_144, clk144_period_ns),
        ("utmi", dut.clk_utmi, clk_utmi_period_ns),
    ):
        old = _clock_tasks.get(name)
        if old is not None:
            old.cancel()
        # 144/30 MHz do not divide 1 ns evenly (6.9444.../33.333... ns
        # repeating), so no exact `Fraction`-at-1ps-precision period
        # exists -- round to the nearest integer picosecond (matching
        # usbfs.transceiver._ns_to_timer's convention) and give an
        # explicit `period_high` half-period so an odd total picosecond
        # count doesn't also trip cocotb's "must be evenly divisible by 2"
        # check for an *implicit* 50% duty cycle split.
        period_ps = round(period_ns * 1000)
        _clock_tasks[name] = cocotb.start_soon(
            Clock(sig, period_ps, unit="ps", period_high=period_ps // 2).start()
        )
    await Timer(1, unit="ns")


async def reset_dut(dut):
    dut.Reset.value = 1
    dut.dp.value = 1  # idle J
    dut.dm.value = 0
    await ClockCycles(dut.clk_144, 8)
    dut.Reset.value = 0
    # Both per-domain reset synchronizers (rtl/usb_rx_cdc.v) need to
    # deassert before the FIFO/pointers come out of reset.
    await ClockCycles(dut.clk_utmi, 8)


async def start_test(dut, clk144_period_ns=CLK144_PERIOD_NS_NOMINAL,
                      clk_utmi_period_ns=CLK_UTMI_PERIOD_NS_NOMINAL):
    await set_clocks(dut, clk144_period_ns, clk_utmi_period_ns)
    await reset_dut(dut)


def _encode_state(state):
    """LineState -> the 2-bit value rtl/usb_linestate.v reports
    ({dm_sync, dp_sync}, per Decision 4's port table)."""
    dp, dm = to_dpdm(state)
    return (dm << 1) | dp


def _dedupe(seq):
    out = []
    for v in seq:
        if not out or out[-1] != v:
            out.append(v)
    return out


def _is_subsequence(needle, haystack):
    it = iter(haystack)
    return all(x in it for x in needle)


class LineStateMonitor(Monitor):
    def __init__(self, dut):
        super().__init__(dut)
        self.trace = []

    async def _run(self):
        while True:
            await RisingEdge(self.dut.clk_utmi)
            await ReadOnly()
            self.trace.append(int(self.dut.LineState.value))


async def _drive_and_receive(dut, states, timing=None, idle_bit_times=4,
                              settle_utmi_cycles=40, extra_monitors=()):
    tx = IdealTransceiver(dut.dp, dut.dm, timing=timing)
    mon = RxMonitor(dut)
    mon.start()
    for m in extra_monitors:
        m.start()

    await tx.drive_idle(idle_bit_times)
    await tx.drive_states(states)
    await tx.drive_idle(idle_bit_times)
    await ClockCycles(dut.clk_utmi, settle_utmi_cycles)

    mon.stop()
    for m in extra_monitors:
        m.stop()
    return mon


# ---------------------------------------------------------------------------
# Zero-offset, bit-exact reception -- every usbfs.scenarios scenario.
# ---------------------------------------------------------------------------

_ZERO_OFFSET_SCENARIOS = {
    "max_length_bulk_payload": scenarios.max_length_bulk_payload,
    "max_length_isochronous_payload": scenarios.max_length_isochronous_payload,
    "stuff_before_eop_payload": scenarios.stuff_before_eop_payload,
    "all_ones_payload": scenarios.all_ones_payload,
    "all_zeros_payload": scenarios.all_zeros_payload,
    "corrupted_crc_token": scenarios.corrupted_crc_token,  # correct base case
    "truncated_packet": scenarios.truncated_packet,  # correct base case
}


def _make_zero_offset_test(name, builder):
    async def _test(dut):
        await start_test(dut)
        scenario = builder()
        mon = await _drive_and_receive(dut, scenario.states)
        assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario), (
            f"{name}: byte mismatch, got {mon.bytes!r}"
        )
        assert not mon.saw_error, f"{name}: unexpected RxError at zero offset"

    _test.__name__ = f"test_zero_offset_{name}"
    _test.__qualname__ = _test.__name__
    _test.__doc__ = f"Bit-exact zero-offset reception: usbfs.scenarios.{name}()."
    return _test


for _name, _builder in _ZERO_OFFSET_SCENARIOS.items():
    globals()[f"test_zero_offset_{_name}"] = cocotb.test()(
        _make_zero_offset_test(_name, _builder)
    )


# ---------------------------------------------------------------------------
# Frequency-offset acceptance criteria -- the point of this issue.
# ---------------------------------------------------------------------------


async def _device_clock_periods(offset_ppm):
    scale = 1.0 + offset_ppm / 1_000_000.0
    return CLK144_PERIOD_NS_NOMINAL * scale, CLK_UTMI_PERIOD_NS_NOMINAL * scale


async def _run_offset_case(dut, host_offset_ppm, device_offset_ppm, scenario=None,
                            allow_out_of_spec=False):
    clk144_ns, clk_utmi_ns = await _device_clock_periods(device_offset_ppm)
    await start_test(dut, clk144_ns, clk_utmi_ns)
    if scenario is None:
        scenario = scenarios.max_length_isochronous_payload()
    timing = TimingConfig(freq_offset_ppm=host_offset_ppm,
                           allow_out_of_spec=allow_out_of_spec)
    mon = await _drive_and_receive(dut, scenario.states, timing=timing,
                                    settle_utmi_cycles=60)
    return scenario, mon


@cocotb.test()
async def test_offset_host_plus_quarter_percent(dut):
    """USB FS reference-clock tolerance, host side alone: +2500 ppm
    (+0.25%), device nominal."""
    scenario, mon = await _run_offset_case(dut, host_offset_ppm=2500.0,
                                            device_offset_ppm=0.0)
    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)
    assert not mon.saw_error


@cocotb.test()
async def test_offset_host_minus_quarter_percent(dut):
    scenario, mon = await _run_offset_case(dut, host_offset_ppm=-2500.0,
                                            device_offset_ppm=0.0)
    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)
    assert not mon.saw_error


@cocotb.test()
async def test_offset_combined_half_percent_host_fast(dut):
    """Both endpoints of the +/-0.25% tolerance simultaneously, host and
    device offset in opposite directions: host slow (+2500 ppm bit
    period) + device fast (-2500 ppm clk period) = ~0.5% combined
    relative separation."""
    scenario, mon = await _run_offset_case(
        dut, host_offset_ppm=MAX_FREQ_OFFSET_PPM, device_offset_ppm=-MAX_FREQ_OFFSET_PPM
    )
    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)
    assert not mon.saw_error


@cocotb.test()
async def test_offset_combined_half_percent_host_slow(dut):
    """The opposite pairing: host fast, device slow."""
    scenario, mon = await _run_offset_case(
        dut, host_offset_ppm=-MAX_FREQ_OFFSET_PPM, device_offset_ppm=MAX_FREQ_OFFSET_PPM
    )
    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)
    assert not mon.saw_error


@cocotb.test()
async def test_offset_sweep_finds_first_failure(dut):
    """Sweep the *combined* host+device relative offset beyond the
    required +/-0.5% bound, in coarse steps, to locate (and log) the first
    combined offset at which reception fails. Uses `all_ones_payload` (not
    the 1023-byte scenario) purely to keep this exploratory sweep's total
    simulated cycle count small -- see this file's module docstring for
    why packet length is not expected to matter to this design's failure
    point. Asserts only that the suite's own required bound (+/-0.5%
    combined, checked above) is not the sweep's own stopping point --
    the *measured* failure offset is recorded in docs/bit-sync-budget.md,
    not re-derived from this test on every run.
    """
    combined_ppm_steps = [5000.0, 10000.0, 20000.0, 30000.0, 40000.0, 50000.0,
                          55000.0, 60000.0, 65000.0]
    first_failure = None
    for combined_ppm in combined_ppm_steps:
        half = combined_ppm / 2.0
        scenario, mon = await _run_offset_case(
            dut, host_offset_ppm=half, device_offset_ppm=-half,
            scenario=scenarios.all_ones_payload(),
            # Steps beyond 5000 ppm combined exceed the +/-2500 ppm
            # per-instance USB FS physical tolerance (timing.MAX_FREQ_OFFSET_PPM)
            # by design -- this sweep exists to find the design's actual
            # failure point, which is expected to lie beyond the spec-required
            # bound, not to claim a real device could run this far out of spec.
            allow_out_of_spec=True,
        )
        ok = (bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)) and not mon.saw_error
        dut._log.info(f"offset sweep: combined={combined_ppm} ppm ok={ok}")
        if not ok and first_failure is None:
            first_failure = combined_ppm
            break
    dut._log.info(f"offset sweep: first failing combined offset = {first_failure} ppm")
    assert first_failure is None or first_failure > 5000.0, (
        "design fails at or before the required +/-0.5% combined bound"
    )


# ---------------------------------------------------------------------------
# SOP lock from every one of the 12 oversampling phases.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_sop_lock_all_oversample_phases(dut):
    period_ps = round(CLK144_PERIOD_NS_NOMINAL * 1000)
    for phase_idx in range(12):
        await start_test(dut)
        offset_ps = round(phase_idx * period_ps / 12)
        scenario = scenarios.stuff_before_eop_payload()

        tx = IdealTransceiver(dut.dp, dut.dm)
        mon = RxMonitor(dut)
        mon.start()
        await tx.drive_idle(2)
        if offset_ps > 0:
            # cocotb's Timer rejects a zero duration (phase_idx == 0 needs
            # no extra phase shift at all -- skip the call rather than
            # asking for Timer(0, ...)).
            await Timer(offset_ps, unit="ps")
        await tx.drive_states(scenario.states)
        await tx.drive_idle(2)
        await ClockCycles(dut.clk_utmi, 30)
        mon.stop()

        assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario), (
            f"phase {phase_idx}/12: byte mismatch"
        )
        assert not mon.saw_error, f"phase {phase_idx}/12: unexpected RxError"


# ---------------------------------------------------------------------------
# Bit-stuff violation -> RxError, no silent corruption.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_bit_stuff_violation_asserts_rxerror(dut):
    await start_test(dut)
    scenario = scenarios.all_ones_payload()
    mutated_states = scenarios.missing_stuff_bit("DATA1", payload=scenario.payload)

    mon = await _drive_and_receive(dut, mutated_states)

    assert mon.saw_error, "RxError was never asserted on a bit-stuff violation"
    assert bytes(mon.bytes) != scenarios.byte_stream_for_scenario(scenario), (
        "corrupted stream must not silently reproduce the clean byte sequence"
    )


@cocotb.test()
async def test_no_bit_stuff_violation_on_clean_all_ones(dut):
    """Negative-control pairing: the *correctly* stuffed all-ones payload
    must not spuriously assert RxError."""
    await start_test(dut)
    scenario = scenarios.all_ones_payload()
    mon = await _drive_and_receive(dut, scenario.states)
    assert not mon.saw_error
    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)


# ---------------------------------------------------------------------------
# EOP detection / RxActive deassertion at the correct boundary.
# ---------------------------------------------------------------------------

# Upper bound on how long after the driven EOP's terminating J bit ends the
# UTMI-side RxActive may take to fall, assembled from the receive path's
# documented latencies (worst-case terms, each independently derivable from
# the RTL this suite drives):
#   - one FS bit period: `usb_bit_sync.v`'s CDR places the J cell's bit
#     strobe within the J bit cell (CENTER_PHASE cycles after the SE0->J
#     transition re-anchors the phase counter);
#   - 3 clk_144 cycles: `usb_rx_framer.v` registers `eop_detected` off the
#     strobe and drops `rx_active` on the following edge, plus margin for
#     the input synchronizer's own registration;
#   - 3 clk_utmi cycles: `usb_rx_cdc.v`'s 2-flop level synchronizer (the
#     fall can land just after an edge, so two flops cost up to just under
#     three periods);
#   - 1 clk_utmi cycle: `RxMonitor` samples once per clk_utmi edge, so the
#     fall is observed up to one period after it happens.
EOP_DEASSERT_LATENCY_MAX_NS = (
    FS_BIT_PERIOD_NS
    + 3 * CLK144_PERIOD_NS_NOMINAL
    + 3 * CLK_UTMI_PERIOD_NS_NOMINAL
    + CLK_UTMI_PERIOD_NS_NOMINAL
)


def _assert_rxactive_eop_window(active_trace, sample_times_ns,
                                window_lo_ns, window_hi_ns):
    """Assert that RxActive framed exactly one packet and fell inside the
    given deassertion window. Everything here is checked against the
    caller-supplied window (derived from the driven stimulus and the
    receive path's latency budget, never from the trace itself), so the
    assertion can actually fail on a mis-timed drop -- unlike the
    last-high-search + trailing-sum check it replaces (issue #441), whose
    trailing sum was zero by construction.
    """
    assert active_trace, "RxActive trace is empty"
    assert len(sample_times_ns) == len(active_trace)
    assert not active_trace[-1], "RxActive never returned low (EOP not recognized)"
    high_idx = [i for i, v in enumerate(active_trace) if v]
    assert high_idx, "RxActive never asserted (SOP not recognized)"
    first, last = high_idx[0], high_idx[-1]
    assert last - first + 1 == len(high_idx), (
        f"RxActive asserted in {last - first + 1 - len(high_idx) + 1} disjoint "
        f"intervals (dropped and re-asserted), expected exactly one"
    )
    # The fall event itself lies in (t_last_high, t_first_low]: bounding the
    # first low sample bounds the fall.
    t_fall = sample_times_ns[last + 1]
    assert t_fall >= window_lo_ns, (
        f"RxActive fell at t={t_fall:.1f} ns, before the EOP window opened "
        f"at t={window_lo_ns:.1f} ns (the SE0->J transition) -- an early or "
        f"mid-packet drop"
    )
    assert t_fall <= window_hi_ns, (
        f"RxActive fell at t={t_fall:.1f} ns, after the EOP window closed "
        f"at t={window_hi_ns:.1f} ns (EOP end + receive-path latency budget)"
    )


async def _drive_packet_with_eop_timestamps(dut, scenario, idle_bit_times=4,
                                            settle_utmi_cycles=30):
    """Drive one packet split at its own EOP boundaries (per
    `usbfs.packets.EOP_STATES`, which `scenarios`' parse() already
    guarantees terminates every scenario) and return the monitor plus the
    driven-stimulus timestamps the EOP window is measured from: the start
    of the stuffed body, the start of EOP's SE0 pair, the SE0->J
    transition, and the end of EOP's terminating J bit. Measuring the
    boundaries from the drive sequence itself -- rather than re-deriving
    them from bit arithmetic -- keeps the window independent of both the
    monitor trace and the timing model's internals."""
    assert tuple(scenario.states[-3:]) == EOP_STATES, (
        f"scenario {scenario.name} does not terminate in a well-formed EOP"
    )
    tx = IdealTransceiver(dut.dp, dut.dm)
    mon = RxMonitor(dut)
    mon.start()

    await tx.drive_idle(idle_bit_times)
    t_body_start = get_sim_time(units="ns")
    await tx.drive_states(scenario.states[:-3])  # SYNC + stuffed body
    t_se0_start = get_sim_time(units="ns")
    await tx.drive_states(scenario.states[-3:-1])  # EOP's two SE0 bit times
    t_se0_to_j = get_sim_time(units="ns")
    await tx.drive_states(scenario.states[-1:])  # EOP's terminating J bit
    t_eop_end = get_sim_time(units="ns")
    await tx.drive_idle(idle_bit_times)
    await ClockCycles(dut.clk_utmi, settle_utmi_cycles)

    mon.stop()
    return mon, (t_body_start, t_se0_start, t_se0_to_j, t_eop_end)


@cocotb.test()
async def test_eop_deasserts_rxactive_at_correct_boundary(dut):
    """RxActive asserts exactly once per packet and falls inside the window
    bounded by the driven EOP (its SE0->J transition on the early side,
    its end plus the receive path's synchronization-latency budget on the
    late side) -- the byte comparison alone cannot see a dropped or stuck
    RxActive."""
    await start_test(dut)
    scenario = scenarios.stuff_before_eop_payload()
    mon, (_t_body_start, _t_se0_start, t_se0_to_j, t_eop_end) = (
        await _drive_packet_with_eop_timestamps(dut, scenario)
    )

    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)
    _assert_rxactive_eop_window(
        mon.active_trace, mon.sample_times_ns,
        window_lo_ns=t_se0_to_j,
        window_hi_ns=t_eop_end + EOP_DEASSERT_LATENCY_MAX_NS,
    )


@cocotb.test()
async def test_eop_window_check_rejects_dropped_rxactive(dut):
    """Negative controls for `test_eop_deasserts_rxactive_at_correct_boundary`
    (issue #441): a mid-packet RxActive drop and an early final drop must
    both FAIL the window check even though the received bytes are correct
    -- the circular trailing-sum check this replaces accepted both. The
    synthetic drop traces are the real clean run's trace (whose byte
    stream is asserted correct here) truncated at the drop point, so only
    *where RxActive falls* differs from the passing run above."""
    await start_test(dut)
    scenario = scenarios.stuff_before_eop_payload()
    mon, (t_body_start, t_se0_start, t_se0_to_j, t_eop_end) = (
        await _drive_packet_with_eop_timestamps(dut, scenario)
    )

    # The clean run's bytes are correct -- the negative controls below
    # mis-time RxActive only, which is exactly the failure mode the byte
    # comparison cannot catch.
    assert bytes(mon.bytes) == scenarios.byte_stream_for_scenario(scenario)
    window_lo, window_hi = t_se0_to_j, t_eop_end + EOP_DEASSERT_LATENCY_MAX_NS

    def dropped_trace(t_drop_ns):
        """The clean trace with RxActive forced low from the first sample
        at/after `t_drop_ns` (the clean trace is a single contiguous
        interval, so the truncation yields a shorter single interval)."""
        drop_idx = next(i for i, t in enumerate(mon.sample_times_ns)
                        if t >= t_drop_ns)
        return (mon.active_trace[:drop_idx]
                + [False] * (len(mon.active_trace) - drop_idx))

    def must_fail(trace, why):
        try:
            _assert_rxactive_eop_window(trace, mon.sample_times_ns,
                                        window_lo, window_hi)
        except AssertionError:
            return
        raise AssertionError(f"EOP window check accepted {why}")

    # Mid-packet drop: halfway through the stuffed body, long before any
    # EOP signaling exists on the bus.
    must_fail(dropped_trace((t_body_start + t_se0_start) / 2.0),
              "a mid-packet RxActive drop")
    # Early final drop: right as EOP's SE0 begins -- after the last byte
    # has been deserialized, but two bit times before the window opens.
    must_fail(dropped_trace(t_se0_start), "an early final RxActive drop")
    # And the honest trace itself must pass the same check (pairing the
    # controls with the positive case they are mutations of).
    _assert_rxactive_eop_window(mon.active_trace, mon.sample_times_ns,
                                window_lo, window_hi)


# ---------------------------------------------------------------------------
# LineState matches the reference model's driven sequence.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_linestate_matches_driven_sequence(dut):
    await start_test(dut)
    scenario = scenarios.stuff_before_eop_payload()
    lsmon = LineStateMonitor(dut)

    await _drive_and_receive(dut, scenario.states, idle_bit_times=4,
                              settle_utmi_cycles=20, extra_monitors=(lsmon,))

    driven = [LineState.J] * 4 + list(scenario.states) + [LineState.J] * 4
    expected_seq = _dedupe(_encode_state(s) for s in driven)
    observed_seq = _dedupe(lsmon.trace)
    assert _is_subsequence(expected_seq, observed_seq), (
        f"LineState sequence mismatch:\nexpected order {expected_seq}\n"
        f"observed {observed_seq}"
    )


# ---------------------------------------------------------------------------
# Bus reset (sustained SE0) / suspend (sustained idle J) detection.
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_bus_reset_detected_on_sustained_se0(dut):
    from usbfs.timing import RESET_DETECT_MIN_NS

    await start_test(dut)
    assert dut.BusReset.value == 0

    dut.dp.value = 0
    dut.dm.value = 0
    await Timer(RESET_DETECT_MIN_NS * 0.5, unit="ns")
    assert dut.BusReset.value == 0, "reset asserted before the detection threshold"

    await Timer(RESET_DETECT_MIN_NS * 0.75, unit="ns")
    assert dut.BusReset.value == 1, "reset not asserted after the detection threshold"

    dut.dp.value = 1
    dut.dm.value = 0
    # `BusReset` is the UTMI-domain (clk_utmi, 30 MHz) port, crossed from
    # the 144 MHz-domain detector by a 2-flop synchronizer
    # (rtl/usb_rx_cdc.v) -- waiting in clk_144 cycles here would be far
    # too short to see that crossing complete (30 MHz is ~4.8x slower).
    # Wait clk_utmi cycles instead, well beyond the input-sync + detector
    # + CDC latency chain.
    await ClockCycles(dut.clk_utmi, 6)
    assert dut.BusReset.value == 0, "reset did not clear once SE0 ended"


@cocotb.test()
async def test_suspend_detected_on_sustained_idle_j(dut):
    from usbfs.timing import SUSPEND_DETECT_MIN_NS

    await start_test(dut)
    assert dut.Suspend.value == 0

    dut.dp.value = 1
    dut.dm.value = 0
    await Timer(SUSPEND_DETECT_MIN_NS * 1.02, unit="ns")
    assert dut.Suspend.value == 1, "suspend not asserted after the detection threshold"
