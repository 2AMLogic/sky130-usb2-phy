# 0001: Clocking, CDC discipline, jitter metric, and PVT envelope

- **Status**: Proposed
- **Date**: 2026-08-07
- **Decided by**: Builder agent, issue #9
- **Related**: #1 (target spec ratification), #2 (architecture/partitioning),
  #11 (physical-flow bootstrap — consumes the corner matrix in §5 below),
  #12 (TX-path RTL — consumes §4's port table), #13 (RX-path RTL — consumes
  §3's CDC discipline and §4's port table)

## Context

`spec/usb2-phy.md` (ratified 2026-08-05, issue #1) and `spec/architecture.md`
(issue #2) are the authoritative, ratified spec for this repo. Per
CLAUDE.md, "Spec changes go through `spec/` with a decision record; agents
do not relax the ratified spec to make results pass" — so this record does
**not** edit either ratified document. It closes five holes reported in
issue #9 that make parts of the ratified scope unimplementable or
unverifiable as written:

1. §4/§6's PLL jitter budget is stated as a **cycle-to-cycle** bound, which
   is dimensionally the wrong metric for the sampling-margin argument §4
   uses to derive it, and is numerically vacuous as stated.
2. §3 ratifies a 30 MHz UTMI interface clock with no stated source, and it
   does not divide cleanly from the 144 MHz oversampling clock §4 also
   ratifies (144 / 30 = 4.8).
3. Nothing in the ratified spec defines clock-domain-crossing (CDC)
   discipline between the 144 MHz recovery domain and the 30 MHz UTMI
   domain — no per-signal domain ownership, no synchronizer depth, no reset
   scheme.
4. §3 ratifies "UTMI (not UTMI+)" and a signal list, but §9 References cites
   no normative UTMI document, and 8-bit-at-30-MHz is not one of UTMI's own
   two defined operating points (8-bit/60 MHz, 16-bit/30 MHz).
5. §5 gives 1.8 V core / 3.3 V I/O as bare nominals with no tolerance and no
   temperature range, so no PVT corner matrix can be defined for T1-tier
   sim-validated evidence (`klayout-tools/docs/design-evidence-tiers.md`
   item 5).

Every RTL issue in this batch (#12 TX-path, #13 RX-path) and the digital
timing-signoff leg of the T1 evidence ladder are blocked on these being
answered here rather than invented independently by two parallel builders.

Every number introduced below is a **design target**, not a verified
result — per CLAUDE.md, "Verification is the product: no claim without a
testbench." None of it has been run through cocotb, STA, or a PVT-corner
simulation yet; that is exactly what #11's flow bootstrap and #12/#13's
testbenches exist to do next.

---

## Decision 1 — Restate the PLL jitter requirement in a metric that binds

### The problem, quantified

`spec/usb2-phy.md` §4/§6 and `spec/architecture.md`'s interface-requirements
table levy: *"Cycle-to-cycle jitter < 5% of one FS bit period, i.e. < 4.17 ns
at 144 MHz."* The arithmetic (0.05 x 83.33 ns = 4.17 ns) is correct; the
**metric** is wrong for what §4's own derivation argues about.

- One 144 MHz period is 1 / 144 MHz = **6.944 ns**. A *cycle-to-cycle*
  (adjacent-period) bound of 4.17 ns permits any two consecutive periods to
  differ by up to 4.17 ns, i.e. an instantaneous period anywhere in
  **6.944 ns ± 4.17 ns = [2.78 ns, 11.11 ns]**, i.e. an instantaneous
  frequency wandering over **1/11.11 ns to 1/2.78 ns = [90 MHz, 360 MHz]**.
  No PLL that could plausibly be built would violate this — the requirement
  is non-binding.
- §4's own derivation text says the number is meant to bound "the bit/edge
  synchronization logic['s]...sampling margin" — and sampling margin over a
  bit period is set by **accumulated timing error across the ~12
  oversampling cycles that span one bit**, not by the edge-to-edge
  difference of two *adjacent* cycles. Cycle-to-cycle jitter is exactly the
  one common jitter metric that does not bound that quantity.

### Options considered

**(a) Keep cycle-to-cycle (period) jitter, < 4.17 ns.** This is the current
spec text. Rejected: shown above to be non-binding (permits ±36% frequency
excursion between adjacent cycles) and mismatched to the sampling-margin
argument that motivates it.

**(b) RMS long-term jitter at a stated offset (phase-noise-style figure).**
Common in PLL/clock datasheets, and appropriate when a spectral
characterization (phase-noise plot from a SPICE-level PLL sim) is
available. Rejected for this record: (1) this repo's digital half has no
mechanism to *verify* an RMS/spectral figure — cocotb and STA both operate
on discrete-time / worst-case-timing models, not power-spectral-density
integrals; (2) RMS is a statistical figure, and the bit/edge synchronization
logic's actual failure mode is a **single-shot** timing margin at each
sampling instant, which an RMS number does not directly bound without an
additional (and here, unstated) crest-factor / peak-to-peak conversion
assumption. Better suited to the PLL sibling canary's own internal
verification than to the interface contract this repo hands it.

**(c) Total accumulated peak-to-peak timing error over the window that
spans one bit period (12 UI of the 144 MHz clock), i.e. period jitter
accumulated across 12 cycles.** This directly matches what the bit/edge
synchronization logic needs: it samples the incoming NRZI stream against
the 12th oversampling edge after the one it used to align to the previous
bit boundary, so the quantity that must stay inside margin is *the position
of that 12th edge relative to its ideal position*, not the spacing between
any two adjacent edges.

### Decision

**Adopt option (c).** The PLL output jitter requirement is restated as:

> **Accumulated (12-UI) peak-to-peak jitter < 5% of one FS bit period, i.e.
> < 4.17 ns, measured as the maximum deviation of the position of the
> 12th rising edge of the 144 MHz oversampling clock from its ideal
> position (12 x 6.944 ns = 83.33 ns after a reference edge), minimized
> over the choice of reference edge, over the PLL's full jitter
> characterization interval.**

Derivation, restated with the corrected metric:

- FS bit period = 1 / 12 Mbps = 83.33 ns (unchanged from §2/§4).
- Sampling-margin target = 5% of one bit period = 4.17 ns peak-to-peak
  (unchanged numeric budget — only the metric it is applied to changes).
- 144 MHz oversampling clock period = 1 / 144 MHz = 6.944 ns; 12x
  oversampling means exactly 12 oversampling-clock cycles span one FS bit
  (144 MHz / 12 Mbps = 12, confirmed integer — this is the number that
  *does* divide cleanly, unlike the 30 MHz UTMI clock in Decision 2 below).
- The quantity that must stay inside the 4.17 ns margin is therefore the
  **12-cycle (12-UI) accumulated jitter** of the 144 MHz clock: how far the
  edge nominally 12 periods later can land from 12 x 6.944 ns = 83.33 ns
  after the reference edge, worst-case over the PLL's operation.

**No separate cycle-to-cycle (adjacent-period) figure is levied.** A PLL
that meets the 12-UI accumulated bound will, by construction, show
adjacent-period jitter that is a small fraction of the accumulated figure
in any sane design (jitter does not average out that far over just 2
cycles) — but that is a consequence of good design practice, not an
independently specified requirement, since the accumulated figure is the
one thing the sampling-margin argument actually needs.

### This supersedes

- `spec/usb2-phy.md` §4, row "**PLL output jitter budget**" and its
  following derivation paragraph.
- `spec/usb2-phy.md` §6, row "PLL | Output jitter (cycle-to-cycle, feeding
  oversampling clock) | < 5% of one bit period (< 4.17 ns at 144 MHz, 12x
  oversampling of 12 Mbps)".
- `spec/usb2-phy.md` §8.3, first sentence's "cycle-to-cycle" qualifier.
- `spec/architecture.md`'s interface-requirements table row "PLL | Output
  jitter (cycle-to-cycle, feeding oversampling clock) | < 5% of one bit
  period (< ~4.2 ns at 12 Mbps, 12x oversampling) | Draft budget; tightens
  once the recovery logic's oversampling ratio is fixed" — the oversampling
  ratio (12x) has in fact been fixed since §4 was ratified; that row's
  "draft, tightens later" status was itself stale and is superseded by this
  record's non-draft accumulated-jitter figure.

The **numeric budget (4.17 ns) is unchanged** — only the metric it applies
to changes, from cycle-to-cycle to 12-UI accumulated. This is a correction
to what the sibling PLL canary is being asked to verify, not a relaxation:
the new metric is strictly **more** constraining than the old one (compare
the ±36% frequency-excursion tolerance a cycle-to-cycle reading of the old
text permitted against the 12-UI accumulated bound, which is the metric
real PLL jitter specifications are normally characterized against).

### Sibling-canary ownership status

Per CLAUDE.md's friction protocol, a requirement change owed to a sibling
canary would normally be filed as an issue on that canary's tracker. As of
this record, `gh repo list 2AMLogic` shows no `sky130-pll` (or equivalently
named) repository — the only PLL canary in the org is `gf180-pll`, which
targets a different PDK and is not the sibling this repo's §4/§6 rows are
written against. **No cross-repo issue is filed.** This jitter-metric
correction is presently **unowned by any sibling canary** and is recorded
here so that whichever repo eventually becomes the sky130 PLL canary
inherits the corrected metric from this record rather than the
non-binding cycle-to-cycle reading in the original ratified text.

---

## Decision 2 — Name the source of the 30 MHz UTMI clock

### The problem

§3 ratifies a 30 MHz UTMI interface clock. §4 levies exactly one clock
output on the PLL sibling canary: the 144 MHz oversampling clock. Nothing
states where 30 MHz comes from, and it cannot be obtained by integer
division of 144 MHz (144 / 30 = 4.8) or by integer multiplication of the
12 MHz reference (12 x 2.5 = 30, non-integer).

### Options considered

**(a) Add a second PLL output: a dedicated 30 MHz UTMI clock, generated
from the same VCO as the 144 MHz oversampling clock via independent integer
dividers.** The least-common-multiple of 144 MHz and 30 MHz is 720 MHz
(720 / 5 = 144, 720 / 24 = 30), so a PLL with a >=720 MHz VCO can produce
both outputs from a single locked loop via two integer counters. This
preserves `spec/usb2-phy.md` §3's ratified 30 MHz value untouched.

**(b) Re-fix the UTMI clock to a value that divides 144 MHz cleanly** — the
candidates named in issue #9 are 144/3 = 48 MHz, 144/4 = 36 MHz, and
144/6 = 24 MHz. This would let the UTMI clock be generated as a simple
synchronous divider of the 144 MHz recovery-domain clock rather than as an
independent PLL output, which superficially looks like it removes a clock
domain.

### Decision

**Adopt option (a).** The PLL sibling canary is levied a second output
requirement: a 30 MHz UTMI-domain clock, generated from the same voltage-
controlled oscillator as the 144 MHz oversampling output (e.g. a >=720 MHz
VCO with /5 and /24 integer dividers — the specific VCO frequency and
divider implementation are the PLL canary's own design choice; only the
30 MHz output and its co-generation from a common, phase-locked source are
levied as the interface requirement).

### Rationale / why (b) is rejected

Rejected the re-fix to 36/48/24 MHz for three reasons:

1. **It does not remove the CDC problem it appears to.** Even if the UTMI
   clock were an exact integer divide of 144 MHz (144/4 = 36 MHz is a clean
   divide), the *dominant* asynchronous boundary in this system is not
   between two locally-generated clocks — it is between the **host's**
   recovered bit timing (asynchronous by construction; the host's 12 Mbps
   ±0.25% is set by a crystal independent of this device's local crystal)
   and **any** locally-generated clock, 30 MHz or 36 MHz alike. Re-fixing
   the UTMI clock rate does not touch that boundary at all; it only
   simplifies a second-order boundary between two already-local, already
   PLL-derived clocks. See Decision 3 below: that boundary is treated as a
   full asynchronous CDC crossing regardless of which option is chosen here
   (144 MHz and 30 MHz are not integer-related even when co-generated from
   a shared VCO, as shown by the 4.8:1 non-integer output ratio — see next
   point), so option (b)'s "simpler CDC" premise does not hold in this
   design as sharply as it would if the recovery-to-UTMI boundary were the
   only asynchronous one in the system.
2. **A shared-VCO 144/30 MHz pair is still not simple-integer-related to
   each other**, so it buys no CDC simplification over option (b) even on
   its own terms: 144 MHz / 30 MHz = 4.8, so the 144 MHz and 30 MHz edges
   realign only every 5 UTMI cycles (= 24 oversampling cycles), not every
   cycle. This record does not rely on that periodic realignment for
   single-cycle timing closure — Decision 3 treats the 144 MHz/30 MHz
   boundary as a full CDC crossing with synchronizers, the same discipline
   it would need under option (b)'s "clean division" premise if that
   premise were taken at face value for only the local-clock boundary.
3. **Reopening a ratified, cross-referenced row costs more than it buys.**
   §3's 30 MHz value is already cited by `spec/architecture.md`'s block
   diagram annotation and is the presumed operating point for the not-yet-
   written TX-path (#12) and RX-path (#13) RTL. 30 MHz is also, per
   Decision 4 below, the *closer* of the two UTMI-canonical clock rates
   (16-bit/30 MHz) to what this record is already recording as a deviation;
   36/48/24 MHz would be further from either UTMI-canonical rate with no
   canonical-width match to compensate, compounding rather than reducing
   the recorded deviation, for a CDC benefit that (per points 1-2) does not
   actually materialize in this design.

**This leaves exactly one live answer: 30 MHz, sourced from a second PLL
output co-generated with the 144 MHz oversampling clock from a shared VCO.**
36/48/24 MHz are rejected options, not live alternatives.

### This extends

- `spec/usb2-phy.md` §4 / §6 (PLL interface requirements) — adds a second
  PLL output row (30 MHz UTMI clock) alongside the existing 144 MHz
  oversampling-clock row. Does not change §3's ratified 30 MHz value.
- `spec/architecture.md`'s interface-requirements table — same addition.

---

## Decision 3 — CDC discipline between the 144 MHz and 30 MHz domains

### Domain model

This block has (at least) three timing domains once Decisions 1-2 are
applied:

1. **Host-recovered domain** — the incoming NRZI bit stream's actual
   transition timing, set by the host's transmit clock (12 Mbps ±0.25%,
   USB 2.0 §7.1.11), asynchronous to every local clock by construction.
   This is *not* a clock domain with its own flip-flops; it is resolved
   into the 144 MHz domain by the bit/edge synchronization logic itself
   (the oversampling *is* the mechanism that captures this asynchronous
   signal — this is standard PHY practice, not a CDC crossing in the
   register-transfer sense).
2. **144 MHz recovery domain** — the oversampling clock (Decision 1),
   locally generated, driving the bit/edge synchronization logic, the
   serializer/deserializer, and the RX status generation
   (`RxActive`/`RxError`/`LineState` sourcing) described in
   `spec/architecture.md`'s block diagram.
3. **30 MHz UTMI domain** — the UTMI interface clock (Decision 2), driving
   every port-level UTMI signal in §3's list, because UTMI is by
   definition a synchronous parallel bus clocked by its own `Clock` signal.

The 144 MHz <-> 30 MHz boundary is a genuine asynchronous CDC crossing per
Decision 2's rationale (4.8:1 non-integer ratio, no exploitable fixed
single-cycle phase relationship). This decision defines the discipline for
crossing it.

### Options considered

**Synchronizer depth for level/status signals — 2-flop vs. 3-flop.** A
2-flop synchronizer is the industry-standard minimum for metastability
resolution at these clock rates (144 MHz / 30 MHz are both slow by modern
CDC standards, giving ample settling time per stage); a 3-flop synchronizer
trades one extra cycle of latency for a lower residual metastability
failure rate. **Chosen: 2-flop**, for every level/status crossing in the
table below (`TxReady`, `RxActive`, `RxError`, `LineState`, and the
UTMI-domain quasi-static control inputs). Rationale: this block's MTBF
budget has not been derived from a target field-failure rate (no such
target exists yet in the ratified spec), so there is no quantified reason
to pay the extra latency of a 3-flop stage; 2-flop is the standard default
and is a cheap, reversible choice if a later MTBF analysis (a future
decision record) demands more margin.

**Reset distribution — one global synchronized reset vs. per-domain
synchronizers.** A single reset synchronized once (e.g. only in the 144 MHz
domain) and fanned out to the 30 MHz domain as an unsynchronized signal
would be simpler to draw, but reintroduces exactly the kind of asynchronous,
unsynchronized crossing this whole record exists to eliminate — the 30 MHz
domain would see an async reset deassertion edge with respect to its own
clock, the classic reset-recovery/removal timing violation. **Chosen:
per-domain reset synchronizers** (see "Reset scheme" below), one local
synchronizer in each of the 144 MHz and 30 MHz domains, both fed from the
same asynchronous `Reset` input. Rationale: this is the standard
reset-domain-crossing (RDC) pattern precisely because it avoids that
violation, at the cost of two small synchronizer instances instead of one
— a cost this record judges worth paying rather than leaving an
unsynchronized reset edge in either domain.

**RX byte handoff — request/acknowledge handshake vs. asynchronous elastic
FIFO.** See "RX byte handoff" below for the full derivation; summarized
here: a handshake was rejected because the host, not this PHY, controls
when RX bytes arrive (the PHY cannot ask the host to pause mid-packet), so
the 144 MHz domain must be able to write without waiting on UTMI-domain
permission — only an elastic buffer supports that. **Chosen: asynchronous
(dual-clock) elastic FIFO**, depth derived below.

### Per-signal domain ownership

All UTMI **port-level** signals are, by definition, in the 30 MHz UTMI
domain (Clock) — that is what makes UTMI a synchronous parallel bus. The
CDC question is which *internal* signal or path crosses from the 144 MHz
recovery domain to produce each UTMI-domain port, and what synchronizer
governs that crossing.

| Signal | Direction (Link<->PHY) | Width | Port domain | Crossing / synchronizer |
|---|---|---|---|---|
| `Clock` | PHY -> Link (output; sourced from the PLL's 30 MHz output, Decision 2) | 1 | defines UTMI domain | n/a — this is the domain-defining clock |
| `Reset` | Link -> PHY (input) | 1 | async | Asynchronous assert, per-domain synchronized deassert — see "Reset scheme" below |
| `TxValid` | Link -> PHY (input) | 1 | UTMI (30 MHz) | 30->144 MHz: 2-flop synchronizer, held as a level until acknowledged by `TxReady` (request/acknowledge handshake, not a single-cycle pulse) |
| `DataOut[7:0]` | Link -> PHY (input) | 8 | UTMI (30 MHz) | Sampled into the 144 MHz domain in the same cycle `TxValid` is acknowledged (data held stable by the link controller for the duration of the handshake, standard UTMI convention) — no separate byte-wide synchronizer; correctness relies on the `TxValid`/`TxReady` handshake, not a bus synchronizer |
| `TxReady` | PHY -> Link (output) | 1 | UTMI (30 MHz) | 144->30 MHz: 2-flop synchronizer on a level signal generated by the TX state machine (144 MHz domain, since it must track bit-serializer/oversampling-clock availability) |
| `RxValid` | PHY -> Link (output) | 1 | UTMI (30 MHz) | 144->30 MHz: asynchronous RX byte FIFO (see "RX byte handoff" below) — `RxValid` is the FIFO's not-empty/pop-valid signal in the UTMI domain |
| `RxActive` | PHY -> Link (output) | 1 | UTMI (30 MHz) | 144->30 MHz: 2-flop synchronizer (slow-changing status level, asserted SOP..EOP in the 144 MHz domain) |
| `RxError` | PHY -> Link (output) | 1 | UTMI (30 MHz) | 144->30 MHz: 2-flop synchronizer on a level held for at least one 30 MHz cycle by the 144 MHz-domain error-detect logic (bit-stuff violation / framing error — see Decision 4's port table for the exact assertion condition) |
| `DataIn[7:0]` | PHY -> Link (output) | 8 | UTMI (30 MHz) | 144->30 MHz: asynchronous RX byte FIFO, same crossing as `RxValid` — see below |
| `LineState[1:0]` | PHY -> Link (output) | 2 | UTMI (30 MHz) | 144->30 MHz: 2-flop synchronizer per bit (electrical line-state sample, sourced from the differential-receiver/squelch sibling canary through the 144 MHz domain) |
| `OpMode[1:0]` | Link -> PHY (input) | 2 | UTMI (30 MHz) | 30->144 MHz: 2-flop synchronizer per bit (quasi-static control, consumed by the TX serializer, which runs in the 144 MHz domain — see Decision 4 for the bit-stuffing/NRZI-disable encoding this field carries) |
| `TermSelect` | Link -> PHY (input) | 1 | UTMI (30 MHz) | 30->144 MHz: 2-flop synchronizer (quasi-static; consumed by the 144 MHz domain logic that drives the pull-up/pull-down control interface, `spec/usb2-phy.md` §6) |
| `XcvrSelect` | Link -> PHY (input) | 2 (canonical UTMI width; only the FS encoding is meaningful for this FS-only device — see Decision 4) | UTMI (30 MHz) | 30->144 MHz: 2-flop synchronizer per bit (quasi-static) |
| `SuspendM` | Link -> PHY (input) | 1 | UTMI (30 MHz) | 30->144 MHz: 2-flop synchronizer (quasi-static; gates the analog front end via the sibling-canary control interfaces) |

### Reset scheme

`Reset` is an asynchronous input (the link controller may assert it without
regard to either local clock). Discipline: **asynchronous assert,
synchronous deassert, per domain.** Two independent local reset signals are
derived from the single `Reset` port:

- `rst_144_n` — asserted immediately (combinationally/asynchronously) when
  `Reset` asserts; deassertion is synchronized to the 144 MHz clock through
  a standard 2-flop asynchronous-assert/synchronous-deassert reset
  synchronizer local to the 144 MHz domain.
- `rst_utmi_n` — same structure, synchronized to the 30 MHz clock, local to
  the UTMI domain.

Both domains' resets share the same asynchronous assertion event but
deassert independently, on their own clock, at whatever cycle each
domain's synchronizer releases — this is the standard reset-domain-crossing
(RDC) pattern and avoids one domain coming out of reset mid-cycle relative
to the other. The RX byte FIFO's pointers (below) are held reset until
*both* `rst_144_n` and `rst_utmi_n` have deasserted, to guarantee the FIFO
starts empty and pointer-synchronized on both sides.

Per common secondary-source UTMI descriptions (flagged in Decision 4 as
pending verification against a primary document), `Reset` is
**active-high**: the link controller drives `Reset = 1` to force the PHY
into reset.

### RX byte handoff: elastic FIFO, not a handshake — derivation

**Decision: an asynchronous (dual-clock) elastic FIFO, depth 8 entries x 8
bits, Gray-coded read/write pointers, 2-flop synchronizers on each
pointer's crossing (standard AFIFO construction).** Not a request/
acknowledge handshake.

**Why a FIFO and not a handshake:** on the TX path, the PHY can throttle
the link controller via `TxReady` because the link controller is the one
choosing when to source data. On the RX path, the *host* controls when
bytes arrive — the PHY cannot signal the host to pause mid-packet over
USB — so the 144 MHz domain must be able to write a completed byte into
the UTMI domain without waiting for permission from the UTMI-domain
consumer. That asymmetry is why RX needs an elastic buffer and TX does not.

**Why 8 entries is enough — the accumulation argument:**

The relevant rate mismatch is between the host's transmit rate (12 Mbps
±0.25%, USB 2.0 §7.1.11, independent crystal) and this device's local rate
(also traceable to a ±0.25% local crystal, §4) — up to **±0.5% relative**
between the two, as stated in issue #9.

The counter-argument issue #9 raises must be addressed directly: does the
FIFO need to absorb *sustained*, multi-packet drift, or only *per-packet*
drift? **Per-packet only** — `RxValid`/`RxActive` deassert at each packet's
EOP (`spec/usb2-phy.md` §3, §6's `LineState`/`RxActive` generation), which
is a hard resync point: the FIFO drains to empty between packets (the link
controller consumes every asserted `RxValid` byte, and the 144 MHz domain
stops producing new bytes once EOP is detected), so drift accumulated
during one packet does not carry over into the next. The FIFO therefore
only needs to be sized for the worst-case *single maximum-length FS
packet*, not for indefinite operation.

USB 2.0 full-speed's largest single packet is an isochronous data payload
of up to 1023 bytes (the largest FS transaction size defined in the spec).
Time to transmit 1023 bytes at 12 Mbps:

```
t = 1023 bytes x 8 bits/byte / 12e6 bits/s = 8184 / 12e6 = 682 us
```

Worst-case accumulated timing drift over that packet at ±0.5% relative rate
error:

```
drift = 682 us x 0.005 = 3.41 us
```

Converted to bytes at the nominal local byte rate (1 byte = 8 bits /
12 Mbps = 0.667 us):

```
drift_bytes = 3.41 us / 0.667 us/byte ~= 5.1 bytes
```

Rounding up for margin (packet-framing overhead beyond the 1023-byte
payload, and synchronizer/pointer-crossing latency in the AFIFO itself,
typically 2-3 entries of "safety" depth in a standard dual-clock FIFO
design) gives **8 entries** as a comfortable, implementation-convenient
(power-of-two) depth. This is a design target: the exact depth must be
re-derived and testbench-verified once #12/#13's RTL and #11's flow are in
place, particularly if the assumed 1023-byte max-packet figure or the
±0.5% relative-rate figure changes.

### This extends

- `spec/usb2-phy.md` §3 (adds `Clock` to the signal list, which §3's table
  omits — see Decision 4) and §6 (adds the CDC discipline that governs how
  the RX-status/`LineState` rows in that table are delivered to the UTMI
  domain). No existing §3/§6 row is contradicted; this is new content that
  §3/§6 left unstated.

---

## Decision 4 — Normative UTMI reference, full port table, and the recorded deviation

### Availability finding (per CLAUDE.md's friction protocol)

Per issue #9's Notes section: if the missing UTMI reference "turns out to
be a licensing/availability problem rather than an oversight, record that
finding...rather than inventing semantics." That is the case here. UTMI —
the *Universal Transceiver Macrocell Interface* — was never adopted as an
official USB Implementers Forum (usb.org) chapter; it originated as an
industry document among transceiver vendors (commonly cited as **"UTMI
(Universal Transceiver Macrocell Interface) Specification, Revision
1.05," dated March 29, 2001**) and, unlike the USB 2.0 core specification
`spec/usb2-phy.md` §9 already cites, does not have a single stable,
freely-redistributable canonical URL. No copy of the primary document was
located in this session.

### Options considered

**(a) Invent port encodings outright, uncited, to unblock #12/#13
immediately.** Rejected: this is exactly the "papering over a gap" failure
mode CLAUDE.md's friction protocol and issue #9's Notes section both warn
against — an invented encoding would read as ratified fact to whoever
implements #12/#13 next, with no way to tell it apart from a cited value.

**(b) Block this record on obtaining a primary copy of the UTMI
specification before naming any port table at all.** Rejected: this would
leave #12/#13 with no port list to build against — worse than a flagged,
honestly-sourced reconstruction, and the primary document's availability is
outside this repo's control (a licensing/availability finding, not
something more investigation here can resolve).

**(c) Reconstruct the port table from corroborating secondary sources
(vendor UTMI-compatible transceiver datasheets and application notes),
explicitly flag every reconstructed encoding/polarity claim, and record the
primary-source availability gap as a finding rather than silently
resolving it.** **Chosen.** This unblocks #12/#13 today with a table that
is auditable — every claim not directly traceable to the ratified USB 2.0
spec or this repo's own prior decisions is marked **[reconstructed]** and
explicitly named as a design target pending verification, so a future
correction is a targeted table update, not a rediscovery of which values
were ever solid.

**This record does not invent UTMI semantics from nothing.** The port
table below is reconstructed from widely-corroborated secondary
descriptions of the same signal set and encodings that recur consistently
across independent UTMI-compatible transceiver datasheets and application
notes from multiple vendors (the pattern of `TxValid`/`TxReady` handshake,
`OpMode[1:0]` bit-stuff/NRZI-disable encoding, active-low `SuspendM`, etc.
is stable across sources) — but every encoding/polarity claim below is
flagged **[reconstructed]** and must be treated as a **design target
pending verification** against a primary copy of the UTMI 1.05 document if
one becomes available, not as ratified fact. If a primary copy surfaces
later, reconcile this table against it in a superseding record rather than
silently drifting the RTL from what is written here.

### Full UTMI port table

| Name | Direction | Width | Domain | Semantics |
|---|---|---|---|---|
| `Clock` | PHY -> Link | 1 | defines UTMI domain | 30 MHz UTMI interface clock (Decision 2); this repo's PHY is the clock source, per common UTMI convention that the transceiver ("macrocell") supplies the interface clock to the link controller. **Absent from `spec/usb2-phy.md` §3's signal list** — added here. |
| `Reset` | Link -> PHY | 1 | async | **[reconstructed]** Active-high. Forces both the 144 MHz and UTMI domains into reset — see Decision 3's reset scheme. |
| `TxValid` | Link -> PHY | 1 | UTMI | Asserted by the link controller while `DataOut` holds a byte to transmit; held asserted (with `DataOut` stable) until `TxReady` acknowledges. |
| `TxReady` | PHY -> Link | 1 | UTMI | Asserted by the PHY when it can accept the next byte on `DataOut`; the `TxValid`/`TxReady` pair is a standard two-signal handshake. |
| `DataOut[7:0]` | Link -> PHY | 8 | UTMI | Byte to transmit, **not yet NRZI-encoded or bit-stuffed** — those transforms happen downstream in this repo's serializer (`spec/architecture.md` block diagram), except when `OpMode = 2'b10` (below), which disables them entirely. |
| `RxValid` | PHY -> Link | 1 | UTMI | Asserted for one `Clock` cycle per valid byte on `DataIn` (RX byte FIFO pop-valid, Decision 3). |
| `RxActive` | PHY -> Link | 1 | UTMI | Asserted from SOP detection through EOP detection (mid-packet indicator), synchronized from the 144 MHz recovery domain (Decision 3). Distinguishes "no receive in progress" from "receiving, but no new byte this cycle" (which `RxValid` alone cannot). |
| `RxError` | PHY -> Link | 1 | UTMI | **[reconstructed]** Asserted (while `RxActive` is high) when the 144 MHz-domain recovery logic detects a bit-stuff violation or a framing error (EOP where none was expected, or a missing EOP within the maximum packet duration) in the current packet. |
| `DataIn[7:0]` | PHY -> Link | 8 | UTMI | Received byte, de-stuffed and NRZI-decoded (except in `OpMode = 2'b10`, below), valid when `RxValid` is asserted. |
| `LineState[1:0]` | PHY -> Link | 2 | UTMI | **[reconstructed]** Direct electrical sample of the D+/D- pads as delivered by the differential-receiver sibling canary (`LineState[1] = D-`, `LineState[0] = D+`), **not** pre-encoded to J/K — the link controller derives J/K/SE0/SE1 from this raw sample and the currently selected speed (moot here, since this device is FS-only). |
| `OpMode[1:0]` | Link -> PHY | 2 | UTMI | **[reconstructed]** `00` = Normal operation; `01` = Non-driving (TX drivers disabled); `10` = Disable bit-stuffing and NRZI encoding (raw/transparent mode — the TX path must implement this encoding per issue #9's Hole 4); `11` = Reserved. |
| `TermSelect` | Link -> PHY | 1 | UTMI | Selects FS termination (pull-up/pull-down configuration) on the pad ring via the control interface recorded in `spec/usb2-phy.md` §6's pull-up/pull-down row. For this FS-only device, effectively a static "FS termination enabled" select. |
| `XcvrSelect` | Link -> PHY | 2 (canonical UTMI width; only the FS encoding is wired) | UTMI | **[reconstructed]** Canonical UTMI selects HS/FS/LS transceiver mode; since this device is ratified FS-only (`spec/usb2-phy.md` §8.1/§8.2), only the FS encoding is meaningful — the PHY treats other encodings as don't-care. Retained at full width for UTMI port-list compatibility rather than narrowed to 0 bits, so a future HS effort (§8.1's trigger) does not need to widen the port. |
| `SuspendM` | Link -> PHY | 1 | UTMI | **[reconstructed]** Active-low (the "M" suffix denotes active-low in the UTMI naming convention): `SuspendM = 0` commands the PHY into suspend/low-power state; `1` is normal operation. |

### The recorded deviation

**UTMI's own two defined operating points are 8-bit data bus at 60 MHz, or
16-bit data bus at 30 MHz.** `spec/usb2-phy.md` §3 ratifies **8-bit at
30 MHz** — neither canonical point.

**Options considered:** (a) **re-fix §3 to one of the two canonical
points** (8-bit/60 MHz or 16-bit/30 MHz) to eliminate the deviation
entirely; (b) **keep 8-bit/30 MHz and record it as a deviation.** Rejected
(a): 8-bit/60 MHz only exists to serve HS's 480 Mbps bandwidth need (out of
scope, §8.1), and 16-bit/30 MHz only exists to halve HS's required clock
rate by doubling width — both canonical points are HS-motivated, and
adopting either for an FS-only device buys nothing while reopening a
ratified row (§3) and, for 16-bit, breaking the 8-bit width Decision 2
above and `spec/architecture.md`'s block diagram already assume. **Chosen
(b)**: this is not superseded by this record; it is **recorded here,
explicitly, as a deviation**, since it was previously stated as if it were
a normal UTMI configuration.

**Rationale for the deviation (defensible, not accidental):** FS's 12 Mbps
payload rate needs roughly 1.5 MB/s of interface bandwidth (12 Mbps / 8 =
1.5 MB/s); 8-bit at 30 MHz delivers up to 30 MB/s, throttled by
`TxReady`/`RxValid` — 20x headroom. There is no FS-relevant benefit to
either canonical point: 8-bit/60 MHz exists to serve HS's 480 Mbps (60 MB/s
raw), which is out of scope per §8.1; 16-bit/30 MHz exists to halve the
clock rate at HS's bandwidth by doubling width, equally irrelevant to an
FS-only, 8-bit-native design.

**Integration consequence, stated plainly:** a stock/off-the-shelf UTMI
link-controller IP core built against one of the two canonical points will
**not** plug into this PHY without reconfiguration — it will either expect
60 MHz timing at this device's 8-bit width, or a 16-bit bus at this
device's 30 MHz clock rate. Any future integration work must budget for
adapting (or configuring, if the IP supports configurable width/rate) the
link-controller side to this deviation; this repo does not treat it as
free.

### This extends

- `spec/usb2-phy.md` §3 — adds the `Clock` port (absent from the ratified
  signal list) and the full direction/width/domain/semantics detail none
  of which was previously specified; adds §9's missing normative UTMI
  citation (with the availability caveat above). Does not change §3's
  ratified "UTMI, not UTMI+, 8-bit, 30 MHz" decision — records its relation
  to UTMI's canonical operating points as a deviation, which §3/§8.2 did
  not previously state.

---

## Decision 5 — PVT envelope, verifiable against the shipped `sky130_fd_sc_hd` liberty grid

### The problem

`spec/usb2-phy.md` §5 states 1.8 V core / 3.3 V I/O as bare nominals: no
supply tolerance, no temperature range (`grep -i "temperat\|°C"
spec/usb2-phy.md` returns nothing). There is therefore no corner matrix for
T1-tier evidence (`klayout-tools/docs/design-evidence-tiers.md` item 5:
"Full PVT corner simulation vs a ratified spec").

The shipped `sky130_fd_sc_hd` liberty corners are:

| Corner | Process | Temperature | Core voltage |
|---|---|---|---|
| `ss_n40C_1v60` | slow-slow | -40 C | 1.60 V |
| `ss_100C_1v60` | slow-slow | 100 C | 1.60 V |
| `tt_025C_1v80` | typical-typical | 25 C | 1.80 V |
| `tt_100C_1v80` | typical-typical | 100 C | 1.80 V |
| `ff_n40C_1v95` | fast-fast | -40 C | 1.95 V |
| `ff_100C_1v95` | fast-fast | 100 C | 1.95 V |

There is no 125 C corner and no 1.98 V corner in this grid, so a round
"±10%, -40...125 C" envelope (the number an agent might otherwise invent)
would be **unverifiable** against the decks that must verify it.

### Options considered

**(a) Invent a round, symmetric envelope** (e.g. "±10% supply,
-40...125 C") because it looks like a conventional industrial spec.
Rejected: neither bound is verifiable against the shipped
`sky130_fd_sc_hd` grid (no 1.98 V corner for +10%, no 125 C corner at
all) — this is precisely the "unverifiable claim" CLAUDE.md's "no claim
without a testbench" rule exists to prevent.

**(b) Bound the envelope directly to the shipped liberty corners' actual
values**, even where that makes the tolerance asymmetric (-11.1%/+8.3%
rather than a round ±10%) or the temperature ceiling lower than a
conventional industrial 125 C (100 C instead). **Chosen.** Rationale: an
envelope that is defined as exactly what the verification grid covers is
verifiable by construction — every bound in this decision has a named
corner backing it, so a future STA run either confirms or refutes the
envelope against a real deck, rather than against an aspirational number
with no corresponding corner.

### Decision

**Core supply envelope: 1.60 V - 1.95 V, cited directly as the range the
shipped `ss_*_1v60` / `ff_*_1v95` corners bound**, rather than as an
invented symmetric percentage. Relative to the ratified 1.8 V nominal
(§5), this is **-11.1% / +8.3%**, asymmetric — stated as such rather than
rounded to a symmetric figure that would claim coverage (+10%, i.e.
1.98 V) the shipped grid cannot verify.

**Temperature envelope: -40 C to 100 C**, cited directly as the union of
the shipped grid's temperature extremes (`ss`/`ff` corners at -40 C and
100 C; `tt` at 25 C and 100 C). **Known verification gap, stated rather
than papered over:** the shipped grid has no `tt_n40C` corner — the
"typical process, cold" cell is not directly characterized. Timing signoff
at -40 C for typical-process cells relies on interpolation/bounding
between `ss_n40C_1v60`/`ff_n40C_1v95` rather than a direct `tt` corner at
that temperature. This is a limitation inherited from the PDK's shipped
liberty grid, not invented by this record, and should not be silently
assumed away.

**I/O supply envelope: 3.0 V - 3.6 V**, restating §5's basis text (USB FS
driver output regulated range, USB 2.0 Table 7-2/§7.1.5) for envelope
completeness. **Not covered by this record's STA corner matrix** — the
`sky130_fd_sc_hd` grid above characterizes 1.8 V core-logic cells only; the
3.3 V-class I/O device flavor and its own PVT signoff are, per §5's
existing text, an implementation decision for whichever sibling canary
block owns the pad ring, not this repo's digital core STA.

### Committed multi-corner STA set

**All six shipped corners are committed** (the T1 evidence tier requires
full PVT coverage across every spec row, not a reduced subset):
`ss_n40C_1v60`, `ss_100C_1v60`, `tt_025C_1v80`, `tt_100C_1v80`,
`ff_n40C_1v95`, `ff_100C_1v95`.

**Setup-binding corner (design target, pending actual STA):
`ss_n40C_1v60`, not `ss_100C_1v60`.** sky130's slow corner at low core
voltage is documented to exhibit **temperature inversion** — at low Vdd,
threshold-voltage temperature coefficient dominates over carrier-mobility
temperature dependence, so cell delay *increases* as temperature
*decreases*, opposite the older-node intuition that "hot is always
slowest." This is a widely-documented sky130-specific characteristic in
the open sky130 digital flow community (OpenLane/OpenROAD sky130 default
corner-selection guidance flags it explicitly). Accordingly this record
treats `ss_n40C_1v60` as the presumptive worst-case (max-delay,
setup-critical) corner. `ss_100C_1v60` remains in the committed set
regardless — both to check the traditional hot-slow assumption directly
(it has not been ruled out) and because leakage/dynamic-power margins can
bind there instead of setup timing.

**Hold-binding corner (design target, pending actual STA):
`ff_n40C_1v95`.** Fast process, cold, high voltage combine to minimize
cell delay (temperature inversion is a low-Vdd slow-corner phenomenon and
is not expected to reverse this at the fast/high-voltage corner), making
`ff_n40C_1v95` the fastest overall corner and the presumptive min-delay
(hold-critical) corner.

**Both bindings above are stated as design targets, not verified
results** — no STA has been run against this repo's RTL, because no RTL
exists yet (#12/#13 are blocked on this record). #11's physical-flow
bootstrap and #12/#13's synthesis outputs are what will actually confirm
or overturn these bindings; if STA shows a different corner binds, that is
new evidence for a superseding record, not a contradiction of this one.

### This extends

- `spec/usb2-phy.md` §5 — adds tolerance and temperature range to the bare
  nominal voltages; does not change the ratified 1.8 V / 3.3 V nominal
  values themselves.

---

## Consequences

- **#12 (TX-path RTL) and #13 (RX-path RTL) can now build against a fixed
  port table (Decision 4), a fixed clock source (Decision 2), and fixed CDC
  discipline (Decision 3)** without each independently inventing an answer
  that would fail to compose with the other.
- **#11 (physical-flow bootstrap) gains a committed 6-corner STA set
  (Decision 5)** and can adopt it once RTL exists, rather than working at a
  single nominal corner indefinitely.
- **The PLL sibling canary's interface requirement changes**: the jitter
  metric it must meet is now 12-UI accumulated jitter (Decision 1, stricter
  and better-specified than the old cycle-to-cycle reading), and it now
  owes a second 30 MHz output co-generated with the 144 MHz output
  (Decision 2) rather than one output. **No cross-repo issue exists to
  carry this** because no sky130 PLL canary repo exists yet (see Decision
  1's ownership-status note) — whoever stands one up should be pointed at
  this record.
- **The UTMI signal encodings in Decision 4's port table are unverified
  against a primary document** (availability finding) and must be treated
  as design targets. If a primary UTMI 1.05 copy is later obtained and any
  encoding here is wrong, that requires a superseding record and, likely,
  RTL rework in #12/#13 if they have already locked to the wrong encoding
  — this is flagged now specifically so #12/#13 know the risk exists going
  in, rather than discovering it after RTL is written.
- **The RX elastic-FIFO depth (8 entries, Decision 3) is a first-pass
  design target** derived from the 1023-byte FS max-packet assumption and
  the ±0.5% relative rate-error figure; either input changing (e.g. if the
  actual max packet this device needs to support is smaller/larger, or the
  local crystal's actual tolerance differs from §4's ±0.25%) requires
  re-deriving the depth, not silently reusing 8.
- **No `spec/usb2-phy.md` or `spec/architecture.md` text changes.** Every
  decision above is additive or a cited supersession recorded *here*; the
  ratified documents remain exactly as ratified. `git diff origin/main --
  spec/usb2-phy.md spec/architecture.md` is empty for this change.

## References

1. USB Implementers Forum, *Universal Serial Bus Specification, Revision
   2.0*, April 2000 — Chapter 7 ("Electrical"), §7.1.5, §7.1.11, Table 7-2
   (already cited in `spec/usb2-phy.md` §9; restated here for the FS
   max-packet and reference-tolerance figures Decision 3/5 use).
2. "UTMI (Universal Transceiver Macrocell Interface) Specification,
   Revision 1.05," March 29, 2001 — industry document, not a usb.org
   publication; no canonical freely-redistributable copy was located in
   this session (see Decision 4's availability finding). Port-table
   entries sourced from this document are marked **[reconstructed]** from
   corroborating secondary sources (vendor UTMI-compatible transceiver
   datasheets and application notes) pending verification against a
   primary copy.
3. `spec/usb2-phy.md` (issue #1) and `spec/architecture.md` (issue #2) —
   the ratified documents this record extends; see those documents'
   own §9/References for their upstream sources.
4. SkyWater `sky130_fd_sc_hd` open PDK standard-cell liberty timing files
   — corner names and PVT values cited in Decision 5 are the corners as
   shipped in the open PDK's `timing/` liberty set.
5. OpenLane / OpenROAD sky130 default-corner-selection guidance (public
   sky130 digital-flow documentation) — source for the temperature-
   inversion characteristic cited in Decision 5's setup-corner rationale.
