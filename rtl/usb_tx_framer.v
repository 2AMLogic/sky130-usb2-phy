// usb_tx_framer.v -- packet framing (SYNC/EOP sequencing, issue #12 scope
// item 2) and the line-state driver interface handed to the current-mode
// driver sibling canary (scope item 5, spec/usb2-phy.md section 6's
// "Control interface from UTMI layer" row).
//
// Owns the TX packet-level state machine: IDLE (waiting for a packet to
// start) -> SYNC (fixed 8-bit 0x80 pattern, LSB-first "00000001", never
// bit-stuffed -- verification/usbfs/pid.py's SYNC_BYTE) -> DATA (byte
// stream from the UTMI handshake, bit-stuffed via usb_bit_stuffer.v) ->
// FLUSH (the mandatory extra bit-time only entered when the packet's last
// real bit leaves a bit-stuff pending -- the "stuff bit immediately
// before EOP" case) -> HOLD (one bit-time of no-op; see below) ->
// EOP0/EOP1/EOP2 (two bit-times of SE0, one bit-time of J -- USB 2.0 Spec
// Rev 2.0 section 7.1.9) -> back to IDLE (driver released).
//
// Why HOLD exists: whichever bit-time produces the packet's *last* body
// bit (the DATA state's last real bit, or FLUSH's forced stuff bit) also
// registers `nrzi_level`'s new value on that exact same `bit_stb` edge --
// the same "transition edge also produces this bit-time's output" pattern
// `entering_sync` below handles for SYNC's own first bit. Without HOLD,
// the very next state would be ST_EOP0, whose tx_dp/tx_dn override
// (forced SE0) is selected by the very same edge that only just finished
// registering the last body bit's correct level -- so that freshly-
// correct level would never be visible on the output pins for even one
// bit-time; the line would jump straight from the *previous* bit's level
// to SE0, silently dropping the packet's actual last bit. HOLD interposes
// exactly one bit-time (driving == 1, still selecting nrzi_level, but not
// feeding any new bit into the stuffer/encoder -- `nrzi_bit_stb` and
// `stuff_bit_stb` are both 0 during HOLD) so the last bit's now-settled
// `nrzi_level` gets its own visible bit-time before EOP0 begins.
//
// This module does not itself implement NRZI encoding or bit stuffing --
// it drives usb_nrzi_encoder.v and usb_bit_stuffer.v (instantiated as
// siblings in usb_tx_serializer.v, which wires the loop:
// this module's DATA-phase bit -> stuffer -> encoder -> this module's pad
// stage) through the two small port groups below, and generates the SYNC
// bit pattern and the EOP override levels itself.
//
// UTMI TX handshake (issue #12 scope item 1, spec/decision-records/0001's
// Decision 3/4 port table): `TxValid`/`TxReady`/`DataOut` here are the
// 144 MHz-domain-side view of those signals -- per that decision record,
// `TxValid` is a level held (with `DataOut` stable) until `TxReady`
// acknowledges, and `TxReady` is itself synchronized 144->30 MHz by
// integration-level logic this issue does not build (CDC synchronizers
// to the actual 30 MHz UTMI clock domain are out of this issue's scope;
// see usb_tx_serializer.v's header comment).
//
// TxReady back-pressure: TxReady is asserted, continuously, for the
// entire bit-time during which this byte's *last* real bit is pending
// (byte_idx == 7 and the bit stuffer confirms it will really be consumed,
// not stuffed) -- so a byte's request-to-request interval is 8 bit-times
// normally and stretches to exactly 9 bit-times when a stuff bit falls
// within that byte (the extra bit-time the stuffer spends *not*
// consuming a real bit delays byte_idx from ever reaching a
// consumed-and-equal-7 cycle by one tick). This is issue #12's required
// "TxReady deasserts for exactly one extra bit time" behavior, and it
// falls out of the mechanism with no special-casing for where the stuff
// bit lands (including exactly at a byte boundary).
//
// OpMode == 2'b10 (spec/decision-records/0001 Decision 4): "disable
// bit-stuffing and NRZI encoding" (raw/transparent test mode). This
// implementation applies that bypass only to the packet body (DATA/FLUSH
// phases) -- SYNC is PHY-generated framing, not link-controller payload,
// so it is always properly NRZI-encoded regardless of OpMode. FLUSH is
// structurally unreachable under bypass (the stuffer never reports a
// pending stuff while bypassed), so this choice never produces an
// inconsistent state.

