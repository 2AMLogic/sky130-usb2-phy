// usb_bit_destuffer.v -- bit destuffing (issue #13, block 3b), mirroring
// the TX path's stuffer. USB 2.0 Spec Rev 2.0 section 7.1.9: a '0' is
// inserted after every six consecutive '1's before NRZI encoding: this
// module removes it. A **seventh** consecutive '1' (i.e. a '1' where the
// mandatory stuffed '0' was required) is a bit-stuff violation and pulses
// `stuff_err` -- consumed by usb_rx_framer.v to assert `RxError` and abort
// the packet, rather than silently forwarding a corrupted byte stream (the
// acceptance criterion this module exists to satisfy). Mirrors
// verification/usbfs/stuffing.py's `destuff()`.
//
// Applied to every bit **from SOP lock through EOP** (`enable`, driven by
// usb_rx_framer.v's `rx_active`) -- per USB 2.0 Spec Rev 2.0 section 7.1.9,
// stuffing covers everything after SYNC through the end of CRC, and
// `verification/usbfs/stuffing.py`'s `stuff()`/`destuff()` (this module's
// golden reference) start each packet's run counter fresh at 0, not
// carrying over any count from SYNC or from idle. This module mirrors that:
// while `enable` is low (not SOP-locked -- i.e. searching for SYNC, or idle
// before/after a packet) it holds its run counter at zero and passes every
// decoded bit through untouched, so `usb_rx_framer.v` can still search for
// the (never-stuffed) SYNC pattern on this module's output. Real destuffing
// (run counting, stuffed-0 removal, 7th-consecutive-1 violation detection)
// only applies while `enable` is high.
//
// This also fixes a real bug an earlier draft of this module had: without
// an enable/reset-on-idle gate, an indefinitely long idle (continuous
// decoded '1's, since NRZI of "no transitions" is all-ones) before SOP or
// after EOP eventually hits the same "six consecutive ones" pattern this
// module is built to flag -- a false-positive `stuff_err` with no real
// bit-stuff violation on the wire at all. Gating the run counter to only
// run while genuinely inside a locked packet (`enable` = `rx_active`)
// removes that false-positive path entirely: idle time, of any length,
// never accumulates into the run counter.
//
// Domain: 144 MHz recovery clock.
`default_nettype none

module usb_bit_destuffer (
    input  wire clk_144,
    input  wire rst_144_n,

    input  wire enable,      // usb_rx_framer.v's rx_active (SOP..EOP)

    input  wire data_strobe,
    input  wire data_bit,

    output reg  bit_valid,   // pulses for a genuine (non-stuffed) data bit
    output reg  out_bit,
    output reg  stuff_err    // pulses on a bit-stuff violation
);

    reg [2:0] ones_run;  // 0..6, held at 0 whenever !enable

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            ones_run  <= 3'd0;
            bit_valid <= 1'b0;
            out_bit   <= 1'b0;
            stuff_err <= 1'b0;
        end else begin
            bit_valid <= 1'b0;
            stuff_err <= 1'b0;
            if (!enable) begin
                // Not SOP-locked: transparent pass-through, no run
                // counting, no stuffing errors possible (see header).
                ones_run <= 3'd0;
                if (data_strobe) begin
                    bit_valid <= 1'b1;
                    out_bit   <= data_bit;
                end
            end else if (data_strobe) begin
                if (ones_run == 3'd6) begin
                    // A stuffed 0 was mandatory here.
                    if (data_bit == 1'b1) begin
                        stuff_err <= 1'b1;  // violation: 7th consecutive 1
                        ones_run  <= 3'd0;
                    end else begin
                        ones_run  <= 3'd0;  // stuff bit consumed, not forwarded
                    end
                end else begin
                    bit_valid <= 1'b1;
                    out_bit   <= data_bit;
                    ones_run  <= (data_bit == 1'b1) ? (ones_run + 3'd1) : 3'd0;
                end
            end
        end
    end

endmodule

`default_nettype wire
