// usb_rx_cdc.v -- domain crossing from the 144 MHz recovery domain to the
// 30 MHz UTMI domain (issue #13, block 7), and the per-domain reset
// synchronizers both domains use.
//
// Every crossing and structural choice here is fixed by
// spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md
// Decision 3 -- not invented in this module:
//
// - `RxValid`/`DataIn[7:0]`: an **asynchronous (dual-clock) elastic
//   FIFO**, 8 entries x 8 bits, Gray-coded read/write pointers, 2-flop
//   synchronizers on each pointer's crossing (standard AFIFO
//   construction, Decision 3's "RX byte handoff" derivation). The link
//   controller is assumed to consume every asserted `RxValid` byte
//   (Decision 3's per-signal domain-ownership table) -- there is no
//   backpressure signal on this port in the UTMI port table, so the read
//   side pops (and asserts `RxValid`) every UTMI cycle the FIFO is
//   non-empty.
// - `RxActive`/`RxError`/`LineState[1:0]`: plain 2-flop synchronizers
//   (Decision 3's synchronizer-depth choice for level/status signals).
// - `Reset` -> `rst_144_n`/`rst_utmi_n`: asynchronous assert, synchronous
//   deassert, one local synchronizer per domain, both fed from the same
//   async `Reset` input (Decision 3's "Reset scheme"). The FIFO's
//   pointers are held in reset until **both** domain resets have
//   deasserted.
//
// `bus_reset_detected`/`suspend_detected` (issue #13 block 8, see
// usb_rx_framer.v's header for why these exist beyond the literal port
// table) are carried across with the same 2-flop level-synchronizer
// treatment as `RxActive`/`RxError`/`LineState`.
`default_nettype none

module usb_rx_cdc #(
    parameter integer FIFO_DEPTH_LOG2 = 3  // 8 entries (Decision 3)
) (
    // Asynchronous reset input (Link -> PHY `Reset`), active-high.
    input  wire reset_async,

    // ---- 144 MHz recovery domain ----
    input  wire        clk_144,
    output wire         rst_144_n,

    input  wire        rx_byte_valid,
    input  wire [7:0]  rx_byte,
    input  wire        rx_active_144,
    input  wire        rx_error_144,
    input  wire [1:0]  line_state_144,
    input  wire        bus_reset_144,
    input  wire        suspend_144,

    // ---- 30 MHz UTMI domain ----
    input  wire        clk_utmi,
    output wire         rst_utmi_n,

    output wire        RxValid,
    output wire [7:0]  DataIn,
    output wire        RxActive,
    output wire        RxError,
    output wire [1:0]  LineState,
    output wire        BusReset,
    output wire        Suspend
);

    localparam integer AW = FIFO_DEPTH_LOG2;

    // ---- per-domain reset synchronizers (async assert, sync deassert) ----
    reg [1:0] rst144_meta;
    always @(posedge clk_144 or posedge reset_async) begin
        if (reset_async) rst144_meta <= 2'b00;
        else              rst144_meta <= {rst144_meta[0], 1'b1};
    end
    assign rst_144_n = rst144_meta[1];

    reg [1:0] rstutmi_meta;
    always @(posedge clk_utmi or posedge reset_async) begin
        if (reset_async) rstutmi_meta <= 2'b00;
        else              rstutmi_meta <= {rstutmi_meta[0], 1'b1};
    end
    assign rst_utmi_n = rstutmi_meta[1];

    // FIFO pointers held reset until BOTH domain resets have deasserted.
    wire fifo_rst_n = rst_144_n & rst_utmi_n;

    // ---- write side (144 MHz): async elastic FIFO ----
    reg [AW:0] wptr_bin, wptr_gray;
    wire [AW:0] rptr_gray_wsync;
    wire wr_en;
    wire [AW:0] wptr_bin_next  = wptr_bin + (wr_en ? 1'b1 : 1'b0);
    wire [AW:0] wptr_gray_next = (wptr_bin_next >> 1) ^ wptr_bin_next;
    wire full = (wptr_gray_next ==
                 {~rptr_gray_wsync[AW:AW-1], rptr_gray_wsync[AW-2:0]});
    assign wr_en = rx_byte_valid & ~full;

    reg [7:0] mem [0:(1 << AW) - 1];

    always @(posedge clk_144 or negedge fifo_rst_n) begin
        if (!fifo_rst_n) begin
            wptr_bin  <= {(AW + 1) {1'b0}};
            wptr_gray <= {(AW + 1) {1'b0}};
        end else begin
            wptr_bin  <= wptr_bin_next;
            wptr_gray <= wptr_gray_next;
            if (wr_en) mem[wptr_bin[AW-1:0]] <= rx_byte;
        end
    end

    // ---- read side (30 MHz UTMI): auto-pop while non-empty ----
    reg [AW:0] rptr_bin, rptr_gray;
    wire [AW:0] wptr_gray_rsync;
    wire empty = (rptr_gray == wptr_gray_rsync);
    wire rd_en = ~empty;
    wire [AW:0] rptr_bin_next  = rptr_bin + (rd_en ? 1'b1 : 1'b0);
    wire [AW:0] rptr_gray_next = (rptr_bin_next >> 1) ^ rptr_bin_next;

    reg [7:0] data_out;
    reg       rxvalid_r;

    always @(posedge clk_utmi or negedge fifo_rst_n) begin
        if (!fifo_rst_n) begin
            rptr_bin  <= {(AW + 1) {1'b0}};
            rptr_gray <= {(AW + 1) {1'b0}};
            data_out  <= 8'h00;
            rxvalid_r <= 1'b0;
        end else begin
            rptr_bin  <= rptr_bin_next;
            rptr_gray <= rptr_gray_next;
            rxvalid_r <= rd_en;
            if (rd_en) data_out <= mem[rptr_bin[AW-1:0]];
        end
    end

    assign RxValid = rxvalid_r;
    assign DataIn  = data_out;

    // ---- pointer synchronizers (2-flop, Gray-coded) ----
    reg [AW:0] wptr_gray_rs1, wptr_gray_rs2;
    always @(posedge clk_utmi or negedge fifo_rst_n) begin
        if (!fifo_rst_n) begin
            wptr_gray_rs1 <= {(AW + 1) {1'b0}};
            wptr_gray_rs2 <= {(AW + 1) {1'b0}};
        end else begin
            wptr_gray_rs1 <= wptr_gray;
            wptr_gray_rs2 <= wptr_gray_rs1;
        end
    end
    assign wptr_gray_rsync = wptr_gray_rs2;

    reg [AW:0] rptr_gray_ws1, rptr_gray_ws2;
    always @(posedge clk_144 or negedge fifo_rst_n) begin
        if (!fifo_rst_n) begin
            rptr_gray_ws1 <= {(AW + 1) {1'b0}};
            rptr_gray_ws2 <= {(AW + 1) {1'b0}};
        end else begin
            rptr_gray_ws1 <= rptr_gray;
            rptr_gray_ws2 <= rptr_gray_ws1;
        end
    end
    assign rptr_gray_wsync = rptr_gray_ws2;

    // ---- level synchronizers (144 -> UTMI), 2-flop each ----
    reg rxactive_s1, rxactive_s2;
    reg rxerror_s1, rxerror_s2;
    reg [1:0] linestate_s1, linestate_s2;
    reg busreset_s1, busreset_s2;
    reg suspend_s1, suspend_s2;

    always @(posedge clk_utmi or negedge rst_utmi_n) begin
        if (!rst_utmi_n) begin
            rxactive_s1  <= 1'b0; rxactive_s2  <= 1'b0;
            rxerror_s1   <= 1'b0; rxerror_s2   <= 1'b0;
            linestate_s1 <= 2'b00; linestate_s2 <= 2'b00;
            busreset_s1  <= 1'b0; busreset_s2  <= 1'b0;
            suspend_s1   <= 1'b0; suspend_s2   <= 1'b0;
        end else begin
            rxactive_s1  <= rx_active_144;
            rxactive_s2  <= rxactive_s1;
            rxerror_s1   <= rx_error_144;
            rxerror_s2   <= rxerror_s1;
            linestate_s1 <= line_state_144;
            linestate_s2 <= linestate_s1;
            busreset_s1  <= bus_reset_144;
            busreset_s2  <= busreset_s1;
            suspend_s1   <= suspend_144;
            suspend_s2   <= suspend_s1;
        end
    end

    assign RxActive  = rxactive_s2;
    assign RxError   = rxerror_s2;
    assign LineState = linestate_s2;
    assign BusReset  = busreset_s2;
    assign Suspend   = suspend_s2;

endmodule

`default_nettype wire