`default_nettype none

module usb_tx_framer (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        bit_stb,

    // UTMI TX handshake (144 MHz-domain-side view -- see header comment)
    input  wire        TxValid,
    output wire        TxReady,
    input  wire [7:0]  DataOut,
    input  wire [1:0]  OpMode,

    // usb_nrzi_encoder.v interface
    output wire        nrzi_bit_stb,
    output wire        nrzi_sof,
    output wire        nrzi_bypass,
    output wire        nrzi_bit_in,
    input  wire        nrzi_level,

    // usb_bit_stuffer.v interface
    output wire        stuff_bit_stb,
    output wire        stuff_sof,
    output wire        stuff_bypass,
    output wire        stuff_bit_in,
    input  wire        stuff_bit_out,
    input  wire        stuff_consume,
    input  wire        stuff_pending_after,

    // Line-state driver interface -- spec/usb2-phy.md section 6, "Control
    // interface from UTMI layer" row (current-mode driver sibling):
    // "Differential drive enable, output enable (OE), and TxD+/TxD- data
    // lines." Nothing else is exposed, per issue #12's scope discipline.
    output wire        tx_drive_en,
    output wire        tx_oe,
    output wire        tx_dp,
    output wire        tx_dn
);

    localparam [2:0] ST_IDLE  = 3'd0;
    localparam [2:0] ST_SYNC  = 3'd1;
    localparam [2:0] ST_DATA  = 3'd2;
    localparam [2:0] ST_FLUSH = 3'd3;
    localparam [2:0] ST_HOLD  = 3'd4; // one bit-time: last body bit's level settles
    localparam [2:0] ST_EOP0  = 3'd5; // SE0, bit-time 1
    localparam [2:0] ST_EOP1  = 3'd6; // SE0, bit-time 2
    localparam [2:0] ST_EOP2  = 3'd7; // J,   bit-time 3

    // SYNC field: 0x80, LSB-first "0000 0001" -- verification/usbfs/pid.py
    localparam [7:0] SYNC_PATTERN = 8'h80;

    wire raw_mode = (OpMode == 2'b10);

    reg [2:0] state;
    reg [2:0] sync_idx;
    reg [7:0] byte_reg;
    reg [2:0] byte_idx;
    reg       first_byte;

    wire sync_bit = SYNC_PATTERN[sync_idx];

    // `entering_sync`: the IDLE->SYNC transition edge itself. `state` is a
    // *registered* value, so on the bit_stb edge where the FSM below moves
    // IDLE -> SYNC, every combinational read of `state` above still sees
    // the pre-edge value (ST_IDLE) -- ST_IDLE is deliberately absent from
    // the nrzi_bit_stb/nrzi_sof "active" state list below, so without this
    // term the encoder would miss encoding SYNC's bit 0 on this edge
    // entirely (it would first see state==ST_SYNC only on the *next*
    // bit_stb pulse, one full bit-time late, desynchronizing the whole
    // packet's line-state stream by one bit-time relative to
    // `usbfs.packets.build()`). Every other state-to-state transition
    // (SYNC->DATA, DATA->DATA, DATA->FLUSH) does not need this treatment:
    // each transitions *from* a state already in the active list, so the
    // same pre-edge-state read that gates the FSM's own transition also
    // still gates nrzi_bit_stb/stuff_bit_stb correctly on that edge. Only
    // the very first bit-time, leaving IDLE (which is not itself an
    // "active" driving state), needs the explicit OR term below.
    wire entering_sync = (state == ST_IDLE) && TxValid;

    // ---- usb_bit_stuffer.v interface -------------------------------
    assign stuff_bit_in  = (state == ST_FLUSH) ? 1'b0 : byte_reg[byte_idx];
    assign stuff_sof     = bit_stb && (state == ST_DATA) && first_byte && (byte_idx == 3'd0);
    assign stuff_bypass  = raw_mode;
    assign stuff_bit_stb = bit_stb && ((state == ST_DATA) || (state == ST_FLUSH));

    // ---- usb_nrzi_encoder.v interface ------------------------------
    // `sync_idx` is advanced to 1 the instant SYNC is entered (see the
    // ST_IDLE FSM case below), so bit index 0 is never re-observed with
    // `state == ST_SYNC` -- `entering_sync` is therefore the *only* source
    // of SYNC's sof pulse; the `sync_idx == 0` reading would be dead
    // (structurally unreachable) if also OR'd in here.
    assign nrzi_bit_in  = (state == ST_SYNC || entering_sync) ? sync_bit : stuff_bit_out;
    assign nrzi_sof     = bit_stb && entering_sync;
    assign nrzi_bypass  = raw_mode && ((state == ST_DATA) || (state == ST_FLUSH));
    assign nrzi_bit_stb = bit_stb && ((state == ST_SYNC) || (state == ST_DATA) || (state == ST_FLUSH) || entering_sync);

    // ---- UTMI handshake ----------------------------------------------
    // Combinational (not bit_stb-gated) so the requesting window is the
    // full bit-time leading up to the tick that needs the byte -- see
    // header comment.
    assign TxReady = (state == ST_IDLE) ||
                      ((state == ST_DATA) && (byte_idx == 3'd7) && stuff_consume);

    // ---- Line-state driver interface -------------------------------
    wire driving = (state == ST_SYNC) || (state == ST_DATA) || (state == ST_FLUSH) ||
                   (state == ST_HOLD) ||
                   (state == ST_EOP0) || (state == ST_EOP1) || (state == ST_EOP2);
    wire line_bit_phase = (state == ST_SYNC) || (state == ST_DATA) || (state == ST_FLUSH) ||
                          (state == ST_HOLD);

    assign tx_oe       = driving;
    assign tx_drive_en = driving;
    assign tx_dp = (state == ST_EOP0 || state == ST_EOP1) ? 1'b0 :
                   (state == ST_EOP2)                      ? 1'b1 :
                   line_bit_phase                           ? nrzi_level :
                   1'b1; // idle default: J
    assign tx_dn = (state == ST_EOP0 || state == ST_EOP1) ? 1'b0 :
                   (state == ST_EOP2)                      ? 1'b0 :
                   line_bit_phase                           ? ~nrzi_level :
                   1'b0; // idle default: J

    // ---- Packet FSM ----------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= ST_IDLE;
            sync_idx   <= 3'd0;
            byte_idx   <= 3'd0;
            byte_reg   <= 8'd0;
            first_byte <= 1'b0;
        end else if (bit_stb) begin
            case (state)
                ST_IDLE: begin
                    if (TxValid) begin
                        byte_reg   <= DataOut;
                        state      <= ST_SYNC;
                        // `entering_sync` above already encodes SYNC bit 0
                        // combinationally on *this* edge (using sync_idx's
                        // pre-edge value, 0) -- advance sync_idx to 1 here
                        // so the next bit_stb pulse (now state == ST_SYNC)
                        // encodes bit 1, not bit 0 a second time.
                        sync_idx   <= 3'd1;
                        first_byte <= 1'b1;
                    end
                end

                ST_SYNC: begin
                    if (sync_idx == 3'd7) begin
                        state    <= ST_DATA;
                        byte_idx <= 3'd0;
                    end else begin
                        sync_idx <= sync_idx + 3'd1;
                    end
                end

                ST_DATA: begin
                    if (stuff_consume) begin
                        if (byte_idx == 3'd7) begin
                            if (TxValid) begin
                                byte_reg   <= DataOut;
                                byte_idx   <= 3'd0;
                                first_byte <= 1'b0;
                            end else begin
                                // See HOLD's header-comment note: neither
                                // branch goes straight to ST_EOP0 -- this
                                // edge's own nrzi_bit_stb pulse (state ==
                                // ST_DATA is still in the "active" set)
                                // just finalized this bit's `nrzi_level`;
                                // HOLD gives it one bit-time to be visible
                                // before EOP0's override takes over.
                                state <= stuff_pending_after ? ST_FLUSH : ST_HOLD;
                            end
                        end else begin
                            byte_idx <= byte_idx + 3'd1;
                        end
                    end
                    // else: this cycle inserted a stuff bit -- byte_idx and
                    // byte_reg hold, the same real bit is retried next cycle.
                end

                ST_FLUSH: begin
                    // Same reasoning as the ST_DATA branch above: this
                    // edge's nrzi_bit_stb just finalized the forced stuff
                    // bit's level (state == ST_FLUSH is in the "active"
                    // set) -- go to HOLD, not directly to EOP0.
                    state <= ST_HOLD;
                end

                ST_HOLD: state <= ST_EOP0;

                ST_EOP0: state <= ST_EOP1;
                ST_EOP1: state <= ST_EOP2;
                ST_EOP2: state <= ST_IDLE;

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule

`default_nettype wire
