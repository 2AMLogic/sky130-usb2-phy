# 0002: Shared USB protocol RTL — master, classification, and canonical interfaces

- **Status**: Proposed
- **Date**: 2026-09-21
- **Decided by**: Builder agent, issue #79
- **Related**: #60 (measured the divergence), #79 (this reconciliation),
  gf180-usb2-phy#84 (consumer-side twin), gf180-usb2-phy#7 (that repo's
  harness bootstrap — *not* from this repo, see Context),
  2AMLogic/2am#899 (ratified the reuse rule this executes),
  `0001-clocking-cdc-jitter-metric-and-pvt-envelope.md` (the ratified
  record whose Decisions 1/3/4 every interface verdict below cites),
  `rtl/README.md` §"Relationship to sibling PDK repos (issue #60)" (the
  downstream-audience statement this record requires)

## Context

Issue #60 measured that this repo and `gf180-usb2-phy` each carry an
independently written implementation of the same USB 2.0
specification-defined protocol logic (NRZI coder, bit stuffer/destuffer,
SYNC detection, line-state, EOP detection) — sharing a module name but
not a git blob, and not even an interface (re-verified 2026-09-21 at
`origin/main` `38f4a97`: `rtl/usb_nrzi_encoder.v` uses
`bit_stb/bypass/sof/bit_in → level_out`; gf180's `rtl/usb_nrzi_encoder.v`
uses `data_valid/init/data_bit → line_valid/line_bit`).
`2AMLogic/2am#899` turned that fleet-level duplication into
cross-cutting rule 9 (`2AMLogic/2am` `REUSE.md`, ratified 2026-09-18,
widened 2026-09-21, verified in `2am` @ `9032d1d`): shared
PDK-independent RTL has **one master and stamped copies**. #899's own
scope excluded reconciling the two USB repos; this record is that
follow-up, master-side only. The consumer-side half — vendoring under
`rtl/common/`, the root `reuse.lock.json` pin, `reuse-check.py` in CI —
is the twin issue gf180-usb2-phy#84 and is restated here only as the
contract the twin pins against (Decision 6).

**Master by precedence, not lineage.** REUSE.md's tie-breaks, in order:
(1) *lineage* — a `ported_from` edge in `2am`'s `repos.yml`. Verified
against `repos.yml` @ `9032d1d` (live `gh api
repos/2AMLogic/2am/contents/repos.yml?ref=9032d1d`): neither USB repo's
entry carries `ported_from` pointing at the other, so tie-break 1 does
not formally connect these repos. (2) *precedence* — the repo whose copy
was committed first. Measured 2026-09-21: the four same-name modules were
first committed here in `25a74e6` and `2377616` on 2026-08-07, and in
gf180-usb2-phy in `3140467` on 2026-08-17. **sky130-usb2-phy is master by
precedence**, by ten days on every shared file. (The two facts the
original #60-era text leaned on were corrected during curation of #79 and
are recorded here so they are not re-derived: repo *creation* dates are
not the tie-break, and gf180-usb2-phy#7 bootstrapped that repo's harness
from `sky130-modexp`, not from this repo.)

This record classifies every module in `rtl/`, names the canonical
interface for each shared module, and states the downstream-audience
commitment REUSE.md requires of a master. It changes no `.v` file and
supersedes no decision in DR-0001 — where a verdict below could only be
reached by superseding a DR-0001 decision, that option is explicitly
rejected (see Alternatives), and a genuinely different interface pick
would have to arrive as a new superseding record under this directory,
never as an unrecorded RTL edit.

## Decision

### Decision 1 — Master: sky130-usb2-phy (REUSE.md tie-break 2, precedence)

Adopted: **this repo is the master for the shared USB protocol RTL.**
Evidence: the precedence measurement in Context (first commits
2026-08-07 here vs 2026-08-17 in gf180, per module).

### Decision 2 — The classification: every module in `rtl/`, exactly once

The shared set is named explicitly, per the rule: **every module whose
behaviour is defined by the USB 2.0 specification and which contains
nothing PDK-dependent**. The full `rtl/` inventory at `38f4a97` is 13
`.v` files (re-counted 2026-09-21); each is classified exactly once:

