// usb_tx_serializer.v -- top-level FS transmit datapath (issue #12).
//
// Integration point for the FS TX path named in spec/architecture.md's
// partition table ("Serializer / deserializer") and first-buildable-slice
// section: exposes the full external interface (UTMI TX handshake in,
// line-state driver interface out) and instantiates usb_tx_framer.v (SYNC/
// EOP framing + line driver), usb_bit_stuffer.v (bit stuffing), and
// usb_nrzi_encoder.v (NRZI encoding), wiring them in dataflow order:
//
//   DataOut byte stream (usb_tx_framer.v)
//     -> usb_bit_stuffer.v (body bits only; SYNC bypasses this stage)
//     -> usb_nrzi_encoder.v
//     -> usb_tx_framer.v's line-state pad stage (also generates SYNC's own
//        NRZI-encoded bits and forces the EOP SE0/J levels directly)
//
// Clock domain (spec/decision-records/0001, Decisions 1-3): `clk` is the
// 144 MHz oversampling clock (12x the 12 Mbps FS bit rate); `rst_n` is
// that decision record's `rst_144_n` (asynchronous assert, synchronous
// deassert, already local to this domain). `TxValid`/`TxReady`/`DataOut`/
// `OpMode` are presented here as already-synchronized 144 MHz-domain
// signals -- the decision record's Decision 3 per-signal CDC table
// specifies 2-flop synchronizers crossing these to/from the 30 MHz UTMI
// domain, but that crossing (and the top-level module that would
// instantiate this serializer alongside the 30 MHz-domain UTMI ports) is
// integration-level work for a future issue, not built here. See issue
// #12's scope: "UTMI TX handshake ... in the UTMI clock domain, per the
// port table and clock decision" is satisfied at the signal/port-name
// level; the CDC synchronizer instances themselves are explicitly out of
// this issue's stated deliverables (rtl/usb_tx_serializer.v,
// usb_bit_stuffer.v, usb_nrzi_encoder.v, usb_tx_framer.v only).
//
// Bit-rate timing (issue #12 scope item 6): the 12 Mbps FS bit clock is
// exactly 144 MHz / 12 -- `BIT_DIV` below is that integer divide, used as
// a bit-time enable (`bit_stb`) on the shared 144 MHz clock rather than a
// second timing source.

`default_nettype none

module usb_tx_serializer (
    input  wire        clk,     // 144 MHz oversampling clock
    input  wire        rst_n,   // rst_144_n (decision record 0001, Decision 3)

    // UTMI TX handshake -- spec/usb2-phy.md section 3,
    // spec/decision-records/0001 Decision 4's port table
    input  wire        TxValid,
    output wire        TxReady,
    input  wire [7:0]  DataOut,
    input  wire [1:0]  OpMode,

    // Line-state driver interface -- spec/usb2-phy.md section 6's
    // "Control interface from UTMI layer" row (current-mode driver
    // sibling canary). Nothing else is exposed.
    output wire        tx_drive_en,
    output wire        tx_oe,
    output wire        tx_dp,
    output wire        tx_dn
);

    // ---- Bit-rate timing: 144 MHz / 12 = 12 MHz (issue #12 scope item 6) --
    localparam integer BIT_DIV = 12;

    reg [3:0] div_cnt;
    wire      bit_stb = (div_cnt == BIT_DIV - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            div_cnt <= 4'd0;
        end else if (bit_stb) begin
            div_cnt <= 4'd0;
        end else begin
            div_cnt <= div_cnt + 4'd1;
        end
    end

    // ---- usb_tx_framer.v <-> usb_bit_stuffer.v / usb_nrzi_encoder.v -----
    wire nrzi_bit_stb, nrzi_sof, nrzi_bypass, nrzi_bit_in, nrzi_level;
    wire stuff_bit_stb, stuff_sof, stuff_bypass, stuff_bit_in;
    wire stuff_bit_out, stuff_consume, stuff_pending_after;

    usb_tx_framer u_framer (
        .clk      (clk),
        .rst_n    (rst_n),
        .bit_stb  (bit_stb),

        .TxValid  (TxValid),
        .TxReady  (TxReady),
        .DataOut  (DataOut),
        .OpMode   (OpMode),

        .nrzi_bit_stb (nrzi_bit_stb),
        .nrzi_sof     (nrzi_sof),
        .nrzi_bypass  (nrzi_bypass),
        .nrzi_bit_in  (nrzi_bit_in),
        .nrzi_level   (nrzi_level),

        .stuff_bit_stb       (stuff_bit_stb),
        .stuff_sof           (stuff_sof),
        .stuff_bypass        (stuff_bypass),
        .stuff_bit_in        (stuff_bit_in),
        .stuff_bit_out       (stuff_bit_out),
        .stuff_consume       (stuff_consume),
        .stuff_pending_after (stuff_pending_after),

        .tx_drive_en (tx_drive_en),
        .tx_oe       (tx_oe),
        .tx_dp       (tx_dp),
        .tx_dn       (tx_dn)
    );

    usb_bit_stuffer u_stuffer (
        .clk    (clk),
        .rst_n  (rst_n),
        .bit_stb(stuff_bit_stb),
        .bypass (stuff_bypass),
        .sof    (stuff_sof),
        .bit_in (stuff_bit_in),

        .bit_out             (stuff_bit_out),
        .consume             (stuff_consume),
        .stuff_pending_after (stuff_pending_after)
    );

    usb_nrzi_encoder u_nrzi (
        .clk    (clk),
        .rst_n  (rst_n),
        .bit_stb(nrzi_bit_stb),
        .bypass (nrzi_bypass),
        .sof    (nrzi_sof),
        .bit_in (nrzi_bit_in),

        .level_out (nrzi_level)
    );

endmodule

`default_nettype wire
