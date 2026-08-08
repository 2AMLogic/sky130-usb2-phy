// usb_nrzi_decoder.v -- NRZI decode (issue #13, block 3a), mirroring the
// TX path's (issue #12's) encoder. USB 2.0 Spec Rev 2.0 section 7.1.9: "a
// '0' bit is represented by a transition in the line state, and a '1' bit
// is represented by no transition." Decode is the inverse: compare each
// recovered line level against the previous one -- equal means '1', a
// change means '0'. Mirrors verification/usbfs/nrzi.py's `decode()`.
//
// Domain: 144 MHz recovery clock. Takes bit_strobe/bit_level/bit_is_jk from
// usb_bit_sync.v (one line-level sample per recovered bit period, already
// placed at the bit-cell centre) and emits one decoded data bit per
// bit_strobe, one clk_144 cycle later.
//
// `bit_is_jk` gates decoding: NRZI encoding is only defined over the two
// valid differential states (J, K) -- a bit cell sampled as SE0 (EOP's two
// SE0 bit times, or a bus reset) or SE1 (illegal) is not NRZI data and
// must not be decoded as if it were (no data_strobe pulse, no prev_level
// update, for that cell) -- see usb_bit_sync.v's header for the bug this
// closes (SE0 bit cells otherwise decode as extensions of whatever level
// preceded them, corrupting usb_bit_destuffer.v's stuffing-violation
// count with bits that were never really part of the NRZI stream).
`default_nettype none

module usb_nrzi_decoder (
    input  wire clk_144,
    input  wire rst_144_n,

    input  wire bit_strobe,
    input  wire bit_level,
    input  wire bit_is_jk,

    output reg  data_strobe,
    output reg  data_bit
);

    // Idle bus level is J (1); matches usb_bit_sync.v's reset value and
    // verification/usbfs/nrzi.py's IDLE_LEVEL / start_level=1 convention.
    reg prev_level;

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            prev_level  <= 1'b1;
            data_strobe <= 1'b0;
            data_bit    <= 1'b0;
        end else begin
            data_strobe <= bit_strobe && bit_is_jk;
            if (bit_strobe && bit_is_jk) begin
                data_bit   <= (bit_level == prev_level) ? 1'b1 : 1'b0;
                prev_level <= bit_level;
            end
        end
    end

endmodule

`default_nettype wire
