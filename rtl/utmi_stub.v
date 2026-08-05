// utmi_stub.v -- toolchain-plumbing placeholder, NOT real UTMI protocol logic.
//
// This module exists solely to prove the digital verification/synthesis
// harness (cocotb + Icarus, Yosys against sky130_fd_sc_hd, both driven
// through `klt`) works end-to-end in this repo -- see issue #3. It uses the
// UTMI signal names from `spec/usb2-phy.md` section 3 so the plumbing is
// exercised with the right shapes, but the behavior is a trivial registered
// pass-through: no NRZI encode/decode, no bit stuffing, no line-state
// handling. The real UTMI digital layer is a separate, future issue that
// depends on this harness, not the other way around.
//
// Behavior: on every rising clock edge (while not in reset), DataOut is
// registered onto DataIn, and TxValid is registered onto both TxReady and
// RxValid. That is the entire function.

`default_nettype none

module utmi_stub (
    input  wire       clk,
    input  wire       rst_n,

    // TX-path-shaped inputs
    input  wire        TxValid,
    input  wire [7:0]  DataOut,

    // RX/TX-path-shaped outputs (registered pass-through only)
    output reg          TxReady,
    output reg          RxValid,
    output reg  [7:0]   DataIn
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            TxReady <= 1'b0;
            RxValid <= 1'b0;
            DataIn  <= 8'h00;
        end else begin
            TxReady <= TxValid;
            RxValid <= TxValid;
            DataIn  <= DataOut;
        end
    end

endmodule

`default_nettype wire
