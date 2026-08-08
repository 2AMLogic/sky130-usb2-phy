# Bit/edge synchronizer sampling-margin budget (issue #13)

**Status: measured, 2026-08-07**, against `rtl/usb_bit_sync.v` /
`rtl/usb_rx_path.v` through `verification/test_usb_rx.py`'s frequency-offset
suite (Icarus Verilog 13.0, cocotb 2.0.1, `klt functional-verification`).
This document is the written derivation issue #13 asks for: the sampling
window, the worst-case drift between guaranteed transitions, the resulting
margin, and how that margin compares to the PLL jitter figure in
`spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`
("decision record #9" below).

## 1. The design being budgeted

`rtl/usb_bit_sync.v` implements a **hard-resync, transition-tracking**
bit/edge synchronizer: a free-running mod-12 phase counter tracks position
within the current bit cell (`OVERSAMPLE_RATIO = 12`, matching 144 MHz / 12
Mbps); every clk_144 cycle in which a synchronized NRZI transition is
detected on `dp`, the counter is reset unconditionally to the reference
position (phase 0). Between transitions the counter free-runs at the local
144 MHz rate, and `bit_strobe`/`bit_level` sample the line at
`CENTER_PHASE = 6` — the exact centre of the recovered 12-cycle bit cell.

Two properties of this design matter for the margin derivation:

1. **Full half-cell margin by construction.** Sampling at the exact centre
   of the bit cell gives the maximum theoretically achievable margin before
   a sample lands in the *wrong* bit: the sample point can drift up to
   `CENTER_PHASE = 6` cycles in either direction (half of the 12-cycle bit
   period) before crossing an actual bit boundary. This is the total
   available budget, before subtracting anything: **6 oversampling cycles =
   6 x 6.944 ns = 41.67 ns** (half of the 83.33 ns FS bit period).
2. **No error accumulates across a resync.** Because every detected
   transition is a *hard* reset (not a filtered/tracking-loop correction),
   timing error does not compound across multiple bit periods — each
   transition discards all prior phase error and re-anchors to the
   just-observed edge (to within input-synchronizer latency, see §4). The
   quantity that must stay inside the 6-cycle margin is therefore the error
   accumulated **since the last transition**, not error accumulated over an
   entire packet.

## 2. The worst-case drift window: 7 bit times, fixed by bit stuffing

`rtl/usb_bit_destuffer.v` (mirroring `verification/usbfs/stuffing.py`)
implements USB 2.0's bit-stuffing rule: a 0 is inserted after every six
consecutive 1s. This guarantees **at least one NRZI transition every seven
bit times** (six consecutive 1-bits with no transition, followed by a
mandatory stuffed 0, which is a transition). Seven bit times at 12x
oversampling is:

```
7 bit times x 12 cycles/bit = 84 oversampling cycles (clk_144 cycles)
```

This — not one bit period (12 cycles) — is the longest interval the
bit/edge synchronizer must ever bridge with **zero** resync opportunity.
Any timing-margin analysis of this design must use this 84-cycle window,
not a 12-cycle one; §5 below explains why this matters when comparing
against decision record #9's stated metric.

## 3. Margin consumed by the required host/device frequency offset

The acceptance criteria for this issue require correct reception at up to
±0.25% (2500 ppm) offset on either endpoint alone, and ±0.5% (5000 ppm)
**combined**, host and device offset in opposite directions (USB 2.0 §7.1.11
FS reference-clock tolerance, `spec/usb2-phy.md` §4).

A relative frequency offset `f` accumulates a timing error of
`f x (elapsed time)` between the true bit boundary and where the local,
freely-running phase counter would place it, absent a resync. Over the
worst-case 84-cycle (7-bit-time) window from §2, expressed in oversampling
cycles:

```
error_cycles = f x 84 cycles
```

At the required ±0.5% (0.005) combined bound:

```
error_cycles = 0.005 x 84 = 0.42 cycles = 0.42 x 6.944 ns = 2.92 ns
```

Against the 6-cycle (41.67 ns) total budget from §1, the *required*
frequency-offset tolerance consumes only **0.42 / 6 ≈ 7% of the available
margin** — the design has substantial headroom over the spec-mandated
bound by this analytic estimate alone, before even running a simulation.

Solving the same equation for the offset that exactly exhausts the full
6-cycle budget gives the analytic (idealized, no synchronizer-latency or
quantization loss) failure point:

```
f_analytic = 6 cycles / 84 cycles = 0.0714 = 7.14%
```

## 4. Measured result: the cocotb offset sweep

`verification/test_usb_rx.py::test_offset_sweep_finds_first_failure` drives
combined host+device offset (opposite directions, `usbfs.scenarios.all_ones_payload`
— the maximum-transition-density-adjacent stuffing pattern, chosen so every
inter-transition gap in the driven stream sits near the 7-bit-time worst
case from §2) through an increasing step list and records the first offset
at which the received byte stream or `RxError` diverges from the reference
model.

**Measured result (2026-08-07 run, Icarus 13.0):**

| Combined offset | Result |
|---|---|
| 0.5% (5000 ppm) | pass (also confirmed by the dedicated acceptance-criterion tests: ±2500 ppm each endpoint alone, and ±0.5% combined in both directions) |
| 1.0% – 5.0% (10000–50000 ppm) | pass |
| 5.5% (55000 ppm) | pass |
| **6.0% (60000 ppm)** | **first failure** |

The measured failure point (somewhere in **(5.5%, 6.0%]**, bounded by the
sweep's 0.5%-step granularity — a finer sweep would narrow this further but
was not run, since the acceptance criterion only asks the sweep to *locate*
the first-failing offset, not resolve it to arbitrary precision) is **10x –
12x the required ±0.5% combined bound**, and reasonably close to but
somewhat tighter than the §3 analytic estimate (7.14%). The gap between the
7.14% analytic figure and the ~6% measured figure is attributable to
effects the §3 arithmetic does not model:

