// usb_bit_stuffer.v -- inserts a 0 after six consecutive 1s.
//
// USB 2.0 Spec Rev 2.0 section 7.1.9: "a zero is inserted after every six
// consecutive ones in the data stream before the data is NRZI encoded.
// This guarantees at least one transition every seven bit times." Matches
// verification/usbfs/stuffing.py's `stuff()` bit for bit -- see that
// module's docstring for the stuff-bit-immediately-before-EOP edge case
// this module's `stuff_pending_after` output exists to let a caller
// detect without wasting a bit-time (see usb_tx_framer.v).
//
// Clock domain: 144 MHz oversampling-clock domain (spec/decision-records/
// 0001, Decision 3), gated by `bit_stb` (the bit-time strobe), same as
// usb_nrzi_encoder.v.
//
// Protocol with the caller (usb_tx_framer.v): `bit_in` must be held
// stable by the caller across a cycle where `consume` reads 0 -- that
// cycle inserted a stuff bit and did not consume `bit_in`; the caller
// presents the same `bit_in` again on the following `bit_stb` cycle.
//
// `stuff_pending_after` is a same-cycle lookahead: while `consume` is 1
// (this cycle's `bit_in` really is being sent), it reports whether the
// run-of-ones counter will read the maximum (6) immediately afterward --
// i.e., whether the *next* bit-time is mandatorily a stuff bit. This lets
// a caller that has just sent its last real bit (no more data behind it,
// e.g. end of packet) decide, in the same cycle, whether to spend one more
// bit-time on a forced stuff bit before framing EOP -- the "stuff bit
// immediately before EOP" case issue #12 requires with no extra idle
// bit-time on the wire either way.
//
// Bypass (`bypass`, driven from OpMode == 2'b10, spec/decision-records/
// 0001's Decision 4): disables stuffing entirely -- `bit_in` always passes
// straight through, always consumed, `stuff_pending_after` always 0.

`default_nettype none

module usb_bit_stuffer (
    input  wire clk,
    input  wire rst_n,

    input  wire bit_stb,             // one-cycle pulse: evaluate this bit-time
    input  wire bypass,              // 1 = stuffing disabled (raw/transparent mode)
    input  wire sof,                 // pulse (coincident with bit_stb): reset the
                                      // consecutive-ones run counter -- start of a
                                      // new packet's stuffable field (post-SYNC)
    input  wire bit_in,              // candidate next real bit (LSB-first stream)

    output wire bit_out,             // this bit-time's bit in the stuffed domain
    output wire consume,             // 1 = bit_in was accepted this cycle (advance
                                      // to the next real bit); 0 = a stuff bit was
                                      // forced instead, bit_in was not consumed
    output wire stuff_pending_after  // lookahead, valid when consume == 1: the very
                                      // next bit-time is mandatorily a forced stuff
);

    reg [2:0] run; // consecutive-ones counter, 0..6

    wire run_maxed = (run == 3'd6);
    wire do_stuff  = !bypass && !sof && run_maxed;

    assign consume              = !do_stuff;
    assign bit_out               = do_stuff ? 1'b0 : bit_in;
    assign stuff_pending_after   = !bypass && !sof && !do_stuff && bit_in && (run == 3'd5);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run <= 3'd0;
        end else if (bit_stb) begin
            if (bypass) begin
                run <= 3'd0;
            end else if (sof) begin
                run <= bit_in ? 3'd1 : 3'd0;
            end else if (do_stuff) begin
                run <= 3'd0;
            end else begin
                run <= bit_in ? (run + 3'd1) : 3'd0;
            end
        end
    end

endmodule

`default_nettype wire
