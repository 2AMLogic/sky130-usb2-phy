// usb_rx_path.v -- top-level integration of the FS receive datapath
// (issue #13): wires usb_bit_sync -> usb_nrzi_decoder -> usb_bit_destuffer
// -> usb_rx_framer -> usb_linestate -> usb_rx_cdc into the block chain
// spec/architecture.md's block diagram and issue #13's dataflow-ordered
// block list describe. Not itself a Deliverable-named module (the issue
// says "one module per function"), but every sub-block needs a single HDL
// toplevel for `klt functional-verification` (cocotb) to attach to, and a
// single point that documents how the pieces actually connect together.
//
// Per CLAUDE.md's scope-discipline rule, this module (and everything it
// instantiates) consumes the oversampling clock (`clk_144`), the UTMI
// clock (`clk_utmi`), and the pad-level `dp`/`dm` samples as *given*
// inputs -- it does not generate either clock or model the analog
// receiver that produces `dp`/`dm`. Both clocks and the line-level inputs
// are the sibling PLL / differential-receiver canaries' job
// (`spec/architecture.md`'s partition table).
`default_nettype none

module usb_rx_path #(
    // Passed through to usb_rx_framer.v. Defaults are the spec-correct
    // values (2.5 us reset / 3 ms suspend detection at 144 MHz); a
    // testbench MAY override them (e.g. to keep a suspend-detection cocotb
    // test's simulated cycle count tractable) -- see verification/test_usb_rx.py.
    // Overriding does not change the *mechanism* under test, only how long
    // it takes to trip, so this is not a relaxation of the acceptance
    // criterion.
    parameter integer RESET_DETECT_CYCLES   = 360,
    parameter integer SUSPEND_DETECT_CYCLES = 432_000,
    parameter integer MAX_PACKET_CYCLES     = 200_000
) (
    // Asynchronous reset (Link -> PHY `Reset`), active-high -- Decision 3
    // of spec/decision-records/0001-...md.
    input  wire Reset,

    // 144 MHz oversampling clock (PLL sibling canary) and the raw
    // pad-level D+/D- samples (differential-receiver sibling canary).
    input  wire clk_144,
    input  wire dp,
    input  wire dm,

    // 30 MHz UTMI interface clock (PLL sibling canary, Decision 2).
    input  wire clk_utmi,

    // UTMI RX-path port set (spec/usb2-phy.md section 3, Decision 4's
    // port table).
    output wire        RxValid,
    output wire [7:0]  DataIn,
    output wire        RxActive,
    output wire        RxError,
    output wire [1:0]  LineState,

    // Bus reset / suspend status -- see usb_rx_framer.v's header for why
    // these are exposed beyond the literal UTMI port table.
    output wire BusReset,
    output wire Suspend
);

    wire rst_144_n;
    wire rst_utmi_n;  // synchronized by usb_rx_cdc; not otherwise used here

    // ---- 144 MHz recovery-domain chain ----
    wire dp_sync, dm_sync;
    wire bit_strobe, bit_level, bit_is_jk;

    usb_bit_sync u_bit_sync (
        .clk_144    (clk_144),
        .rst_144_n  (rst_144_n),
        .dp         (dp),
        .dm         (dm),
        .dp_sync    (dp_sync),
        .dm_sync    (dm_sync),
        .bit_strobe (bit_strobe),
        .bit_level  (bit_level),
        .bit_is_jk  (bit_is_jk),
        .edge_detect()
    );

    wire data_strobe, data_bit;

    usb_nrzi_decoder u_nrzi_decoder (
        .clk_144     (clk_144),
        .rst_144_n   (rst_144_n),
        .bit_strobe  (bit_strobe),
        .bit_level   (bit_level),
        .bit_is_jk   (bit_is_jk),
        .data_strobe (data_strobe),
        .data_bit    (data_bit)
    );

    wire bit_valid, out_bit, stuff_err;
    wire rx_active_144;

    // `enable` = the framer's own `rx_active` (SOP-locked..EOP) -- a
    // registered feedback from usb_rx_framer.v below, not a combinational
    // loop: usb_bit_destuffer.v only *uses* enable to decide whether to
    // count/emit a stuffing violation on THIS cycle's data_strobe, it does
    // not feed back into anything usb_rx_framer.v reads combinationally
    // this same cycle. See usb_bit_destuffer.v's header for why this gate
    // exists (idle before SOP / after EOP must never accumulate into the
    // six-consecutive-ones run counter).
    usb_bit_destuffer u_bit_destuffer (
        .clk_144     (clk_144),
        .rst_144_n   (rst_144_n),
        .enable      (rx_active_144),
        .data_strobe (data_strobe),
        .data_bit    (data_bit),
        .bit_valid   (bit_valid),
        .out_bit     (out_bit),
        .stuff_err   (stuff_err)
    );

    wire        rx_byte_valid_144;
    wire [7:0]  rx_byte_144;
    wire        rx_error_144;
    wire        bus_reset_144;
    wire        suspend_144;

    usb_rx_framer #(
        .RESET_DETECT_CYCLES  (RESET_DETECT_CYCLES),
        .SUSPEND_DETECT_CYCLES(SUSPEND_DETECT_CYCLES),
        .MAX_PACKET_CYCLES    (MAX_PACKET_CYCLES)
    ) u_rx_framer (
        .clk_144            (clk_144),
        .rst_144_n          (rst_144_n),
        .dp_sync            (dp_sync),
        .dm_sync            (dm_sync),
        .bit_strobe         (bit_strobe),
        .bit_valid          (bit_valid),
        .out_bit            (out_bit),
        .stuff_err          (stuff_err),
        .rx_byte_valid      (rx_byte_valid_144),
        .rx_byte            (rx_byte_144),
        .rx_active          (rx_active_144),
        .rx_error           (rx_error_144),
        .bus_reset_detected (bus_reset_144),
        .suspend_detected   (suspend_144)
    );

    wire [1:0] line_state_144;

    usb_linestate u_linestate (
        .dp_sync    (dp_sync),
        .dm_sync    (dm_sync),
        .line_state (line_state_144)
    );

    // ---- domain crossing to the 30 MHz UTMI domain ----
    usb_rx_cdc u_rx_cdc (
        .reset_async     (Reset),

        .clk_144         (clk_144),
        .rst_144_n       (rst_144_n),
        .rx_byte_valid   (rx_byte_valid_144),
        .rx_byte         (rx_byte_144),
        .rx_active_144   (rx_active_144),
        .rx_error_144    (rx_error_144),
        .line_state_144  (line_state_144),
        .bus_reset_144   (bus_reset_144),
        .suspend_144     (suspend_144),

        .clk_utmi        (clk_utmi),
        .rst_utmi_n      (rst_utmi_n),
        .RxValid         (RxValid),
        .DataIn          (DataIn),
        .RxActive        (RxActive),
        .RxError         (RxError),
        .LineState       (LineState),
        .BusReset        (BusReset),
        .Suspend         (Suspend)
    );

endmodule

`default_nettype wire