- The 2-flop input synchronizer in `rtl/usb_bit_sync.v` (block 1) adds up
  to 2 clk_144 cycles of latency between a real line transition and the
  hard-resync reacting to it — a fixed latency, not scaling with offset,
  but it eats directly into the same 6-cycle budget.
- `all_ones_payload`'s stuffing pattern places *every* inter-transition gap
  near the 7-bit-time maximum (rather than just one occurrence in a mixed
  packet), so the sweep exercises the worst case repeatedly across the
  packet, and any single occurrence failing fails the whole test — a
  stricter bar than a single-worst-case-gap analytic estimate.

Both effects reduce the achievable margin relative to the idealized
analytic figure, which is the expected direction (measurement should be
`<=` the ideal estimate, not `>`) and is exactly what was observed.

**Conclusion for the acceptance criteria:** the design passes at ±0.25% each
endpoint alone and at ±0.5% combined (both directions) with the
maximum-length (1023-byte) FS isochronous payload (`test_offset_host_plus_quarter_percent`,
`test_offset_host_minus_quarter_percent`, `test_offset_combined_half_percent_host_fast`,
`test_offset_combined_half_percent_host_slow` in `test_usb_rx.py`, all
passing), and the sweep identifies first failure at 6.0% combined offset —
comfortably outside the required envelope, with roughly an order of
magnitude of margin to spare.

## 5. Relationship to decision record #9's PLL jitter figure — a real gap, stated plainly

Decision record #9 ("0001-clocking-cdc-jitter-metric-and-pvt-envelope.md")
Decision 1 restates the PLL's jitter requirement as: **accumulated (12-UI)
peak-to-peak jitter < 5% of one FS bit period (< 4.17 ns), measured as the
maximum deviation of the 12th rising edge of the 144 MHz clock from its
ideal position, relative to a reference edge.** Its own derivation text
states the window explicitly: *"the quantity that must stay inside the
4.17 ns margin is therefore the 12-cycle (12-UI) accumulated jitter of the
144 MHz clock."*

**This does not match the window this specific bit/edge synchronizer design
actually needs**, and that mismatch should be stated plainly rather than
silently reconciled:

- Decision record #9's 12-UI metric implicitly assumes the relevant
  reference-edge-to-sample-edge span is **one bit period** (12 UI).
- This design's actual worst-case span between a resync opportunity and
  the sample point it must still land correctly for is **up to 84 UI**
  (7 bit times), per §2 above — because bit stuffing, not "once per bit,"
  is what fixes the transition-density guarantee this design relies on for
  resync.

A 12-UI accumulated-jitter figure does not, by itself, bound an 84-UI
window without an explicit accumulation model (how does jitter grow from a
12-UI observation to an 84-UI one?) — decision record #9 does not supply
one, and this record does not invent one either. What can be said,
honestly, is only a **conservative, unverified extrapolation**:

- If the PLL's 12-UI figure (4.17 ns) is assumed to scale **linearly** with
  window length (the pessimistic assumption for a jitter source with any
  systematic/deterministic component, and an overestimate for pure random
  jitter, which typically grows closer to sqrt(N) over N periods) — the
  worst-case 84-UI figure would be `4.17 ns x (84 / 12) = 29.17 ns`.
- Added to the §3 required frequency-offset allocation (2.92 ns) over the
  same 84-cycle window: `29.17 + 2.92 = 32.08 ns`, against the total 41.67 ns
  budget (§1) — **fits, with 9.58 ns (23%) headroom**, under this
  conservative linear-scaling assumption.

**This is not a verification of decision record #9's figure** — no real PLL
exists yet to characterize (per that record's own "sibling-canary ownership
status" section, no `sky130-pll` canary exists in the org), and a linear
jitter-accumulation assumption is exactly the kind of unstated-model gap
CLAUDE.md's "no claim without a testbench" rule warns about. What this
section *does* establish, honestly: decision record #9's 12-UI metric, as
literally written, does not bound the window this design's resync algorithm
actually depends on, and a conservative (not proven) extrapolation suggests
the two are compatible with real margin to spare, rather than in tension.
**A future decision record — once a real sky130 PLL canary exists to
characterize — should either (a) restate the jitter requirement directly
over an 84-UI (7-bit-time) window to match this design's actual dependency,
or (b) state an explicit accumulation model (e.g. a documented random-walk
assumption) sufficient to derive an 84-UI bound from a 12-UI measurement
rigorously.** Until then, treat the extrapolation in this section as a
plausibility argument, not a closed derivation.

## 6. Reproducing this

```bash
cd verification
klt functional-verification request-usb-rx.json --format json
```

`test_offset_sweep_finds_first_failure`'s log lines (`offset sweep:
combined=<ppm> ppm ok=<bool>` and the final `first failing combined offset =
<ppm> ppm`) are what §4's table above was read from
(`verification/.klt/functional-verification/test_icarus.log` after a run).
The step list in that test is intentionally coarser near the low end (fast
CI) and finer (0.5% steps) around the measured failure region documented
here; widen it locally for a tighter bound on the exact failure point if
that precision is ever needed.

## What this does and does not prove

This proves the **digital** bit/edge synchronizer's margin against an
*ideal*, jitter-free 144 MHz clock plus a modeled host/device frequency
offset (`usbfs.timing.TimingConfig` and direct `clk_144`/`clk_utmi` period
scaling in `test_usb_rx.py`) — it does not, and cannot, verify the real PLL
sibling canary's actual jitter performance, which does not exist yet. §5's
extrapolation is explicitly flagged as unverified for exactly that reason.
