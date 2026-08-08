// usb_bit_sync.v -- the digital half of clock/data recovery (issue #13,
// block 1 + block 2): input synchronization plus a 12x-oversampled
// transition-tracking bit/edge synchronizer.
//
// Domain: 144 MHz recovery clock (clk_144), per
// spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md
// Decision 1/2. Implements spec/architecture.md's "Bit / edge
// synchronization logic" block.
//
// ---------------------------------------------------------------------
// Block 1 -- input synchronization
// ---------------------------------------------------------------------
// `dp`/`dm` arrive from the differential-receiver sibling canary
// asynchronous to clk_144 (a real chip pin, not a locally-generated
// signal). A 2-flop synchronizer resolves metastability before any
// edge-sensitive logic touches them -- standard practice, independent of
// the CDC discipline table in the decision record above (that table
// governs the 144<->30 MHz *UTMI-side* boundary only; this is the
// *pad-level* input synchronizer feeding the 144 MHz domain itself).
//
// This module deliberately does **not** consume a separate `squelch`
// input. `spec/usb2-phy.md` section 6 assigns SE0/EOP detection to the
// differential receiver's own single-ended thresholds ("used for SE0/EOP
// detection"), not to the squelch/envelope detector -- squelch's role in
// USB PHYs is primarily HS signal-presence detection, out of scope for
// this FS-only issue. `dp`/`dm` alone (already digitized by the receiver
// sibling canary) carry everything this recovery logic needs.
//
// ---------------------------------------------------------------------
// Block 2 -- bit/edge synchronizer (hard resync on every NRZI transition)
// ---------------------------------------------------------------------
// A free-running mod-`OVERSAMPLE_RATIO` phase counter tracks position
// within the current bit cell. Every clk_144 cycle in which the
// synchronized `dp` line changes value (an NRZI transition -- `dp` alone
// is sufficient: during J/K data signaling dp and dm are complementary,
// so a `dp` toggle exactly marks every J<->K transition) the counter is
// **hard-reset** to the reference position (this is "re-align on every
// transition" from the issue body, not a filtered/PLL-style tracking
// loop). Between transitions the counter free-runs at the local 144 MHz
// rate. `bit_strobe` pulses once per recovered bit period, coincident
// with `bit_level` sampling the line at `CENTER_PHASE` cycles after the
// last transition -- nominally the centre of the bit cell
// (CENTER_PHASE=6 of a 12-cycle bit period).
//
// Worst-case drift budget: bit stuffing (`rtl/usb_bit_destuffer.v`)
// guarantees a transition at least every **seven** bit times (six
// consecutive '1' data bits, no NRZI transition, followed by a mandatory
// stuffed '0'). Because every transition performs a *hard* resync (not an
// accumulating/filtered correction), timing error does not compound
// across multiple bit periods -- each resync discards all prior phase
// error and re-anchors to the just-observed edge. The quantity that
// matters is therefore the error accumulated over at most this single
// 7-bit-time (84 oversampling-cycle) gap, not over the whole packet. See
// `docs/bit-sync-budget.md` for the full numeric derivation (quantization
// error, host/device frequency-offset contribution over that 7-bit-time
// window, and the PLL's own 12-UI accumulated-jitter budget from Decision
// 1 of the decision record above) and the measured first-failing offset
// from the cocotb sweep.
`default_nettype none

module usb_bit_sync #(
    parameter integer OVERSAMPLE_RATIO = 12,  // Decision 1: 144 MHz / 12 Mbps
    parameter integer CENTER_PHASE     = 6    // sample point, cycles after an edge
) (
    input  wire clk_144,
    input  wire rst_144_n,

    // Raw pad-level inputs (differential-receiver sibling canary), async.
    input  wire dp,
    input  wire dm,

    // Synchronized, continuously-updated 144 MHz-domain line levels.
    // Consumed by usb_linestate.v (LineState[1:0]) and usb_rx_framer.v
    // (EOP / bus-reset / suspend detection, which need the raw line state
    // at every bit_strobe or every cycle, not just the decoded bit
    // stream).
    output wire dp_sync,
    output wire dm_sync,

    // Recovered bit stream: bit_level is dp_sync sampled at the recovered
    // bit-cell centre; bit_strobe pulses for exactly one clk_144 cycle
    // once per recovered bit period, the same cycle bit_level and
    // bit_is_jk are valid. usb_nrzi_decoder.v consumes all three.
    //
    // bit_is_jk: true when the sampled cell is a valid differential J or K
    // state (dp_sync != dm_sync) as opposed to SE0 (both 0, EOP/reset
    // signaling) or SE1 (both 1, illegal). NRZI encoding is defined only
    // over J/K -- SE0's "no transition" during EOP's two SE0 bit times
    // must never be handed to usb_nrzi_decoder.v as if it were data (doing
    // so double-counts SE0 bit cells as spurious decoded '1's/'0's feeding
    // usb_bit_destuffer.v's six-consecutive-ones counter, a real bug an
    // earlier draft of this module had no guard against).
    output reg  bit_strobe,
    output reg  bit_level,
    output reg  bit_is_jk,

    // One-cycle pulse the cycle a transition (candidate bit boundary) is
    // detected on the synchronized dp line. Diagnostic / available for a
    // future SOP-search optimization; not required for correct NRZI
    // decode (usb_rx_framer.v locks SOP from the destuffed bit stream).
    output wire edge_detect
);

    // ---- block 1: 2-flop input synchronizer ----
    reg dp_ff1, dp_ff2, dp_ff2_d;
    reg dm_ff1, dm_ff2;

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            dp_ff1   <= 1'b1;  // idle bus level (J: dp=1, dm=0)
            dp_ff2   <= 1'b1;
            dp_ff2_d <= 1'b1;
            dm_ff1   <= 1'b0;
            dm_ff2   <= 1'b0;
        end else begin
            dp_ff1   <= dp;
            dp_ff2   <= dp_ff1;
            dp_ff2_d <= dp_ff2;
            dm_ff1   <= dm;
            dm_ff2   <= dm_ff1;
        end
    end

    assign dp_sync      = dp_ff2;
    assign dm_sync      = dm_ff2;
    assign edge_detect  = dp_ff2 ^ dp_ff2_d;

    // ---- block 2: hard-resync phase counter ----
    localparam integer PHASE_W = 4;  // OVERSAMPLE_RATIO <= 16 for this width

    reg [PHASE_W-1:0] phase;

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            phase <= {PHASE_W{1'b0}};
        end else if (edge_detect) begin
            // This cycle *is* phase 0 (the edge); next cycle is phase 1.
            phase <= {{(PHASE_W-1){1'b0}}, 1'b1};
        end else if (phase == OVERSAMPLE_RATIO[PHASE_W-1:0] - 1'b1) begin
            phase <= {PHASE_W{1'b0}};
        end else begin
            phase <= phase + 1'b1;
        end
    end

    wire is_center = (phase == CENTER_PHASE[PHASE_W-1:0]);

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            bit_strobe <= 1'b0;
            bit_level  <= 1'b1;
            bit_is_jk  <= 1'b1;
        end else begin
            bit_strobe <= is_center;
            bit_level  <= dp_sync;
            bit_is_jk  <= dp_sync ^ dm_sync;
        end
    end

endmodule

`default_nettype wire
