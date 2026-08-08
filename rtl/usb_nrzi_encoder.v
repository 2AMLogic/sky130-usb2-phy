// usb_nrzi_encoder.v -- NRZI (Non-Return-to-Zero Inverted) line encoder.
//
// USB 2.0 Spec Rev 2.0 section 7.1.9: "a '0' bit is represented by a
// transition in the line state, and a '1' bit is represented by no
// transition." Matches verification/usbfs/nrzi.py's convention exactly:
// `level` 1 == the bus idle level (J for FS signaling), and encoding
// starts from `start_level = 1` at the top of every packet (see `sof`
// below) -- see usbfs/packets.py's `wrap_stuffed()`.
//
// Clock domain: this module free-runs on `clk`/`rst_n`, the 144 MHz
// oversampling-clock domain per spec/decision-records/0001's Decision 3.
// It only updates state on cycles where `bit_stb` is asserted (the 12
// MHz/83.33 ns bit-time strobe usb_tx_serializer.v derives from that
// clock -- issue #12 scope item 6).
//
// One instance is shared, at the usb_tx_serializer.v top level, by both
// the fixed SYNC pattern and the (bit-stuffed) packet body -- both need
// NRZI encoding, but SYNC is never bit-stuffed, so usb_bit_stuffer.v sits
// only between the byte source and this module's `bit_in`, not upstream
// of the SYNC pattern.
//
// Bypass (`bypass`, driven from OpMode == 2'b10 per the clocking decision
// record's Decision 4 port table): the raw/transparent UTMI test mode.
// While bypassed, `bit_in` is placed directly onto `level_out` with no
// NRZI transform and no persisted transition state -- see
// usb_tx_serializer.v's header comment for why this only applies to the
// packet body, not the SYNC pattern, in this implementation.

`default_nettype none

module usb_nrzi_encoder (
    input  wire clk,
    input  wire rst_n,

    input  wire bit_stb,   // one-cycle pulse: consume `bit_in` this bit-time
    input  wire bypass,    // 1 = raw/transparent mode, no NRZI transform
    input  wire sof,       // pulse (coincident with bit_stb): re-derive this
                            // bit's transition from the idle J level (1),
                            // matching nrzi.encode()'s start_level=1 -- not a
                            // register clear, just this cycle's reference
    input  wire bit_in,    // next pre-NRZI bit (LSB-first stream)

    output reg  level_out  // encoded line level: 1 = J-equivalent (idle),
                            // 0 = K-equivalent -- linestate.level_to_state()
);

    wire base_level  = sof ? 1'b1 : level_out;
    wire next_level  = bit_in ? base_level : ~base_level;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            level_out <= 1'b1; // idle J
        end else if (bit_stb) begin
            level_out <= bypass ? bit_in : next_level;
        end
    end

endmodule

`default_nettype wire