| Module | Verdict | Justification (USB 2.0 § / DR-0001 decision) |
|---|---|---|
| `usb_nrzi_encoder.v` | **vendorable-shared** | USB 2.0 Spec Rev 2.0 §7.1.9 NRZI line encoding — a pure spec-defined transform, no PDK dependence (verified: no PDK references in the file). Interface is DR-0001-derived, see Decision 3. |
| `usb_nrzi_decoder.v` | **vendorable-shared** | §7.1.9 NRZI decode, inverse transform, no PDK dependence (verified). See Decision 3. |
| `usb_bit_stuffer.v` | **vendorable-shared** | §7.1.9 bit stuffing ("a zero is inserted after every six consecutive ones"), no PDK dependence (verified). See Decision 3. |
| `usb_bit_destuffer.v` | **vendorable-shared** | §7.1.9 bit destuffing + stuff-violation detection, no PDK dependence (verified). See Decision 3. |
| `usb_bit_sync.v` | **architecture-bound — not shared** | Sync/bit recovery here is the 12×-oversampling, hard-resync-on-every-transition bit/edge synchronizer of DR-0001 Decision 1 (144 MHz oversampling clock, 144/12 = 12 cycles per bit) and Decision 3 (the 144 MHz recovery domain). This is architecture, not a USB-specified transform — see Decision 4's sync-detection pair. |
| `usb_linestate.v` | **architecture-bound — not shared** | LineState formatting is DR-0001 Decision 4's port-table choice (raw `{D-, D+}`, `LineState[1] = D-`, not pre-encoded J/K) — a deliberate, ratified shape; the differing gf180 module instantiates a different ratified choice, see Decision 4's line-state pair. |
| `usb_rx_framer.v` | **architecture-bound — not shared** | SOP/SYNC lock, EOP detection, deserialization, watchdog, reset/suspend detection are this repo's consumer architecture; the EOP-detection function it embeds is mapped as a functional pair in Decision 4. |
| `usb_rx_cdc.v` | **architecture/integration — not shared** | The embodiment of DR-0001 Decision 3's CDC discipline between this repo's 144 MHz recovery and 30 MHz UTMI domains; exists only because those two domains do. |
| `usb_rx_path.v` | **integration top — not shared** | Wires the RX modules into `spec/architecture.md`'s dataflow order; carries integration, not USB-spec behaviour. |
| `usb_tx_framer.v` | **architecture — not shared** | Packet-level state machine (SYNC/DATA/FLUSH/EOP/IDLE), `TxReady` back-pressure, line-state mux — consumer architecture per `spec/usb2-phy.md` §3/§6 as wired by DR-0001 Decision 4's port table. |
| `usb_tx_serializer.v` | **integration top — not shared** | UTMI TX handshake exposure plus the exact `/12` `bit_stb` derivation from the 144 MHz clock (DR-0001 Decision 1's 144/12 relationship); instantiates the shared stuffer/encoder below itself. |
| `usb_utmi_top.v` | **integration top — not shared** | The UTMI digital toplevel instantiating both datapaths; adds the 30↔144 MHz crossings and per-domain reset scheme of DR-0001 Decision 3 and exposes Decision 4's full UTMI port table. Integration by definition, not protocol logic. |
| `utmi_stub.v` | **toolchain plumbing — not shared** | Exists solely to prove the cocotb/Icarus + Yosys toolchain end-to-end (issue #3, `rtl/README.md`); carries no USB-spec protocol behaviour. |

"Vendorable" is the *verdict about the module's content*, not an action
in this repo: nothing is vendored here, and this repo's file layout is
unchanged (Decision 6).

### Decision 3 — Canonical interfaces for the four same-name modules

One interface per module: **this repo's own port list**, selected
because it is not incidental — it falls out of ratified DR-0001. gf180
adapts at its boundary (gf180-usb2-phy#84); per REUSE.md, gf180's
`mode: vendored` entries byte-match these files, and any difference it
keeps must be a `diverged:` entry pointing at a gf180-side decision
record. The canonical port lists, from `origin/main` `38f4a97`:

**`usb_nrzi_encoder.v`** — canonical:

```verilog
module usb_nrzi_encoder (
    input  wire clk,
    input  wire rst_n,
    input  wire bit_stb,   // one-cycle pulse: consume bit_in this bit-time
    input  wire bypass,    // 1 = raw/transparent mode, no NRZI transform
    input  wire sof,       // packet-start: re-derive from idle J level
    input  wire bit_in,
    output reg  level_out
);
```

Why: `bit_stb` is the bit-time strobe of the 144 MHz oversampling domain
(DR-0001 Decision 1's 12-cycles-per-bit relationship; Decision 3's domain
model), and `bypass` is the raw-mode port DR-0001 Decision 4's port table
mandates (`OpMode = 2'b10` disables bit-stuffing and NRZI encoding). gf180's
alternative (`init/data_valid/data_bit → line_valid/line_bit`, a 12 MHz
interface-clock valid-strobe shape) matches that repo's
no-oversampling architecture, not this ratified one.

**`usb_nrzi_decoder.v`** — canonical:

```verilog
module usb_nrzi_decoder (
    input  wire clk_144,
    input  wire rst_144_n,
    input  wire bit_strobe,
    input  wire bit_level,
    input  wire bit_is_jk,
    output reg  data_strobe,
    output reg  data_bit
);
```

Why: it consumes the recovered bit stream of DR-0001 Decision 3's 144 MHz
recovery domain, and `bit_is_jk` is load-bearing there: NRZI is defined
only over J/K, so SE0/SE1 cells (EOP, bus reset) must not be decoded as
data — the gating is part of this repo's verified behaviour, gf180's
interface (`init/line_valid/line_bit → data_valid/data_bit`) has no
equivalent input and would drop it.

**`usb_bit_stuffer.v`** — canonical:

```verilog
module usb_bit_stuffer (
    input  wire bit_stb,
    input  wire bypass,
    input  wire sof,
    input  wire bit_in,
    output wire bit_out,
    output wire consume,             // 0 = a stuff bit was forced this bit-time
    output wire stuff_pending_after  // lookahead: next bit-time is a forced stuff
    // + clk, rst_n
);
```

Why: `bypass`/`sof` carry DR-0001 Decision 4's raw-mode port and the
per-packet run reset; `consume`/`stuff_pending_after` express the
stuff-bit-insertion back-pressure in the strobed domain the caller
(usb_tx_framer.v) is ratified to use. gf180's alternative
(`init/in_valid/in_ready → out_valid/out_bit/out_stuffed`, a ready/valid
stream) is a different handshake discipline for a different clocking
architectecture.

**`usb_bit_destuffer.v`** — canonical:

```verilog
module usb_bit_destuffer (
    input  wire enable,       // SOP..EOP gating (rx_active)
    input  wire data_strobe,
    input  wire data_bit,
    output reg  bit_valid,
    output reg  out_bit,
    output reg  stuff_err     // pulses on a bit-stuff violation
    // + clk_144, rst_144_n
);
```

Why: `enable` scopes destuffing to SOP-lock-through-EOP exactly as
§7.1.9 requires (stuffing covers post-SYNC through CRC), and the
144 MHz recovery-domain inputs (Decision 3) are what the upstream
decoder produces here. gf180's alternative (`init/in_valid/in_bit →
out_valid/out_bit/stuff_err`) uses the same §7.1.9 threshold but a
packet-start-clear (`init`) instead of SOP..EOP gating, against a
different domain. (`stuff_err`'s 7th-consecutive-1 semantics match; the
divergence is the interface and domain, not the transform.)

Each pick above cites DR-0001 by design — a different pick (gf180's
interface for any module) would supersede DR-0001 Decisions 3/4 for that
module and must go through a new superseding decision record under this
directory per CLAUDE.md; that is explicitly out of scope here: **this
record supersedes nothing.**

### Decision 4 — The three differently-named functional pairs, mapped by function, each not-shared

Each pair is mapped by its USB-spec-defined *function* and given an
explicit verdict. No pair is silently dropped; none is added to the
shared set, because each implementation is DR-0001-architecture-bound,
not spec-portable:

| Function (pair) | This repo | gf180-usb2-phy | Verdict |
|---|---|---|---|
| Sync detection | `usb_bit_sync.v` (12×-oversampled bit/edge recovery) | `usb_sync_detector.v` (pattern-match on decoded bits at the interface clock) | **architecture-bound, not shared** — this repo's module *is* the DR-0001 Decision 1/3 oversampling recovery (144 MHz, 144/12 = 12); gf180's operates on already-decoded bits in a no-oversampling architecture. Same §7.1.9-visible outer function, different layers — not interchangeable files. |
| Line-state reporting | `usb_linestate.v` (combinational raw `{D-, D+}` format) | `usb_line_state_decode.v` (registered, J-reset-default decoded state) | **architecture-bound, not shared** — the raw vs. encoded shapes are both deliberate: DR-0001 Decision 4's port table fixes `LineState[1:0]` as the raw electrical sample with J/K derivation left to the link controller; gf180's ratified choice differs. |
| EOP detection | embedded in `usb_rx_framer.v` (samples raw `dp_sync`/`dm_sync` once per recovered bit period: SE0, SE0, J) | standalone `usb_eop_detector.v` (counts SE0 on decoded line state) | **architecture-bound, not shared** — here EOP detection is inseparable from the recovery-domain sampling of DR-0001 Decisions 1/3 and shares the framer's bit_strobe cadence; it is not even a standalone module in this repo, so no shareable file exists without inventing one. |

### Decision 5 — RTL-boundary scope: the analog halves stay two designs

Per REUSE.md's "same analog block on two PDKs" row — a port re-derives
everything device-level — the analog front ends (differential receiver /
squelch, current-mode driver, and the PLL that DR-0001 Decision 2 taxes
with the 30 MHz output) are **genuinely two designs and stay that way**;
they are out of the shared set by rule, not by omission. Nothing
PDK-dependent is in the shared set: the four vendorable-shared modules
were checked at `38f4a97` and contain no PDK references — they are pure
digital transforms guarded by `default_nettype none`. The map above plus
this section accounts for gf180-usb2-phy's entire `rtl/` inventory's
disposition (9 `.v` files, verified 2026-09-21): the four same-name
modules (Decision 3), the three functional pairs (Decision 4), and the
remainder — `usb_utmi_phy.v`, that repo's integration top (the
counterpart of this repo's `usb_utmi_top.v`/`usb_rx_path.v` integration
tier: consumer architecture, not shared by the same tier rules as
Decision 2's rows here), and `harness_counter.v`, simulation-harness
mechanics inside rule 9's 2026-09-21 widening — both of which are the
twin's ledger entries, not this record's (gf180-usb2-phy#84).

### Decision 6 — The consumer contract (gf180-usb2-phy#84's half, restated)

REUSE.md puts `reuse.lock.json` at the root of the **consumer**: nothing
is vendored in this repo, this repo grows no lock file, and this repo's
file layout is unchanged — the consumer maps paths (REUSE.md's own worked
example names exactly this edge: upstream `rtl/usb_nrzi_encoder.v` →
local `rtl/common/usb_nrzi_encoder.v`). gf180-usb2-phy#84 delivers the
vendored copies under `rtl/common/`, the lock pinning the **merged commit
SHA of this record** (full 40-hex; the twin computes per-file SHA-256s
from that commit), `reuse-check.py` in CI, and any `diverged:` entries
pointing at gf180-side decision records. Master-side obligations this
record commits to: `rtl/README.md` §"Relationship to sibling PDK repos
(issue #60)" names gf180-usb2-phy as the consuming repo (the
downstream-audience statement), and — per REUSE.md, "its consumers are its
spec" — the four shared files' interfaces are now a downstream surface:
master-side interface changes carry an adaptation cost on the twin and
must not be made casually or unrecorded.

## Alternatives considered

- **gf180-usb2-phy as master** — rejected by the precedence measurement
  (Context): every shared file was committed here ten days first. REUSE.md
  tie-break 2 decides; tie-break 1 (lineage) is inapplicable (no
  `ported_from` edge either direction, verified @ `9032d1d`.
- **A dedicated shared repo** — not an agent's call: REUSE.md reserves
  creating repositories and admitting them to the fleet for the operator
  (rule 8) pending operator decision. Until one exists, the master stays
  where precedence put it.
- **Adopting gf180's per-module interfaces** (the 12 MHz valid/ready
  stream shape) — rejected: it would supersede DR-0001 Decisions 3
  (domain/strobe discipline, recovery-domain gating inputs) and 4 (the
  `OpMode = 2'b10` bypass port, raw LineState) for those modules.
  Agents do not relax a ratified record to make results pass; the
  sky130 interfaces are the natural shape of the ratified architecture,
  so this record selects them rather than re-litigating DR-0001.
- **Refactoring the three functional pairs into shared files** —
  rejected: their implementations are shaped by ratified DR-0001
  architecture (oversampling recovery, raw LineState, recovery-domain
  EOP sampling). An extracted "shared" sync detector or EOP detector
  would either re-litigate DR-0001 or present an interface neither repo's
  ratified architecture consumes. They are recorded as
  architecture-bound in Decision 4 instead of being silently dropped.
- **Vendoring stamped copies into this repo** — rejected: REUSE.md
  assigns `common/`-directory vendored copies and the root lock to the
  consumer; the master keeps its layout (Decision 6).

## Consequences

- **What becomes possible**: gf180-usb2-phy#84 can vendor the four shared
  files with a byte-exact provenance trail (commit SHA + per-file
  SHA-256), and `reuse-check.py` makes future divergence between the two
  repos *detectable* instead of silent — the gap #60 measured (not one
  shared blob) becomes structurally impossible to re-create unnoticed.
- **What becomes harder**: master-side changes to the four shared files
  are no longer local decisions — gf180-usb2-phy is a downstream
  audience, its adaptation cost is real (the strobe/bypass interfaces
  must be adapted at its boundary, or recorded as `diverged:`), and an
  unrecorded interface change on the master would strand a pinned
  consumer. Interface changes hereafter need the twin's lock updated or a
  divergence record, per REUSE.md.
- **No RTL, testbench, or verification change**: this record introduces
  **no new numeric design target** and changes no `.v` file — the four
  shared modules remain verified by this repo's existing bit-exact
  cocotb/Icarus suites (`verification/test_usb_tx.py`,
  `verification/test_usb_rx.py`, `verification/test_usb_utmi_top.py`)
  against `verification/usbfs`'s reference model. Nothing needs
  re-running; the classification is a prose deliverable whose
  correctness is enforced by review and (on the twin's side) by
  `reuse-check.py` byte-stamps, not by a testbench. Per CLAUDE.md
  ("no claim without a testbench") that is stated as such, not implied.
- **The pin is the twin's to make**: until gf180-usb2-phy#84 lands its
  lock, this record's authority on that side is by reference — nothing in
  this repo enforces the consumer's stamp.

## References

- Issue #60 (measured divergence, per-module), issue #79 (this
  reconciliation; its curated inventory and verified corrections).
- gf180-usb2-phy#84 (consumer-side twin, open), gf180-usb2-phy#7 (harness
  bootstrap provenance — from `sky130-modexp`, not this repo).
- `2AMLogic/2am#899`; `2AMLogic/2am` `REUSE.md` cross-cutting rule 9 @
  `9032d1d` (tie-breaks, lock/vendoring contract, worked example,
  downstream-audience requirement), verified 2026-09-21.
- `spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md`
  Decisions 1 (144 MHz oversampling, 144/12 = 12), 2 (30 MHz UTMI clock),
  3 (domain model + CDC discipline), 4 (UTMI port table: `OpMode`,
  raw `LineState[1:0]`).
- `rtl/README.md` §"Relationship to sibling PDK repos (issue #60)" and
  its module tables (annotated with these verdicts).
- USB 2.0 Specification Rev 2.0 §7.1.9 (NRZI encoding, bit stuffing);
  §7.1.11 (data-rate tolerance — recovered-bit timing context for
  Decision 4's sync pair).
