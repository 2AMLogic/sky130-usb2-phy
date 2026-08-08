// usb_rx_framer.v -- SOP/SYNC lock, EOP detection, deserialization, and
// bus reset / suspend detection (issue #13, blocks 4, 5, and 8).
//
// Domain: 144 MHz recovery clock.
//
// ---------------------------------------------------------------------
// SOP lock (block 4)
// ---------------------------------------------------------------------
// An 8-bit shift register tracks the last 8 destuffed data bits
// (`usb_bit_destuffer.v`'s `bit_valid`/`out_bit`) and continuously
// compares them to the SYNC pattern. USB transmits LSB-first
// (`verification/usbfs/bits.py`); SYNC's byte value is 0x80, whose
// LSB-first bit order is seven 0s then a 1
// (`verification/usbfs/pid.py`'s `SYNC_BYTE`). With the shift register
// convention below (new bit enters the LSB, oldest bit falls off the
// MSB), the *oldest* bit in an 8-deep window sits at bit 7 and the
// *newest* at bit 0 -- so a matched SYNC window reads `8'h01` (bit7=0
// .. bit0=1). Bit-exact match against a live 8'h01 target, checked every
// valid bit, needs no separate "aligned to a byte boundary" bookkeeping:
// idle (continuous decoded '1's, since no line transitions occur) can
// never spell out this pattern, and a match can only land where the true
// SYNC field's last bit really was, which is exactly the boundary the
// PID byte needs to start deserializing from.
//
// ---------------------------------------------------------------------
// Deserializer (block 5) and EOP detection (block 4)
// ---------------------------------------------------------------------
// Once SOP-locked (`rx_active`), destuffed bits are shifted LSB-first
// into a byte assembly register; every 8th valid bit produces
// `rx_byte_valid` + `rx_byte`. EOP (USB 2.0 section 7.1.9: two bit times
// of SE0 followed by one bit time of J) is **not** part of the
// bit-stuffed/NRZI-encoded stream at all (see
// `verification/usbfs/packets.py`'s `EOP_STATES`, appended *after* NRZI
// encoding) -- it is detected independently, directly from
// `usb_bit_sync.v`'s raw `dp_sync`/`dm_sync` sampled once per recovered
// bit period (`bit_strobe`), by matching the last three bit_strobe
// samples against (SE0, SE0, J). The destuffed-bit pipeline (NRZI decode
// + destuff, ~2 clk_144 cycles) is far shorter than one recovered bit
// period (~12 cycles), so by the time EOP's own two SE0 bit-strobes and
// terminating J bit-strobe elapse (~24-36 cycles after the last real data
// bit), the last data byte has already been fully deserialized -- no race
// between the two detection paths.
//
// A bit-stuff violation (`usb_bit_destuffer.v`'s `stuff_err`) or a
// missing-EOP watchdog timeout both assert `rx_error` (sticky for the
// rest of the packet) and immediately abort deserialization
// (`rx_active` deasserts) rather than delivering a corrupted trailing
// byte -- the acceptance criterion "does not silently corrupt the byte
// stream."
//
// ---------------------------------------------------------------------
// Bus reset / suspend detection (block 8)
// ---------------------------------------------------------------------
// Free-running counters, independent of SOP/EOP framing state, watch for
// sustained SE0 (bus reset, USB 2.0 section 7.1.7.3) or sustained idle J
// (suspend, section 7.1.7.6) directly on `dp_sync`/`dm_sync`, at the
// thresholds `verification/usbfs/timing.py` names
// (`RESET_DETECT_MIN_NS` / `SUSPEND_DETECT_MIN_NS`).
//
// **Design note, since the decision record's Decision 4 UTMI port table
// allocates no dedicated port for these:** per that table, `Reset` and
// `SuspendM` are both Link->PHY *inputs* (the link controller commands
// reset/suspend; it does not receive a PHY-sourced pin telling it the
// bus is in one). A real link controller derives "bus reset in progress"
// / "bus suspended" by watching `LineState` itself over time, exactly
// what this block does internally. Because issue #13 (block 8) names
// this detection as this repo's own job and an explicit acceptance
// criterion ("detected and reported"), this module exposes the detected
// conditions directly (`bus_reset_detected` / `suspend_detected`,
// carried to the UTMI domain by `usb_rx_cdc.v` alongside
// `RxActive`/`RxError`/`LineState`) as a documented extension beyond the
// literal port table, not a silently invented UTMI signal -- a future
// link-controller integration can either consume these directly or
// re-derive them from `LineState` with its own timer.
`default_nettype none

module usb_rx_framer #(
    parameter integer RESET_DETECT_CYCLES   = 360,     // 2.5 us @ 144 MHz
    parameter integer SUSPEND_DETECT_CYCLES = 432_000,  // 3 ms @ 144 MHz
    parameter integer MAX_PACKET_CYCLES     = 200_000   // missing-EOP watchdog
) (
    input  wire clk_144,
    input  wire rst_144_n,

    // From usb_bit_sync.v.
    input  wire dp_sync,
    input  wire dm_sync,
    input  wire bit_strobe,

    // From usb_nrzi_decoder.v -> usb_bit_destuffer.v.
    input  wire bit_valid,
    input  wire out_bit,
    input  wire stuff_err,

    // Deserialized byte + packet status, 144 MHz domain.
    output reg        rx_byte_valid,
    output reg  [7:0] rx_byte,
    output reg        rx_active,
    output reg        rx_error,

    // Block 8 -- see header.
    output reg         bus_reset_detected,
    output reg         suspend_detected
);

    // ---- SYNC pattern search ----
    localparam [7:0] SYNC_MATCH = 8'h01;

    reg [7:0] sync_shreg;
    wire [7:0] sync_shreg_next = {sync_shreg[6:0], out_bit};
    wire sync_match = bit_valid && !rx_active && (sync_shreg_next == SYNC_MATCH);

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            sync_shreg <= 8'hFF;  // never matches SYNC_MATCH by itself
        end else if (bit_valid && !rx_active) begin
            sync_shreg <= sync_shreg_next;
        end
    end

    // ---- EOP history (raw line state at each recovered bit centre) ----
    reg [1:0] eop_prev1, eop_prev2;  // {dp_sync,dm_sync} 1 / 2 strobes ago

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            eop_prev1 <= 2'b10;  // idle J
            eop_prev2 <= 2'b10;
        end else if (bit_strobe) begin
            eop_prev2 <= eop_prev1;
            eop_prev1 <= {dp_sync, dm_sync};
        end
    end

    wire eop_detected = bit_strobe && rx_active &&
                         (eop_prev1 == 2'b00) && (eop_prev2 == 2'b00) &&
                         ({dp_sync, dm_sync} == 2'b10);

    // ---- deserializer ----
    reg [7:0] byte_shreg;
    reg [2:0] bit_count;
    wire [7:0] byte_shreg_next = {out_bit, byte_shreg[7:1]};
    wire byte_complete = bit_valid && rx_active && (bit_count == 3'd7);

    // ---- missing-EOP watchdog ----
    reg [31:0] active_cycles;
    wire watchdog_timeout = rx_active && (active_cycles >= MAX_PACKET_CYCLES[31:0]);

    // ---- reset / suspend free-running counters ----
    localparam integer RUN_W = 20;  // >= ceil(log2(SUSPEND_DETECT_CYCLES+1))
    reg [RUN_W-1:0] se0_run, j_run;
    wire se0_now = ~dp_sync & ~dm_sync;
    wire j_now   = dp_sync & ~dm_sync;

    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            se0_run <= {RUN_W{1'b0}};
            j_run   <= {RUN_W{1'b0}};
            bus_reset_detected <= 1'b0;
            suspend_detected   <= 1'b0;
        end else begin
            se0_run <= se0_now ? (&se0_run ? se0_run : se0_run + 1'b1) : {RUN_W{1'b0}};
            j_run   <= j_now   ? (&j_run   ? j_run   : j_run   + 1'b1) : {RUN_W{1'b0}};
            bus_reset_detected <= (se0_run >= RESET_DETECT_CYCLES[RUN_W-1:0]);
            suspend_detected   <= (j_run   >= SUSPEND_DETECT_CYCLES[RUN_W-1:0]);
        end
    end

    // ---- main sequential state: rx_active / rx_error / byte output ----
    always @(posedge clk_144 or negedge rst_144_n) begin
        if (!rst_144_n) begin
            rx_active     <= 1'b0;
            rx_error      <= 1'b0;
            rx_byte_valid <= 1'b0;
            rx_byte       <= 8'h00;
            byte_shreg    <= 8'h00;
            bit_count     <= 3'd0;
            active_cycles <= 32'd0;
        end else begin
            rx_byte_valid <= 1'b0;

            if (rx_active) begin
                active_cycles <= active_cycles + 32'd1;
            end

            if (sync_match) begin
                // SOP lock: enter active reception, fresh byte assembly.
                rx_active  <= 1'b1;
                rx_error   <= 1'b0;
                byte_shreg <= 8'h00;
                bit_count  <= 3'd0;
                active_cycles <= 32'd0;
            end else if (rx_active && stuff_err) begin
                rx_active <= 1'b0;
                rx_error  <= 1'b1;
            end else if (rx_active && watchdog_timeout) begin
                rx_active <= 1'b0;
                rx_error  <= 1'b1;
            end else if (eop_detected) begin
                rx_active <= 1'b0;
            end else if (bus_reset_detected && rx_active) begin
                rx_active <= 1'b0;
            end else if (bit_valid && rx_active) begin
                byte_shreg <= byte_shreg_next;
                if (byte_complete) begin
                    bit_count     <= 3'd0;
                    rx_byte_valid <= 1'b1;
                    rx_byte       <= byte_shreg_next;
                end else begin
                    bit_count <= bit_count + 3'd1;
                end
            end
        end
    end

endmodule

`default_nettype wire
